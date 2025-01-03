# core.py
"""
core.py - Contains the core logic for micropytest:
 - test discovery
 - run_tests
 - logging context/handlers
 - storing durations in .micropytest.json

Users who want a programmatic approach can just import run_tests(),
and won't need to deal with the CLI or argument parsing.
"""

import logging
import sys
import json
import traceback
import inspect
import time
from pathlib import Path
import importlib.util
from datetime import datetime
from collections import Counter
from . import __version__

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
except ImportError:
    class _FallbackFore:
        RED = GREEN = YELLOW = MAGENTA = CYAN = ""
    class _FallbackStyle:
        RESET_ALL = ""
    Fore = _FallbackFore()
    Style = _FallbackStyle()

CONFIG_FILE = ".micropytest.json"


class LiveFlushingStreamHandler(logging.StreamHandler):
    """
    A stream handler that flushes logs immediately, giving real-time console output.
    """
    def emit(self, record: logging.LogRecord):
        super().emit(record)
        self.flush()


def create_live_console_handler(formatter=None, level=logging.INFO):
    handler = LiveFlushingStreamHandler(stream=sys.stdout)
    if formatter:
        handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler


class TestContext:
    """
    A context object passed to each test if it accepts 'ctx'.
    Allows logging via ctx.debug(), etc. and storing artifacts.
    """
    def __init__(self):
        self.log_records = []
        self.log = logging.getLogger()
        self.artifacts = {}

    def debug(self, msg: str):
        self.log.debug(msg)

    def warn(self, msg: str):
        self.log.warning(msg)

    def error(self, msg: str):
        self.log.error(msg)

    def fatal(self, msg: str):
        self.log.critical(msg)

    def add_artifact(self, key, value):
        from pathlib import Path
        if isinstance(value, (str, Path)):
            path_val = Path(value)
            if path_val.is_file():
                self.debug(f"Artifact file '{value}' exists.")
            else:
                self.warn(f"Artifact file '{value}' does NOT exist.")
            self.artifacts[key] = {'type': 'filename', 'value': value}
        else:
            self.artifacts[key] = {'type': 'primitive', 'value': value}


class GlobalContextLogHandler(logging.Handler):
    """
    A handler that captures all logs into a single test's context log_records,
    so we can show them in a final summary or store them.
    """
    def __init__(self, ctx: TestContext, formatter=None):
        super().__init__()
        self.ctx = ctx
        if formatter:
            self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.ctx.log_records.append((record.levelname, msg))


class SimpleLogFormatter(logging.Formatter):
    """
    Format logs with a timestamp and color-coded level, e.g.:
    HH:MM:SS LEVEL|LOGGER| message
    """
    def format(self, record: logging.LogRecord) -> str:
        tstamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname
        origin = record.name
        message = record.getMessage()

        if level in ("ERROR", "CRITICAL"):
            color = Fore.RED
        elif level == "WARNING":
            color = Fore.YELLOW
        elif level == "DEBUG":
            color = Fore.MAGENTA
        elif level == "INFO":
            color = Fore.CYAN
        else:
            color = ""

        return f"{color}{tstamp} {level:8s}|{origin:11s}| {message}{Style.RESET_ALL}"


