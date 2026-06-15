# Codebase Audit Report

## 1. Summary of Findings
We have completed a comprehensive read-only audit of the 8 requested QML files. The E2E baseline test suite currently passes all 72 tests; however, our audit has revealed critical, latent production issues—including a runtime crash risk in `Hypr.qml` caused by a mismatch between the production C++ `QQmlListProperty` and the test suite's `QVariantList` mock, a potential divide-by-zero that leads to `NaN` colors in `Colours.qml`, and a lack of request timeouts in QML network operations (`XMLHttpRequest` and custom `Requests`).

---

## 2. Baseline E2E Test Results
- **Command Run**: `QT_QPA_PLATFORM=offscreen uv run --with PySide6 --with pytest pytest tests/test_ricing.py`
- **Result**: `72 passed in 3.21s`
- **Status**: **PASSING**
- **Note on Coverage**: While the tests pass, the mock environment does not perfectly replicate the C++ plugin types (especially `QQmlListProperty`), which masked type-safety issues that would cause runtime crashes in production.

---

## 3. Detailed File Audits

### 3.1. `services/Audio.qml`
- **External Commands**:
  - Sets volume and mute via `wpctl`: `wpctl set-volume <id> <vol>` and `wpctl set-mute <id> <mute>`.
  - **Failure Handling**: If `wpctl` is missing or fails, the shell does not report errors. Additionally, `customVolume` and `customMuted` will remain locked to their override values because the actual volume will never update to trigger the reset.
- **Type-Safety & Signatures**:
  - Property declarations like `sinks`, `sources`, `streams`, `physicalSinks`, and `physicalSources` are defined as `var` arrays.
  - Parameters like `amount` in `incrementVolume(amount: var)` use `var` to support fallback logic (`amount || GlobalConfig.services.audioIncrement`), which is appropriate since passing `undefined` is allowed.
- **Fallback Logic**:
  - If `Pipewire` is unavailable or fails, it falls back gracefully by returning `null` or setting muted to `false` / volume to `0` and aborting sync operations safely via checks like `if (!Pipewire || !Pipewire.nodes) return;`.

### 3.2. `services/Colours.qml`
- **Potential Crashes / Unhandled Errors**:
  - **Divide by Zero & NaN Propagation**: In `alterColour(c: color, a: real, layer: int)`:
    ```js
    const luminance = getLuminance(c);
    const offset = ...;
    const scale = (luminance + offset) / luminance;
    ```
    If `c` is pure black (`#000000` or `#00000000`), `getLuminance(c)` returns `0`. This causes `scale` to evaluate to `Infinity` or `NaN`.
    Consequently, `r`, `g`, and `b` evaluate to `NaN` (due to `0 * Infinity` or `0 * NaN`).
    `Qt.rgba(NaN, NaN, NaN, a)` is then called, which returns an invalid color object. This leads to warning spam and broken visual bindings in QML.
- **External Commands**:
  - Runs `caelestia scheme set --notify -m <mode>` detached. Fails silently if `caelestia` binary is missing.

### 3.3. `services/Copilot.qml`
- **Potential Crashes / Unhandled Errors**:
  - **Lack of XMLHttpRequest Timeouts**: XMLHttpRequests for both Gemini and Ollama lack `.timeout` properties or `ontimeout` handlers. If the endpoints are slow or hang, the request queue remains blocked (`activeRequestsCount` stays positive, blocking the maximum concurrency limit of 4).
  - **Bracket Notation Property Writes**: In `executeSingleAction`, it does `vis[act.name] = act.state` on a `DrawerVisibilities` QObject. This works in most Qt/QML versions but is less robust than explicit property setters and can emit warnings.
- **Fallback Logic**:
  - Properly detects `GEMINI_API_KEY` presence. If missing, or if Gemini API requests fail (network errors, JSON parsing errors, or status code !== 200), it successfully triggers the local Ollama fallback via `triggerFallback()`.

### 3.4. `services/Hypr.qml`
- **Potential Crashes / Unhandled Errors**:
  - **Critical Production Crash Risk (QQmlListProperty vs Array)**: On line 27, it accesses:
    ```qml
    readonly property HyprKeyboard keyboard: extras && extras.devices && extras.devices.keyboards ? extras.devices.keyboards.find(kb => kb.main) : null
    ```
    In production C++ (`hyprdevices.hpp`), `keyboards` is exposed as a `QQmlListProperty<caelestia::internal::hypr::HyprKeyboard>`.
    Unlike standard JavaScript arrays, `QQmlListProperty` in Qt 6 does **not** have the `.find()` method. Calling `.find()` will throw:
    `TypeError: Property 'find' of object ... is not a function`
    This crash was masked in tests because the test suite mocked `keyboards` as a Python `QVariantList` (which converts to a standard JS Array).
    *Note: A similar issue occurs in `modules/bar/popouts/kblayout/KbLayoutModel.qml` lines 182 and 200.*
