#!/usr/bin/env python3
"""
RVSEC Watchdog - Container Stall Detector with Auto-Resume
Monitors containers, detects stalls, and automatically resumes execution.
"""

import json
import subprocess
import sys
import time
import logging
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class FlushFileHandler(logging.FileHandler):
    """FileHandler with immediate flush."""
    def emit(self, record):
        super().emit(record)
        self.flush()


class FlushStreamHandler(logging.StreamHandler):
    """StreamHandler with immediate flush."""
    def emit(self, record):
        super().emit(record)
        self.flush()


def setup_logging(log_file: Path, verbose: bool = False):
    """Setup logging to file and console with immediate flush."""
    file_handler = FlushFileHandler(log_file, encoding='utf-8')
    stream_handler = FlushStreamHandler(sys.stdout)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger('watchdog')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


@dataclass
class ContainerHealth:
    """Container health state."""
    container_id: str
    container_name: str
    is_running: bool = False
    tasks_completed: int = 0
    tasks_total: int = 0
    cpu_percent: float = 0.0
    memory_usage: str = ""
    log_lines_5min: int = 0
    zombie_count: int = 0
    timestamp_dir: str = ""

    @property
    def progress_pct(self) -> float:
        if self.tasks_total == 0:
            return 0.0
        return (self.tasks_completed / self.tasks_total) * 100

    def status_char(self) -> str:
        """Single char status: R=running, D=done, S=stopped, P=preprocessing."""
        if not self.is_running:
            return "S"
        if self.tasks_total == 0:
            return "P"
        if self.tasks_completed >= self.tasks_total:
            return "D"
        return "R"

    def compact_str(self) -> str:
        """Compact representation: ID:STATUS:COMPLETED/TOTAL"""
        if self.tasks_total == 0:
            return f"{self.container_id}:{self.status_char()}:prep"
        return f"{self.container_id}:{self.status_char()}:{self.tasks_completed}/{self.tasks_total}"

    def is_stuck(self, prev_tasks: int, min_cpu: float = 50.0) -> tuple[bool, list[str]]:
        """Check if container is stuck. Returns (is_stuck, reasons)."""
        reasons = []

        if not self.is_running:
            return False, ["not running"]

        if self.tasks_total == 0:
            return False, ["preprocessing"]

        if self.tasks_completed >= self.tasks_total:
            return False, ["completed"]

        stuck_score = 0

        # Tasks not progressing (weight: 2)
        if self.tasks_completed == prev_tasks and prev_tasks > 0:
            reasons.append(f"no progress {self.tasks_completed}/{self.tasks_total}")
            stuck_score += 2

        # Low CPU (weight: 1)
        if self.cpu_percent < min_cpu:
            reasons.append(f"low CPU {self.cpu_percent:.0f}%")
            stuck_score += 1

        # No recent logs (weight: 2)
        if self.log_lines_5min == 0:
            reasons.append("no logs 5min")
            stuck_score += 2

        # Zombie processes (weight: 1)
        if self.zombie_count > 0:
            reasons.append(f"{self.zombie_count} zombies")
            stuck_score += 1

        return stuck_score >= 3, reasons


