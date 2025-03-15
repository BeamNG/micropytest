# microPyTest

**microPyTest** is a minimal, pure python-based test runner that you can use directly in code.

![screenshot.png](https://github.com/BeamNG/micropytest/raw/main/docs/screenshot.png)

## Key Points

- **Code-first approach**: Import and run tests from your own scripts.
- **Artifact tracking**: Each test can record artifacts (files or data) via a built-in **test context**.
- **Command execution**: Run and interact with external processes with real-time output processing.
- **Lightweight**: Just Python. No special config or advanced fixtures.
- **Optional CLI**: You can also run tests via the `micropytest` command, but **embedding** in your own code is the primary focus.

## Installation

```bash
pip install micropytest
```

## Usage in Code

Suppose you have some test files under `my_tests/`:

```python
# my_tests/test_example.py
def test_basic():
    assert 1 + 1 == 2

def test_with_context(ctx):
    ctx.debug("Starting test_with_context")
    assert 2 + 2 == 4
    ctx.add_artifact("numbers", {"lhs": 2, "rhs": 2})
```

You can **run** them from a Python script:

```python
import micropytest.core

results = micropytest.core.run_tests(tests_path="my_tests")
passed = sum(r["status"] == "pass" for r in results)
total = len(results)
print("Test run complete: {}/{} passed".format(passed, total))
```

- Each test that accepts a `ctx` parameter gets a **TestContext** object with `.debug()`, `.warn()`, `.add_artifact()`, etc.
- Results include logs, artifacts, pass/fail/skip status, and **duration**.

## Command Execution

microPyTest includes a `Command` class for running and interacting with external processes:

```python
from micropytest.command import Command
import sys

def test_interactive_command(ctx):
    # Run a Python interpreter interactively
    with Command([sys.executable, "-i"]) as cmd:
        # Send a command
        cmd.write("print('Hello, world!')\n")
        
        # Check the output
        stdout = cmd.get_stdout()
        
        # Exit the interpreter
        cmd.write("exit()\n")
    
    # Verify the output
    assert any("Hello, world!" in line for line in cmd.get_stdout())
```

Key features:
- Run commands with callbacks for real-time output processing
- Interact with processes via stdin
- Access stdout/stderr at any point during execution
- Set custom environment variables and working directories

## Differences from pyTest

- **Code-first**: You typically call `run_tests(...)` from Python scripts. The CLI is optional if you prefer it.

- **Artifact handling is built-in**: `ctx.add_artifact("some_key", value)` can store files or data for later review. No extra plugin required.

- **Command execution built-in**: No need for external plugins to run and interact with processes.

- **No fixtures or plugins**: microPyTest is intentionally minimal. Tests can still share state by passing a custom context class if needed.

- **No configuration**: There's no `pytest.ini` or `conftest.py`. Just put your test functions in `test_*.py` or `*_test.py`.

- **Time estimates for each test**

## Quickstart

See the examples subfolder

## Optional CLI

If you prefer a command-line flow:

```bash
micropytest [OPTIONS] [PATH]
```

- `-v, --verbose`: Show all debug logs & artifacts.
- `-q, --quiet`: Only prints a final summary.

Example:

```bash
micropytest -v my_tests
```

## Changelog

- **v0.4** – Added Command class for process execution and interaction
- **v0.3.1** – Fixed screenshot in pypi
- **v0.3** – Added ability to skip tests
- **v0.2** – Added support for custom context classes
- **v0.1** – Initial release

Enjoy your **micro** yet **mighty** test runner!