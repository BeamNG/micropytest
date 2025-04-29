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


def parameterize(argument_generator_function):
    """
    Decorator to supply a generator function of arguments for a parameterized test.
    
    Usage:
        @parameterize(generator_function)
        def test_parameterized(ctx, param):
            # Test code here
    """
    def decorator(func):
        # Store the parameter generator function as an attribute on the test function
        func._argument_generator = argument_generator_function
        return func
    return decorator
