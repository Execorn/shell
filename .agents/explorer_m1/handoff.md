# Handoff Report — Codebase Audit & Baseline Test Verification

This report summarizes the findings of the codebase audit and the E2E baseline test verification.

## 1. Observation

### E2E Test Suite Execution
We executed the pytest suite command:
`QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_ricing.py`
The tool output reported:
```
tests/test_ricing.py ...................................................... [ 70%]
.....................                                                       [100%]
============================== 72 passed in 3.21s ==============================
```

### Audited Code Findings

#### A. QQmlListProperty `.find` Crash Risk
- **Location**: `services/Hypr.qml` Line 27:
  ```qml
  readonly property HyprKeyboard keyboard: extras && extras.devices && extras.devices.keyboards ? extras.devices.keyboards.find(kb => kb.main) : null
  ```
- **Definition**: `plugin/src/Caelestia/Internal/hyprdevices.hpp` Line 58:
  ```cpp
  Q_PROPERTY(QQmlListProperty<caelestia::internal::hypr::HyprKeyboard> keyboards READ keyboards NOTIFY keyboardsChanged)
  ```
- **Test Mock**: `tests/test_ricing.py` Line 367 and `tests/conftest.py` Line 708:
  ```python
  @Property('QVariantList', notify=keyboardsChanged)
  def keyboards(self): return self._keyboards
  ```
- **Note**: A similar `.find` on `keyboards` also exists in `modules/bar/popouts/kblayout/KbLayoutModel.qml` lines 182 and 200.

#### B. Pure Black Divide-by-Zero in Colours.qml
- **Location**: `services/Colours.qml` Lines 37-41:
  ```qml
  function alterColour(c: color, a: real, layer: int): color {
      const luminance = getLuminance(c);
      const offset = (!light || layer == 1 ? 1 : -layer / 2) * (light ? 0.2 : 0.3) * (1 - transparency.base) * (1 + wallLuminance * (light ? (layer == 1 ? 3 : 1) : 2.5));
      const scale = (luminance + offset) / luminance;
  ```
  If `luminance === 0` (e.g. for pure black `#000000`), `scale` evaluates to `Infinity` or `NaN`.

#### C. Lack of XMLHttpRequest Timeouts
- **Location**: `services/Copilot.qml` Lines 34-89 (Ollama connection) and Lines 91-158 (Gemini connection).
- **Observation**: No `timeout` property is set on the `XMLHttpRequest` instances, meaning if local Ollama or the Gemini API hangs, the QML UI thread is blocked and concurrency queue limits (`activeRequestsCount >= 4` check on line 161) are permanently frozen.

#### D. Hardcoded Script Path in Wallpapers.qml
- **Location**: `services/Wallpapers.qml` Line 45:
  ```qml
  Quickshell.execDetached(["/home/execorn/ricing/shell/scripts/apply-theme.py", "--wallpaper", path]);
  ```
  This hardcodes the path to the user's home directory.

#### E. Unprotected JSON Parsing and Silent Failures in Weather.qml
- **Location**: `services/Weather.qml` Lines 48-55, 69-79, 82-93, 99-109, 117-163.
- **Observation**: Inside success callbacks for `Requests.get(...)`, `JSON.parse(text)` is called directly without a `try/catch` block. Furthermore, most `Requests.get(...)` calls do not supply a third `onError` argument, failing silently on network errors.

#### F. NaN Coordinates in Overview.qml
- **Location**: `modules/overview/Overview.qml` Lines 260-263:
  ```qml
  readonly property real scaleX: (modelData.lastIpcObject?.at?.[0] - mX) * (grid.cardWidth / mW)
  readonly property real scaleY: (modelData.lastIpcObject?.at?.[1] - mY) * (grid.cardHeight / mH)
  readonly property real scaleW: (modelData.lastIpcObject?.size?.[0]) * (grid.cardWidth / mW)
  readonly property real scaleH: (modelData.lastIpcObject?.size?.[1]) * (grid.cardHeight / mH)
  ```
  If `modelData.lastIpcObject` or its `at` / `size` array is missing/undefined, these values evaluate to `NaN` and propagate to item geometry properties, causing rendering glitches and warning logs.

---

## 2. Logic Chain

1. **Test Passing status**: Running the pytest E2E suite command verified that 72/72 tests passed.
2. **Mock discrepancy**: Comparing the C++ definition of `keyboards` (`QQmlListProperty`) with the Python test mock (`QVariantList`) reveals that the tests run in an environment where `keyboards` is a standard JS array.
3. **TypeError**: In standard QML, `QQmlListProperty` does not have standard JS Array prototype functions like `.find()`. In production, this causes a runtime crash (`TypeError: Property 'find' of object ... is not a function`) when accessing `Hypr.keyboard`.
4. **Pure Black crash risk**: `getLuminance(c)` returns `0` for pure black. Because `alterColour` does not check for `luminance === 0` before division, `scale` becomes `Infinity`/`NaN`. Passing `NaN` to `Qt.rgba()` creates invalid colors.
5. **XMLHttp/Process Timeout vulnerability**: The lack of timeouts on XMLHttpRequests in `Copilot.qml` and `Ocr.qml`, as well as on processes (like `caelestia` or `wpctl`), means that any hung network endpoint or process blocks QML state changes permanently.
6. **Path Typo**: The audit target `components/Overview.qml` was not found at that path; searching confirmed its actual location is `modules/overview/Overview.qml`.

---

## 3. Caveats

- We only performed a read-only investigation and did not write or modify the source code files.
- We assumed that the production C++ environment uses the standard Qt 6 QML JS engine behavior where `QQmlListProperty` does not inherit from `Array.prototype`.

---

## 4. Conclusion

The current E2E test suite passes 100% on the baseline, but the codebase has several hidden robustness bugs and a critical runtime crash threat in production due to the `QQmlListProperty` mismatch. Address the `.find` call on `keyboards`, fix the `alterColour` divide-by-zero, configure `XMLHttpRequest` timeouts, and resolve the hardcoded script path in `Wallpapers.qml`.

---

## 5. Verification Method

- **Command**:
  `QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_ricing.py`
  (Verifies baseline tests pass).
- **Manual Inspection**:
  Verify files `services/Hypr.qml` (line 27), `services/Colours.qml` (line 41), and `services/Wallpapers.qml` (line 45) to inspect the reported vulnerabilities.
