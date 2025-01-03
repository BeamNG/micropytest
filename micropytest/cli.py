import os
import sys
import argparse
import logging
from collections import Counter

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

from . import __version__
from .core import (
    create_live_console_handler,
    SimpleLogFormatter,
    run_tests
)

def console_main():
    parser = argparse.ArgumentParser(
        prog="micropytest",
        description="micropytest - 'pytest but smaller, simpler, and smarter'."
    )
    parser.add_argument("--version", action="store_true",
                        help="Show micropytest version and exit.")

    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("-v", "--verbose", action="store_true", help="More logs.")
    parser.add_argument("-q", "--quiet",   action="store_true", help="Quiet mode.")
    args = parser.parse_args()

    # If --version is requested, just print it and exit
    if args.version:
        print(__version__)
        sys.exit(0)

    if args.verbose and args.quiet:
        parser.error("Cannot use both -v and -q together.")

    # root logger
    root_logger = logging.getLogger()

    # Create our formatter and handler
    live_format = SimpleLogFormatter()
    live_handler = create_live_console_handler(formatter=live_format)

    # If quiet => set level above CRITICAL (so no logs) and skip attaching the handler
    if args.quiet:
        root_logger.setLevel(logging.CRITICAL + 1)
    elif args.verbose:
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(live_handler)
    else:
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(live_handler)

    # Only show estimates if not quiet
    show_estimates = not args.quiet

    # Log version only if not quiet (or if you want to keep it, you can remove the condition)
    if not args.quiet:
        logging.info("micropytest version: {}".format(__version__))

    # Run tests
    test_results = run_tests(tests_path=args.path, show_estimates=show_estimates)

    # Count outcomes
    passed = sum(r["status"] == "pass" for r in test_results)
    skipped = sum(r["status"] == "skip" for r in test_results)
    total = len(test_results)
    failed = total - (passed + skipped)

    # Tally warnings/errors from logs
    log_counter = Counter()
    for outcome in test_results:
        for (lvl, msg) in outcome["logs"]:
            log_counter[lvl] += 1
    warnings_count = log_counter["WARNING"]
    errors_count   = log_counter["ERROR"] + log_counter["CRITICAL"]

    # If not quiet, we print the fancy ASCII summary and per-test lines
    if not args.quiet:
        print(r"""
            _____    _______        _
        |  __ \  |__   __|      | |
    _   _| |__) |   _| | ___  ___| |_
    | | | |  ___/ | | | |/ _ \/ __| __|
    | |_| | |   | |_| | |  __/\__ \ |_
    | ._,_|_|    \__, |_|\___||___/\__|
    | |           __/ |
    |_|          |___/           Report
        """)

        # Show each test's line
        for outcome in test_results:
            status = outcome["status"]
            if status == "pass":
                color_status = Fore.GREEN + "PASS"
            elif status == "skip":
                color_status = Fore.MAGENTA + "SKIP"
            else:
                color_status = Fore.RED + "FAIL"

            duration_s = outcome["duration_s"]
            testkey = "{}::{}".format(
                os.path.basename(outcome["file"]),
                outcome["test"]
            )

            print("{:50s} - {}{} in {:.3f}s".format(
                testkey, color_status, Style.RESET_ALL, duration_s)
            )

            if args.verbose:
                for (lvl, msg) in outcome["logs"]:
                    print("  {}".format(msg))
                if outcome["artifacts"]:
                    print("  Artifacts: {}".format(outcome["artifacts"]))
                print()

    # Build the final summary line for both quiet and non-quiet modes
    def plural(count, singular, plural_form):
        return singular if count == 1 else plural_form

    total_str = "{} {}".format(total, plural(total, "test", "tests"))

    summary_chunks = []
    if passed > 0:
        summary_chunks.append("{}{} passed{}".format(Fore.GREEN, passed, Style.RESET_ALL))
    if skipped > 0:
        summary_chunks.append("{}{} skipped{}".format(Fore.MAGENTA, skipped, Style.RESET_ALL))
    if failed > 0:
        summary_chunks.append("{}{} failed{}".format(Fore.RED, failed, Style.RESET_ALL))
    if warnings_count > 0:
        summary_chunks.append("{}{} warning{}{}".format(
            Fore.YELLOW, warnings_count,
            "" if warnings_count == 1 else "s",
            Style.RESET_ALL
        ))
    if errors_count > 0:
        summary_chunks.append("{}{} error{}{}".format(
            Fore.RED, errors_count,
            "" if errors_count == 1 else "s",
            Style.RESET_ALL
        ))

    # Total time across all tests
    total_time = sum(o["duration_s"] for o in test_results)
    if total_time > 0.01:
        summary_chunks.append("{}took {:.2f}s{}".format(Fore.CYAN, total_time, Style.RESET_ALL))

    if not summary_chunks:
        summary_chunks.append("{}no tests run{}".format(Fore.CYAN, Style.RESET_ALL))

    # Final summary line
    if args.quiet:
        print("microPyTest v{}: {} => {}".format(__version__, total_str, ", ".join(summary_chunks)))
    else:
        print("Summary: {} => {}".format(total_str, ", ".join(summary_chunks)))
