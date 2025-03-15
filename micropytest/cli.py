import os
import sys
import argparse
import logging
from collections import Counter

# Import Rich components instead
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from . import __version__
from .core import (
    create_live_console_handler,
    SimpleLogFormatter,
    run_tests
)

def console_main():
    # Create a Rich console for output
    console = Console()
    
    parser = argparse.ArgumentParser(
        prog="micropytest",
        description="micropytest - 'pytest but smaller, simpler, and smarter'."
    )
    parser.add_argument("--version", action="store_true",
                        help="Show micropytest version and exit.")

    parser.add_argument("--path", "-p", default=".", 
                        help="Path to the directory containing tests (default: current directory)")
    parser.add_argument("-v", "--verbose", action="store_true", help="More logs.")
    parser.add_argument("-q", "--quiet",   action="store_true", help="Quiet mode with progress bar.")
    parser.add_argument("--no-progress", action="store_true",
                       help="Disable progress bar.")
    parser.add_argument("--test", dest='test',
                        help='Run a specific test by name')
    
    # Tag filtering
    parser.add_argument('--tag', action='append', dest='tags',
                        help='Run only tests with the specified tag (can be used multiple times)')

    # Tag exclusion
    parser.add_argument('--exclude-tag', action='append', dest='exclude_tags',
                        help='Exclude tests with the specified tag (can be used multiple times)')
    
    # Parse only the known arguments
    args, _ = parser.parse_known_args()
    
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

    # If quiet => set level above CRITICAL (so no logs)
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
    
    # Determine whether to show progress bar
    # Show by default, unless explicitly disabled with --no-progress
    show_progress = not args.no_progress
    
    # Log version only if not quiet (or if you want to keep it, you can remove the condition)
    if not args.quiet:
        logging.info("micropytest version: {}".format(__version__))

    # Run tests with progress bar
    test_results = run_tests(
        tests_path=args.path, 
        show_estimates=show_estimates,
        test_filter=args.test,
        tag_filter=args.tags,
        exclude_tags=args.exclude_tags,
        show_progress=show_progress,
        quiet_mode=args.quiet,
    )

    # Count outcomes
    passed = sum(r["status"] == "pass" for r in test_results)
    skipped = sum(r["status"] == "skip" for r in test_results)
    total = len(test_results)
    failed = total - (passed + skipped)

    # Calculate total time across all tests
    try:
        total_time = sum(r["duration_s"] for r in test_results)
    except (KeyError, TypeError):
        # Fallback if there's an issue with the calculation
        total_time = 0
        for r in test_results:
            if isinstance(r, dict):
                total_time += r["duration_s"]

    # Tally warnings/errors from logs
    log_counter = Counter()
    for outcome in test_results:
        for (lvl, msg) in outcome["logs"]:
            log_counter[lvl] += 1
    warnings_count = log_counter["WARNING"]
    errors_count   = log_counter["ERROR"] + log_counter["CRITICAL"]

    # If not quiet, we print the fancy ASCII summary and per-test lines
    if not args.quiet and len(test_results) > 1:
        console.print(Panel.fit("""
        _____    _______        _
       |  __ \  |__   __|      | |
  _   _| |__) |   _| | ___  ___| |_
 | | | |  ___/ | | | |/ _ \/ __| __|
 | |_| | |   | |_| | |  __/\__ \ |_
 | ._,_|_|    \__, |_|\___||___/\__|
 | |           __/ |
 |_|          |___/           Report
 """, title="microPyTest", border_style="cyan"))

        # Show each test's line with Rich formatting
        for outcome in test_results:
            status = outcome["status"]
            duration_s = outcome["duration_s"]
            testkey = "{}::{}".format(
                os.path.basename(outcome["file"]),
                outcome["test"]
            )

            duration_str = ""
            if duration_s > 0.01:
                duration_str = f" in {duration_s:.2g} seconds"
            
            # Use Rich's styling with fixed-width formatting for the status
            if status == "pass":
                status_display = "[green]PASS[/green]"
            elif status == "skip":
                status_display = "[magenta]SKIP[/magenta]"
            else:
                status_display = "[red]FAIL[/red]"
            
            # Ensure consistent width by using a fixed-width format string
            console.print(f"{testkey:50s} - {status_display:20}{duration_str}")

            if args.verbose:
                for (lvl, msg) in outcome["logs"]:
                    console.print(f"  {msg}")
                if outcome["artifacts"]:
                    console.print(f"  Artifacts: {outcome['artifacts']}")
                console.print()

    # Build the final summary with Rich formatting
    def plural(count, singular, plural_form):
        return singular if count == 1 else plural_form

    total_str = f"{total} {plural(total, 'test', 'tests')}"

    # Create a Rich Text object for the summary
    summary = Text()
    summary.append("Summary: ")
    summary.append(f"{total_str} => ")
    
    parts = []
    if passed > 0:
        parts.append(Text(f"{passed} passed", style="green"))
    if skipped > 0:
        parts.append(Text(f"{skipped} skipped", style="magenta"))
    if failed > 0:
        parts.append(Text(f"{failed} failed", style="red"))
    if warnings_count > 0:
        parts.append(Text(f"{warnings_count} warning{'' if warnings_count == 1 else 's'}", style="yellow"))
    if errors_count > 0:
        parts.append(Text(f"{errors_count} error{'' if errors_count == 1 else 's'}", style="red"))
    
    # Add timing information
    if total_time > 0.01:
        parts.append(Text(f"took {total_time:.2g} seconds", style="cyan"))
    
    if not parts:
        parts.append(Text("no tests run", style="cyan"))
    
    # Join the parts with commas
    for i, part in enumerate(parts):
        summary.append(part)
        if i < len(parts) - 1:
            summary.append(", ")
    
    # Print the final summary
    if args.quiet:
        prefix = Text(f"microPyTest v{__version__}: {total_str} => ")
        console.print(prefix + summary)
    else:
        console.print(summary)
