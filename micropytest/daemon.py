"""
This script should be started as daemon subprocess.
It sends keep-alive messages to an API endpoint periodically.
"""
import sys
import os
import signal
import time
import threading
import requests
from micropytest.store import RunningAliveResponseData

ALIVE_INTERVAL = 5  # seconds

def main():
    if len(sys.argv) < 2:
        print("Usage: python daemon.py <api_endpoint>", file=sys.stderr)
        sys.exit(1)
    api_endpoint = sys.argv[1]

    run_id = None
    lock = threading.Lock()
    parent_pid = os.getppid()

    def worker():
        while True:
            time.sleep(ALIVE_INTERVAL)
            with lock:
                rid = run_id
            if rid is None:
                continue
            cancel = send_running_alive(rid, api_endpoint)
            if cancel:
                try:
                    os.kill(parent_pid, signal.SIGINT)
                except Exception:
                    pass
                with lock:
                    run_id = None

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        line = sys.stdin.readline()
        if line == '':
            break  # parent exited or closed stdin -> exit
        line = line.strip()
        with lock:
            if line.startswith("start "):
                parts = line.split()
                if len(parts) == 2:
                    if run_id is None:
                        run_id = int(parts[1])
            elif line == "stop":
                run_id = None

    thread.join()


def send_running_alive(run_id: int, url: str) -> bool:
    """Report to server that a test is still running, return True if the test was cancelled server side."""
    url = f"{url}/runs/{run_id}/running_alive"
    response = requests.put(url, headers={}, timeout=1)
    response.raise_for_status()
    response_data = RunningAliveResponseData.model_validate(response.json())
    return response_data.cancel


if __name__ == "__main__":
    main()
