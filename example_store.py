"""Example using TestStore."""
import time
from micropytest.store import TestStore, KeepAlive, TestContextStored
from micropytest.core import discover_tests, run_single_test
from micropytest.cli import print_report, print_summary


def main():
    store = TestStore(url="http://localhost:8000/testframework/api")
    discover_ctx = TestContextStored(store)
    tests_path = "."

    # Discover tests and enqueue them
    print("Discovering tests...")
    tests = discover_tests(discover_ctx, tests_path)
    t = time.time()
    for test in tests:
        store.enqueue_test(test)
    print(f"Enqueued {len(tests)} tests in {time.time() - t:.2f} seconds")

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
    time.sleep(0.5)  # on Windows caught KeyboardInterrupt needs some time to recover (otherwise exit code is 130)


if __name__ == "__main__":
    main()
