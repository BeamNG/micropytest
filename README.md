# microPyTest

A minimal, **“pytest-like”** testing framework designed to help you **test anything using Python** while focusing on:

- **Simplicity & minimal configuration**
- **Real-time** console logs and immediate feedback
- Built-in **artifact tracking** and duration-based **time estimates**

---

## Why micropytest?

While [pytest](https://docs.pytest.org) is a powerful and well-established test framework, micropytest has a **narrower**, **lighter** scope and a **different philosophy**:

1. **No heavy config or plugins**
   - micropytest aims for “just run the tests.” Put your test functions in `test_*.py` or `*_test.py`, and you’re good to go—no `pytest.ini` or conftest overhead.

2. **Artifact Tracking & Context**
   - Each test can receive a **test context** (`ctx`) that provides `ctx.debug()`, `ctx.warn()`, etc. **plus** an easy way to record artifacts (`ctx.add_artifact(...)`).
   - This is **built-in**, so you don’t need plugins or extra steps to track test-related files or metadata.

3. **Real-time Logs**
   - micropytest flushes logs **immediately** (so you see them as they happen). Pytest also captures logs, but micropytest is specifically optimized for real-time feedback in simpler, custom test scenarios (e.g., hardware tests, external integrations).

4. **Time Estimates**
   - Each test’s runtime is saved in `.micropytest.json`. Next run, you’ll see estimates like “(est ~0.5s)” so you can get a sense of your overall test duration.
   - Great if you have a large number of tests or tests that call external APIs/hardware.

5. **Low overhead, direct**
   - You can programmatically run micropytest (`run_tests(...)` function) or invoke the CLI. No advanced plugin system or advanced hooking needed—just Python code.

If you need **rich** features like advanced parameterization, detailed fixtures, or a vast ecosystem of plugins, pytest is still your best friend. But if you want a **tiny** runner that does the basics well, tries to be friendly and “just works,” micropytest might be for you!

## Installation

You can install **micropytest** via pip. For instance, from a local checkout:

```bash
pip install micropytest
```

This will make the `micropytest` command available in your current Python environment.

## CLI Usage

From the root of your project (or any directory containing tests):

```bash
micropytest [OPTIONS] [PATH]
```

**Options**:

- **`-v, --verbose`**: Increase logging verbosity (show debug messages, artifacts, etc.).
- **`-q, --quiet`**: Quiet mode—only a colorized summary at the end, no real-time logs.

If you **omit** the path, `micropytest` defaults to the **current directory** (`.`).

**Examples**:

```bash
micropytest
micropytest -v my_tests
micropytest -q /path/to/tests
```

Watch the **live** logs as each test starts, logs messages, and finishes with a summary.

## Features & Highlights

1. **Real-time Console Output**
   A special “live” log handler flushes output **immediately**, so you see logs as they happen (no waiting for buffers).

2. **Test Discovery**
   Recursively scans for files named `test_*.py` or `*_test.py`, and for each Python function named `test_*`.

3. **Test Context (`ctx`)**
   - If your test function has a parameter, e.g., `def test_something(ctx):`, micropytest **injects** a `TestContext`.
   - The context offers logging shortcuts (`ctx.debug()`, `ctx.warn()`, etc.) and **artifact tracking** (`ctx.add_artifact(...)`).

4. **Per-Test Durations**
   - After each test, micropytest logs its runtime and stores it in `.micropytest.json`.
   - Future runs use that data for **time estimates** (e.g., “(est ~0.8s)”).

5. **Quiet & Verbose Modes**
   - **Quiet mode**: minimal final summary only.
   - **Verbose mode**: extra debug logs per test, including artifacts.

6. **Colorful Output**
   - Uses [**colorama**](https://pypi.org/project/colorama/) (if installed) to color warnings, errors, passes/fails, etc.
   - Falls back to plain text if colorama isn’t available.

---

## What’s Different from Pytest?

- **No large ecosystem of plugins**—just straightforward features in a single package.
- **Built-in artifact handling**—pytest can do this with plugins or custom code, but micropytest makes it **central**.
- **Immediate flushing**—pytest can capture logs, but micropytest specifically **flushes** after each log to give you **instant** feedback.
- **Simple configuration**—no `pytest.ini`, no conftest magic.
- **Time estimates** out of the box.
- **No advanced fixtures**—micropytest is intentionally minimal.

If you need advanced pytest fixtures or plugin ecosystems, **pytest** is probably the better solution. But for small, script-based testing scenarios where you want real-time logs and minimal overhead, **micropytest** is a great fit.

---

## Writing Tests

### 1. Creating Test Files

Place your tests in files named `test_*.py` or `*_test.py`, anywhere in your project.

```
my_project/
└── tests/
    ├── test_example.py
    ├── sample_test.py
    └── ...
```

micropytest will automatically discover these test files.

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
    filepath = "data.csv"
    ctx.add_artifact("my_data", filepath)
    # If data.csv doesn't exist, you'll see a warning in real-time logs.
```

Artifacts appear in the **verbose** summary and can be parsed by custom tools if you process the results programmatically.

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
    print("Programmatic run: {}/{} tests passed!".format(passed, total))

if __name__ == "__main__":
    custom_test_run()
```

This can be useful if you want to incorporate micropytest into a larger Python script or custom pipeline, **without** using the CLI.

---

## About `.micropytest.json`

Micropytest saves **per-test durations** in a file named `.micropytest.json` at the root of your test folder. For example:

```json
{
  "_comment": "This file is optional: it stores data about the last run of tests for estimates.",
  "test_durations": {
    "tests\\test_something.py::test_foo": 1.2345,
    "tests\\test_hello.py::test_world": 0.0521
  }
}
```

- **Keys** are `"file_path::test_function"`.
- **Values** are runtime durations (in seconds) from your last run.
- Micropytest uses these to **estimate** how long tests might take on subsequent runs.
- You can **remove** or **ignore** `.micropytest.json` if you don’t care about estimates.

---

## Example Output

Here’s an example **verbose** run (shortened):

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
...
19:05:40 INFO    |root       | Tests completed: 7/7 passed.

        _____    _______        _
       |  __ \  |__   __|      | |
  _   _| |__) |   _| | ___  ___| |_
 | | | |  ___/ | | | |/ _ \/ __| __|
 | |_| | |   | |_| | |  __/\__ \ |_
 | ._,_|_|    \__, |_|\___||___/\__|
 | |           __/ |
 |_|          |___/           Report

...
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

---

## Changelog

### v0.1 - 2025-01-01
- Initial release.

---

## Developer Guide

### Local Development

If you plan on **making changes** to micropytest (fixing bugs, adding features, etc.) and want to test those changes **locally** before sharing or publishing, follow these steps:

1. **Clone the repository** (or download the source):
   ```bash
   git clone https://github.com/BeamNG/micropytest.git
   cd micropytest
   ```

2. **Create and activate** a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   # (Windows) .venv\Scripts\activate
   ```

3. **Make changes** in the source code:
   - Edit files under `micropytest/`.
   - Update docstrings, add tests, etc.

4. **Install locally**:
    ```bash
    pip install -e .
    ```

5. **Test locally**:
    ```bash
    micropytest examples
    ```

### Building & Publishing

Once you have **tested** your changes and are ready to publish your version of micropytest to [PyPI](https://pypi.org/) (or to a private index), follow these steps:

1. **Set up** a fresh environment (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   # (Windows) .venv\Scripts\activate
   ```

2. **Install** build tools:
   ```bash
   pip install build twine colorama
   ```

3. **Build** the distribution:
   ```bash
   python -m build
   ```
   This creates a `dist/` folder with `.tar.gz` and `.whl` files.

4. **Upload** with [Twine](https://twine.readthedocs.io/):
   ```bash
   # For PyPI:
   twine upload dist/*

   # For TestPyPI:
   twine upload --repository testpypi dist/*
   ```

5. **Install & verify**:
   ```bash
   pip install micropytest
   micropytest --version
   ```
   Check that the installed version matches what you published.

That’s it! Now your modified version of micropytest is on PyPI (or TestPyPI). Others can install it with:

```bash
pip install micropytest
```

---

Enjoy your **micro** yet **mighty** testing framework!