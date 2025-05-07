import json
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

    def is_empty(self):
        return len(self.args) == 0 and len(self.kwargs) == 0

    def to_json(self) -> str:
        """Canonical JSON serialization."""
        d = {'args': list(self.args), 'kwargs': self.kwargs}
        # sort keys and use most compact representation
        # note that tuples in data will be converted to lists (irreversibly)
        return json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

    @staticmethod
    def from_json(s: str) -> "Args":
        """Create an Args object from canonical JSON serialization."""
        d = json.loads(s)
        return Args(*d['args'], **d['kwargs'])


__all__ = ["parameterize", "Args"]