def load_test_module_by_path(file_path):
    """
    Dynamically import a Python file as a module, so we can discover test_* functions.
    """
    spec = importlib.util.spec_from_file_location("micropytest_dynamic", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_test_files(start_dir="."):
    """
    Recursively find all *.py that match test_*.py or *_test.py,
    excluding files in virtual environment or site-packages folders.
    """
    start_path = Path(start_dir)
    test_files = []
    for pyfile in start_path.rglob("*.py"):
        parts = set(pyfile.parts)
        # Skip typical venv or site-packages directories
        if (".venv" in parts or "venv" in parts or "site-packages" in parts):
            continue
        name = pyfile.name
        if name.startswith("test_") or name.endswith("_test.py"):
            test_files.append(str(pyfile))
    return test_files


def load_lastrun(tests_root: str):
    """
    Load .micropytest.json from the given tests root (tests_root/.micropytest.json) if present.
    Returns a dict with test durations, etc.
    """
    p = Path(tests_root) / CONFIG_FILE
    if p.exists():
        try:
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def store_lastrun(tests_root: str, test_durations):
    """
    Write out test durations to tests_root/.micropytest.json.
    """
    data = {
        "_comment": "This file is optional: it stores data about the last run of tests for doing time estimates.",
        "micropytest_version": __version__,
        "test_durations": test_durations
    }
    p = Path(tests_root) / CONFIG_FILE
    try:
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def run_tests(tests_path: str, show_estimates: bool):
    """
    The core function that:
      1) Discovers test_*.py
      2) For each test function test_*,
         - optionally injects a TestContext
         - times the test
         - logs pass/fail
      3) Updates .micropytest.json with durations
      4) Returns a list of test results

    Note: Logging configuration (verbosity, quiet, etc.) can be done by the caller.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # or caller sets this

    formatter = SimpleLogFormatter()

    # Load known durations from tests_path/.micropytest.json
    lastrun_data = load_lastrun(tests_path)
    test_durations = lastrun_data.get("test_durations", {})

    # Discover test callables
    test_files = find_test_files(tests_path)
    test_funcs = []
    for f in test_files:
        try:
            mod = load_test_module_by_path(f)
        except Exception:
            root_logger.error(f"Error importing {f}:\n{traceback.format_exc()}")
            continue

        for attr in dir(mod):
            if attr.startswith("test_"):
                fn = getattr(mod, attr)
                if callable(fn):
                    test_funcs.append((f, attr, fn))

    total_tests = len(test_funcs)
    test_results = []
    passed_count = 0

    # Possibly show total estimate
    if show_estimates and total_tests > 0:
        sum_known = 0.0
        for (fpath, tname, _) in test_funcs:
            key = f"{fpath}::{tname}"
            sum_known += test_durations.get(key, 0.0)
        if sum_known > 0:
            root_logger.info(
                f"{Fore.CYAN}Estimated total time: ~{sum_known:.1f}s for {total_tests} tests{Style.RESET_ALL}"
            )

    # Run each test
    for (idx, (file_path, test_name, test_func)) in enumerate(test_funcs, start=1):
        ctx = TestContext()

        # attach a log handler for this test
        test_handler = GlobalContextLogHandler(ctx, formatter=formatter)
        root_logger.addHandler(test_handler)

        key = f"{file_path}::{test_name}"
        known_dur = test_durations.get(key, 0.0)

        if show_estimates:
            root_logger.info(
                f"{Fore.CYAN}STARTING: {key} (est ~{known_dur:.1f}s){Style.RESET_ALL}"
            )

        sig = inspect.signature(test_func)
        expects_ctx = len(sig.parameters) > 0

        t0 = time.perf_counter()
        outcome = {
            "file": file_path,
            "test": test_name,
            "status": None,
            "logs": ctx.log_records,
            "artifacts": ctx.artifacts,
            "duration_s": 0.0,
        }

        try:
            if expects_ctx:
                test_func(ctx)
            else:
                test_func()

            duration = time.perf_counter() - t0
            outcome["duration_s"] = duration
            passed_count += 1
            outcome["status"] = "pass"
            root_logger.info(
                f"{Fore.GREEN}FINISHED PASS: {key} ({duration:.3f}s){Style.RESET_ALL}"
            )
        except Exception:
            duration = time.perf_counter() - t0
            outcome["duration_s"] = duration
            outcome["status"] = "fail"
            root_logger.error(
                f"{Fore.RED}FINISHED FAIL: {key} ({duration:.3f}s)\n{traceback.format_exc()}{Style.RESET_ALL}"
            )
        finally:
            root_logger.removeHandler(test_handler)

        test_durations[key] = duration
        test_results.append(outcome)

    root_logger.info(
        f"{Fore.CYAN}Tests completed: {passed_count}/{total_tests} passed.{Style.RESET_ALL}"
    )

    # Write updated durations to tests_path/.micropytest.json
    store_lastrun(tests_path, test_durations)
    return test_results
