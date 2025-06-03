"""Example using TestStore."""
import time
from micropytest.store import TestStore, KeepAlive, TestContextStored
from micropytest.core import discover_tests, run_single_test


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
