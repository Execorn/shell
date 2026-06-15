## 2026-06-15T09:25:51Z

You are the Robustness Sweeper and Fix Implementer (archetype: teamwork_preview_worker).
Your working directory is: /home/execorn/ricing/shell/.agents/worker_m2_gen2

**Objective**:
Implement fixes for the logical, state-management, and test flakiness bugs identified by the reviewers. Run the E2E test suite to verify the changes.

**Vulnerabilities/Bugs to Fix**:
1. **Fix `Copilot.qml` duplicate request counter decrements**:
   In `services/Copilot.qml`'s `sendToOllama()`, remove `activeRequestsCount--` and `processNextRequest()` from the `xhr.ontimeout` and `xhr.onerror` callbacks. Let the `xhr.onreadystatechange` handler manage the decrement and queue processing when `readyState === XMLHttpRequest.DONE`. Make sure `activeRequestsCount` is only decremented once per request.
2. **Fix `Copilot.qml` Temporal Dead Zone warning/error**:
   In `services/Copilot.qml`'s `sendToGemini()`, declare `triggerFallback` as a standard hoisted function:
   ```javascript
   function triggerFallback() {
       if (fallbackTriggered) return;
       fallbackTriggered = true;
       console.log("[Copilot.qml] Falling back to Ollama...");
       sendToOllama();
   }
   ```
   This ensures it is hoisted correctly and resolves the QML compiler warning about variable use before declaration.
3. **Fix `Ocr.qml` error message overwriting**:
   In `services/Ocr.qml`, in both `translateText` and `explainText`, inside `xhr.onreadystatechange`, only set `root.lastError` in the `else` block if `root.lastError` is not already set. E.g.:
   ```javascript
   if (!root.lastError) {
       root.translatedText = "";
       root.lastError = "Ollama connection error.";
   }
   ```
   This preserves the specific error messages set in the timeout/error handlers.
4. **Fix `Ocr.qml` USER fallback and unique temp path**:
   - In `services/Ocr.qml` line 18, use:
     `readonly property string user: Quickshell.env("USER") || "default"`
   - To avoid multi-user temp file conflicts, define the temp path dynamically with a session-specific random number in `services/Ocr.qml`:
     `readonly property string tempPath: "/tmp/ocr_capture_" + (Quickshell.env("USER") || "user") + "_" + Math.floor(Math.random() * 10000) + ".png"`
   - In `tests/test_ricing.py` line 817, update the mock `grim` script to touch the file path passed as the last argument, so it handles the dynamically generated path:
     `grim.write_text("#!/bin/bash\\ntouch \\\"\${@: -1}\\\"\\necho \\\"grim $@\\\" >> /tmp/grim_calls.log\\nexit 0\\n")`
5. **Fix test suite flakiness (GC issues & unlink races)**:
   - In `tests/test_ricing.py` line 808, change `log_path.unlink()` to `log_path.unlink(missing_ok=True)`.
   - In `tests/test_ricing.py` around line 1005 (inside `ricing_suite` fixture), add `"xhr_fn": xhr_fn` to the yielded dictionary to prevent garbage collection of the mock `XMLHttpRequest` instance:
     ```python
     yield {
         "engine": qml_engine,
         "ollama": ollama_mock,
         "requests": requests_mock,
         "cutils": cutils_mock,
         "quickshell": quickshell_mock,
         "xhr_fn": xhr_fn, # Prevent garbage collection!
         ...
     ```

**MANDATORY INTEGRITY WARNING**:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

**Output Requirements**:
Write a detailed report `changes.md` in your working directory listing the file modifications. Write `handoff.md` with your status, observations, logic chain, and test execution results.

When done, send a message to the Project Orchestrator (conversation ID: d1f698d1-d2a9-44c5-b75f-68f6c3e23aae) to report completion.
