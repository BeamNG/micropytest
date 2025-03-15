import os
import sys
from micropytest.decorators import tag

@tag('artifacts', 'string', 'unit', 'fast')
def test_artifact_str(ctx):
    ctx.add_artifact("my_string", "hello world")
    assert True

@tag('artifacts', 'number', 'unit', 'fast')
def test_artifact_num(ctx):
    ctx.add_artifact("my_number", 42)
    assert True

@tag('artifacts', 'dict', 'unit', 'fast')
def test_artifact_dict(ctx):
    ctx.add_artifact("my_dict", {"key": 123})
    assert True

@tag('artifacts', 'error-handling', 'unit')
def test_artifact_missing(ctx):
    # Should log a warning: file does NOT exist
    ctx.add_artifact("non_existent", "/no/such/file/1234.bin")
    assert True

@tag('artifacts', 'filesystem', 'unit')
def test_submit_current_file(ctx):
    ctx.add_artifact("current_file", os.path.abspath(__file__))
    assert True
