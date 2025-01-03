import time

def test_no_ctx():
    """
    A test function that doesn't accept ctx.
    """
    # This test is extremely simple: just a raw assertion
    assert 2 + 2 == 4

def test_long():
    time.sleep(0.5)

def test_long2():
    time.sleep(1)

def test_with_ctx(ctx):
    """
    A test function that accepts a context (ctx).
    Demonstrates logging and artifacts usage.
    """
    ctx.debug("Starting test_with_ctx")
    answer = 2 * 21

    if answer != 42:
        ctx.error(f"Unexpected answer: {answer}")
    else:
        ctx.debug("Got the correct answer: 42")

    # Add an artifact for demonstration
    ctx.add_artifact("calculation_info", {"lhs": 2, "rhs": 21, "result": answer})

    # A normal assertion
    assert answer == 42

def test_skip(ctx):
    ctx.skip_test("We never run this test as example")

