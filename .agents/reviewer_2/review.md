## Review Summary

**Verdict**: REQUEST_CHANGES

The modifications implemented in Milestone 2 address several robustness concerns (such as the division by zero in Colours.qml, dynamic path resolution in Wallpapers.qml, array validation in Overview.qml, and try-catch handling in Weather.qml). However, critical issues in Copilot request queue management and OCR error reporting were identified, alongside minor issues regarding multi-user file collision and flaky test setups.

---

## Findings

### [Critical] Finding 1: Double-decrement of activeRequestsCount in Copilot.qml

- **What**: In `services/Copilot.qml` (within `sendToOllama`), the `activeRequestsCount` is decremented in both `xhr.ontimeout` / `xhr.onerror` AND `xhr.onreadystatechange` (when `xhr.readyState === XMLHttpRequest.DONE`).
- **Where**: `services/Copilot.qml`, lines 39-50 and lines 75-78.
- **Why**: When a timeout or connection error occurs in QML's `XMLHttpRequest`, the `ontimeout` or `onerror` handler is called first (decrementing the count). Then, the request state transitions to `DONE` (readyState 4), which triggers `onreadystatechange`. Because the `onreadystatechange` handler checks `readyState === XMLHttpRequest.DONE` without checking if the request already failed or timed out, it decrements `activeRequestsCount` a second time. This causes the counter to go negative, corrupting the concurrency management of the request queue.
- **Suggestion**: Use a guard boolean (e.g., `let requestCompleted = false;` or check `if (activeRequestsCount > 0)`) or centralize the decrement and `processNextRequest` call into a single place (e.g., only inside `onreadystatechange` by checking `xhr.status` or by clearing the handlers when one executes).

### [Major] Finding 2: OCR Error Message Overwritten in Ocr.qml

- **What**: Detailed error messages set during timeout or error in `translateText` and `explainText` are immediately overwritten by a generic error message.
- **Where**: `services/Ocr.qml`, lines 57-66, 83-98, 113-122, and 139-154.
- **Why**: When an Ollama request times out or fails, `xhr.ontimeout` or `xhr.onerror` is fired, setting `root.lastError` to a descriptive message like `"Ollama connection error. (Request timed out)"`. Immediately after, the state transitions to `DONE`, firing `onreadystatechange`. Since `xhr.status` is not 200 (it is 0), the `else` branch inside `onreadystatechange` is executed, overwriting `root.lastError` back to the generic `"Ollama connection error."`. This defeats the purpose of the detailed error handlers.
- **Suggestion**: Guard the `onreadystatechange` error handler or only set the generic error if a more specific one hasn't already been recorded, or check `xhr.status` to distinguish timeout/network failures.

### [Minor] Finding 3: Multi-User Collision Potential on Default OCR Suffix

- **What**: Fallback screenshot path `/tmp/ocr_capture_default.png` is shared across users if the `USER` environment variable is not defined.
- **Where**: `services/Ocr.qml`, line 18-19.
- **Why**: On multi-user systems, if the `USER` variable is empty for any reason, the fallback name `"default"` is used. If one user runs the OCR, the file `/tmp/ocr_capture_default.png` is created with their ownership. If another user subsequently runs the OCR, they will face permission conflicts trying to overwrite it.
- **Suggestion**: Fallback to a random string or a process-specific ID (e.g., using a random suffix or the PID) rather than a static `"default"` fallback.

### [Minor] Finding 4: Flaky Test Environment (Race Condition in mock_bins)

- **What**: Test run fails intermittently at setup due to `FileNotFoundError` when deleting mock log files in `tests/test_ricing.py`.
- **Where**: `tests/test_ricing.py`, line 805-809.
- **Why**: In `mock_bins` fixture, the code loops over mock log files and calls `log_path.unlink()` if `log_path.exists()` returns true. However, if another process or thread deletes the file between the `exists()` check and `unlink()`, it raises `FileNotFoundError`.
- **Suggestion**: Use `log_path.unlink(missing_ok=True)` (supported in Python 3.8+) to prevent this race condition.

### [Minor] Finding 5: QML Import Path Pollution in tests

- **What**: `tests/test_ricing.py` uses a hardcoded path `/tmp/qml-imports` for importing QML modules, whereas other tests (such as `conftest.py`) use PID-suffixed directories.
- **Where**: `tests/test_ricing.py`, line 554, 894, etc.
- **Why**: This can lead to random type loading errors (e.g. `module "qs.utils" is not installed` or type mismatch) if multiple test runs pollute the import path or if files are partially deleted during execution of the full suite.
- **Suggestion**: Refactor `test_ricing.py` to use a dynamic PID-based import directory similar to the other test suites.

---

## Verified Claims

- `services/Hypr.qml` keyboard list iteration fix → verified via manual review and executing test suite → **PASS** (replaces unsafe `.find()` on C++ list property with basic `for` loop).
- `services/Colours.qml` divide-by-zero fix → verified via manual review and test run → **PASS** (adds `luminance === 0` guard preventing `NaN` and `Infinity`).
- `services/Wallpapers.qml` dynamic script path resolution → verified via manual review and test run → **PASS** (replaces hardcoded paths with `Quickshell.shellPath(...)`).
- `services/Weather.qml` JSON.parse try-catch and onError callbacks → verified via manual review and test run → **PASS** (safeguards all JSON decoding).
- `modules/overview/Overview.qml` window scale checks → verified via manual review and test run → **PASS** (ensures non-empty and non-NaN arrays before computing scaling coordinates).

---

## Coverage Gaps

- **Parallel test execution safety** — risk level: low — the test suite is meant to run sequentially, but if run in parallel, temp files in `/tmp` will collide. No further investigation required, just documentation.

---

## Unverified Items

- None. All files and claims in the review scope have been fully examined and tested.
