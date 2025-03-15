import time
import sys
import os
from micropytest.command import Command

def test_simple_command(ctx):
    """Basic example: Run a simple command and check its output."""
    with Command(["echo", "Hello World"]) as cmd:
        cmd.wait()
        stdout = cmd.get_stdout()
        
    ctx.debug(f"Command output: {stdout}")
    assert len(stdout) == 1
    assert "Hello World" in stdout[0]

def test_command_with_error(ctx):
    """Example: Handle command that produces error output."""
    # Use sys.executable to get the path to the current Python interpreter
    with Command([sys.executable, "-c", "import sys; print('Standard output'); print('Error output', file=sys.stderr)"]) as cmd:
        cmd.wait()
        stdout = cmd.get_stdout()
        stderr = cmd.get_stderr()
    
    assert "Standard output" in stdout[0]
    assert "Error output" in stderr[0]
    
    # Add artifacts for inspection
    ctx.add_artifact("command_output", {
        "stdout": stdout,
        "stderr": stderr
    })

def test_command_with_callbacks(ctx):
    """Example: Use callbacks to process output in real-time."""
    stdout_lines = []
    stderr_lines = []
    
    def stdout_callback(line):
        stdout_lines.append(line)
        ctx.debug(f"Got stdout: {line}")
    
    def stderr_callback(line):
        stderr_lines.append(line)
        ctx.debug(f"Got stderr: {line}")
    
    cmd = Command([sys.executable, "-c", "import sys; print('Line 1'); print('Line 2'); print('Error', file=sys.stderr)"])
    cmd.run(stdout_callback=stdout_callback, stderr_callback=stderr_callback)
    cmd.wait()
    
    assert len(stdout_lines) == 2
    assert len(stderr_lines) == 1
    assert stdout_lines == ["Line 1", "Line 2"]
    assert stderr_lines == ["Error"]

def test_interactive_basic(ctx):
    """Example: Basic interactive command usage."""
    with Command([sys.executable, "-i"]) as cmd:
        # Send a command to the Python interpreter
        cmd.write("print('Hello from interactive Python')\n")
        
        # Give it a moment to process
        time.sleep(0.1)
        
        # Check output
        stdout = cmd.get_stdout()
        ctx.debug(f"Python output: {stdout}")
        
        # Exit the interpreter
        cmd.write("exit()\n")
    
    # Verify the output contains our printed message
    assert any("Hello from interactive Python" in line for line in cmd.get_stdout())

def test_interactive_with_output_access(ctx):
    """Example: Interactive command with conditional behavior based on output."""
    with Command([sys.executable, "-i"]) as cmd:
        # Write a command
        cmd.write("print('Hello, world!')\n")
        
        # Give it a moment to process
        time.sleep(0.1)
        
        # Check the output so far
        stdout = cmd.get_stdout()
        ctx.debug(f"Current stdout: {stdout}")
        
        # Continue interaction based on what we've seen
        if any("Hello, world!" in line for line in stdout):
            cmd.write("print('Got the greeting!')\n")
        
        # Write more commands
        cmd.write("result = 2 + 2\n")
        cmd.write("print(f'Result: {result}')\n")
        
        # Wait a bit and check output again
        time.sleep(0.1)
        stdout = cmd.get_stdout()
        
        # Exit the interpreter
        cmd.write("exit()\n")
    
    # After the context manager exits, we can still access all output
    final_stdout = cmd.get_stdout()
    ctx.add_artifact("python_interaction", {
        "stdout": final_stdout,
        "stderr": cmd.get_stderr()
    })
    
    # Verify the interaction worked as expected
    assert any("Hello, world!" in line for line in final_stdout)
    assert any("Result: 4" in line for line in final_stdout)

def test_command_with_environment(ctx):
    """Example: Run a command with custom environment variables."""
    custom_env = {"TEST_VAR": "custom_value"}
    
    # Make sure to include the current environment variables too
    env = os.environ.copy()
    env.update(custom_env)
    
    with Command([sys.executable, "-c", "import os; print(os.environ.get('TEST_VAR', 'not_set'))"], 
                env=env) as cmd:
        cmd.wait()
        stdout = cmd.get_stdout()
    
    assert stdout[0] == "custom_value"

def test_command_with_working_directory(ctx):
    """Example: Run a command in a specific working directory."""
    import os
    import tempfile
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Run command in the temporary directory
        with Command([sys.executable, "-c", "import os; print(os.getcwd())"], 
                    cwd=temp_dir) as cmd:
            cmd.wait()
            stdout = cmd.get_stdout()
        
        # Verify the command ran in the specified directory
        # Use realpath to resolve any symlinks for consistent comparison
        assert os.path.realpath(stdout[0]) == os.path.realpath(temp_dir)

def test_complex_interaction(ctx):
    """Example: Complex interaction with a command-line program."""
    # This example simulates interaction with a CLI program that asks questions
    with Command([sys.executable, "-c", """
import sys
print("What is your name?")
sys.stdout.flush()
name = input()
print(f"Hello, {name}!")
print("What is your favorite number?")
sys.stdout.flush()
number = input()
print(f"Your favorite number is {number}")
"""]) as cmd:
        # Wait for the first question
        time.sleep(0.1)
        stdout = cmd.get_stdout()
        ctx.debug(f"Program asked: {stdout}")
        
        # Answer the first question
        cmd.write("Alice\n")
        time.sleep(0.1)
        
        # Wait for the second question
        stdout = cmd.get_stdout()
        ctx.debug(f"Program output after first answer: {stdout}")
        
        # Answer the second question
        cmd.write("42\n")
        time.sleep(0.1)
        
        # Get final output
        stdout = cmd.get_stdout()
        ctx.debug(f"Final program output: {stdout}")
    
    # Verify the interaction
    all_output = cmd.get_stdout()
    assert any("What is your name?" in line for line in all_output)
    assert any("Hello, Alice!" in line for line in all_output)
    assert any("Your favorite number is 42" in line for line in all_output) 