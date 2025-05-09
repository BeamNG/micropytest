"""Test-specific data types."""
import os
from dataclasses import dataclass
from typing import Optional, Any, Literal
from .parameters import Args
from datetime import datetime
from logging import LogRecord

TestStatus = Literal["pass", "fail", "skip"]

@dataclass
class TestAttributes:
    """A test function, including tags."""
    file: str
    name: str
    function: callable
    tags: set[str]


@dataclass
class Test:
    """A discovered test, including its arguments and tags."""
    file: str
    name: str
    function: callable
    tags: set[str]
    args: Args

    @property
    def key(self):
        file = self.file.replace('\\', '/')
        return f"{file}::{self.name}"

    @property
    def short_key(self):
        return f"{os.path.basename(self.file)}::{self.name}"

    @property
    def short_key_with_args(self):
        if self.args.is_empty():
            return self.short_key
        return f"{self.short_key}{self.args}"


@dataclass
class TestResult:
    """The result of a single test."""
    test: Test
    status: TestStatus
    logs: list[LogRecord]
    artifacts: dict[str, Any]
    exception: Optional[Exception]
    return_value: Any
    start_time: datetime
    duration_s: float
