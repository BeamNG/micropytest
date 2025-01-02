# microPyTest

A minimal, **“pytest-like”** testing framework designed to help you **test anything using Python**.
It works by:

- Discovering test files that match `test_*.py` or `*_test.py`
- Running each test function in real time (with immediate logs)
- Injecting a **test context** (`ctx`) that provides logging methods and artifact tracking
- **Storing per-test durations** in `.micropytest.json` for future **time estimates**
- Offering **quiet** or **verbose** CLI modes

**Current version**: `micropytest version: X.Y.Z` (logged at startup)

> **Note**: Since micropytest can be used to test **anything** via Python scripts, it’s useful for test tasks like:
> - Calling external APIs and verifying responses
> - Testing local scripts or command-line tools
> - Running hardware or network checks
> - Any scenario where Python can orchestrate or verify results, *not* just Python libraries

---

## Table of Contents

1. [Installation](#installation)
2. [CLI Usage](#cli-usage)
3. [Features & Highlights](#features--highlights)
4. [Writing Tests](#writing-tests)
5. [Running Tests Programmatically (No CLI)](#running-tests-programmatically-no-cli)
6. [About `.micropytest.json`](#about-micropytestjson)
7. [Example Output](#example-output)

---

## Installation

You can install **micropytest** via pip. For instance, from a local checkout:

```bash
pip install micropytest
```

This will make the `micropytest` command available in your current Python environment.

---

## CLI Usage

From the root of your project (or any directory containing tests):

```bash
micropytest [OPTIONS] [PATH]
```

**Options**:

- **`-v, --verbose`**: Increase logging verbosity (e.g., show debug messages).
- **`-q, --quiet`**: Quiet mode—only a colorized summary at the end.

If you **omit** the path, `micropytest` defaults to the **current directory** (`.`).

**Examples**:

```bash
micropytest
micropytest -v my_tests
micropytest -q /path/to/tests
```

Watch the **live** logs as each test starts, logs messages, and finishes with a summary.

---

## Features & Highlights

1. **Real-time Console Output**
   - A special “live” log handler flushes output **immediately**, so you see logs as they happen (no waiting for buffers).

2. **Test Discovery**
   - Recursively scans for files named `test_*.py` or `*_test.py`, and for each Python function named `test_*`.

3. **Test Context (`ctx`)**
   - If your test function is defined with a parameter, e.g. `def test_something(ctx):`, micropytest will pass in a `TestContext`.
   - The context offers logging shortcuts (`ctx.debug()`, `ctx.warn()`, etc.) and **artifact tracking** (recording files or data for later review).

4. **Per-Test Durations**
   - After each test, micropytest logs its exact runtime and stores it in `.micropytest.json`.
   - Future runs use that stored duration to **estimate** how long each test might take.

5. **Quiet & Verbose Modes**
   - **Quiet mode**: minimal final summary only (handy for CI or quick checks).
   - **Verbose mode**: additional debug output per test, plus all logs in real time.

6. **Colorful Output**
   - Uses [**colorama**](https://pypi.org/project/colorama/) (if installed) to color warnings, errors, passes/fails, etc.
   - Falls back to plain text if colorama is unavailable.

---

## Writing Tests

Below is a quick overview of **how to write your tests** for micropytest, including **logging**, **asserts**, and **artifacts**.

### 1. Creating Test Files

Place your tests in files named `test_*.py` or `*_test.py`, anywhere in your project. For example:

```
my_project/
└── tests/
    ├── test_example.py
    ├── sample_test.py
    └── ...
```

As soon as you run `micropytest`, it will **automatically** discover these test files.

### 2. Defining Test Functions

Inside each test file, define **functions** that begin with `test_`. For instance:

```python
# test_example.py

def test_basic():
    # This test doesn't need a context; we can just use normal Python asserts.
    assert 1 + 1 == 2, "Math is broken!"

def test_with_context(ctx):
    # This test *does* accept a context parameter (ctx).
    # We can log, store artifacts, etc.
    ctx.debug("Starting test_with_context")

    # Normal Python assertion still applies
    assert 2 + 2 == 4

    # Artifacts: store anything you like for later
    ctx.add_artifact("some_info", {"key": "value"})
```

### 3. Using Logging

Micropytest captures any log calls (e.g., `logging.info`, `logging.warning`) **plus** calls on `ctx`:

- **Standard Python logging**:

  ```python
  import logging

  def test_logging():
      logging.info("This is an INFO log from standard logging.")
      logging.warning("And here's a WARNING.")
      assert True
  ```

- **Context-based logging**:

  ```python
  def test_with_ctx(ctx):
      ctx.debug("This is a DEBUG message via the test context.")
      ctx.warn("This is a WARNING via the test context.")
      assert True
  ```

All these logs appear **in real time** on the console, and also get saved in the test’s log records for the final summary if you run in verbose mode.

### 4. Using Asserts

You can simply use **Python’s built-in `assert`** statements:

```python
def test_something():
    assert 5 > 3
    assert "hello" in "hello world"
```

If an assertion fails, micropytest will **catch** the `AssertionError` and mark the test as **FAILED**.

### 5. Using Artifacts

Artifacts let you **record** additional data—like files or JSON objects—that help diagnose or preserve test information:

```python
def test_artifacts(ctx):
    # For example, check if a file exists
    filepath = "my_data.txt"
    ctx.add_artifact("data_file", filepath)

    # If 'my_data.txt' does NOT exist, you'll see a warning in the logs
    # (and you can choose to fail the test if needed)
```

**Artifacts** appear in the final logs (verbose mode) or can be extracted programmatically after the run. They are purely for your convenience—micropytest doesn’t enforce pass/fail on artifact existence unless you want to (you can raise exceptions if a file is missing).

---

## Running Tests Programmatically (No CLI)

Even though micropytest ships with a **CLI**, you can **import** and **run tests** from your own code if you prefer:

```python
# run_tests_example.py
from micropytest.core import run_tests

def custom_test_run():
    # Suppose we want to run tests from "./my_tests",
    # but not via the command line
    results = run_tests(tests_path="./my_tests", show_estimates=True)

    # 'results' is a list of dicts like:
    #  {
    #    "file": filepath,
    #    "test": test_name,
    #    "status": "pass" or "fail",
    #    "logs": list of (log_level, message),
    #    "artifacts": dict of your stored artifacts,
    #    "duration_s": float (runtime in seconds)
    #  }

    # Summarize
    passed = sum(1 for r in results if r["status"] == "pass")
    total = len(results)
    print(f"Programmatic run: {passed}/{total} tests passed!")

if __name__ == "__main__":
    custom_test_run()
```

By setting up appropriate **logging handlers** in your code, you can also see real-time logs in your own custom environment.

---

## About `.micropytest.json`

A file named **`.micropytest.json`** (in your project directory) tracks **test durations** between runs:

```json
{
  "_comment": "This file is optional: it stores data about the last run of tests for estimates.",
  "test_durations": {
    "tests\\test_something.py::test_foo": 1.2345,
    "tests\\test_hello.py::test_world": 0.0521
  }
}
```

- Each **key** is `filepath::test_function`, mapping to the **most recent** runtime in seconds.
- On subsequent runs, micropytest uses these durations to guess how long each test might take, printing estimates such as `est ~0.8s`.
- Deleting or ignoring this file simply means you lose time-based estimates (the framework still runs tests normally).

---

## Example Output

Here’s an example **verbose** run:

```bash
micropytest -v examples
```

You might see:

```
(.venv) >micropytest examples -v
19:05:38 INFO    |root       | micropytest version: 0.1.0
19:05:38 INFO    |root       | Estimated total time: ~1.5s for 7 tests
19:05:38 INFO    |root       | STARTING: examples\test_artifacts.py::test_artifact_exists (est ~0.0s)
19:05:38 INFO    |root       | FINISHED PASS: examples\test_artifacts.py::test_artifact_exists (0.001s)
19:05:38 INFO    |root       | STARTING: examples\test_artifacts.py::test_artifact_missing (est ~0.0s)
19:05:38 WARNING |root       | Artifact file '/no/such/file/1234.bin' does NOT exist.
19:05:38 INFO    |root       | FINISHED PASS: examples\test_artifacts.py::test_artifact_missing (0.000s)
19:05:38 INFO    |root       | STARTING: examples\test_demo.py::test_long (est ~0.5s)
19:05:39 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_long (0.500s)
19:05:39 INFO    |root       | STARTING: examples\test_demo.py::test_long2 (est ~1.0s)
19:05:40 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_long2 (1.000s)
19:05:40 INFO    |root       | STARTING: examples\test_demo.py::test_no_ctx (est ~0.0s)
19:05:40 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_no_ctx (0.000s)
19:05:40 INFO    |root       | STARTING: examples\test_demo.py::test_with_ctx (est ~0.0s)
19:05:40 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_with_ctx (0.000s)
19:05:40 INFO    |root       | STARTING: examples\subfolder\test_sub.py::test_something_else (est ~0.0s)
19:05:40 INFO    |root       | Standard Python logging used here.
19:05:40 INFO    |root       | FINISHED PASS: examples\subfolder\test_sub.py::test_something_else (0.000s)
19:05:40 INFO    |root       | Tests completed: 7/7 passed.

        _____    _______        _
       |  __ \  |__   __|      | |
  _   _| |__) |   _| | ___  ___| |_
 | | | |  ___/ | | | |/ _ \/ __| __|
 | |_| | |   | |_| | |  __/\__ \ |_
 | ._,_|_|    \__, |_|\___||___/\__|
 | |           __/ |
 |_|          |___/           Report

test_artifacts.py::test_artifact_exists            - PASS in 0.001s
  19:05:38 INFO    |root       | STARTING: examples\test_artifacts.py::test_artifact_exists (est ~0.0s)
  19:05:38 DEBUG   |root       | Artifact file 'tmpwkbz6y9m' exists.
  19:05:38 INFO    |root       | FINISHED PASS: examples\test_artifacts.py::test_artifact_exists (0.001s)
  Artifacts: {'tempfile': {'type': 'filename', 'value': 'tmpwkbz6y9m'}}

test_artifacts.py::test_artifact_missing           - PASS in 0.000s
  19:05:38 INFO    |root       | STARTING: examples\test_artifacts.py::test_artifact_missing (est ~0.0s)
  19:05:38 WARNING |root       | Artifact file '/no/such/file/1234.bin' does NOT exist.
  19:05:38 INFO    |root       | FINISHED PASS: examples\test_artifacts.py::test_artifact_missing (0.000s)
  Artifacts: {'non_existent': {'type': 'filename', 'value': '/no/such/file/1234.bin'}}

test_demo.py::test_long                            - PASS in 0.500s
  19:05:38 INFO    |root       | STARTING: examples\test_demo.py::test_long (est ~0.5s)
  19:05:39 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_long (0.500s)

test_demo.py::test_long2                           - PASS in 1.000s
  19:05:39 INFO    |root       | STARTING: examples\test_demo.py::test_long2 (est ~1.0s)
  19:05:40 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_long2 (1.000s)

test_demo.py::test_no_ctx                          - PASS in 0.000s
  19:05:40 INFO    |root       | STARTING: examples\test_demo.py::test_no_ctx (est ~0.0s)
  19:05:40 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_no_ctx (0.000s)

test_demo.py::test_with_ctx                        - PASS in 0.000s
  19:05:40 INFO    |root       | STARTING: examples\test_demo.py::test_with_ctx (est ~0.0s)
  19:05:40 DEBUG   |root       | Starting test_with_ctx
  19:05:40 DEBUG   |root       | Got the correct answer: 42
  19:05:40 INFO    |root       | FINISHED PASS: examples\test_demo.py::test_with_ctx (0.000s)
  Artifacts: {'calculation_info': {'type': 'primitive', 'value': {'lhs': 2, 'rhs': 21, 'result': 42}}}

test_sub.py::test_something_else                   - PASS in 0.000s
  19:05:40 INFO    |root       | STARTING: examples\subfolder\test_sub.py::test_something_else (est ~0.0s)
  19:05:40 DEBUG   |root       | test_something_else started
  19:05:40 INFO    |root       | Standard Python logging used here.
  19:05:40 INFO    |root       | FINISHED PASS: examples\subfolder\test_sub.py::test_something_else (0.000s)
  Artifacts: {'metadata': {'type': 'primitive', 'value': {'purpose': 'demonstration'}}}


```

Enjoy your **micro** yet **mighty** test framework!