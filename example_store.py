"""Run tests using TestStore to save test results on server. This will:
- Discover tests
- Enqueue them on server
- Pick up tests one by one, run them and store results on server
"""
import os
import time
from micropytest.store import TestStore, KeepAlive, TestContextStored
from micropytest.core import discover_tests, run_single_test, setup_logging
from micropytest.cli import print_report, print_summary

API_URL = os.environ.get("API_URL", "http://localhost:8000/testframework/api")
TESTS_PATH = os.environ.get("TESTS_PATH", ".")


def main():
    print(f"Set up test store...")
    store = TestStore(url=API_URL)
    discover_ctx = TestContextStored(store)
    setup_logging()

    # Discover tests and enqueue them
    print("Discovering tests...")
    tests = discover_tests(discover_ctx, TESTS_PATH)
    print(f"Discovered {len(tests)} tests")
    if len(tests) == 0:
        print("No tests to run.")
        return
    t = time.time()
    for test in tests:
        store.enqueue_test(test)
    print(f"Enqueued {len(tests)} tests in {time.time() - t:.2f} seconds")
    print(f"Job ID: {store.job}")

    # Start tests in queue
    print("Running tests...")
    test_results = []
    while True:
        test_run = store.start_test()
        if test_run is None:
            break
        ctx = TestContextStored(store, test_run.run_id)
        try:
            with KeepAlive(store, test_run.run_id):
                print(f"Running test: {test_run.test.short_key_with_args}")
                result = run_single_test(test_run.test, ctx)
            store.finish_test(test_run.run_id, result)
            test_results.append(result)
        except KeyboardInterrupt:
            print("test was cancelled by user, continuing with next test")
    print_report(test_results)
    print_summary(test_results)
    num_not_run = len(tests) - len(test_results)
    if num_not_run > 0:
        print(f"=> {num_not_run} tests were not run")


if __name__ == "__main__":
    main()
