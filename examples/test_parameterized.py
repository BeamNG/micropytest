from micropytest.parameters import parameterize, Args
from micropytest.decorators import tag

def generate_arguments(ctx):
    """Generate a list of arguments (parameter values) for the test."""
    # This is a simple generation, you could also write custom logic depending on the context or the environment.
    # For example, you could get the set of changed files of the last commit from the VCS and run a test
    # only on the changed set of files.
    # If you return an empty list, this is equivalent to skipping the test.
    # A single ctx object is passed to all generator functions during the discovery phase.
    # You can access ctx.test to get a TestAttributes object (including test name, function, tags, etc.)
    ctx.info(f"generate_arguments: test tags are: {ctx.test.tags}")
    ctx.info(f"generate_arguments: test is: {ctx.test.name}")
    return [
        Args(1, False),
        Args(2, False),
        Args(3, False),
        Args(42, True),
        Args(43, False, verbose=True),
    ]


@tag("weekly", "fast")
@parameterize(generate_arguments)
def test_parameterized(ctx, param, expected_result, verbose=False):
    """A test function with parameters."""
    # The first parameter of a parameterized test must be the context object (whether it is used or not).
    ctx.info(f"Running test with param: {param}")
    result = param == 42
    if verbose:
        ctx.info(f"Result: {result}, expected: {expected_result}")
    assert result == expected_result
