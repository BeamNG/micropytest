import logging
import sys
import os
import json
import traceback
import inspect
import time
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


async def run_tests(tests_path,
              show_estimates=False,
              context_class=TestContext,
              context_kwargs={},
              test_filter=None,
              tag_filter=None,
              exclude_tags=None,
              show_progress=True,
              quiet_mode=False,
              _is_nested_call=False):
    """
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
    :param quiet_mode: (bool) Whether the runner is in quiet mode
    :param _is_nested_call: (bool) Internal parameter to detect recursive calls
    """
    # Disable progress bar for nested calls to prevent conflicts
    if _is_nested_call:
        show_progress = False
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # or caller sets this

    # Load known durations
    lastrun_data = load_lastrun(tests_path)
    test_durations = lastrun_data.get("test_durations", {})

    # Convert tag_filter to a set for easier comparison
    tag_set = set()
    if tag_filter:
        if isinstance(tag_filter, str):
            tag_set = {tag_filter}
        else:
            tag_set = set(tag_filter)
            
    # Convert exclude_tags to a set
    exclude_tag_set = set()
    if exclude_tags:
        if isinstance(exclude_tags, str):
            exclude_tag_set = {exclude_tags}
        else:
            exclude_tag_set = set(exclude_tags)

    # Discover test callables
    test_files = find_test_files(tests_path)
    test_funcs = []
    for f in test_files:
        try:
            mod = load_test_module_by_path(f)
        except Exception:
            root_logger.error("Error importing {}:\n{}".format(f, traceback.format_exc()))
            continue

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

    total_tests = len(test_funcs)
    test_results = []
    passed_count = 0
    skipped_count = 0

    # Possibly show total estimate
    if show_estimates and total_tests > 0:
        sum_known = 0.0
        for (fpath, tname, _, _) in test_funcs:
            key = "{}::{}".format(fpath, tname)
            sum_known += test_durations.get(key, 0.0)
        if sum_known > 0:
            root_logger.info(
                f"Estimated total time: ~ {sum_known:.2g} seconds for {total_tests} tests"
            )

    # Initialize progress bar if requested
    progress = None
    task_id = None
    
    if show_progress and not _is_nested_call:
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
            root_logger.warning("Rich library not installed. Progress bar not available.")
        except Exception as e:
            root_logger.warning(f"Failed to initialize progress bar: {e}")
            progress = None
            task_id = None

    # Initialize counters for statistics
    pass_count = 0
    fail_count = 0
    skip_count = 0
    warning_count = 0
    
    try:
        # Run tests with progress updates
        for i, (fpath, tname, fn, tags) in enumerate(test_funcs):
            # Create a context of the user-specified type
            ctx = context_class(**context_kwargs)

            # attach a log handler for this test
            test_handler = GlobalContextLogHandler(ctx, formatter=SimpleLogFormatter(use_colors=False))
            root_logger.addHandler(test_handler)

            key = "{}::{}".format(fpath, tname)
            known_dur = test_durations.get(key, 0.0)

            if show_estimates:
                est_str = ''
                if known_dur > TIME_REPORT_CUTOFF:
                    est_str = f" (estimated ~ {known_dur:.2g} seconds)"
                root_logger.info(f"STARTING: {key}{est_str}")

            sig = inspect.signature(fn)
            expects_ctx = len(sig.parameters) > 0

            t0 = time.perf_counter()
            outcome = {
                "file": fpath,
                "test": tname,
                "status": None,
                "logs": ctx.log_records,
                "artifacts": ctx.artifacts,
                "duration_s": 0.0,
                "tags": list(tags)
            }

            try:
                if expects_ctx:
                    await run_test_async(fn, ctx)
                else:
                    await run_test_async(fn, ctx)

                duration = time.perf_counter() - t0
                outcome["duration_s"] = duration
                passed_count += 1
                outcome["status"] = "pass"
                duration_str = ''
                if duration > TIME_REPORT_CUTOFF:
                    duration_str = f" ({duration:.2g} seconds)"
                root_logger.info(f"FINISHED PASS: {key}{duration_str}")

            except SkipTest as e:
                duration = time.perf_counter() - t0
                outcome["duration_s"] = duration
                outcome["status"] = "skip"
                skipped_count += 1
                # We log skip as INFO or WARNING (up to you). Here we use CYAN for a mild notice.
                root_logger.info(f"SKIPPED: {key} ({duration:.3f}s) - {e}")

            except Exception:
                duration = time.perf_counter() - t0
                outcome["duration_s"] = duration
                outcome["status"] = "fail"
                root_logger.error(f"FINISHED FAIL: {key} ({duration:.3f}s)\n{traceback.format_exc()}")

            finally:
                root_logger.removeHandler(test_handler)

            test_durations[key] = outcome["duration_s"]
            test_results.append(outcome)

            # Add tags to the log output if present
            if tags:
                tag_str = ", ".join(sorted(tags))
                root_logger.info(f"Tags: {tag_str}")

            # Update statistics
            status = outcome["status"]
            description = '[green]Running tests...'
            if status == "pass":
                pass_count += 1
            elif status == "skip":
                skip_count += 1
            else:
                fail_count += 1
            
            # After running each test, update the warning count
            warning_count_in_test = sum(1 for lvl, _ in ctx.log_records if lvl == "WARNING")
            warning_count += warning_count_in_test
            
            # Update progress with new statistics - safely
            if progress and task_id is not None:
                try:
                    stats = f"[green]{pass_count:3d}✓[/green] [red]{fail_count:3d}✗[/red] [magenta]{skip_count:3d}→[/magenta] [yellow]{warning_count:3d}⚠[/yellow] "
                    progress.update(task_id, advance=1, description=description, stats=stats)
                except Exception as e:
                    # If updating the progress bar fails, log it but continue
                    root_logger.debug(f"Failed to update progress bar: {e}")
                
                # Add a small delay to make the status visible
                if i < total_tests - 1:  # Not the last test
                    time.sleep(0.1)

    finally:
        # Ensure progress bar is stopped
        if progress:
            try:
                progress.stop()
            except Exception:
                pass

    # Print final summary
    root_logger.info(f"Tests completed: {passed_count}/{total_tests} passed, {skipped_count} skipped.")

    # Write updated durations
    store_lastrun(tests_path, test_durations)
    return test_results
