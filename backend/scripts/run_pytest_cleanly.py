from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        process.kill()
        try:
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run pytest and fail deterministically if it does not terminate."
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    if arguments.timeout <= 0:
        parser.error("--timeout must be positive")
    pytest_args = arguments.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    command = [sys.executable, "-m", "pytest", *pytest_args]
    backend_directory = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        command,
        cwd=backend_directory,
        start_new_session=os.name != "nt",
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        ),
    )
    try:
        return process.wait(timeout=arguments.timeout)
    except subprocess.TimeoutExpired:
        print(
            f"pytest did not terminate within {arguments.timeout:g} seconds; "
            "terminating its process tree",
            file=sys.stderr,
        )
        _terminate_process_tree(process)
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
