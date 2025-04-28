import os
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

@tag('artifacts', 'filesystem', 'unit')
def test_submit_current_file(ctx):
    ctx.add_artifact("current_file", os.path.abspath(__file__))
    assert True
