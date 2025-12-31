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


def create_dashboard(exp_dir: Path, container_prefix: str, start_time: datetime) -> Layout:
    """Cria o dashboard completo."""
    layout = Layout()

    # Divide em header + main
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=4)
    )

    # Header
    elapsed = datetime.now() - start_time
    elapsed_str = str(elapsed).split('.')[0]

    header_text = Text()
    header_text.append("🔬 RVSEC Experiment Monitor", style="bold cyan")
    header_text.append(f"  |  ⏱ Tempo: {elapsed_str}", style="dim")
    header_text.append(f"  |  📅 {datetime.now().strftime('%H:%M:%S')}", style="dim")

    layout["header"].update(Panel(header_text, box=box.ROUNDED))

    # Main - Tabela de containers
    stats = get_container_stats(container_prefix)
    statuses = get_container_status(container_prefix)

    table = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True)
    table.add_column("Container", style="cyan", width=14)
    table.add_column("Status", width=12)
    table.add_column("CPU", justify="right", width=8)
    table.add_column("RAM", justify="right", width=10)
    table.add_column("Progresso", width=12)
    table.add_column("Tarefa Atual", style="dim")

    container_dirs = sorted([d for d in exp_dir.iterdir() if d.is_dir() and d.name.isdigit()])

    total_tasks = 0
    total_completed = 0

    for cdir in container_dirs:
        container_name = f"{container_prefix}-{cdir.name}"
        status_raw = statuses.get(container_name, "N/A")
        stat = stats.get(container_name, {})

        # Progresso
        results_dir = cdir / "results"
        memory = get_execution_memory(results_dir) if results_dir.exists() else None
        tasks = count_tasks(memory)
        total_tasks += tasks['total']
        total_completed += tasks['completed']

        # Status colorido
        if "Up" in status_raw:
            status_text = Text("● Running", style="green")
        elif "Exited (0)" in status_raw:
            status_text = Text("✓ Done", style="blue")
        elif "Exited" in status_raw:
            status_text = Text("✗ Failed", style="red")
        else:
            status_text = Text(status_raw[:10], style="yellow")

        # Progresso com barra
        pct = tasks['pct']
        bar_filled = int(pct / 10)
        bar_empty = 10 - bar_filled
        progress_bar = f"[green]{'█' * bar_filled}[/green][dim]{'░' * bar_empty}[/dim] {pct:.0f}%"

        # Tarefa atual
        current_task = get_current_task(results_dir) if "Up" in status_raw else "-"

        table.add_row(
            cdir.name,
            status_text,
            stat.get('cpu', '-'),
            stat.get('mem_usage', '-'),
            progress_bar,
            current_task[:25]
        )

    layout["main"].update(Panel(table, title="Containers", box=box.ROUNDED))

    # Footer - Resumo
    total_pct = (total_completed / total_tasks * 100) if total_tasks > 0 else 0
    bar_filled = int(total_pct / 5)
    bar_empty = 20 - bar_filled
    total_bar = f"[bold green]{'█' * bar_filled}[/bold green][dim]{'░' * bar_empty}[/dim]"

    # Estimativa de tempo
    if total_completed > 0 and total_pct < 100:
        time_per_task = elapsed.total_seconds() / total_completed
        remaining_tasks = total_tasks - total_completed
        eta_seconds = time_per_task * remaining_tasks
        eta = str(timedelta(seconds=int(eta_seconds)))
    else:
        eta = "--:--:--"

    footer_text = Text()
    footer_text.append(f"\n  Total: {total_bar} {total_completed}/{total_tasks} ({total_pct:.1f}%)")
    footer_text.append(f"\n  ETA: {eta}", style="dim")

    layout["footer"].update(Panel(footer_text, title="Progresso Geral", box=box.ROUNDED))

    return layout


def monitor(exp_dir: str, container_prefix: str, watch: bool = False, interval: int = 10):
    """Função principal de monitoramento."""
    exp_path = Path(exp_dir)

    if not exp_path.exists():
        console.print(f"[red]Diretório não encontrado: {exp_dir}[/red]")
        return

    start_time = datetime.now()

    if watch:
        console.print("[bold cyan]Iniciando monitor... (Ctrl+C para sair)[/bold cyan]\n")
        with Live(console=console, refresh_per_second=0.5, screen=True) as live:
            while True:
                try:
                    dashboard = create_dashboard(exp_path, container_prefix, start_time)
                    live.update(dashboard)
                    time.sleep(interval)
                except KeyboardInterrupt:
                    break
        console.print("\n[bold]Monitor encerrado.[/bold]")
    else:
        dashboard = create_dashboard(exp_path, container_prefix, start_time)
        console.print(dashboard)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monitor de Experimentos RVSEC")
    parser.add_argument("exp_dir", help="Diretório do experimento (ex: mini-exp-03)")
    parser.add_argument("--prefix", "-p", default="rv-mini03", help="Prefixo dos containers")
    parser.add_argument("--watch", "-w", action="store_true", help="Modo watch (atualização contínua)")
    parser.add_argument("--interval", "-i", type=int, default=10, help="Intervalo de atualização (segundos)")

    args = parser.parse_args()
    monitor(args.exp_dir, args.prefix, args.watch, args.interval)
