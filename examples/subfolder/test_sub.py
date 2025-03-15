# subfolder/test_sub.py

import logging
from micropytest.decorators import tag

@tag('subfolder', 'logging', 'unit')
def test_something_else(ctx):
    """
    Uses the test context and standard Python logging.
    """
    ctx.debug("test_something_else started")

    # We can also log with Python's logging, which is captured by micropytest:
    logging.info("Standard Python logging used here.")

    #ctx.warn("This is a warning message from ctx.")

    ctx.add_artifact("metadata", {"purpose": "demonstration"})

    # Minimal assertion
    assert 1 == 1