- **Fallback Logic**:
  - Keyboard rules file path defaults to `/usr/share/X11/xkb/rules/base.lst` if `CAELESTIA_XKB_RULES_PATH` is unset. If the file is missing, the load fails gracefully, and `kbLayout` falls back to `"??"`.

### 3.5. `services/Ocr.qml`
- **Potential Crashes / Unhandled Errors**:
  - **Hardcoded Temp File / Permission Collisions**: Writes captured screen to `/tmp/ocr_capture.png`. If multiple users are logged into the system, or if permissions block overwriting this file, OCR will fail.
  - **Discards Diagnosis Info**: Discards `tesseract` error output (`2>/dev/null`), making it impossible to diagnose missing language packs.
  - **Missing Dependencies**: If `slurp`, `grim`, `tesseract`, or `wl-copy`/`wl-paste` are missing, the command fails. The user is shown a generic "No text detected, or operation cancelled" error rather than a specific warning about missing dependencies.
  - **No Network Timeouts**: Similar to Copilot, XMLHttpRequests to local Ollama lack timeouts, which can freeze status variables.

### 3.6. `services/Wallpapers.qml`
- **Potential Crashes / Unhandled Errors**:
  - **Hardcoded Absolute Path**: The theme application command is hardcoded to a specific user's home directory:
    `"/home/execorn/ricing/shell/scripts/apply-theme.py"`
    This will fail immediately if the shell is run by a different user or from a different location.
- **Fallback Logic**:
  - If the wallpaper path file cannot be loaded or is empty, it correctly falls back to `assets/wallpaper.webp` and sets `actualCurrent = fallback`.

### 3.7. `services/Weather.qml`
- **Potential Crashes / Unhandled Errors**:
  - **Unhandled JSON Parsing Exceptions**: Success callbacks for `Requests.get` do not wrap `JSON.parse` in `try/catch`. If an API returns non-JSON text (like an HTML error page from Openstreetmap or Open-Meteo), a syntax error is thrown, interrupting QML execution.
  - **No Error Handling**: The callbacks for `Requests.get` in `reload()`, `fetchCoordsFromCity()`, and `fetchWeatherData()` do not provide the optional `onError` callback. Under network-down conditions, they fail silently.
  - **QNetworkRequest Timeouts**: The underlying C++ helper `Requests::get` in `requests.cpp` connects to `QNetworkReply::finished` without setting a timeout on the `QNetworkAccessManager` request, making it susceptible to hanging indefinitely on slow connections.

### 3.8. `modules/overview/Overview.qml` (Audited from `modules/overview/Overview.qml`)
- **Potential Crashes / Unhandled Errors**:
  - **NaN Geometry Warnings / Render Glitches**: The window thumbnail Repeater calculates coordinates/sizes using scaling formulas:
    ```qml
    readonly property real scaleX: (modelData.lastIpcObject?.at?.[0] - mX) * (grid.cardWidth / mW)
    ```
    If a window has no `lastIpcObject` yet (e.g. immediately upon opening), or if monitor geometry details are unavailable, `scaleX`, `scaleY`, `scaleW`, and `scaleH` become `NaN`. Passing `NaN` coordinates to the delegate item leads to console warning spam and rendering glitches.
  - **Strict Type Checking**: Compares monitor ID using strict equality (`===`): `monitors[i].id === monitorId`. A mismatch between string and number representation will prevent the window from being displayed in the correct thumbnail.

---

## 4. Key Recommendations

1. **Fix QQmlListProperty `.find` Calls**:
   Convert the list property to a standard JS array before searching, e.g.:
   `[...extras.devices.keyboards].find(kb => kb.main)` or implement a custom search helper.
2. **Add Guard for Pure Black in `Colours.qml`**:
   Check if `luminance` is `0` before division in `alterColour` to prevent `NaN` values.
3. **Use Robust File Paths in `Wallpapers.qml`**:
   Resolve `apply-theme.py` dynamically using `Quickshell.shellPath()` or environment variables rather than hardcoding `/home/execorn/...`.
4. **Implement XMLHttpRequest Timeouts**:
   Set `xhr.timeout = 10000;` and define `xhr.ontimeout` callbacks in `Copilot.qml` and `Ocr.qml`.
5. **Catch JSON Parsing Errors**:
   Wrap `JSON.parse` in `try/catch` blocks inside `Weather.qml`'s network callbacks.
6. **Provide NaN Fallbacks for Thumbnail Coordinates**:
   Use safety defaults like `x: isNaN(scaleX) ? 0 : scaleX` in `Overview.qml`.
7. **Use Unique Paths in `Ocr.qml`**:
   Instead of `/tmp/ocr_capture.png`, use a unique user-specific filename or path to avoid conflicts.
