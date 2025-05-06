# test_vcs.py
import os
from shutil import rmtree, copyfile
import subprocess
import stat
from pathlib import Path
from time import sleep
from micropytest.vcs_helper import VCSHelper, VCSError, VCSInfo, VCSHistoryEntry
from micropytest.decorators import tag
from dataclasses import asdict


@tag('vcs', 'git', 'integration')
def test_vcs_helper_git(ctx):
    """Run a test that dumps VCS information about this file."""
    vcs_helper_function(ctx, __file__)


@tag('vcs', 'svn', 'integration')
def test_vcs_helper_svn(ctx):
    """Run a test that dumps VCS information about a dummy SVN file."""
    # Only run this test in CT, where subversion must be installed
    if not os.environ.get("CI"):
        ctx.skip_test("Skipping test_vcs_helper_svn.")

    with DummySVNRepo("svn_repo") as repo:
        svn_file = os.path.join(repo.working_copy_path, "hello.txt")
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

    # Get basic repo info
    repo_root = vcs.get_repo_root(file_path)
    ctx.info(f"Repository Root: {repo_root}")
    branch = vcs.get_branch(repo_root)
    ctx.info(f"Branch: {branch}")
    if vcs_type == "git":
        assert os.path.abspath(repo_root) == os.path.abspath(os.path.dirname(os.path.dirname(file_path))), "Repo path mismatch"
        ci_branch = os.environ.get("GITHUB_REF_NAME")
        if ci_branch:
            assert branch == ci_branch, "Branch mismatch"
    elif vcs_type == "svn":
        assert os.path.abspath(repo_root) == os.path.abspath(os.path.dirname(file_path)), "Repo path mismatch"
        assert branch == "trunk", "Branch mismatch"

    # Get file creator info
    ctx.info("File Creator Information:")
    try:
        creator = vcs.get_file_creator(current_file)
        assert isinstance(creator, VCSInfo)
        ctx.info(f"  Created by: {creator.name}")
        ctx.info(f"  Email: {creator.email}")
        ctx.info(f"  Creation date: {creator.date}")
        # Store creator info as an artifact
        ctx.add_artifact("file_creator", asdict(creator))

        # Add an assertion to verify creator info
        assert creator.name, "Creator name should not be empty"
    except VCSError as e:
        ctx.error(f"  {e}")

    # Get last modifier info
    ctx.info("Last Modifier Information:")

    try:
        last_modifier = vcs.get_last_modifier(current_file)
        assert isinstance(last_modifier, VCSInfo)
        ctx.info(f"  Last modified by: {last_modifier.name}")
        ctx.info(f"  Email: {last_modifier.email}")
        ctx.info(f"  Last modified on: {last_modifier.date}")
        # Store last modifier info as an artifact
        ctx.add_artifact("last_modifier", asdict(last_modifier))
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
            if "def test_vcs_helper" in line:
                function_line = i
                break

        if function_line > 0:
            ctx.info(f"  Function starts at line: {function_line}")

            # Get author of this function
            try:
                line_author = vcs.get_line_author(current_file, function_line)
                assert isinstance(line_author, VCSInfo)
                ctx.info(f"  Function written by: {line_author.name}")
                ctx.info(f"  Email: {line_author.email}")
                ctx.info(f"  Written on: {line_author.date}")

                # Get commit message
                commit_msg = vcs.get_line_commit_message(current_file, function_line)
                assert isinstance(commit_msg, str)
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
            assert isinstance(entry, VCSHistoryEntry)
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
                assert isinstance(line_author, VCSInfo)
                ctx.info(f"    Author: {line_author.name}")
                ctx.info(f"    Last modified: {line_author.date}")
                line_analysis[line_num] = asdict(line_author)
            except VCSError as e:
                ctx.error(f"    {e}")

        # Store line analysis as an artifact
        ctx.add_artifact("line_analysis", line_analysis)
    except Exception as e:
        ctx.error(f"  Error in line-by-line analysis: {str(e)}")


class DummySVNRepo:
    def __init__(self, path):
        path = os.path.abspath(path)
        self.path = path
        self.repo_path = os.path.join(path, 'repo')
        self.working_copy_path = os.path.join(path, 'working_copy')
        self.url = Path(self.repo_path).absolute().as_uri()

    def setup(self):
        if os.path.exists(self.path):
            raise RuntimeError(f"Path {self.path} already exists")

        try:
            os.makedirs(self.repo_path, exist_ok=True)

            # Create repository
            subprocess.check_call(['svnadmin', 'create', self.repo_path])

            # Create an initial layout for the repo
            # We'll create trunk/ with a file inside
            layout_dir = os.path.join(self.path, 'import_layout')
            os.makedirs(os.path.join(layout_dir, 'trunk'))
            with open(os.path.join(layout_dir, 'trunk', 'hello.txt'), 'w') as f:
                f.write('Hello SVN!\n')

            # Import the layout into the repo
            subprocess.check_call(['svn', 'import', layout_dir, self.url, '-m', 'Initial commit'])

            # Checkout trunk to working copy
            subprocess.check_call(['svn', 'checkout', f'{self.url}/trunk', self.working_copy_path])

            # Make some changes and commit them
            sleep(2)
            with open(os.path.join(self.working_copy_path, 'hello.txt'), 'a') as f:
                f.write('Hello again!\n')
            for d in ['subdir', 'subdir2']:
                os.makedirs(os.path.join(self.working_copy_path, d))
                subprocess.check_call(['svn', 'add', os.path.join(self.working_copy_path, d)])
            subprocess.check_call(['svn', 'commit', self.working_copy_path, '-m', 'Second commit'])
            sleep(2)
            with open(os.path.join(self.working_copy_path, 'hello.txt'), 'a') as f:
                f.write('Hello a third time!\n\ndef test_vcs_helper:\n    pass\n')
            for f in ['hello.txt']:
                copyfile(os.path.join(self.working_copy_path, f), os.path.join(self.working_copy_path, 'subdir', f))
                subprocess.check_call(['svn', 'add', os.path.join(self.working_copy_path, 'subdir', f)])
            for d in ['subdir2']:
                os.rmdir(os.path.join(self.working_copy_path, d))
                subprocess.check_call(['svn', 'delete', os.path.join(self.working_copy_path, d)])
            subprocess.check_call(['svn', 'commit', self.working_copy_path, '-m', 'Third commit'])
            subprocess.check_call(['svn', 'update', os.path.join(self.working_copy_path, 'subdir')])
            subprocess.check_call(['svn', 'delete', os.path.join(self.working_copy_path, 'subdir'), '--force'])
            subprocess.check_call(['svn', 'commit', self.working_copy_path, '-m', 'Fourth commit'])

        except Exception as e:
            self.cleanup()
            raise RuntimeError(f"Failed to setup dummy SVN repo: {e}")

    def cleanup(self):
        def remove_readonly(func, path, excinfo):
            os.chmod(path, stat.S_IWRITE)  # Attempt to make file writable
            func(path)  # Retry the remove/delete

        if os.path.isdir(self.path):
            rmtree(self.path, onerror=remove_readonly)

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()
