# E2E Test Infrastructure: Caelestia Shell Ricing Maximum

This document details the end-to-end (E2E) testing infrastructure, methodology, directory layout, and the test case catalog for Caelestia Shell's ricing maximum features.

---

## 1. Ricing Maximum Features Under Test

The E2E test suite validates the following six core desktop customization and assistant features:

1. **R1: Dynamic Colours & Wallpapers (Material You Color Engine)**
   - Extracts and loads dynamic schemes based on wallpaper analysis.
   - Monitors state files (`scheme.json`, `path.txt`) using a customized `FileView` watcher.
   - Applies transparency rules, color adjustments (e.g. `alterColour`, `getLuminance`), and notifies Hyprland of layer rule updates.

2. **R2: Interactive Workspace Overview Overlay**
   - Displays workspace cards, active toplevels (windows), and monitor structures.
   - Handles drag-and-drop window movements across workspaces, invoking matching IPC calls (`dispatch`).
   - Allows click-to-focus on toplevels or workspaces, cycling special workspaces.

3. **R3: Per-App Audio Mixer & Media Visualizer**
   - Tracks audio streams, input sources, and output sinks via Pipewire node classification.
   - Manages volume adjustment and mute state delegation on active sinks/sources/streams.
   - Triggers desktop toast notifications upon hardware or default route changes.

4. **R4: Unified Control Center**
   - Integrates quick toggles (DND, Wi-Fi, Bluetooth, VPN, Game Mode) and sliders.
   - Handles weather information geocoding (Nominatim fallback) and forecast loading.
   - Manages visual visibility states and layouts.

5. **R5: AI Copilot Sidebar**
   - Facilitates conversational interactions with a local desktop assistant via Ollama or Gemini APIs.
   - Parses markdown JSON block commands (volume, workspace, wallpaper, launcher drawers) and executes shell actions.
   - Manages and clears conversational history.

6. **R6: Screen OCR & Translation**
   - Triggers region capture (`slurp`, `grim`) and runs OCR extraction (`tesseract`).
   - Translates extracted text to target languages and generates contextual explanations.
   - Synthesizes and queries Ollama.

---

## 2. Testing Methodology

The E2E testing framework is designed around system requirements using the following techniques:
- **Offscreen QML Rendering**: Runs the Qt QML engine with `QT_QPA_PLATFORM=offscreen` to test QML modules without spawning a visible window.
- **Mock System Services**: Substitutes real hardware and network backends with QML-registered Python mocks:
  - `MockHyprland`: Mimics workspace/monitor setups, window state mapping, and logs `hyprctl` calls to `/tmp/hyprctl_calls.log`.
  - `Pipewire`: Simulates audio hotplugging, streams, volume levels, and mute states.
  - `MockOllama` & `MockRequests`: Simulates model inference and HTTP services synchronously for consistent, deterministic testing.
  - `OverrideMockProcess`: Intercepts system process executions (like `grim` / `tesseract` for OCR) and handles stdout piping.
- **Hierarchical Verification (4 Tiers)**:
  - *Tier 1 (Feature Coverage)*: Confirms normal happy-path operation.
  - *Tier 2 (Boundary & Corner Cases)*: Exercises extreme inputs, error states, and rate limits.
  - *Tier 3 (Cross-Feature Interaction)*: Validates pairwise integrations (e.g., Copilot trigger adjustments to Audio).
  - *Tier 4 (Real-World Workflows)*: Simulates continuous state transitions (e.g., startup sequence, full OCR pipeline).

---

## 3. Directory Layout

The workspace is organized as follows:
```
/home/execorn/ricing/shell/
├── services/               # Core QML service singletons under test
│   ├── Audio.qml           # Per-app audio routing & mixer
│   ├── Colours.qml         # Dynamic color scheme processor
│   ├── Copilot.qml         # AI assistant integration
│   ├── Hypr.qml            # Hyprland IPC bridge
│   ├── Ocr.qml             # OCR & translation process
│   ├── Wallpapers.qml      # Wallpaper cycle controller
│   └── Weather.qml         # Geolocation & weather forecast
├── components/             # UI elements & popouts
│   ├── Overview.qml        # Workspace card overlay
│   └── ...                 # Other shell UI components
├── tests/                  # Verification files
│   ├── conftest.py         # Global pytest fixtures, QApplication, and QML registrations
│   └── test_ricing.py      # The 72-case E2E test suite
└── TEST_INFRA.md           # This architecture document
```

