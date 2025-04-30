from dataclasses import dataclass


@dataclass
class TestStats:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    warnings: int = 0
    errors: int = 0
    total_time: float = 0.0

    def update(self, outcome):
        """Update counters based on test outcome."""
        status = outcome["status"]
        logs = outcome["logs"]
        if status == "pass":
            self.passed += 1
        elif status == "fail":
            self.failed += 1
        elif status == "skip":
            self.skipped += 1
        self.warnings += sum(1 for lvl, _ in logs if lvl == "WARNING")
        self.errors += sum(1 for lvl, _ in logs if (lvl == "ERROR" or lvl == "CRITICAL"))
        self.total_time += outcome["duration_s"]
        return self

    @staticmethod
    def from_results(test_results):
        stats = TestStats()
        for outcome in test_results:
            stats.update(outcome)
        return stats
