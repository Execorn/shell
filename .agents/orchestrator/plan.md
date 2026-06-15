# Action Plan - Caelestia Quickshell Robustness Sweep

This plan outlines the steps for executing the code review, robustness sweep, and bug-fixing pass on the "Ricing Maximum" features (the 6 Pillars) of Caelestia Quickshell.

## Objectives
1. Ensure all 6 pillars are robust and crash-free.
2. Resolve potential QML TypeErrors, reference errors, and implicit conversions.
3. Ensure process invocations (`Process`) handle failures, missing commands, and timeout scenarios gracefully.
4. Add robust fallbacks when external services are slow or unavailable.
5. Audit and improve QML type signatures.
6. Verify via pytest that all 72 E2E test cases pass without regressions.

---

## Milestones

### Milestone 1: Codebase Exploration & Initial Test Verification
- **Goal**: Run the initial test suite and explore the codebase to identify robustness/type safety bugs.
- **Tasks**:
  1. Spawn an Explorer agent to run the baseline E2E test suite using `QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_pricing.py` (or whatever exact command matches).
  2. The Explorer will inspect the 6 core service files (`services/Audio.qml`, `services/Colours.qml`, `services/Copilot.qml`, `services/Hypr.qml`, `services/Ocr.qml`, `services/Wallpapers.qml`, `services/Weather.qml`) and `components/Overview.qml`.
  3. Identify any issues related to process invocation failures, missing fallbacks, or type safety issues.
- **Verification**: Handoff report from the Explorer detailing test results and findings.

### Milestone 2: Robustness Fixes & Style Audit Implementation
- **Goal**: Address all findings from Milestone 1 and implement robust error-handling, process wrappers, and QML type-safety.
- **Tasks**:
  1. Spawn a Worker agent to apply code changes.
  2. Implement proper exit status / error handling for all external commands: `matugen`, `hyprctl`, `wpctl`, `wlsunset`, `grim`, `slurp`, `tesseract`.
  3. Implement fallback logic for offline/slow backends (PipeWire, NetworkManager, Bluez, Gemini API, local Ollama).
  4. Perform QML Type-Safety audit (convert `var` where too permissive to specific types like `real`, `int`, `string`, `bool`, etc.).
  5. Require the Worker to run the E2E test suite to verify no regressions are introduced.
- **Verification**: Worker handoff report showing successful builds/tests.

### Milestone 3: Multi-Agent Review, Challenge, & Forensic Audit
- **Goal**: Ensure the highest quality and compliance using Reviewers, Challengers, and the Forensic Auditor.
- **Tasks**:
  1. Spawn 2 Reviewers to review the correctness of changes and verify code style.
  2. Spawn a Challenger to execute stress/differential testing or verify edge cases.
  3. Spawn a Forensic Auditor (`teamwork_preview_auditor`) to verify integrity.
- **Verification**: Clean verdict from the Forensic Auditor, positive verdicts from Reviewers, and zero issues from the Challenger.
