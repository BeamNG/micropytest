"""
test_custom_context_integration.py

Demonstrates a micropytest "nested test" that calls run_tests() itself,
while preventing infinite recursion. Also shows how to:

1. Override default warn/error behaviors in a custom context.
2. Provide a shared resource (e.g., a DB connection).
3. Add utility methods to the context (e.g., ctx.do_something()).
4. Exclude this file from re-discovery using an environment variable.
5. Confirm that we're actually using the correct custom context.
"""

import os
import micropytest.core

class MyCustomContext(micropytest.core.TestContext):
    """
    A custom context that overrides 'warn' and 'error' methods for demonstration,
    and also holds a shared resource (like a DB connection).
    """

    def __init__(self, custom_label=None, db_conn=None):
        """
        :param custom_label: A string label we'll inject into warn/error messages.
        :param db_conn: An optional database connection or other shared resource.
        """
        super(MyCustomContext, self).__init__()
        self.custom_label = custom_label
        self.db_conn = db_conn  # hold onto a shared resource, if provided

    def warn(self, msg):
        """
        Override the base warn method to prepend our custom label.
        """
        labeled_msg = "[WARN-{}] {}".format(self.custom_label, msg)
        super(MyCustomContext, self).warn(labeled_msg)

    def error(self, msg):
        """
        Override the base error method to prepend our custom label.
        """
        labeled_msg = "[ERROR-{}] {}".format(self.custom_label, msg)
        super(MyCustomContext, self).error(labeled_msg)

    def do_db_query(self, query):
        """
        Example utility method: run a DB query using the stored db_conn,
        and log something about it.
        """
        if not self.db_conn:
            self.warn("No db_conn available, skipping query: {}".format(query))
            return None
        self.debug("Running DB query: {}".format(query))
        # Hypothetical usage:
        # result = self.db_conn.execute(query)
        # return result
        return "fake_result"


def test_db_usage(ctx):
    """
    A simple test that demonstrates usage of ctx.do_db_query().
    Also confirms we have the correct MyCustomContext instance.
    """
    # Make sure we're indeed using MyCustomContext
    if ctx.__class__.__name__ != "MyCustomContext": # you can also use isinstance if you put the UserContext in a separate file
        # this example might be run with the default context as well
        ctx.skip_test("Not the having the custom context")

    result = ctx.do_db_query("SELECT * FROM sample_table")
    assert result == "fake_result", "Expected 'fake_result' from do_db_query"


def test_custom_context_integration():
    """
    This test invokes micropytest itself (run_tests) with a custom context
    to verify that overriding warn/error/etc. and shared resources behave as expected.

    We prevent endless recursion by checking 'IN_NESTED_RUN' in the environment.
    When the nested run_tests() runs, it will see that env var and skip calling itself again.
    """
    if "IN_NESTED_RUN" in os.environ:
        # If this env var is set, we're in the nested invocation => skip to avoid recursion
        return

    # Mark that we're in the nested run now, so the discovered tests won't call us again
    os.environ["IN_NESTED_RUN"] = "1"

    # Provide a 'fake_db_conn' if you want to demonstrate usage.
    fake_db_conn = object()  # or your real DB connection

    # We'll run the tests in the current directory with a custom context and DB connection.
    results = micropytest.core.run_tests(
        tests_path=".",  # or "example_tests", etc.
        show_estimates=True,
        context_class=MyCustomContext,
        show_progress=False,  # required for nested run to not conflict with progress bar of parent run
        context_kwargs={
            "custom_label": "(nested)",
            "db_conn": fake_db_conn,
        }
    )
    stats = micropytest.core.TestStats.from_results(results)

    # Summarize results
    passed = stats.passed + stats.skipped
    total = len(results)

    # Ensure that all tests discovered by the nested run pass
    assert passed == total, "Expected all tests to pass with the custom context!"

    # Ensure that there were no errors
    assert stats.errors == 0, "Expected no errors."
