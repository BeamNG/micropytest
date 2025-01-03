# microPyTest

**microPyTest** is a minimal, Python-based test runner that you can use directly in code.

## Key Points

- **Code-first approach**: Import and run tests from your own scripts.
- **Artifact tracking**: Each test can record artifacts (files or data) via a built-in **test context**.
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

## Differences from pyTest

If you’re coming from pytest:

1. **No fixtures or plugins**

   microPyTest is intentionally minimal. Tests can still share state by passing a custom context class if needed.

2. **No complex configuration**

   There’s no `pytest.ini` or `conftest.py`. Just put your test functions in `test_*.py` or `*_test.py`.

3. **Artifact handling is built-in**

   `ctx.add_artifact("some_key", value)` can store files or data for later review. No extra plugin required.

4. **Time estimates for each test**

5. **Code-first**

   You typically call `run_tests(...)` from Python scripts. The CLI is optional if you prefer it.

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

- **v0.3** – Added ability to skip tests
- **v0.2** – Added support for custom context classes
- **v0.1** – Initial release

Enjoy your **micro** yet **mighty** test runner!