# Unit & Integration Tests

This folder contains local test artifacts for the Python code execution service.

- `test_executor.py` (in the project root) sends multiple scripts to the `/execute` endpoint to verify:
  - Valid script execution with `numpy`
  - Infinite loop timeout handling
  - Filesystem write protections
  - Syntax error handling
  - Missing `main()` detection
- PNG screenshots in this folder capture successful terminal runs of these tests.

These assets are included to document local verification of the sandboxed execution environment.