---

## 4. Full Feature Checklist (72 Test Cases)

Below is the catalog of all 72 tests matching the 4-tier hierarchy:

### Tier 1: Feature Coverage (30 Tests)
- [x] `test_t1_r1_colours_load_scheme` — Load and apply scheme.json colors
- [x] `test_t1_r1_colours_load_preview` — Handle palette preview mode
- [x] `test_t1_r1_wallpapers_set_wallpaper` — Write wallpaper path and trigger reload
- [x] `test_t1_r1_wallpapers_set_random` — Choose a random wallpaper from directories
- [x] `test_t1_r1_wallpapers_preview` — Set temporary preview wallpaper
- [x] `test_t1_r2_hypr_dispatch_workspace` — Dispatch Hyprland workspace change commands
- [x] `test_t1_r2_overview_drag_and_drop` — Verify drag-and-drop window routing
- [x] `test_t1_r2_overview_click_card` — Click cards to switch focus
- [x] `test_t1_r2_hypr_monitor_names` — Retrieve active monitor layout names
- [x] `test_t1_r2_hypr_cycle_special_workspace` — Toggle special scratchpad workspaces
- [x] `test_t1_r3_audio_list_streams` — Query active audio streams from Pipewire
- [x] `test_t1_r3_audio_set_volume` — Adjust output sink volume
- [x] `test_t1_r3_audio_toggle_mute` — Mute and unmute sink devices
- [x] `test_t1_r3_audio_default_sink` — Handle default output sink change
- [x] `test_t1_r3_audio_set_audio_sink_source` — Switch active input source or output sink
- [x] `test_t1_r4_weather_fetch_coords_from_city` — Geocode city to latitude/longitude
- [x] `test_t1_r4_weather_fetch_city_from_coords` — Reverse geocode coordinates to city names
- [x] `test_t1_r4_weather_ipinfo_fallback` — Fallback to IP address location when GPS is unavailable
- [x] `test_t1_r4_weather_fetch_forecast` — Query external weather forecast API
- [x] `test_t1_r4_control_center_toggles` — Trigger Control Center DND, WiFi, and game toggles
- [x] `test_t1_r5_copilot_clear_history` — Clear history list model
- [x] `test_t1_r5_copilot_send_message` — Dispatch prompt and receive mocked AI response
- [x] `test_t1_r5_copilot_action_workspace` — Parse and execute "workspace" action blocks
- [x] `test_t1_r5_copilot_action_volume` — Parse and execute "volume" action blocks
- [x] `test_t1_r5_copilot_action_exec` — Parse and execute "exec" app launch action blocks
- [x] `test_t1_r6_ocr_start_ocr` — Verify starting state changes of OCR
- [x] `test_t1_r6_ocr_capture_success` — Execute screenshot capture and OCR pipeline successfully
- [x] `test_t1_r6_ocr_translate` — Translate extracted OCR text to target language via LLM
- [x] `test_t1_r6_ocr_explain` — Explain extracted OCR text via LLM
- [x] `test_t1_r6_ocr_error_handling` — Gracefully handle empty captures or missing text

