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
    file_path = os.path.abspath(__file__)
    file_name = os.path.basename(file_path)
    ctx.add_artifact_file(file_name, file_path)
    assert True
