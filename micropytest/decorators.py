"""Function decorators."""

def tag(*tags):
    """
    Decorator to add tags to a test function.
    
    Usage:
        @tag('fast', 'unit')
        def test_something(ctx):
            # Test code here
    
    Args:
        *tags: One or more string tags to associate with the test
    """
    def decorator(func):
        # Store tags as an attribute on the function
        if not hasattr(func, '_tags'):
            func._tags = set()
        func._tags.update(tags)
        return func
    return decorator