### Tier 2: Boundary & Corner Cases (30 Tests)
- [x] `test_t2_r1_colours_invalid_json` — Handle syntax errors in scheme.json loading
- [x] `test_t2_r1_colours_alter_color_extreme` — Clamp extreme layer modifications (pitch black / pure white)
- [x] `test_t2_r1_colours_get_luminance_extreme` — Calculate luminance for boundaries
- [x] `test_t2_r1_colours_cooldown_rate_limit` — Rate limit rapid hyprland rule updates
- [x] `test_t2_r1_wallpapers_empty_path` — Guard against invalid/empty wallpaper paths
- [x] `test_t2_r2_overview_drag_out_of_bounds` — Ignore drag operations targeted to out-of-bounds workspaces
- [x] `test_t2_r2_overview_empty_workspaces` — Handle Overview rendering when no workspaces are active
- [x] `test_t2_r2_overview_drag_same_workspace` — Ignore drag and drop on the same workspace
- [x] `test_t2_r2_hypr_dispatch_empty_cmd` — Ignore empty Hyprland dispatch calls
- [x] `test_t2_r2_hypr_cycle_special_empty` — Do not crash cycling special workspaces when none exist
- [x] `test_t2_r3_audio_volume_clamp` — Clamp volume parameters above 100% or below 0%
- [x] `test_t2_r3_audio_mute_redundant` — Ignore redundant mute/unmute requests
- [x] `test_t2_r3_audio_empty_devices` — Handle mixer actions when zero audio devices are detected
- [x] `test_t2_r3_audio_null_stream_volume` — Ignore volume adjustments on null audio streams
- [x] `test_t2_r3_audio_default_sink_invalid` — Handle default route changes to nonexistent sinks
- [x] `test_t2_r4_weather_search_empty` — Return empty when searching weather for empty city name
- [x] `test_t2_r4_weather_corrupt_json` — Handle invalid geocoding JSON payloads
- [x] `test_t2_r4_weather_to_fahrenheit_boundaries` — Convert extreme temperatures accurately
- [x] `test_t2_r4_weather_nominatim_failure_fallback` — Fallback during nominatim HTTP failures
- [x] `test_t2_r4_control_center_rapid_toggle` — Throttle rapid clicks on Control Center toggles
- [x] `test_t2_r5_copilot_malformed_action_json` — Handle syntax errors in parsed action markdown blocks
- [x] `test_t2_r5_copilot_empty_message` — Ignore empty prompt submissions
- [x] `test_t2_r5_copilot_unknown_action` — Safely skip unsupported AI actions
- [x] `test_t2_r5_copilot_network_timeout` — Handle Ollama timeouts and report connection errors
- [x] `test_t2_r5_copilot_multiple_actions` — Parse and execute multiple combined action JSON blocks
- [x] `test_t2_r6_ocr_translate_empty` — Reject translation requests when OCR text is empty
- [x] `test_t2_r6_ocr_ollama_timeout` — Handle translation request timeouts
- [x] `test_t2_r6_ocr_explain_timeout` — Handle explanation request timeouts
- [x] `test_t2_r6_ocr_explain_corrupt` — Handle corrupt LLM responses for text explanation
- [x] `test_t2_r6_ocr_resets` — Ensure startOcr clears preceding translation and error states

### Tier 3: Cross-Feature / Pairwise Integration (7 Tests)
- [x] `test_t3_copilot_volume_triggers_audio` — AI copilot actions trigger audio mixer state changes
- [x] `test_t3_copilot_wallpaper_cycles_colours` — AI copilot wallpaper changes cycle colour palettes
- [x] `test_t3_ocr_translation_updates_copilot` — Extracted OCR text feeds into Copilot prompt context
- [x] `test_t3_weather_geocoding_triggers_theme` — Changing geocoded location updates day/night theme modes
- [x] `test_t3_audio_mute_updates_overview` — Mixer mute actions toggle Overview indicators
- [x] `test_t3_overview_drag_triggers_colours` — Dragging windows to workspaces refreshes Material You layer configurations
- [x] `test_load_all_services` — Engine successfully loads and resolves all service singletons

### Tier 4: Real-World Workflows (5 Tests)
- [x] `test_t4_copilot_wallpaper_color_pipeline` — Full pipeline: AI command -> cycles wallpaper -> triggers dynamic colours update
- [x] `test_t4_ocr_translate_explain_workflow` — Full workflow: Capture screen -> extract text -> translate -> explain
- [x] `test_t4_overview_drag_mixer_control` — Move application window on workspace and adjust its specific stream volume
- [x] `test_t4_system_startup_weather_audio` — Startup workflow: load default devices -> load geo-location -> fetch weather
- [x] `test_t4_copilot_mic_mute_launcher` — Combined AI actions: mute microphone and open the application launcher drawer
