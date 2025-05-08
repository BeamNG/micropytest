from dataclasses import dataclass
from .types import TestResult


@dataclass
class TestStats:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    warnings: int = 0
    errors: int = 0
    total_time: float = 0.0

    def update(self, result: TestResult):
        """Update counters based on test result."""
        status = result.status
        logs = result.logs
        if status == "pass":
            self.passed += 1
        elif status == "fail":
            self.failed += 1
        elif status == "skip":
            self.skipped += 1
        self.warnings += sum(1 for record in logs if record.levelname == "WARNING")
        self.errors += sum(1 for record in logs if (record.levelname in ["ERROR", "CRITICAL"]))
        self.total_time += result.duration_s
        return self

    @staticmethod
    def from_results(test_results: list[TestResult]):
        stats = TestStats()
        for result in test_results:
            stats.update(result)
        return stats
