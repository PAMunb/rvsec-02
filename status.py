import argparse
import os
import datetime
import json
from rich import print
import pandas as pd
import time
from pathlib import Path
from rich.progress import Progress, TaskProgressColumn, TimeRemainingColumn, MofNCompleteColumn, SpinnerColumn, \
    DownloadColumn

from time import sleep

from rich.table import Column
from rich.progress import Progress, BarColumn, TextColumn


from rich.console import Console
from rich.table import Table
#from rich_tools import table_to_df


def main():
    parser = argparse.ArgumentParser(description="Allows you to monitor the status of the experiment execution.")
    parser.add_argument("--exec", type=str, help="Show details of an execution. Pass only the execution number (ID). Example: --exec 03")
    parser.add_argument("--save", nargs=2, metavar=("ID", "FILE"), help="Saves execution status to a csv file. Example: --save 01 exec01.csv")

    args = parser.parse_args()

    exec_map = get_results_map()
    if args.exec:
        execution_info(exec_map[args.exec])
    elif args.save:
        table = execution_info(exec_map[args.save[0]], print_to_console=False)       
        save_execution_info(table, args.save[1])
    else:
        all_executions_info(exec_map)


def save_execution_info(table: Table, output_file: str):    
    df = table_to_dataframe(table)
    df.to_csv(output_file, index=False)


def execution_info(execution_memory: str, print_to_console=True):    
    table = Table(title="Tasks from: {}".format(execution_memory))
    # table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("apk", style="magenta")
    table.add_column("rep", justify="right", style="green")
    table.add_column("timeout", justify="right", style="magenta")
    table.add_column("tool", justify="right", style="magenta")
    table.add_column("executed", justify="center", style="magenta")
    table.add_column("time", justify="right", style="magenta")
    execution = read_execution_memory(execution_memory)
    for apk in execution:            
        for rep in execution[apk]:
            for timeout in execution[apk][rep]:
                for tool in execution[apk][rep][timeout]:   
                    task = execution[apk][rep][timeout][tool] 
                    executed = ""
                    time = ""
                    if task["executed"]:
                        time = task["finish"] - task["start"]
                        #python -m rich.emoji
                        executed = ":white_heavy_check_mark:"
                    table.add_row(apk, str(rep), str(timeout), tool, executed, str(time))                    
    if print_to_console:
        console = Console()
        console.print(table)        
    return table


def all_executions_info(exec_map):
    map_total = { }
    total_tasks = 0
    tasks_executed = 0
    for _exec in exec_map:
        execution = read_execution_memory( exec_map[_exec])
        map_total[_exec] = { "total_tasks": 0, "executed": 0, "pct": 0.0}
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
    print(f"tasks_pct={((tasks_executed*100)/total_tasks):.2f}%")


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
    with open(file_path, "r") as exec_file:
        dados = json.load(exec_file)
        return dados


def get_results_map():
    results_map = {}
    subdirectories = [f.path for f in os.scandir(".") if f.is_dir()]
    if not subdirectories:
            return None

    for subdir in subdirectories:           
        if ".git" in subdir or "RESULTS" in subdir or "venv" in subdir:
            continue      
        results_dir = get_latest_subdirectory(os.path.join(subdir,"results"))        
        results_map[subdir[2:]] = os.path.join(subdir,"results",results_dir,"execution_memory.json")
    return results_map


def get_latest_subdirectory(directory):
    try:
        path = Path(directory)
        latest_subdirectory = max(path.glob('*'), key=lambda x: x.stat().st_mtime)
        return latest_subdirectory.name
    except FileNotFoundError:
        print(f"Directory '{directory}' not found.")
        return None


def table_to_dataframe(table: Table):
    data = []
    header = []
    for column in table.columns:
        header.append(column.header)        
        line = []
        for cell in column.cells:
            line.append(cell)            
        data.append(line)    
    transposed_matrix = [[row[i] for row in data] for i in range(len(data[0]))]
    return pd.DataFrame(transposed_matrix, columns=header)    


if __name__ == "__main__":
    main()
