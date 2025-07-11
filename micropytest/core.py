import asyncio
import logging
import sys
import os
import json
import traceback
import inspect
import time
from os import PathLike
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import importlib.util
from .parameters import Args
from .progress import TestProgress
from .stats import TestStats
from .types import Test, TestAttributes, TestResult
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
        self.log_records: list[logging.LogRecord] = []
        self.log = logging.getLogger()
        self.artifacts: dict[str, Any] = {}

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

    def add_artifact(self, key: str, value: Any):
        self.artifacts[key] = value

    def add_log(self, record: logging.LogRecord):
        self.log_records.append(record)

    def add_artifact_file(self, key: str, path: PathLike):
        with open(path, "rb") as f:
            self.add_artifact(key, f.read())

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
        self.ctx.add_log(record)


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

        time = datetime.fromtimestamp(record.created, tz=timezone.utc)
        time_local = time.astimezone()
        tstamp = time_local.strftime("%H:%M:%S")
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


def discover_tests(discover_ctx, tests_path, test_filter=None, tag_filter=None, exclude_tags=None) -> list[Test]:
    """Discover all test functions in the given directory and subdirectories."""
    test_files = find_test_files(tests_path)
    tests = find_test_functions(discover_ctx, test_files, test_filter, tag_filter, exclude_tags)
    return tests


def find_test_functions(discover_ctx, test_files, test_filter=None, tag_filter=None, exclude_tags=None) -> list[Test]:
    """Find all test functions in the given test files."""

    tag_set = tags_to_set(tag_filter)
    exclude_tag_set = tags_to_set(exclude_tags)

    tests = []
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
                        if hasattr(fn, '_argument_generator'):
                            if len(inspect.signature(fn._argument_generator).parameters) == 0:
                                args_list = fn._argument_generator()
                            else:
                                discover_ctx.test = TestAttributes(file=f, name=attr, function=fn, tags=tags)
                                args_list = fn._argument_generator(discover_ctx)
                            if len(args_list) == 0:
                                pass  # ignore this test because no arguments were generated
                            else:
                                for args in args_list:
                                    if not isinstance(args, Args):
                                        f = fn.__name__
                                        raise ValueError(f"Argument generator of '{f}' returned a non-Args object")
                                    tests.append(Test(file=f, name=attr, function=fn, tags=tags, args=args))
                        else:
                            tests.append(Test(file=f, name=attr, function=fn, tags=tags, args=Args()))
    return tests


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


def run_test_function(fn, ctx, args: Args):
    if inspect.iscoroutinefunction(fn):
        if len(inspect.signature(fn).parameters) == 0:
            r = asyncio.run(fn(*args.args, **args.kwargs))
        else:
            r = asyncio.run(fn(ctx, *args.args, **args.kwargs))
    else:
        if len(inspect.signature(fn).parameters) == 0:
            r = fn(*args.args, **args.kwargs)
        else:
            r = fn(ctx, *args.args, **args.kwargs)
    return r


def run_tests(
    tests_path,
    show_estimates=False,
    context_class=TestContext,
    context_kwargs={},
    test_filter=None,
    tag_filter=None,
    exclude_tags=None,
    show_progress=True,
    dry_run=False,
) -> list[TestResult]:
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
    discover_ctx = context_class(**context_kwargs)
    tests = discover_tests(discover_ctx, tests_path, test_filter, tag_filter, exclude_tags)
    test_results = run_discovered_tests(
        tests_path, tests, show_estimates, show_progress, context_class, context_kwargs, dry_run
    )
    return test_results


def get_logger():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    return root_logger


