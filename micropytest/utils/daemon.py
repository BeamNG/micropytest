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

ALIVE_INTERVAL = 5  # seconds
REQUEST_TIMEOUT = 1  # seconds

def main():
    if len(sys.argv) < 2:
        print("Usage: python daemon.py <api_endpoint>", file=sys.stderr)
        sys.exit(1)
    api_endpoint = sys.argv[1]
    session = requests.Session()

    run_id = None
    lock = threading.Lock()
    parent_pid = os.getppid()
    print(f"Started keep-alive daemon pid={os.getpid()} parent_pid={parent_pid}")

    def sleep_responsive(t: float):
        """Sleep for t seconds and return run_id, returns early if run_id is None or -1."""
        slept = 0.0
        sleep_time = 0.1
        while True:
            time.sleep(sleep_time)
            slept += sleep_time
            with lock:
                rid = run_id
            if slept >= t or rid is None or rid == -1:
                break
        return rid

    def worker():
        nonlocal run_id
        while True:
            rid = sleep_responsive(ALIVE_INTERVAL)
            if rid is None:
                continue
            if rid == -1:
                break  # main thread exited loop
            print(f"Sending keep-alive for run {rid}")
            cancel = send_running_alive(rid, api_endpoint, session)
            if cancel:
                try:
                    print("Got cancel: sending SIGINT to parent process")
                    if os.name == 'nt':
                        import ctypes
                        kernel32 = ctypes.windll.kernel32
                        kernel32.GenerateConsoleCtrlEvent(0, 0)
                    else:
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
            # parent exited or closed stdin -> exit
            with lock:
                run_id = -1  # request thread to exit
            break
        line = line.strip()
        print(f"Received command: {line}")
        with lock:
            if line.startswith("start "):
                parts = line.split()
                if len(parts) == 2:
                    if run_id is None:
                        run_id = int(parts[1])
            elif line == "stop":
                run_id = None

    thread.join()
    time.sleep(0.1)  # without this the parent process often exits with code 130 instead of 0 on Windows
    print("Keep-alive daemon exited normally")


def send_running_alive(run_id: int, url: str, session: requests.Session) -> bool:
    """Report to server that a test is still running, return True if the test was cancelled server side."""
    url = f"{url}/runs/{run_id}/alive"
    response = session.put(url, headers={}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()['cancel']


if __name__ == "__main__":
    main()
