# Handoff Report — Second QML Code Reviewer

## 1. Observation

- **Observed File Paths & Modifications**:
  - `services/Hypr.qml`, line 27:
    ```qml
        readonly property HyprKeyboard keyboard: {
            if (!extras || !extras.devices || !extras.devices.keyboards) return null;
            const kbs = extras.devices.keyboards;
            for (let i = 0; i < kbs.length; i++) {
                if (kbs[i] && kbs[i].main) return kbs[i];
            }
            return null;
        }
    ```
  - `services/Colours.qml`, line 41:
    ```qml
    const scale = luminance === 0 ? 0 : (luminance + offset) / luminance;
    ```
  - `services/Copilot.qml`, lines 38-44:
    ```qml
            xhr.timeout = 10000;
            xhr.ontimeout = function() {
                activeRequestsCount--;
                processNextRequest();
                lastError = "Connection to Ollama timed out.";
                console.error("[Copilot.qml Ollama timeout]");
            };
    ```
    And lines 75-78:
    ```qml
            xhr.onreadystatechange = function() {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    activeRequestsCount--;
                    processNextRequest();
    ```
  - `services/Ocr.qml`, lines 57-61:
    ```qml
            xhr.timeout = 10000;
            xhr.ontimeout = function() {
                root.translatedText = "";
                root.lastError = "Ollama connection error. (Request timed out)";
                console.error("[Ocr.qml translation timeout]");
            };
    ```
    And lines 83-85:
    ```qml
            xhr.onreadystatechange = function() {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    if (xhr.status === 200) {
    ```
    And lines 93-96:
    ```qml
                    } else {
                        root.translatedText = "";
                        root.lastError = "Ollama connection error.";
                    }
    ```
  - `tests/test_ricing.py`, lines 805-809:
    ```python
            for log in ["wpctl_calls.log", "grim_calls.log", "hyprctl_calls.log", "caelestia_calls.log", "wlsunset_calls.log", "pkill_calls.log", "nmcli_calls.log", "bluetoothctl_calls.log"]:
                log_path = pathlib.Path("/tmp") / log
                if log_path.exists():
                    log_path.unlink()
    ```
  
- **Test Suite Command & Output**:
  - Command: `QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_ricing.py`
  - Output when test failed due to log unlinking race condition:
    ```
    self = PosixPath('/tmp/caelestia_calls.log'), missing_ok = False
        def unlink(self, missing_ok=False):
            try:
    >           os.unlink(self)
    E           FileNotFoundError: [Errno 2] No such file or directory: '/tmp/caelestia_calls.log'
    ```
  - Output when test failed due to QML import path pollution:
    ```
    file:///tmp/qml-imports/qs/services/Ocr.qml: Type Audio unavailable
    file:///tmp/qml-imports/qs/services/Audio.qml: Type Copilot unavailable
    file:///tmp/qml-imports/qs/services/Copilot.qml:6:1: module "qs.utils" is not installed
    ```

---

## 2. Logic Chain

- **Ollama Request Queue Counter Corruption**:
  - Observation: In `Copilot.qml`, the Ollama request handler decrements `activeRequestsCount` in both `ontimeout` / `onerror` and `onreadystatechange` when `readyState` becomes `DONE`.
  - Logic: In QML's `XMLHttpRequest`, when a request times out or encounters a network error, `ontimeout` / `onerror` is fired, and subsequently, `onreadystatechange` is fired with `readyState === 4` (DONE). Because `onreadystatechange` does not guard against already handled timeouts/errors, it decrements `activeRequestsCount` a second time. This causes the counter to go negative, breaking queue limits.
  - Conclusion: This is a critical correctness bug.

- **OCR Detailed Error Overwriting**:
  - Observation: In `Ocr.qml`, `ontimeout` / `onerror` set `root.lastError` to a descriptive string (e.g. `"Ollama connection error. (Request timed out)"`). Then, `onreadystatechange` is called on completion and overwrites `root.lastError` to `"Ollama connection error."` because `status` is 0.
  - Logic: The execution flow guarantees that `onreadystatechange` runs after `ontimeout` or `onerror` and always falls into the `else` block because `status` is not 200. This overwrites the specific message, hiding the detailed cause from the user.
  - Conclusion: This is a major correctness bug.

- **Multi-user Permission Collision**:
  - Observation: `Ocr.qml` defaults to `/tmp/ocr_capture_default.png` if `Quickshell.env("USER")` is empty.
  - Logic: If user A runs the tool without `USER` set, the file is created with user A's permissions. If user B later runs it under similar conditions, user B's process will fail to write to user A's file.
  - Conclusion: This is a minor security/robustness vulnerability.

- **Test Suite Flakiness**:
  - Observation: Intermittent `FileNotFoundError` during setup and random module loading failures.
  - Logic: The unlinking of log files lacks `missing_ok=True` (making it vulnerable to race conditions), and the hardcoded `/tmp/qml-imports` directory pollutes the environment.
  - Conclusion: The test environment is unstable and needs improvement.

---

## 3. Caveats

- We assumed that QML's `XMLHttpRequest` triggers `onreadystatechange` after `ontimeout`/`onerror`, which aligns with standard W3C and Qt QML behavior.
- We did not write an integration patch directly since the agent is constraint-limited to **review-only**.

---

## 4. Conclusion

- **Verdict**: REQUEST_CHANGES
- While the basic fixes are correct in intent, the double-decrement of `activeRequestsCount` in `Copilot.qml` and the overwriting of detailed error messages in `Ocr.qml` are regressions/bugs that must be resolved. The test suite's stability issues should also be fixed.

---

## 5. Verification Method

- **Files to Inspect**:
  - `services/Copilot.qml`
  - `services/Ocr.qml`
- **Commands to Run**:
  - Run the tests in isolation:
    `QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_copilot_stress.py`
    `QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_ricing.py -k "test_t1_r6_ocr_translate"`
