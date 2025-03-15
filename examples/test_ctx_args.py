import argparse

def test_with_ctx_args(ctx):
    """Test that uses ctx.args with standard argparse."""
    # Create parser
    parser = argparse.ArgumentParser(description="Test with ctx.args")
    parser.add_argument("--string", "-s", default="default string", help="Input string")
    parser.add_argument("--number", "-n", type=int, default=0, help="Input number")
    parser.add_argument("--operation", "-o", choices=["upper", "lower", "length", "square"], 
                        default="upper", help="Operation to perform")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args, _ = parser.parse_known_args()
    
    # Log the parsed arguments
    ctx.debug(f"Parsed arguments:")
    for key, value in vars(args).items():
        ctx.debug(f"  {key}: {value}")
    
    # Process based on arguments
    result = None
    
    if args.operation == "upper":
        result = args.string.upper()
    elif args.operation == "lower":
        result = args.string.lower()
    elif args.operation == "length":
        result = len(args.string)
    elif args.operation == "square":
        result = args.number ** 2
    
    # Log result
    if args.verbose:
        ctx.debug(f"Operation: {args.operation}")
        ctx.debug(f"Result: {result}")
    
    # Add artifacts
    ctx.add_artifact("args", vars(args))
    ctx.add_artifact("result", result)
    
    return result

def test_file_operations(ctx):
    """Test that handles file operations with argparse using ctx.args."""
    import os
    import tempfile
    
    # Create parser
    parser = argparse.ArgumentParser(description="Test file operations")
    parser.add_argument("--filename", help="File to operate on (creates temp file if not provided)")
    parser.add_argument("--mode", choices=["read", "write", "append"], default="write",
                        help="File operation mode")
    parser.add_argument("--content", default="Default content", help="Content to write/append")
    
    # Get args from context, defaulting to empty list if not present
    cli_args = getattr(ctx, 'args', [])
    
    # Parse arguments
    args = parser.parse_args(cli_args)
    
    # Log the parsed arguments
    ctx.debug(f"File operation with arguments:")
    for key, value in vars(args).items():
        ctx.debug(f"  {key}: {value}")
    
    # Use provided filename or create a temporary one
    filename = args.filename
    
    # Create a temporary file if no filename provided
    if not filename:
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            filename = temp.name
            temp.write(b'Initial content\n')
        ctx.debug(f"Created temporary file: {filename}")
    
    try:
        if args.mode == "write":
            with open(filename, "w") as f:
                f.write(args.content)
            result = f"Wrote {len(args.content)} characters"
        
        elif args.mode == "append":
            with open(filename, "a") as f:
                f.write(args.content)
            result = f"Appended {len(args.content)} characters"
        
        elif args.mode == "read":
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    content = f.read()
                result = content
            else:
                ctx.warn(f"File not found: {filename}")
                result = "File not found"
    
    except Exception as e:
        ctx.error(f"File operation failed: {str(e)}")
        raise
    
    finally:
        # Clean up temporary file if we created one
        if not args.filename and os.path.exists(filename):
            os.unlink(filename)
            ctx.debug(f"Deleted temporary file: {filename}")
    
    # Add artifacts
    ctx.add_artifact("filename", filename)
    ctx.add_artifact("result", result)
    
    return result

def test_no_args(ctx):
    """Test that doesn't use arguments."""
    ctx.debug("Running test without using arguments")
    assert True
    return "Success" 