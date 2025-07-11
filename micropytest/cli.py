import sys
import argparse
import logging

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from . import __version__
from .core import (
    setup_logging,
    SimpleLogFormatter,
    run_tests,
    TestStats,
    TIME_REPORT_CUTOFF,
)
from .types import TestResult


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
    parser.add_argument("--dry-run", action="store_true",
                        help='Show what tests would be run without actually running them (assumes they pass)')
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

    # Logging
    setup_logging(quiet=args.quiet, verbose=args.verbose)

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
        dry_run=args.dry_run,
    )

    # Print report and summary line
    print_report(test_results, console=console, quiet=args.quiet, verbose=args.verbose)
    stats = print_summary(test_results, quiet=args.quiet, console=console)

    # Exit with error code 1 if any tests failed or any error occurred
    if stats.failed > 0 or stats.errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)


def print_report(test_results: list[TestResult], console=None, quiet=False, verbose=False):
    """Print detailed report."""
    if console is None:
        console = Console()
    formatter = SimpleLogFormatter() if verbose else None

    # If not quiet, we print the fancy ASCII summary and per-test lines
    if not quiet and len(test_results) > 1:
        console.print(Panel.fit(r"""
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
        for result in test_results:
            status = result.status
            duration_s = result.duration_s
            test_key = result.test.short_key_with_args

            duration_str = f" in {duration_s:.2g} seconds" if duration_s > TIME_REPORT_CUTOFF else ""
            
            # Use Rich's styling with fixed-width formatting for the status
            if status == "pass":
                status_display = "[green]PASS[/green]"
            elif status == "skip":
                status_display = "[magenta]SKIP[/magenta]"
            else:
                status_display = "[red]FAIL[/red]"
            
            # Ensure consistent width by using a fixed-width format string
            console.print(f"{test_key:50s} - {status_display:20}{duration_str}", highlight=False)

            if verbose:
                for record in result.logs:
                    console.print(f"  {formatter.format(record)}")
                if result.artifacts:
                    console.print(f"  Artifacts: {result.artifacts}")
                console.print()


def print_summary(test_results: list[TestResult], quiet=False, console=None) -> TestStats:
    """Print summary line and return stats."""
    if console is None:
        console = Console()

    stats = TestStats.from_results(test_results)

    # Build the final summary with Rich formatting
    def plural(count, singular, plural_form=None):
        if plural_form is None:
            plural_form = singular + "s"
        return singular if count == 1 else plural_form

    total = len(test_results)
    total_str = f"{total} {plural(total, 'test')}"

    # Create a Rich Text object for the summary
    summary = Text()
    summary.append("Summary: ")
    summary.append(f"{total_str} => ")

    parts = []
    if stats.passed > 0:
        parts.append(Text(f"{stats.passed} passed", style="green"))
    if stats.skipped > 0:
        parts.append(Text(f"{stats.skipped} skipped", style="magenta"))
    if stats.failed > 0:
        parts.append(Text(f"{stats.failed} failed", style="red"))
    if stats.warnings > 0:
        parts.append(Text(f"{stats.warnings} {plural(stats.warnings, 'warning')}", style="yellow"))
    if stats.errors > 0:
        parts.append(Text(f"{stats.errors} {plural(stats.errors, 'error')}", style="red"))
    
    # Add timing information
    if stats.total_time > TIME_REPORT_CUTOFF:
        parts.append(Text(f"took {stats.total_time:.2g} seconds", style="cyan"))
    
    if not parts:
        parts.append(Text("no tests run", style="cyan"))

    # Join the parts with commas
    summary.append(Text(", ").join(parts))

    # Print the final summary
    if quiet:
        prefix = Text(f"microPyTest v{__version__}: ")
        console.print(prefix + summary)
    else:
        console.print(summary)

    return stats
