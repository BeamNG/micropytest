import os
import tempfile

def test_artifact_exists(ctx):
    """
    Creates a temporary file, then adds it as an artifact.
    Should log that the file DOES exist.
    """
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"Hello, test!")
        tmp_path = tmp.name

    # Record the artifact path
    ctx.add_artifact("tempfile", tmp_path)

    # Cleanup explicitly
    os.remove(tmp_path)


def test_artifact_missing(ctx):
    """
    Adds a random file path as an artifact, which does NOT exist.
    Should warn that the file does not exist.
    """
    ctx.add_artifact("non_existent", "/no/such/file/1234.bin")
    assert True  # pass
