from .decorators import parameterize

class Args:
    """A container to store function arguments."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        args = [repr(arg) for arg in self.args]
        kwargs = [f"{k}={repr(v)}" for k, v in self.kwargs.items()]
        return f"({', '.join(args + kwargs)})"
    
    def __repr__(self):
        return f"Args{str(self)}"

__all__ = ["parameterize", "Args"]
