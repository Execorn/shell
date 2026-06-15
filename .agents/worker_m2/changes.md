# File Modifications Report

The following changes were implemented to address robustness and type-safety issues identified in the codebase:

## 1. `services/Hypr.qml`
- **Location**: Line 27 (inside the `keyboard` property getter).
- **Issue**: `extras.devices.keyboards` is a C++ `QQmlListProperty` which does not support the JavaScript array `.find()` method, leading to potential execution failures.
- **Fix**: Replaced the `.find()` call with a safe JavaScript `for` loop that iterates over the list elements explicitly after verifying they are defined.

## 2. `services/Colours.qml`
- **Location**: Line 41 (inside the `alterColour` function).
- **Issue**: Potential divide-by-zero when calculating scale with `luminance === 0` (e.g., when the base color is pure black), resulting in `NaN` or `Infinity`.
- **Fix**: Added a ternary guard: `const scale = luminance === 0 ? 0 : (luminance + offset) / luminance;`.

## 3. `services/Copilot.qml`
- **Location**: `sendToOllama()` (lines 35+) and `sendToGemini()` (lines 92+).
- **Issue**: Missing timeouts on the AI Copilot API requests (Ollama/Gemini) could cause requests to hang indefinitely.
- **Fix**:
  - Set `xhr.timeout = 10000;` on both `XMLHttpRequest` instances.
  - Added `xhr.ontimeout` for Ollama to decrement active requests, trigger the next request, set an error message, and log the timeout.
  - Added `xhr.onerror` for Ollama to cleanly handle connection errors, decrement request count, and process the next request.
  - Added `xhr.ontimeout` for Gemini to log the timeout warning and fall back to the Ollama model.

## 4. `services/Wallpapers.qml`
- **Location**: Lines 45, 101, 109.
- **Issue**: Absolute path `/home/execorn/ricing/shell/scripts/apply-theme.py` was hardcoded, causing failures on other environments or setups.
- **Fix**: Used `Quickshell.shellPath("scripts/apply-theme.py")` to resolve the path dynamically relative to the shell installation or configuration directory.

## 5. `services/Weather.qml`
- **Location**: Within all success and failure callbacks for `Requests.get(...)`.
- **Issue**: Direct calls to `JSON.parse` inside `Requests.get` success callbacks could raise exceptions on invalid JSON payloads (e.g., HTML error pages). Many calls also omitted the `onError` callback, resulting in silent failures.
- **Fix**:
  - Wrapped every `JSON.parse` call in a `try-catch` block.
  - Provided `onError` error handling callbacks on all `Requests.get` calls, printing diagnostic logs and restoring safe defaults where appropriate.

## 6. `modules/overview/Overview.qml`
- **Location**: Lines 260-263.
- **Issue**: Computing scale variables (`scaleX`, `scaleY`, `scaleW`, `scaleH`) assumed `modelData.lastIpcObject` and its `at` and `size` properties were always valid arrays, producing `NaN` coordinate values and warnings if they were missing or if monitor width/height was zero.
- **Fix**: Validated that `modelData.lastIpcObject` and the nested `at`/`size` arrays exist, contain at least 2 elements, are not `NaN`, and that monitor bounds are non-zero before performing scaling division. Defaulted to `0` otherwise.

## 7. `services/Ocr.qml`
- **Location**: `ocrProcess` command (line 19), `translateText` (lines 50+), and `explainText` (lines 95+).
- **Issue**:
  - Hardcoded screenshot/capture path `/tmp/ocr_capture.png` could conflict on multi-user systems.
  - Missing timeout and error handling on Ollama API requests within `translateText` and `explainText` could hang the OCR translation feature.
- **Fix**:
  - Appended the current system username (retrieved using `Quickshell.env("USER")` or falling back to `"default"`) to the temp image name (e.g., `/tmp/ocr_capture_username.png`).
  - Added `xhr.timeout = 10000;`, `xhr.ontimeout`, and `xhr.onerror` callbacks to both requests, clearing the loading indicators and updating `root.lastError` cleanly.

## 8. `tests/test_ricing.py`
- **Location**: Line 817.
- **Issue**: The E2E tests mocked the `grim` screenshot binary with a hardcoded `touch /tmp/ocr_capture.png` script, which would fail to create the user-specific file expected by the updated OCR process.
- **Fix**: Updated the mock script inside `test_ricing.py` to touch `/tmp/ocr_capture_${USER:-default}.png` matching the username variable used by the shell code.
