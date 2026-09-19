import os

#import pathlib
import secrets
import signal
import subprocess
import sys
import time

#import threading

total: int = 10
batch_size: int = 2
result = "f6cba7f40fe662133e699e3506501a4c0ea316a8c5934e02bb83ff3ad9e42daf"
result_path = os.path.join("workspace", "result.md")

base_commande = [
    sys.executable,
    "-m",
    "enboite",
    "--model", "ornith-1.5:35b",
    "--ctx", "256000",
    "--thinking",
    "--non-interactive",
    "--prompt-file", "dev/bench/sha256"
]


processes: dict[str, subprocess.Popen] = {}

_result = []

def clear(x: dict[str, subprocess.Popen]) -> dict[str, subprocess.Popen]:
    for path, proc in list(x.items()):
        if proc.poll() != None:
            del x[path]
            
            print(f"{path} : {proc.poll()}")
            file_result = os.path.join(path, result_path)
            
            if os.path.isfile(file_result):
                with open(file_result, "rb") as f:
                    data = f.read(len(result.encode()))
                
                if data == result.encode():
                    print("OK")
                    _result.append(True)
                else:
                    print("INVALIDE")
                    _result.append(False)
            else:
                print("no file")
                _result.append(False)
    return x

start_time = time.monotonic()
try:
    for i in range(total):
        while True:
            if sum(process.poll() is None for process in list(processes.values())) < batch_size:
                data_dir = os.path.join("/tmp", secrets.token_hex(32))
                
                processes[data_dir] = (
                    subprocess.Popen(
                        base_commande + ["--data-dir", data_dir],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                ))
                break
            else:
                #processes = clear(processes)
                time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    try:
        for proc in processes.values():
            proc.wait()
    except KeyboardInterrupt:
        for proc in processes.values():
            proc.send_signal(signal.SIGINT)
    processes = clear(processes)
    
    print(f"result: {sum(_result)}/{total}")
    print(f"time bench: {time.monotonic() - start_time}s")
    sys.exit(0)