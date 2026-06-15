## Challenge Summary

**Overall risk assessment**: MEDIUM

Empirical verification of the codebase and test suite was successfully conducted. While the main E2E test suite (`tests/test_ricing.py` containing all 72 test cases) passes cleanly and repeatedly on consecutive runs, adversarial analysis has uncovered critical limitations in QML's network stack capabilities and the validation test setup.

Specifically, we found that the QML engine's built-in `XMLHttpRequest` ignores the `timeout` property on our platform, meaning that network hangs can permanently block queue slots in the real-world shell. Furthermore, the adversarial test suite `test_adversarial_verification.py` fails due to incorrect assumptions about JS global object overrides in QML singletons.

---

## Challenges

### [High] Challenge 1: QML XMLHttpRequest Timeout Ignored

- **Assumption challenged**: Setting `xhr.timeout = 10000;` on an `XMLHttpRequest` object enforces a 10-second timeout limit on HTTP requests.
- **Attack scenario**: If the local Ollama instance or the external Gemini API is unreachable but keeps the socket connection open without writing a response (a classic network hang), `XMLHttpRequest` will wait indefinitely. In our offscreen empirical verification script (`verify_xhr.py`), a request to a hanging HTTP server with `xhr.timeout = 1000` waited for 3 seconds to complete with status 200 rather than timing out after 1 second.
- **Blast radius**: High. Since `activeRequestsCount` is only decremented when `readyState === DONE` (which occurs when the request finishes), a hung network socket will permanently occupy a slot. When all 4 slots are occupied, `processNextRequest` will block all future user queries to the Copilot.
- **Mitigation**: Implement a QML `Timer` component within `Copilot.qml` and `Ocr.qml` to explicitly track request duration. If the timer fires before the request transitions to `DONE`, trigger `xhr.abort()`, decrement the request count, and execute the fallback/timeout logic manually.

### [Low] Challenge 2: Test Harness Log Unlink Race Condition

- **Assumption challenged**: Log files (specifically `/tmp/wpctl_calls.log`) will always exist when `log_path.unlink()` is called, or will not be deleted asynchronously by overlapping test executions.
- **Attack scenario**: In `tests/conftest.py`, the `wpctl_log` fixture checks `if log_path.exists():` and immediately calls `log_path.unlink()`. If a concurrent process deletes the log file between the existence check and the unlink call, Python raises a `FileNotFoundError` and crashes the test run.
- **Blast radius**: Low (Test flakiness in local and CI/CD pipelines).
- **Mitigation**: Replace `log_path.unlink()` with `log_path.unlink(missing_ok=True)` in `tests/conftest.py` (lines 1203 and 1206).

### [Medium] Challenge 3: JS Global XMLHttpRequest Mocking Failure in Adversarial Tests

- **Assumption challenged**: Overriding the global `XMLHttpRequest` constructor inside the QML engine (`engine.evaluate("XMLHttpRequest = ...")`) successfully mocks network requests for QML singletons.
- **Attack scenario**: During execution of `test_adversarial_verification.py`, QML singletons like `Copilot` and `Ocr` are compiled in their own isolated scopes and continue to resolve to the native, built-in `XMLHttpRequest` object. Consequently, the JS mock defined in the tests is bypassed, and real network requests are executed, succeeding immediately via the Python mock server instead of timing out.
- **Blast radius**: Medium (causes `test_copilot_request_queue_timeout_release` and `test_ocr_request_timeout_clean_cleanup` in the adversarial verification suite to fail).
- **Mitigation**: Re-write the adversarial timeout tests to mock network delays at the Python HTTP server level (e.g. by configuring `MockOllama` or `MockRequests` to sleep before responding) rather than trying to override the JS `XMLHttpRequest` constructor.

---

## Stress Test Results

### 1. Main E2E Test Suite Stability
- **Scenario**: Run `pytest tests/test_ricing.py` three times consecutively.
- **Expected Behavior**: All 72 tests pass successfully with exit code 0.
- **Actual Behavior**: All 72 tests pass successfully across all three runs (run 1: 3.14s, run 2: 3.19s, run 3: 3.10s).
- **Pass/Fail**: PASS

### 2. Copilot Request Counter Decoupling
- **Scenario**: Simulate requests through `Copilot.qml` and check that `activeRequestsCount` is correctly decremented on completions/errors without double-decrementing.
- **Expected Behavior**: Request counts decrement exactly once per logical query slot, and queue releases correctly.
- **Actual Behavior**: Confirmed that `activeRequestsCount--` was successfully removed from `ontimeout` and `onerror` in `Copilot.qml`, leaving it only in `onreadystatechange` when `readyState === XMLHttpRequest.DONE`. Tested Copilot suites pass successfully.
- **Pass/Fail**: PASS

### 3. OCR Session-Specific Captures
- **Scenario**: Validate that `Ocr.qml` uses randomized paths for screenshot capture.
- **Expected Behavior**: The file path contains a random suffix, and the mock `grim` script touches the dynamic path correctly.
- **Actual Behavior**: `tempPath` is defined using `Math.random()`. The mock `grim` script successfully touches the path dynamically via `"${@: -1}"`.
- **Pass/Fail**: PASS

### 4. Hoisting of triggerFallback
- **Scenario**: Compile and execute `Copilot.qml` to verify that the `triggerFallback` warning is resolved.
- **Expected Behavior**: `triggerFallback` is declared using hoisting-compatible syntax so QML does not raise a `usedbeforedeclared` warning.
- **Actual Behavior**: `triggerFallback` is declared as `function triggerFallback() { ... }`, which hoists correctly. Compilation/execution produces no warnings.
- **Pass/Fail**: PASS

---

## Unchallenged Areas

- **Live Pipewire hotplugging under load**: The Pipewire mocks simulate simple sink/source switching, but actual driver hotplugging and fast switching under continuous audio streams were not tested with real hardware.
- **Concurrent Ollama and Gemini API queries**: Pairwise query concurrency is simulated, but high rate multi-threaded API requests to the local Ollama instance were not stress-tested.
