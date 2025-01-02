# micropytest Examples

This folder shows how to use micropytest features:

- Test discovery (test_*.py or *_test.py files)
- Test Context (ctx) usage
- Logging (debug/warn/error/fatal) captured per test
- Storing artifacts in the test context
- Verbose (`-v`) and quiet (`-q`) modes

## How to Run

1. Install `micropytest` (e.g., `pip install -e .` inside the main project folder).
2. From the root of your project (where `micropytest/` is installed), run:

   ```bash
   micropytest examples
   ```

   This will recursively discover test files in `examples/`.

### Verbose Mode

For detailed logs and artifacts:

```bash
micropytest -v examples
```

### Quiet Mode

For minimal output:

```bash
micropytest -q examples
```
