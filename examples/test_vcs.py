# test_vcs.py
import os
from micropytest.vcs_helper import VCSHelper, VCSError
from micropytest.decorators import tag
from dataclasses import asdict


@tag('vcs', 'git', 'integration')
def test_vcs_helper_git(ctx):
    """Run a test that dumps VCS information about this file."""
    vcs_helper_function(ctx, __file__)


@tag('vcs', 'svn', 'integration')
def test_vcs_helper_svn(ctx):
    """Run a test that dumps VCS information about a dummy SVN file."""
    if True:
        ctx.skip_test("Skipping test_vcs_helper_svn.")
    svn_file = "svn_repo/hello.txt"
    vcs_helper_function(ctx, svn_file)


def vcs_helper_function(ctx, file_path):
    # Get the path of the provided file
    current_file = os.path.abspath(file_path)

    # You could use custom VCS by passing the handlers argument to the constructor to supply a list of
    # VCSInterface implementations
    vcs_helper = VCSHelper()

    ctx.info(f"VCS Test")
    ctx.info(f"=============")
    ctx.info(f"Testing file: {current_file}")

    # Detect VCS
    vcs_type = vcs_helper.detect_vcs(os.path.dirname(current_file))
    ctx.info(f"Version Control System: {vcs_type or 'None detected'}")

    # Test the VCS detection
    assert vcs_type is not None, "VCS type should be detected"
    vcs = vcs_helper.get_vcs_handler(os.path.dirname(current_file))
    assert vcs is not None, "VCS should be detected"

    # Get file creator info
    ctx.info("File Creator Information:")
    try:
        creator = vcs.get_file_creator(current_file)
        ctx.info(f"  Created by: {creator.name}")
        ctx.info(f"  Email: {creator.email}")
        ctx.info(f"  Creation date: {creator.date}")
        # Store creator info as an artifact
        ctx.add_artifact("file_creator", creator)

        # Add an assertion to verify creator info
        assert creator.name, "Creator name should not be empty"
    except VCSError as e:
        ctx.error(f"  {e}")

    # Get last modifier info
    ctx.info("Last Modifier Information:")

    try:
        last_modifier = vcs.get_last_modifier(current_file)
        ctx.info(f"  Last modified by: {last_modifier.name}")
        ctx.info(f"  Email: {last_modifier.email}")
        ctx.info(f"  Last modified on: {last_modifier.date}")
        # Store last modifier info as an artifact
        ctx.add_artifact("last_modifier", last_modifier)
    except VCSError as e:
        ctx.error(f"  {e}")

    # Get info about this function's code
    ctx.info("Current Function Information:")
    # Find the approximate line number of this function
    try:
        with open(current_file, 'r') as f:
            lines = f.readlines()

        function_line = 0
        for i, line in enumerate(lines, 1):
            if "def test_vcs_helper_git" in line:
                function_line = i
                break

        if function_line > 0:
            ctx.info(f"  Function starts at line: {function_line}")

            # Get author of this function
            try:
                line_author = vcs.get_line_author(current_file, function_line)
                ctx.info(f"  Function written by: {line_author.name}")
                ctx.info(f"  Email: {line_author.email}")
                ctx.info(f"  Written on: {line_author.date}")

                # Get commit message
                commit_msg = vcs.get_line_commit_message(current_file, function_line)
                ctx.info(f"  Commit message: {commit_msg}")
                # Store function author info as an artifact
                ctx.add_artifact("function_author", {
                    "author": asdict(line_author),
                    "commit_message": commit_msg
                })
            except VCSError as e:
                ctx.error(f"  {e}")
        else:
            ctx.error("  Could not locate function line number")
    except Exception as e:
        ctx.error(f"  Error analyzing function: {str(e)}")

    # Get file history
    ctx.info("File History (last 5 changes):")
    try:
        history = vcs.get_file_history(current_file, 5)
        for i, entry in enumerate(history, 1):
            entry_info = f"  {i}. "
            entry_info += f"{entry.revision} - {entry.author.name} ({entry.author.date})"
            ctx.info(entry_info)
            ctx.info(f"     {entry.message}")
        # Store history as an artifact
        ctx.add_artifact("file_history", [asdict(h) for h in history])
    except VCSError as e:
        ctx.error(f"  {e}")

    # Test for specific line ranges
    ctx.info("Line-by-Line Analysis:")

    # Sample a few lines from the file
    try:
        with open(current_file, 'r') as f:
            lines = f.readlines()

        # Sample lines at different parts of the file
        sample_lines = [
            1,  # First line
            min(20, len(lines)),  # Around line 20
            min(len(lines) // 2, len(lines)),  # Middle of file
            len(lines)  # Last line
        ]

        line_analysis = {}
        for line_num in sample_lines:
            ctx.info(f"\n  Line {line_num}: {lines[line_num-1].strip()}")

            try:
                line_author = vcs.get_line_author(current_file, line_num)
                ctx.info(f"    Author: {line_author.name}")
                ctx.info(f"    Last modified: {line_author.date}")
                line_analysis[line_num] = asdict(line_author)
            except VCSError as e:
                ctx.error(f"    {e}")

        # Store line analysis as an artifact
        ctx.add_artifact("line_analysis", line_analysis)
    except Exception as e:
        ctx.error(f"  Error in line-by-line analysis: {str(e)}")
