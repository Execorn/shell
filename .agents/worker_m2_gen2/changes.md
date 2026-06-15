# Summary of Changes

## 1. `services/Copilot.qml`
- **Duplicate Request Counter Fix**: Removed `activeRequestsCount--` and `processNextRequest()` from `xhr.ontimeout` and `xhr.onerror` callbacks inside `sendToOllama()`. Let the `xhr.onreadystatechange` handler manage the decrement and queue processing when `readyState === XMLHttpRequest.DONE`, ensuring `activeRequestsCount` is only decremented once per request.
- **Hoisting Fix**: Declared `triggerFallback` inside `sendToGemini()` as a standard hoisted function instead of a `const` arrow function, resolving the QML compiler warning about using variables before they are declared.

## 2. `services/Ocr.qml`
- **Error Overwriting Fix**: Wrapped the `else` blocks in `translateText` and `explainText`'s `xhr.onreadystatechange` handlers inside a check `if (!root.lastError)`. This ensures specific error messages set by the timeout/error handlers are not overwritten by the generic "Ollama connection error."
- **USER Fallback and unique temp path**:
  - Replaced the null-coalescing operator `??` with `||` in `readonly property string user: Quickshell.env("USER") || "default"`.
  - Defined the temporary path dynamically using a session-specific random number: `readonly property string tempPath: "/tmp/ocr_capture_" + (Quickshell.env("USER") || "user") + "_" + Math.floor(Math.random() * 10000) + ".png"`.
  - Updated the shell command in `ocrProcess` to use `tempPath` instead of `ocrImagePath`.

## 3. `tests/test_ricing.py`
- **Robustness in Log Unlinking**: Changed `log_path.unlink()` to `log_path.unlink(missing_ok=True)` in `mock_bins()`.
- **Dynamic Path Handling in Mock Grim**: Updated the mock `grim` script to touch the file path passed as the last argument (`${@: -1}`), allowing it to work seamlessly with the dynamically generated random temporary paths from `Ocr.qml`.
- **Garbage Collection Prevention**: Added `"xhr_fn": xhr_fn` to the yielded dictionary in the `ricing_suite` fixture to prevent Python/QML garbage collection of the mock `XMLHttpRequest` instance, resolving test suite flakiness.