class RVSecWatchdog:
    """Watchdog for RVSEC container monitoring."""

    def __init__(
        self,
        exp_dir: Path,
        container_prefix: str,
        interval_minutes: int = 10,
        full_table_interval: int = 6,  # Show full table every N checks (6*10min = 1h)
        docker_compose_file: Path = None,
        log_file: Path = None,
        verbose: bool = False
    ):
        self.exp_dir = Path(exp_dir)
        self.container_prefix = container_prefix
        self.interval = interval_minutes * 60
        self.full_table_interval = full_table_interval
        self.docker_compose_file = docker_compose_file or Path.cwd() / "docker-compose.yml"

        if log_file is None:
            log_file = Path.cwd() / "watchdog.log"
        self.log_file = log_file
        self.logger = setup_logging(log_file, verbose)

        self.previous_tasks: dict[str, int] = {}
        self.resume_attempts: dict[str, int] = {}
        self.max_resume_attempts = 2
        self.check_count = 0

        self.logger.info("=" * 70)
        self.logger.info("RVSEC Watchdog Started")
        self.logger.info(f"  Dir: {self.exp_dir} | Prefix: {self.container_prefix}")
        self.logger.info(f"  Interval: {interval_minutes}min | Full table every: {full_table_interval} checks")
        self.logger.info("=" * 70)

    def run_cmd(self, cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
        """Execute command and return (success, output)."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return True, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    def get_container_stats(self) -> dict[str, dict]:
        """Get CPU/memory stats for containers."""
        success, output = self.run_cmd([
            "docker", "stats", "--no-stream", "--format",
            "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
        ])
        stats = {}
        if success:
            for line in output.strip().split('\n'):
                if line and self.container_prefix in line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        try:
                            cpu = float(parts[1].replace('%', '').strip())
                        except ValueError:
                            cpu = 0.0
                        stats[parts[0]] = {'cpu': cpu, 'mem': parts[2].split('/')[0].strip()}
        return stats

    def get_container_status(self) -> dict[str, str]:
        """Get container running status."""
        success, output = self.run_cmd([
            "docker", "ps", "-a", "--filter", f"name={self.container_prefix}",
            "--format", "{{.Names}}\t{{.Status}}"
        ])
        status = {}
        if success:
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        status[parts[0]] = parts[1]
        return status

    def get_log_lines(self, container_name: str, since: str = "5m") -> int:
        """Count recent log lines."""
        success, output = self.run_cmd(["docker", "logs", container_name, "--since", since], timeout=10)
        if success:
            return len(output.strip().split('\n')) if output.strip() else 0
        return -1

    def get_zombie_count(self, container_name: str) -> int:
        """Count zombie processes in container."""
        success, output = self.run_cmd(["docker", "exec", container_name, "ps", "aux"], timeout=10)
        return output.count('<defunct>') if success else 0

    def get_execution_memory(self, results_dir: Path) -> Optional[dict]:
        """Read latest execution_memory.json."""
        try:
            ts_dirs = sorted([d for d in results_dir.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)
            if ts_dirs:
                mem_file = ts_dirs[0] / "execution_memory.json"
                if mem_file.exists():
                    with open(mem_file) as f:
                        return json.load(f)
        except Exception:
            pass
        return None

    def count_tasks(self, memory: dict) -> tuple[int, int]:
        """Count (completed, total) tasks."""
        if not memory:
            return 0, 0
        total = completed = 0
        for apk, reps in memory.items():
            for rep, timeouts in reps.items():
                for timeout, tools in timeouts.items():
                    for tool, data in tools.items():
                        total += 1
                        if data.get('executed', False):
                            completed += 1
        return completed, total

    def get_timestamp_dir(self, results_dir: Path) -> str:
        """Get latest timestamp directory name."""
        try:
            ts_dirs = sorted([d for d in results_dir.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)
            return ts_dirs[0].name if ts_dirs else ""
        except Exception:
            return ""

    def collect_health(self, container_id: str) -> ContainerHealth:
        """Collect container health information."""
        container_name = f"{self.container_prefix}-{container_id}"
        results_dir = self.exp_dir / container_id / "results"

        health = ContainerHealth(container_id=container_id, container_name=container_name)

        statuses = self.get_container_status()
        health.is_running = "Up" in statuses.get(container_name, "")

        if not health.is_running:
            return health

        stats = self.get_container_stats()
        if container_name in stats:
            health.cpu_percent = stats[container_name]['cpu']
            health.memory_usage = stats[container_name]['mem']

        if results_dir.exists():
            memory = self.get_execution_memory(results_dir)
            health.tasks_completed, health.tasks_total = self.count_tasks(memory)
            health.timestamp_dir = self.get_timestamp_dir(results_dir)

        health.log_lines_5min = self.get_log_lines(container_name)
        health.zombie_count = self.get_zombie_count(container_name)

        return health

    def update_compose_for_resume(self, container_id: str, timestamp: str) -> bool:
        """Update docker-compose.yml for resume."""
        self.logger.info(f"  Updating docker-compose.yml for resume...")
        try:
            with open(self.docker_compose_file, 'r') as f:
                content = f.read()

            service = f"rv{container_id}"
            pattern = rf'(  {service}:.*?environment:\n)(.*?)(    volumes:)'
            match = re.search(pattern, content, re.DOTALL)

            if not match:
                self.logger.error(f"  Section {service} not found")
                return False

            env = match.group(2)
            if 'RV_MEMORY_FILE' in env:
                env = re.sub(r'RV_MEMORY_FILE=.*?execution_memory\.json',
                           f'RV_MEMORY_FILE=/opt/rvsec/rv-android/results/{timestamp}/execution_memory.json', env)
            else:
                resume_cfg = f"""      # Resume config (watchdog)
      - RV_MEMORY_FILE=/opt/rvsec/rv-android/results/{timestamp}/execution_memory.json
      - RV_SKIP_INSTRUMENT=true
      - RV_SKIP_MONITORS=true
      - RV_SKIP_STATIC_ANALYSIS=true
"""
                env = env.rstrip() + '\n' + resume_cfg

            new_content = content[:match.start()] + match.group(1) + env + match.group(3) + content[match.end():]
            with open(self.docker_compose_file, 'w') as f:
                f.write(new_content)

            self.logger.info(f"  docker-compose.yml updated (timestamp: {timestamp})")
            return True
        except Exception as e:
            self.logger.error(f"  Error updating compose: {e}")
            return False

    def perform_resume(self, health: ContainerHealth) -> bool:
        """Execute full resume procedure (recreates container from scratch)."""
        cid, cname, ts = health.container_id, health.container_name, health.timestamp_dir

        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info(f"RESUME: {cname} | ts={ts} | {health.tasks_completed}/{health.tasks_total}")
        self.logger.info("=" * 70)

        if not ts:
            self.logger.error("  No timestamp found!")
            return False

        # Stop (force kill after 30s)
        self.logger.info("  [1/5] Stopping container...")
        ok, out = self.run_cmd(["docker", "stop", "-t", "30", cname], timeout=120)
        if not ok:
            self.logger.error(f"  Stop failed: {out}")
            return False

        # Remove container (recreate from scratch)
        self.logger.info("  [2/5] Removing container...")
        ok, out = self.run_cmd(["docker", "rm", cname], timeout=30)
        if not ok:
            self.logger.error(f"  Remove failed: {out}")
            return False

        # Update compose
        self.logger.info("  [3/5] Configuring resume...")
        if not self.update_compose_for_resume(cid, ts):
            return False

        # Recreate container
        self.logger.info("  [4/5] Recreating container...")
        ok, out = self.run_cmd(["docker", "compose", "up", "-d", f"rv{cid}"], timeout=120)
        if not ok:
            self.logger.error(f"  Recreate failed: {out}")
            return False

        # Verify
        self.logger.info("  [5/5] Verifying resume...")
        time.sleep(15)
        ok, out = self.run_cmd(["docker", "logs", cname, "--tail", "30"], timeout=15)

        if ok and ("Skipping" in out or "memory_file=" in out):
            self.logger.info("  Resume OK - skipping executed tasks")
            self.logger.info("=" * 70)
            return True
        else:
            self.logger.warning("  Resume may have issues - check manually")
            return True

    def check_all(self) -> list[ContainerHealth]:
        """Check all containers."""
        dirs = sorted([d for d in self.exp_dir.iterdir() if d.is_dir() and d.name.isdigit()])
        return [self.collect_health(d.name) for d in dirs]

    def log_full_table(self, health_list: list[ContainerHealth]):
        """Log full status table."""
        self.logger.info("")
        self.logger.info(f"{'ID':<3} {'St':<2} {'CPU':>6} {'RAM':>8} {'Progress':>8} {'Tasks':>11} {'Log':>4} {'Z':>4}")
        self.logger.info("-" * 55)
        for h in health_list:
            st = h.status_char()
            cpu = f"{h.cpu_percent:.0f}%" if h.is_running else "-"
            ram = h.memory_usage[:8] if h.memory_usage else "-"
            prog = f"{h.progress_pct:.0f}%" if h.tasks_total > 0 else "-"
            tasks = f"{h.tasks_completed}/{h.tasks_total}" if h.tasks_total > 0 else "-"
            logs = str(h.log_lines_5min) if h.log_lines_5min >= 0 else "-"
            z = str(h.zombie_count) if h.zombie_count > 0 else "-"
            self.logger.info(f"{h.container_id:<3} {st:<2} {cpu:>6} {ram:>8} {prog:>8} {tasks:>11} {logs:>4} {z:>4}")

        total_c = sum(h.tasks_completed for h in health_list)
        total_t = sum(h.tasks_total for h in health_list)
        total_pct = (total_c / total_t * 100) if total_t > 0 else 0
        self.logger.info("-" * 55)
        self.logger.info(f"ALL   {total_pct:>27.0f}% {total_c:>5}/{total_t:<5}")
        self.logger.info("")

    def log_compact(self, health_list: list[ContainerHealth]):
        """Log compact one-line status."""
        total_c = sum(h.tasks_completed for h in health_list)
        total_t = sum(h.tasks_total for h in health_list)
        total_pct = (total_c / total_t * 100) if total_t > 0 else 0

        parts = [h.compact_str() for h in health_list]
        self.logger.info(f"Check #{self.check_count}: {total_c}/{total_t} ({total_pct:.0f}%) | {' '.join(parts)}")

    def run_once(self) -> tuple[bool, list[str]]:
        """Run one check cycle. Returns (all_ok, errors)."""
        self.check_count += 1
        health_list = self.check_all()

        # Decide log format: full table every N checks or on first run
        if self.check_count == 1 or self.check_count % self.full_table_interval == 0:
            self.log_full_table(health_list)
        else:
            self.log_compact(health_list)

        errors = []
        stuck_detected = False

        for health in health_list:
            cid = health.container_id
            prev = self.previous_tasks.get(cid, -1)

            if prev == -1:
                self.previous_tasks[cid] = health.tasks_completed
                continue

            is_stuck, reasons = health.is_stuck(prev)

            if is_stuck:
                stuck_detected = True
                self.logger.warning(f"STUCK: {health.container_name} - {', '.join(reasons)}")

                attempts = self.resume_attempts.get(cid, 0)
                if attempts >= self.max_resume_attempts:
                    err = f"{health.container_name} stuck after {attempts} resume attempts"
                    self.logger.error(err)
                    errors.append(err)
                else:
                    self.resume_attempts[cid] = attempts + 1
                    self.logger.info(f"Resume attempt {attempts + 1}/{self.max_resume_attempts}")

                    if self.perform_resume(health):
                        self.resume_attempts[cid] = 0
                        self.previous_tasks[cid] = health.tasks_completed
                    else:
                        errors.append(f"Resume failed: {health.container_name}")
            else:
                self.previous_tasks[cid] = health.tasks_completed
                if health.tasks_completed > prev:
                    self.resume_attempts[cid] = 0

        # If stuck was detected, show full table
        if stuck_detected and self.check_count % self.full_table_interval != 0:
            self.log_full_table(health_list)

        return len(errors) == 0, errors

    def run(self):
        """Main watchdog loop."""
        self.logger.info("Starting continuous monitoring (Ctrl+C to stop)")

        # Initial baseline
        health_list = self.check_all()
        for h in health_list:
            self.previous_tasks[h.container_id] = h.tasks_completed
        self.log_full_table(health_list)

        self.logger.info(f"Next check in {self.interval // 60} minutes...")

        try:
            while True:
                time.sleep(self.interval)

                all_ok, errors = self.run_once()

                if not all_ok:
                    self.logger.error("=" * 70)
                    self.logger.error("UNRECOVERABLE ERRORS - manual intervention required:")
                    for e in errors:
                        self.logger.error(f"  - {e}")
                    self.logger.error("=" * 70)
                    return False

                # Check if all completed
                health_list = self.check_all()
                if all(h.tasks_completed >= h.tasks_total and h.tasks_total > 0 for h in health_list):
                    self.logger.info("=" * 70)
                    self.logger.info("ALL CONTAINERS COMPLETED 100%!")
                    self.logger.info("=" * 70)
                    return True

        except KeyboardInterrupt:
            self.logger.info("Watchdog stopped by user")
            return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="RVSEC Watchdog - Container Stall Detector with Auto-Resume",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python watchdog.py containers --prefix rv
  python watchdog.py containers --prefix rv --interval 10 --verbose
  python watchdog.py containers --prefix rv --once
        """
    )

    parser.add_argument("exp_dir", help="Experiment directory (e.g., containers)")
    parser.add_argument("--prefix", "-p", default="rv", help="Container prefix (default: rv)")
    parser.add_argument("--interval", "-i", type=int, default=10, help="Check interval in minutes (default: 10)")
    parser.add_argument("--full-table", "-f", type=int, default=6, help="Full table every N checks (default: 6 = 1h)")
    parser.add_argument("--once", action="store_true", help="Run single check only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--log-file", "-l", type=str, help="Log file (default: watchdog.log)")

    args = parser.parse_args()

    exp_dir = Path(args.exp_dir)
    if not exp_dir.exists():
        print(f"Error: Directory not found: {args.exp_dir}")
        sys.exit(1)

    log_file = Path(args.log_file) if args.log_file else None

    watchdog = RVSecWatchdog(
        exp_dir=exp_dir,
        container_prefix=args.prefix,
        interval_minutes=args.interval,
        full_table_interval=args.full_table,
        log_file=log_file,
        verbose=args.verbose
    )

    if args.once:
        watchdog.check_count = 0  # Force full table on --once
        watchdog.run_once()
        sys.exit(0)
    else:
        success = watchdog.run()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
