#!/usr/bin/env python3
"""
Monitor de Experimentos RVSEC
Interface rica para acompanhamento em tempo real.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
    from rich.text import Text
    from rich import box
except ImportError:
    print("Instale rich: pip install rich")
    sys.exit(1)


console = Console()


def get_container_stats(container_prefix: str) -> dict:
    """Obtém estatísticas de uso de recursos dos containers."""
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"],
            capture_output=True, text=True, timeout=10
        )
        stats = {}
        for line in result.stdout.strip().split('\n'):
            if line and container_prefix in line:
                parts = line.split('\t')
                if len(parts) >= 4:
                    stats[parts[0]] = {
                        'cpu': parts[1],
                        'mem_usage': parts[2].split('/')[0].strip(),
                        'mem_pct': parts[3]
                    }
        return stats
    except Exception:
        return {}


def get_container_status(container_prefix: str) -> dict:
    """Obtém status dos containers."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_prefix}",
             "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        status = {}
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    status[parts[0]] = parts[1]
        return status
    except Exception:
        return {}


def get_experiment_start_time(exp_dir: Path) -> datetime:
    """Obtém o tempo de início do experimento baseado no BATCHES.csv (hora local)."""
    earliest = None

    # Primeiro tenta ler do BATCHES.csv (hora local confiável)
    try:
        batches_csv = exp_dir.parent / "BATCHES.csv"
        if batches_csv.exists():
            import csv
            with open(batches_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    start = row.get('start', '').strip()
                    if start:
                        try:
                            ts = datetime.strptime(start, "%Y-%m-%d %H:%M")
                            if earliest is None or ts < earliest:
                                earliest = ts
                        except ValueError:
                            pass
    except Exception:
        pass

    if earliest:
        return earliest

    # Fallback: ler dos diretórios de timestamp (pode ter timezone diferente)
    try:
        for container_dir in exp_dir.iterdir():
            if container_dir.is_dir() and container_dir.name.isdigit():
                results_dir = container_dir / "results"
                if results_dir.exists():
                    for d in results_dir.iterdir():
                        if d.is_dir() and d.name.isdigit() and len(d.name) == 14:
                            try:
                                ts = datetime.strptime(d.name, "%Y%m%d%H%M%S")
                                if earliest is None or ts < earliest:
                                    earliest = ts
                            except ValueError:
                                pass
    except Exception:
        pass

    return earliest if earliest else datetime.now()


def get_execution_memory(results_dir: Path) -> dict:
    """Lê o execution_memory.json mais recente."""
    try:
        timestamp_dirs = sorted([d for d in results_dir.iterdir() if d.is_dir()], reverse=True)
        if not timestamp_dirs:
            return None
        memory_file = timestamp_dirs[0] / "execution_memory.json"
        if memory_file.exists():
            with open(memory_file) as f:
                return json.load(f)
    except Exception:
        return None
    return None


def count_tasks(memory: dict) -> dict:
    """Conta tarefas totais e completadas."""
    if not memory:
        return {'total': 0, 'completed': 0, 'pct': 0}

    total = 0
    completed = 0

    for apk, reps in memory.items():
        for rep, timeouts in reps.items():
            for timeout, tools in timeouts.items():
                for tool, data in tools.items():
                    total += 1
                    if data.get('executed', False):
                        completed += 1

    pct = (completed / total * 100) if total > 0 else 0
    return {'total': total, 'completed': completed, 'pct': pct}


def estimate_remaining_time(memory: dict, overhead_per_task: int = 35) -> int:
    """Estima tempo restante em segundos baseado nas tasks não executadas.

    Args:
        memory: execution_memory.json dict
        overhead_per_task: segundos de overhead (emulador, etc) por task

    Returns:
        Total de segundos estimados restantes
    """
    if not memory:
        return 0

    total_seconds = 0

    for apk, reps in memory.items():
        for rep, timeouts in reps.items():
            for timeout_str, tools in timeouts.items():
                for tool, data in tools.items():
                    if not data.get('executed', False):
                        try:
                            timeout = int(timeout_str)
                        except ValueError:
                            timeout = 60  # fallback
                        total_seconds += timeout + overhead_per_task

    return total_seconds


def format_eta(seconds: int) -> str:
    """Formata segundos em string legível (ex: 2h30m, 45m, 12h)."""
    if seconds <= 0:
        return "done"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours >= 24:
        days = hours // 24
        hours = hours % 24
        return f"{days}d{hours}h"
    elif hours > 0:
        return f"{hours}h{minutes:02d}m"
    else:
        return f"{minutes}m"


def get_current_task(results_dir: Path) -> str:
    """Tenta identificar a tarefa atual sendo executada."""
    try:
        memory = get_execution_memory(results_dir)
        if not memory:
            return "Instrumentando..."

        for apk, reps in memory.items():
            for rep, timeouts in reps.items():
                for timeout, tools in timeouts.items():
                    for tool, data in tools.items():
                        if not data.get('executed', False) and data.get('start', 0) > 0:
                            return f"{apk[:20]}... | {tool}"
                        elif not data.get('executed', False):
                            return f"{apk[:20]}... | {tool} (pendente)"

        return "Concluído"
    except Exception:
        return "N/A"


def get_container_batches(exp_dir: Path) -> dict:
    """Lê BATCHES.csv e retorna mapeamento container -> batch."""
    batches = {}
    try:
        import csv
        batches_csv = exp_dir.parent / "BATCHES.csv"
        if batches_csv.exists():
            with open(batches_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status') == 'running' and row.get('container'):
                        batches[row['container']] = row['batch']
    except Exception:
        pass
    return batches


def create_dashboard(exp_dir: Path, container_prefix: str) -> Table:
    """Cria o dashboard compacto."""
    stats = get_container_stats(container_prefix)
    statuses = get_container_status(container_prefix)
    batches = get_container_batches(exp_dir)

    table = Table(title="RVSEC Monitor", box=box.ROUNDED, expand=False)
    table.add_column("ID", style="cyan", width=3)
    table.add_column("Bat", style="magenta", width=3)
    table.add_column("Status", width=9)
    table.add_column("CPU", justify="right", width=7)
    table.add_column("RAM", justify="right", width=8)
    table.add_column("Progresso", width=26)
    table.add_column("Tarefas", justify="right", width=10)
    table.add_column("ETA", justify="right", width=7)

    container_dirs = sorted([d for d in exp_dir.iterdir() if d.is_dir() and d.name.isdigit()])

    total_tasks = 0
    total_completed = 0
    total_eta_seconds = 0
    total_cpu = 0.0
    total_ram_gb = 0.0

    for cdir in container_dirs:
        container_name = f"{container_prefix}-{cdir.name}"
        status_raw = statuses.get(container_name, "N/A")
        stat = stats.get(container_name, {})

        results_dir = cdir / "results"
        memory = get_execution_memory(results_dir) if results_dir.exists() else None
        tasks = count_tasks(memory)
        total_tasks += tasks['total']
        total_completed += tasks['completed']

        # ETA calculation
        eta_seconds = estimate_remaining_time(memory)
        total_eta_seconds += eta_seconds
        eta_str = format_eta(eta_seconds) if memory else "-"

        # Accumulate CPU and RAM
        cpu_str = stat.get('cpu', '0%').replace('%', '')
        try:
            total_cpu += float(cpu_str)
        except ValueError:
            pass

        ram_str = stat.get('mem_usage', '0').replace('GiB', '').replace('MiB', '').strip()
        try:
            ram_val = float(ram_str)
            if 'MiB' in stat.get('mem_usage', ''):
                ram_val /= 1024  # Convert MiB to GiB
            total_ram_gb += ram_val
        except ValueError:
            pass

        # Status
        if "Up" in status_raw:
            status_text = Text("Running", style="green")
        elif "Exited (0)" in status_raw:
            status_text = Text("Done", style="blue")
        elif "Exited" in status_raw:
            status_text = Text("Failed", style="red")
        else:
            status_text = Text("-", style="yellow")

        # Progresso com barra (20 blocos, 5% cada)
        pct = tasks['pct']
        bar_filled = min(int(pct / 5), 20)
        bar_empty = 20 - bar_filled

        progress_text = Text()
        progress_text.append('█' * bar_filled, style="green")
        progress_text.append('░' * bar_empty, style="dim")
        progress_text.append(f" {pct:.0f}%")

        table.add_row(
            cdir.name,
            batches.get(cdir.name, "-"),
            status_text,
            stat.get('cpu', '-').replace('%', ''),
            stat.get('mem_usage', '-').replace('GiB', 'G'),
            progress_text,
            f"{tasks['completed']}/{tasks['total']}",
            eta_str
        )

    # Linha de total
    if total_tasks > 0:
        total_pct = (total_completed / total_tasks * 100)
        bar_filled = min(int(total_pct / 5), 20)
        bar_empty = 20 - bar_filled
        total_progress = Text()
        total_progress.append('█' * bar_filled, style="bold green")
        total_progress.append('░' * bar_empty, style="dim")
        total_progress.append(f" {total_pct:.0f}%")
    else:
        total_progress = Text("...", style="yellow")

    table.add_section()
    table.add_row(
        "ALL",
        "—",
        Text("—", style="dim"),
        f"{total_cpu:.0f}",
        f"{total_ram_gb:.1f}G",
        total_progress,
        f"{total_completed}/{total_tasks}",
        "—",
        style="bold"
    )

    return table


def monitor(exp_dir: str, container_prefix: str, watch: bool = False, interval: int = 10):
    """Função principal de monitoramento."""
    exp_path = Path(exp_dir)

    if not exp_path.exists():
        console.print(f"[red]Diretório não encontrado: {exp_dir}[/red]")
        return

    if watch:
        with Live(console=console, refresh_per_second=0.5) as live:
            while True:
                try:
                    table = create_dashboard(exp_path, container_prefix)
                    live.update(table)
                    time.sleep(interval)
                except KeyboardInterrupt:
                    break
    else:
        table = create_dashboard(exp_path, container_prefix)
        console.print(table)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monitor de Experimentos RVSEC")
    parser.add_argument("exp_dir", help="Diretório do experimento (ex: mini-exp-03)")
    parser.add_argument("--prefix", "-p", default="rv-mini03", help="Prefixo dos containers")
    parser.add_argument("--watch", "-w", action="store_true", help="Modo watch (atualização contínua)")
    parser.add_argument("--interval", "-i", type=int, default=10, help="Intervalo de atualização (segundos)")

    args = parser.parse_args()
    monitor(args.exp_dir, args.prefix, args.watch, args.interval)
