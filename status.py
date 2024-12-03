import argparse
import os
import datetime
import json
from rich import print

import time

from rich.progress import Progress, TaskProgressColumn, TimeRemainingColumn, MofNCompleteColumn, SpinnerColumn, \
    DownloadColumn

from time import sleep

from rich.table import Column
from rich.progress import Progress, BarColumn, TextColumn


from rich.console import Console
from rich.table import Table


def main():
    parser = argparse.ArgumentParser(description='Executa ações com base no ID fornecido.')
    parser.add_argument('--exec', type=str, help='ID da ação a ser executada')

    args = parser.parse_args()

    exec_map = get_results_map()
    if args.exec:
        execution_info(exec_map[args.exec])
    else:
        all_executions_info(exec_map)



def execution_info(execution_memory):
    table = Table(title="Tasks")
    # table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("apk", style="magenta")
    table.add_column("rep", justify="right", style="green")
    table.add_column("timeout", justify="right", style="magenta")
    table.add_column("tool", justify="right", style="magenta")
    table.add_column("executed", justify="center", style="magenta")
    table.add_column("time", justify="right", style="magenta")
    execution = read_execution_memory(execution_memory)
    # print(f"execution={execution}")
    for apk in execution:            
        for rep in execution[apk]:
            for timeout in execution[apk][rep]:
                for tool in execution[apk][rep][timeout]:   
                    task = execution[apk][rep][timeout][tool] 
                    # print(task)
                    executed = ""
                    time = ""
                    if task["executed"]:
                        time = task["finish"] - task["start"]
                        #python -m rich.emoji
                        executed = ":white_heavy_check_mark:"
                    table.add_row(apk, str(rep), str(timeout), tool, executed, str(time))
    console = Console()
    console.print(table)


def all_executions_info(exec_map):
    map_total = { }
    total_tasks = 0
    tasks_executed = 0
    for _exec in exec_map:
        execution = read_execution_memory( exec_map[_exec])
        map_total[_exec] = { "total_tasks": 0,
                                "executed": 0,
                                "pct": 0.0}
        for apk in execution:            
            for rep in execution[apk]:
                for timeout in execution[apk][rep]:
                    for tool in execution[apk][rep][timeout]:   
                        task = execution[apk][rep][timeout][tool]                             
                        total_tasks += 1
                        map_total[_exec]["total_tasks"] += 1
                        if task["executed"]:                                         
                            tasks_executed += 1      
                            map_total[_exec]["executed"] += 1     

            
    executions_progress(map_total)

    print(f"tasks_total={total_tasks}")
    print(f"tasks_executed={tasks_executed}")

    



def executions_progress(map_total):
    with Progress(
                TextColumn("[bold green][progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                TextColumn("[green]tasks completed")) as progress:
        for _exec in sorted(map_total):
            total = map_total[_exec]["total_tasks"]
            executed = map_total[_exec]["executed"]
            exec_bar = progress.add_task(f"[green]EXEC_{_exec}", total=total)
            progress.update(exec_bar, advance=executed)


def read_execution_memory(file_path: str):
    with open(file_path, 'r') as exec_file:
        dados = json.load(exec_file)
        return dados


def get_results_map():
    results_map = {}
    subdirectories = [f.path for f in os.scandir(".") if f.is_dir()]
    if not subdirectories:
            return None

    for subdir in subdirectories:           
        if ".git" in subdir:
            continue      
        results_dir = get_latest_subdirectory(os.path.join(subdir,"results"))        
        results_map[subdir[2:]] = os.path.join(subdir,"results",results_dir,"execution_memory.json")
    return results_map


def get_latest_subdirectory(directory):
    try:
        subdirectories = [f.path for f in os.scandir(directory) if f.is_dir()]
        if not subdirectories:
            return None

        modified_times = {
            subdirectory: os.path.getmtime(subdirectory)
            for subdirectory in subdirectories
        }

        latest_subdirectory = max(modified_times, key=modified_times.get)        
        return os.path.basename(latest_subdirectory)
    except FileNotFoundError:
        print(f"O diretório '{directory}' não foi encontrado.")
        return None
    

if __name__ == '__main__':
    # aaa = "/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-02"
    # aaa = "/pedro/desenvolvimento/RV_ANDROID/EXPERIMENTO_02/BASE/para05/04/results"
    # print(get_latest_subdirectory(aaa))
    main()