"""Example using TestStore."""
from micropytest.store import TestStore, KeepAlive
from micropytest.core import discover_tests, TestContext, run_single_test
import logging
from typing import Any, Optional
import time

class TestContextStored(TestContext):
    def __init__(self, store: TestStore, run_id: Optional[int] = None):
        super().__init__()
        self.store: TestStore = store
        self.run_id: int = run_id

    def add_artifact(self, key: str, value: Any):
        super().add_artifact(key, value)
        self.store.add_artifact(self.run_id, key, value)

    def add_log(self, record: logging.LogRecord):
        super().add_log(record)
        self.store.add_logs(self.run_id, [record])


def main():
    store = TestStore(url="http://localhost:8000/testframework/api")
    discover_ctx = TestContextStored(store)
    tests_path = "."

    # Discover tests and enqueue them
    tests = discover_tests(discover_ctx, tests_path)
    t = time.time()
    for test in tests:
        store.enqueue_test(test)
    print(f"Enqueued {len(tests)} tests in {time.time() - t:.2f} seconds")

    # Start tests in queue
    while True:
        test_run = store.start_test()
        if test_run is None:
            break
        ctx = TestContextStored(store, test_run.run_id)
        try:
            with KeepAlive(store, test_run.run_id):
                result = run_single_test(test_run.test, ctx)
            store.finish_test(test_run.run_id, result)
        except KeyboardInterrupt:
            # test was cancelled on server side
            pass


if __name__ == "__main__":
    main()