def run_discovered_tests(
    tests_path,
    tests: list[Test],
    show_estimates=False,
    show_progress=True,
    context_class=TestContext,
    context_kwargs={},
    dry_run=False,
) -> list[TestResult]:
    """Run the given set of tests that were discovered in a previous step."""

    # Logger
    root_logger = get_logger()

    # Load known durations
    test_durations = load_lastrun(tests_path).get("test_durations", {})

    total_tests = len(tests)
    test_results = []

    # Possibly show total estimate
    _show_total_estimate(show_estimates, total_tests, tests, test_durations, root_logger)

    # Initialize counters for statistics
    counts = TestStats()

    with TestProgress(show_progress, total_tests) as progress:
        # Run tests with progress updates
        for test in tests:
            # Create a context of the user-specified type
            ctx = context_class(**context_kwargs)

            # attach a log handler for this test
            test_handler = GlobalContextLogHandler(ctx, formatter=SimpleLogFormatter(use_colors=False))
            root_logger.addHandler(test_handler)

            _show_estimate(show_estimates, test_durations, test.key, root_logger)

            result = run_test_collect_result(test, ctx, root_logger, dry_run)
            counts.update(result)

            test_durations[test.key] = result.duration_s
            test_results.append(result)
            root_logger.removeHandler(test_handler)

            # Add tags to the log output if present
            if test.tags:
                tag_str = ", ".join(sorted(test.tags))
                root_logger.info(f"Tags: {tag_str}")

            # Update progress bar with new statistics
            progress.update(counts)

    # Print final summary
    root_logger.info(f"Tests completed: {counts.passed}/{total_tests} passed, {counts.skipped} skipped.")

    # Write updated durations
    if not dry_run:
        store_lastrun(tests_path, test_durations)
    return test_results


def run_single_test(test: Test, ctx: TestContext) -> TestResult:
    """Run a single test and return its result."""
    root_logger = get_logger()
    test_handler = GlobalContextLogHandler(ctx, formatter=SimpleLogFormatter(use_colors=False))
    root_logger.addHandler(test_handler)
    result = run_test_collect_result(test, ctx, root_logger, dry_run=False)
    root_logger.removeHandler(test_handler)
    return result


def run_test_collect_result(test: Test, ctx, logger, dry_run) -> TestResult:
    """Try to run a single test and return its result."""

    key = test.key
    start_time = datetime.now(timezone.utc)
    exception = None
    return_value = None
    t0 = time.perf_counter()

    try:
        if not dry_run:
            return_value = run_test_function(test.function, ctx, test.args)

        duration = time.perf_counter() - t0
        status = "pass"
        duration_str = ''
        if duration > TIME_REPORT_CUTOFF:
            duration_str = f" ({duration:.2g} seconds)"
        logger.info(f"FINISHED PASS: {key}{duration_str}")

    except SkipTest as e:
        duration = time.perf_counter() - t0
        status = "skip"
        exception = e
        logger.info(f"SKIPPED: {key} ({duration:.3f}s) - {e}")

    except Exception as e:
        duration = time.perf_counter() - t0
        status = "fail"
        exception = e
        logger.error(f"FINISHED FAIL: {key} ({duration:.3f}s)\n{format_exception(e)}")

    return TestResult(
        test=test,
        status=status,
        logs=ctx.log_records,
        artifacts=ctx.artifacts,
        exception=exception,
        return_value=return_value,
        start_time=start_time,
        duration_s=duration,
    )


def _show_total_estimate(show_estimates, total_tests, tests: list[Test], test_durations, logger):
    if show_estimates and total_tests > 0:
        sum_known = 0.0
        for test in tests:
            sum_known += test_durations.get(test.key, 0.0)
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


def format_exception(exception: Exception) -> str:
    """Format exception using '{type}: {message}\\n{traceback}'."""
    tb_str = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    return f"{type(exception).__name__}: {exception}\n{tb_str}"


def setup_logging(quiet=False, verbose=False):
    # Create our formatter and handler
    root_logger = logging.getLogger()
    live_format = SimpleLogFormatter()
    live_handler = create_live_console_handler(formatter=live_format)

    # If quiet => set level above CRITICAL (so no logs)
    if quiet:
        root_logger.setLevel(logging.CRITICAL + 1)
    else:
        level = logging.DEBUG if verbose else logging.INFO
        root_logger.setLevel(level)
        live_handler.setLevel(level)
        root_logger.addHandler(live_handler)
