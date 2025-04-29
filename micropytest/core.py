import logging
import sys
import os
import json
import traceback
import inspect
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import importlib.util

from . import __version__


CONFIG_FILE = ".micropytest.json"
TIME_REPORT_CUTOFF = 0.01 # dont report timings below this

class SkipTest(Exception):
    """
    Raised by a test to indicate it should be skipped.
    """
    pass

class LiveFlushingStreamHandler(logging.StreamHandler):
    """
    A stream handler that flushes logs immediately, giving real-time console output.
    """
    def emit(self, record):
        super(LiveFlushingStreamHandler, self).emit(record)
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
    Allows logging via ctx.debug(), etc., storing artifacts (key-value store), and skipping tests.
    """
    def __init__(self):
        self.log_records = []
        self.log = logging.getLogger()
        self.artifacts = {}

    def debug(self, msg):
        self.log.debug(msg)

    def info(self, msg):
        self.log.info(msg)

    def warn(self, msg):
        self.log.warning(msg)

    def error(self, msg):
        self.log.error(msg)

    def fatal(self, msg):
        self.log.critical(msg)

    def add_artifact(self, key, value):
        self.artifacts[key] = value

    def skip_test(self, msg=None):
        """
        Tests can call this to be marked as 'skipped', e.g. if the environment
        doesn't apply or prerequisites are missing.
        """
        raise SkipTest(msg or "Test was skipped by ctx.skip_test(...)")

    def get_logs(self):
        return self.log_records

    def get_artifacts(self):
        return self.artifacts

class GlobalContextLogHandler(logging.Handler):
    """
    A handler that captures all logs into a single test's context log_records,
    so we can show them in a final summary or store them.
    """
    def __init__(self, ctx, formatter=None):
        logging.Handler.__init__(self)
        self.ctx = ctx
        if formatter:
            self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.ctx.log_records.append((record.levelname, msg))


class SimpleLogFormatter(logging.Formatter):
    """
    Format logs with a timestamp and level, e.g.:
    HH:MM:SS LEVEL|LOGGER| message
    """
    def __init__(self, use_colors=True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record):
        try:
            from colorama import Fore, Style
            has_colorama = True
        except ImportError:
            has_colorama = False
                
        tstamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname
        origin = record.name
        message = record.getMessage()

        color = ""
        reset = ""
        if self.use_colors and has_colorama:
            if level in ("ERROR", "CRITICAL"):
                color = Fore.RED
            elif level == "WARNING":
                color = Fore.YELLOW
            elif level == "DEBUG":
                color = Fore.MAGENTA
            elif level == "INFO":
                color = Fore.CYAN
            reset = Style.RESET_ALL

        return f"{color}{tstamp} {level:8s}|{origin:11s}| {message}{reset}"


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
    excluding typical venv, site-packages, or __pycache__ folders.
    """
    test_files = []
    for root, dirs, files in os.walk(start_dir):
        if (".venv" in root) or ("venv" in root) or ("site-packages" in root) or ("__pycache__" in root):
            continue
        for f in files:
            if (f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py"):
                test_files.append(os.path.join(root, f))
    return test_files


def discover_tests(tests_path, test_filter=None, tag_filter=None, exclude_tags=None):
    """Discover all test functions in the given directory and subdirectories."""
    test_files = find_test_files(tests_path)
    test_funcs = find_test_functions(test_files, test_filter, tag_filter, exclude_tags)
    return test_funcs


def find_test_functions(test_files, test_filter=None, tag_filter=None, exclude_tags=None):
    """Find all test functions in the given test files."""

    tag_set = tags_to_set(tag_filter)
    exclude_tag_set = tags_to_set(exclude_tags)

    test_funcs = []
    for f in test_files:
        # Note: errors that happen during the test discovery phase (e.g. import errors) cannot be suppressed
        # because those errors would not be attributed to a specific test. This would mean that some tests would be
        # unexpectedly skipped in case of programming errors, without any indication of what went wrong.
        mod = load_test_module_by_path(f)

        for attr in dir(mod):
            if attr.startswith("test_"):
                fn = getattr(mod, attr)
                if callable(fn):
                    # Get tags from the function if they exist
                    tags = getattr(fn, '_tags', set())
                    
                    # Apply test filter if provided
                    name_match = not test_filter or test_filter in attr
                    
                    # Apply tag filter if provided
                    tag_match = not tag_set or (tags and tag_set.intersection(tags))
                    
                    # Apply exclude tag filter if provided
                    exclude_match = exclude_tag_set and tags and exclude_tag_set.intersection(tags)
                    
                    if name_match and tag_match and not exclude_match:
                        test_funcs.append((f, attr, fn, tags))
    return test_funcs


def tags_to_set(list_or_str):
    """Convert a list or string to a set."""
    if list_or_str:
        return {list_or_str} if isinstance(list_or_str, str) else set(list_or_str)
    return set()


def load_lastrun(tests_root):
    """
    Load .micropytest.json from the given tests root (tests_root/.micropytest.json), if present.
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


def store_lastrun(tests_root, test_durations):
    """
    Write out test durations to tests_root/.micropytest.json.
    """
    data = {
        "_comment": "This file is optional: it stores data about the last run of tests for time estimates.",
        "micropytest_version": __version__,
        "test_durations": test_durations
    }
    p = Path(tests_root) / CONFIG_FILE
    try:
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


async def run_test_async(fn, ctx):
    if inspect.iscoroutinefunction(fn):
        if len(inspect.signature(fn).parameters) == 0:
            await fn()
        else:
            await fn(ctx)
    else:
        if len(inspect.signature(fn).parameters) == 0:
            fn()
        else:
            fn(ctx)


@dataclass
class TestStats:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    warnings: int = 0
    errors: int = 0
    total_time: float = 0.0

    def update(self, outcome):
        """Update counters based on test outcome."""
        status = outcome["status"]
        logs = outcome["logs"]
        if status == "pass":
            self.passed += 1
        elif status == "fail":
            self.failed += 1
        elif status == "skip":
            self.skipped += 1
        self.warnings += sum(1 for lvl, _ in logs if lvl == "WARNING")
        self.errors += sum(1 for lvl, _ in logs if (lvl == "ERROR" or lvl == "CRITICAL"))
        self.total_time += outcome["duration_s"]
        return self

    @staticmethod
    def from_results(test_results):
        stats = TestStats()
        for outcome in test_results:
            stats.update(outcome)
        return stats


async def run_tests(
    tests_path,
    show_estimates=False,
    context_class=TestContext,
    context_kwargs={},
    test_filter=None,
    tag_filter=None,
    exclude_tags=None,
    show_progress=True,
):
    """
    Discover tests and run them.

    The core function that:
      1) Discovers test_*.py
      2) For each test function test_*,
         - optionally injects a TestContext (or a user-provided subclass)
         - times the test
         - logs pass/fail/skip
      3) Updates .micropytest.json with durations
      4) Returns a list of test results

    :param tests_path: (str) Where to discover tests
    :param show_estimates: (bool) Whether to show time estimates
    :param context_class: (type) A class to instantiate as the test context
    :param context_kwargs: (dict) Keyword arguments to pass to the context class
    :param test_filter: (str) Optional filter to run only tests matching this pattern
    :param tag_filter: (str or list) Optional tag(s) to filter tests by
    :param exclude_tags: (str or list) Optional tag(s) to exclude tests by
    :param show_progress: (bool) Whether to show a progress bar during test execution
    """
    test_funcs = discover_tests(tests_path, test_filter, tag_filter, exclude_tags)
    test_results = await run_discovered_tests(
        tests_path, test_funcs, show_estimates, show_progress, context_class, context_kwargs
    )
    return test_results


async def run_discovered_tests(
    tests_path,
    test_funcs,
    show_estimates=False,
    show_progress=True,
    context_class=TestContext,
    context_kwargs={},
):
    """Run the given set of tests that were discovered in a previous step."""

    # Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Load known durations
    test_durations = load_lastrun(tests_path).get("test_durations", {})

    total_tests = len(test_funcs)
    test_results = []

    # Possibly show total estimate
    _show_total_estimate(show_estimates, total_tests, test_funcs, test_durations, root_logger)

    # Initialize progress bar if requested
    progress, task_id = _initialize_progress_bar(show_progress, total_tests, root_logger)

    # Initialize counters for statistics
    counts = TestStats()

    try:
        # Run tests with progress updates
        for i, (fpath, tname, fn, tags) in enumerate(test_funcs):
            # Create a context of the user-specified type
            ctx = context_class(**context_kwargs)

            # attach a log handler for this test
            test_handler = GlobalContextLogHandler(ctx, formatter=SimpleLogFormatter(use_colors=False))
            root_logger.addHandler(test_handler)

            key = f"{fpath}::{tname}"
            _show_estimate(show_estimates, test_durations, key, root_logger)

            outcome = await run_test_collect_outcome(fpath, tname, fn, tags, ctx, root_logger)
            counts.update(outcome)

            test_durations[key] = outcome["duration_s"]
            test_results.append(outcome)
            root_logger.removeHandler(test_handler)

            # Add tags to the log output if present
            if tags:
                tag_str = ", ".join(sorted(tags))
                root_logger.info(f"Tags: {tag_str}")

            # Update progress with new statistics
            _update_progress_bar(progress, task_id, i, total_tests, root_logger, counts)

    finally:
        _finalize_progress_bar(progress)

    # Print final summary
    root_logger.info(f"Tests completed: {counts.passed}/{total_tests} passed, {counts.skipped} skipped.")

    # Write updated durations
    store_lastrun(tests_path, test_durations)
    return test_results


async def run_test_collect_outcome(fpath, tname, fn, tags, ctx, logger):
    """Try to run a single test and return its outcome."""
    
    key = f"{fpath}::{tname}"
    t0 = time.perf_counter()

    try:
        await run_test_async(fn, ctx)

        duration = time.perf_counter() - t0
        status = "pass"
        duration_str = ''
        if duration > TIME_REPORT_CUTOFF:
            duration_str = f" ({duration:.2g} seconds)"
        logger.info(f"FINISHED PASS: {key}{duration_str}")

    except SkipTest as e:
        duration = time.perf_counter() - t0
        status = "skip"
        logger.info(f"SKIPPED: {key} ({duration:.3f}s) - {e}")

    except Exception:
        duration = time.perf_counter() - t0
        status = "fail"
        logger.error(f"FINISHED FAIL: {key} ({duration:.3f}s)\n{traceback.format_exc()}")

    outcome = {
        "file": fpath,
        "test": tname,
        "status": status,
        "logs": ctx.log_records,
        "artifacts": ctx.artifacts,
        "duration_s": duration,
        "tags": list(tags)
    }
    return outcome


def _show_total_estimate(show_estimates, total_tests, test_funcs, test_durations, logger):
    if show_estimates and total_tests > 0:
        sum_known = 0.0
        for (fpath, tname, _, _) in test_funcs:
            key = f"{fpath}::{tname}"
            sum_known += test_durations.get(key, 0.0)
        if sum_known > 0:
            logger.info(
                f"Estimated total time: ~ {sum_known:.2g} seconds for {total_tests} tests"
            )


def _show_estimate(show_estimates, test_durations, key, logger):
    if show_estimates:
        est_str = ''
        known_dur = test_durations.get(key, 0.0)
        if known_dur > TIME_REPORT_CUTOFF:
            est_str = f" (estimated ~ {known_dur:.2g} seconds)"
        logger.info(f"STARTING: {key}{est_str}")


def _initialize_progress_bar(show_progress, total_tests, logger):
    progress = None
    task_id = None
    
    if show_progress:
        try:
            from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn
            from rich.progress import TimeElapsedColumn, TimeRemainingColumn
            
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(complete_style="green", finished_style="green", pulse_style="yellow", bar_width=None),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("{task.fields[stats]}"),
                expand=False
            )
            
            task_id = progress.add_task(
                "[cyan]Running tests...", 
                total=total_tests,
                stats="[green]  0✓[/green] [red]  0✗[/red] [magenta]  0→[/magenta] [yellow]  0⚠[/yellow] "
            )
            progress.start()
        except ImportError:
            logger.warning("Rich library not installed. Progress bar not available.")
        except Exception as e:
            logger.warning(f"Failed to initialize progress bar: {e}")
            progress = None
            task_id = None
    return progress, task_id


def _update_progress_bar(progress, task_id, i, total_tests, logger, counts):
    if progress and task_id is not None:
        try:
            description = '[green]Running tests...'
            stats = (
                f"[green]{counts.passed:3d}✓[/green] [red]{counts.failed:3d}✗[/red] "
                f"[magenta]{counts.skipped:3d}→[/magenta] [yellow]{counts.warnings:3d}⚠[/yellow] "
            )
            progress.update(task_id, advance=1, description=description, stats=stats)
        except Exception as e:
            # If updating the progress bar fails, log it but continue
            logger.debug(f"Failed to update progress bar: {e}")
        
        # Add a small delay to make the status visible
        if i < total_tests - 1:  # Not the last test
            time.sleep(0.1)


def _finalize_progress_bar(progress):
    # Ensure progress bar is stopped
    if progress:
        try:
            progress.stop()
        except Exception:
            pass
