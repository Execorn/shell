# E2E Test Infra: Caelestia Shell and Cheatsheet

## Test Philosophy
- **Opaque-box, requirement-driven**: The testing framework is designed around system requirements, without depending on the internal implementation design of Quickshell or the parser's internal syntax mapping.
- **Methodology**: Category-Partition + BVA (Boundary Value Analysis) + Pairwise + Workload/Stress Testing.
  - *Category-Partition*: Dividing inputs (Hyprland configuration lines, Pipewire node updates, IPC command triggers) into discrete functional categories.
  - *Boundary Value Analysis*: Testing maximum, minimum, empty, invalid, and recursive values.
  - *Pairwise*: Testing combinations of key features (e.g. parser outputs vs. UI renders, active sink changes vs. toast notifications).
  - *Workload/Stress*: Simulating high-frequency events, deep recursion, and large inputs.

## Feature Inventory
We have identified 25 distinct features (N=25). We will implement a 4-tier test case hierarchy targeting at least 288 test cases (Tier 1: 125, Tier 2: 125, Tier 3: 25, Tier 4: 13).

### Feature Inventory Mapping Table
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | Variable Declaration Extraction | `parse_keybinds.py` lines 250-255 & 360-367 | `test_var_extract_...` (1-5) | `test_t2_var_extract_...` (1-5) | `test_t3_parse_invalid_vars_...` |
| 2 | Recursive Variable Resolution | `parse_keybinds.py` lines 210-233 | `test_var_resolve_...` (1-5) | `test_t2_var_resolve_...` (1-5) | `test_t3_recursive_variables_...` |
| 3 | Variable Cycle/Recursion Guard | `parse_keybinds.py` lines 224-230 | `test_cycle_guard_...` (1-5) | `test_t2_cycle_...` (1-5) | `test_t3_parse_invalid_vars_...` |
| 4 | Keybinding Line Parse and Split | `parse_keybinds.py` lines 370-388 | `test_bind_split_...` (1-5) | `test_t2_bind_split_...` (1-5) | `test_t3_cheatsheet_parser_...` |
| 5 | Modifier Normalization | `parse_keybinds.py` lines 10-26 | `test_mod_norm_...` (1-5) | `test_t2_mod_norm_...` (1-5) | `test_t3_cheatsheet_parser_...` |
| 6 | Internal Keybinding Filtering | `parse_keybinds.py` lines 390-396 | `test_filter_...` (1-5) | `test_t2_filter_...` (1-5) | `test_t3_cheatsheet_parser_...` |
| 7 | Description Association | `parse_keybinds.py` lines 29-128, 149-196, 401-403 | `test_desc_assoc_...` (1-5) | `test_t2_desc_...` (1-5) | `test_t3_recursive_variables_...` |
| 8 | Explicit Section & Category Headers | `parse_keybinds.py` lines 322-337 | `test_header_...` (1-5) | `test_t2_header_...` (1-5) | `test_t3_parse_duplicate_...` |
| 9 | Implicit Category Auto-Routing | `parse_keybinds.py` lines 135-147 & 339-350 | `test_implicit_route_...` (1-5) | `test_t2_implicit_route_...` (1-5) | `test_t3_cheatsheet_parser_...` |
| 10 | JSON Serialization & Integration | `parse_keybinds.py` lines 554-556 | `test_json_...` (1-5) | `test_t2_json_...` (1-5) | `test_t3_parse_invalid_vars_...` |
| 11 | Pipewire Node Tracking & Classification | `services/Audio.qml` lines 17-21 & 252-293 | `test_pw_track_...` (1-5) | `test_t2_pw_track_...` (1-5) | `test_t3_hotplug_headphones_...` |
| 12 | Device Fallback Policy | `services/Audio.qml` lines 94-129 | `test_fallback_...` (1-5) | `test_t2_fallback_...` (1-5) | `test_t3_hotplug_headphones_...` |
| 13 | Active Sink Resolution (Virtual Routing) | `services/Audio.qml` lines 131-169 | `test_active_sink_...` (1-5) | `test_t2_active_sink_...` (1-5) | `test_t3_virtual_routing_...` |
| 14 | Volume Control Delegation | `services/Audio.qml` lines 42-57, 59-66, 92, 180-185 | `test_volume_delegate_...` (1-5) | `test_t2_volume_...` (1-5) | `test_t3_ui_slider_update_...` |
| 15 | Mute/Unmute Control Delegation | `services/Audio.qml` lines 187-199 & 205-207 | `test_mute_delegate_...` (1-5) | `test_t2_mute_...` (1-5) | `test_t3_ui_mute_action_...` |
| 16 | Input Source Management | `services/Audio.qml` lines 32-34, 67-80, 86-88 | `test_source_...` (1-5) | `test_t2_source_...` (1-5) | `test_t3_input_source_...` |
| 17 | Stream Volume & Metadata Management | `services/Audio.qml` lines 180-187, 196-199, 201-213 | `test_stream_...` (1-5) | `test_t2_stream_...` (1-5) | `test_t3_stream_destruction_...` |
| 18 | Desktop Toast Notifications | `services/Audio.qml` lines 219-243 | `test_toast_...` (1-5) | `test_t2_toast_...` (1-5) | `test_t3_hotplug_headphones_...` |
| 19 | Audio Output Cycling | `services/Audio.qml` lines 171-178 | `test_cycle_next_...` (1-5) | `test_t2_cycle_...` (1-5) | `test_t3_audio_output_...` |
| 20 | IPC Integration | `services/Audio.qml` lines 319-335 | `test_ipc_...` (1-5) | `test_t2_ipc_...` (1-5) | `test_t3_ipc_volume_update_...` |
| 21 | Output Device List & Selector | `modules/bar/popouts/Audio.qml` lines 40-53 | `test_ui_sink_...` (1-5) | `test_t2_ui_sink_...` (1-5) | `test_t3_audio_output_...` |
| 22 | Input Device List & Selector | `modules/bar/popouts/Audio.qml` lines 61-72 | `test_ui_source_...` (1-5) | `test_t2_ui_source_...` (1-5) | `test_t3_input_source_...` |
| 23 | Volume Slider Control | `modules/bar/popouts/Audio.qml` lines 74-78 & 91-99 | `test_ui_slider_...` (1-5) | `test_t2_ui_slider_...` (1-5) | `test_t3_ui_slider_update_...` |
| 24 | Mouse Wheel Volume Adjust | `modules/bar/popouts/Audio.qml` lines 80-90 | `test_ui_wheel_...` (1-5) | `test_t2_ui_wheel_...` (1-5) | `test_t3_mouse_wheel_adjust_...` |
| 25 | Popout Control Actions | `modules/bar/popouts/Audio.qml` lines 101-111 | `test_ui_popout_...` (1-5) | `test_t2_ui_popout_...` (1-5) | `test_t3_ui_mute_action_...` |

---

## Test Hierarchy Specification

### Tier 1: Functional & Unit Tests (125 Cases)
These tests target the direct, happy-path functionality of each feature under normal operating conditions.

#### Feature 1: Variable Declaration Extraction
- `test_var_extract_standard`: Verify parsing of standard `$name = value` lines.
- `test_var_extract_whitespace`: Verify variable extraction containing spaces and tabs around variables.
- `test_var_extract_inline_comment`: Verify that inline comments are correctly stripped from the variable value.
- `test_var_extract_unicode`: Verify extracting variable values containing unicode characters.
- `test_var_extract_multiple`: Verify extracting multiple variables from multiple config files.

#### Feature 2: Recursive Variable Resolution
- `test_var_resolve_single`: Verify basic single-level replacement of `$name` with its defined value.
- `test_var_resolve_multi`: Verify multiple distinct variable references in a single string are replaced.
- `test_var_resolve_nested`: Verify variables referencing other variables resolve to the terminal value.
- `test_var_resolve_undefined`: Verify that undefined variables (e.g. `$nonexistent`) remain unresolved.
- `test_var_resolve_mixed`: Verify resolution of a mix of variables and raw text.

#### Feature 3: Variable Cycle/Recursion Guard
- `test_cycle_guard_direct`: Verify that a self-referential variable (e.g. `$a = $a`) stops resolution immediately.
- `test_cycle_guard_indirect`: Verify circular definitions (e.g. `$a = $b`, `$b = $a`) are detected and left unresolved.
- `test_cycle_guard_deep`: Verify circularity detection in deep chains (e.g. `$a -> $b -> $c -> $a`).
- `test_cycle_guard_recovery`: Verify that detecting a cycle in one variable does not prevent resolving other valid variables.
- `test_cycle_guard_limit`: Verify that variables nested up to 50 levels (below python stack limit) resolve successfully.

#### Feature 4: Keybinding Line Parse and Split
- `test_bind_split_standard`: Verify splitting a standard `bind = mods, key, dispatcher, arguments` line.
- `test_bind_split_no_args`: Verify parsing of keybindings without arguments.
- `test_bind_split_special_chars`: Verify splitting lines containing commas in the argument field.
- `test_bind_split_invalid_format`: Verify that keybindings with fewer than 3 elements are safely skipped.
- `test_bind_split_multiple_delimiters`: Verify handling of mixed separators in the modifier group.

#### Feature 5: Modifier Normalization
- `test_mod_norm_lower`: Verify modifier names are converted to uppercase (e.g., `super` -> `SUPER`).
- `test_mod_norm_alternative`: Verify alternative modifier name mappings (e.g., `mod4` -> `SUPER`, `meta` -> `ALT`).
- `test_mod_norm_multiple`: Verify normalization of multi-modifier arrays.
- `test_mod_norm_variable`: Verify that variable modifier names starting with `$` are preserved as-is.
- `test_mod_norm_unknown`: Verify that unknown modifiers are capitalized as fallback.

#### Feature 6: Internal Keybinding Filtering
- `test_filter_interrupt`: Verify keybinds containing the action "interrupt" are ignored.
- `test_filter_catchall`: Verify keybinds containing the key name "catchall" are ignored.
- `test_filter_mouse_actions`: Verify that mouse dragging/clicking bindings (e.g., `mouse:272`) are ignored.
- `test_filter_mouse_scroll`: Verify that mouse scroll bindings (e.g., `mouse_down`) are ignored.
- `test_filter_empty`: Verify that lines with empty binding targets are ignored.

#### Feature 7: Description Association
- `test_desc_assoc_inline`: Verify that inline comments are bound as the keybinding's description.
- `test_desc_assoc_accumulated`: Verify that preceding block comments are accumulated and bound as description.
- `test_desc_assoc_friendly_fallback`: Verify fallback to friendly descriptions for known default actions.
- `test_desc_assoc_exec_fallback`: Verify fallback descriptions for generic `exec` launchers.
- `test_desc_assoc_workspace_fallback`: Verify fallback descriptions for workspace switchers.

#### Feature 8: Explicit Section & Category Headers
- `test_header_section_explicit`: Verify parsing of explicit section headers (`## Section` or `# Section: Title`).
- `test_header_category_explicit`: Verify parsing of explicit category headers (`# Category: Title`).
- `test_header_case_insensitive`: Verify case-insensitivity in header tags.
- `test_header_hierarchy`: Verify that bindings are nested under the most recently declared section and category.
- `test_header_duplicate_prevention`: Verify that duplicate section names are consolidated.

#### Feature 9: Implicit Category Auto-Routing
- `test_implicit_route_window`: Verify routing of window-related comments to the "Window Management" section.
- `test_implicit_route_system`: Verify routing of system-related comments (volume, media) to the "System" section.
- `test_implicit_route_app`: Verify routing of app-related comments to the "Applications" section.
- `test_implicit_route_utility`: Verify routing of utility comments (screenshots, picker) to the "Utilities" section.
- `test_implicit_route_general`: Verify routing of comments that don't match keywords to the "General" section.

#### Feature 10: JSON Serialization & Integration
- `test_json_write_success`: Verify writing parsed structure to JSON with correct indentation.
- `test_json_schema_validation`: Verify that output matches schema (list of sections containing categories containing keybinds list).
- `test_json_utf8`: Verify proper encoding of UTF-8 characters in the serialized output.
- `test_json_create_directory`: Verify that the parser creates the target output directory if it doesn't exist.
- `test_json_clean_empty`: Verify that empty sections or categories containing no bindings are omitted from the JSON output.

#### Feature 11: Pipewire Node Tracking & Classification
- `test_pw_track_sinks`: Verify tracking and filtering of sink nodes.
- `test_pw_track_sources`: Verify tracking and filtering of source nodes.
- `test_pw_track_streams`: Verify tracking and filtering of stream nodes.
- `test_pw_track_physical`: Verify classification of physical vs. virtual nodes.
- `test_pw_track_node_ready`: Verify that nodes are only added when their `ready` state is true.

#### Feature 12: Device Fallback Policy
- `test_fallback_bluetooth`: Verify selection of Bluetooth sink when available.
- `test_fallback_usb`: Verify selection of USB sink if no Bluetooth sink exists.
- `test_fallback_pci`: Verify selection of PCIe analog-stereo sink if no USB/Bluetooth sink exists.
- `test_fallback_first_valid`: Verify selection of first valid physical sink as final fallback.
- `test_fallback_empty_sinks`: Verify fallback returns empty string when physical sinks array is empty.

#### Feature 13: Active Sink Resolution (Virtual Routing)
- `test_active_sink_direct`: Verify sink is updated to default audio sink when not virtual.
- `test_active_sink_virtual_no_driver`: Verify fallback to preferred default sink when virtual routing has no physical driver.
- `test_active_sink_virtual_with_driver`: Verify matching active sink to the physical driver ID when virtual sink (e.g. EasyEffects) is active.
- `test_active_sink_physical_driver_update`: Verify that `physicalDriverId` is correctly mapped to the matching physical sink ID.
- `test_active_sink_none`: Verify sink resets to null if no sinks are available.

#### Feature 14: Volume Control Delegation
- `test_volume_delegate_direct`: Verify volume updates directly affect the default sink's volume property.
- `test_volume_delegate_virtual`: Verify volume updates invoke `wpctl set-volume` on the physical driver when virtual sink is active.
- `test_volume_delegate_bounds`: Verify volume increments/decrements are clamped within safe ranges (0 to maxVolume).
- `test_volume_delegate_increment`: Verify `incrementVolume` increases active volume by the configured step.
- `test_volume_delegate_decrement`: Verify `decrementVolume` decreases active volume by the configured step.

#### Feature 15: Mute/Unmute Control Delegation
- `test_mute_delegate_direct`: Verify toggling mute directly sets the default sink's audio muted property.
- `test_mute_delegate_virtual`: Verify setting mute state runs `wpctl set-mute` on the physical driver when virtual sink is active.
- `test_mute_delegate_stream`: Verify setting mute state on specific audio streams.
- `test_mute_query_fallback`: Verify mute properties fallback to false when sink is invalid.
- `test_mute_custom_state`: Verify custom mute overrides are correctly prioritized over device state.

#### Feature 16: Input Source Management
- `test_source_set_preferred`: Verify updating preferred default audio source.
- `test_source_volume_control`: Verify modifying volume of the default source.
- `test_source_mute_control`: Verify toggling mute of the default source.
- `test_source_bounds`: Verify source volume adjustments clamp within safe ranges.
- `test_source_fallback`: Verify fallback properties when default source is not ready.

#### Feature 17: Stream Volume & Metadata Management
- `test_stream_list_update`: Verify the list of active streams updates on Pipewire changes.
- `test_stream_volume_get_set`: Verify querying and updating individual stream volumes.
- `test_stream_mute_get_set`: Verify querying and updating individual stream mute states.
- `test_stream_meta_app_name`: Verify application name is extracted from stream properties.
- `test_stream_meta_fallback_desc`: Verify fallback to node description/name when application name is missing.

#### Feature 18: Desktop Toast Notifications
- `test_toast_sink_changed`: Verify notification trigger when output sink changes to a new valid device.
- `test_toast_source_changed`: Verify notification trigger when input source changes.
- `test_toast_suppressed_initial`: Verify notifications are suppressed during initial setup.
- `test_toast_disabled_by_config`: Verify notifications are suppressed when disabled in `GlobalConfig`.
- `test_toast_no_duplicate`: Verify no notifications are sent if the device name is unchanged.

#### Feature 19: Audio Output Cycling
- `test_cycle_next_basic`: Verify cycling moves to the next physical sink in the list.
- `test_cycle_next_wrap`: Verify cycling wraps around to the first sink when reaching the end of the list.
- `test_cycle_next_single`: Verify cycling does nothing when only one physical sink is available.
- `test_cycle_next_empty`: Verify cycling is ignored when no physical sinks are available.
- `test_cycle_next_active`: Verify that cycling updates both preferred sink and active volume reference.

#### Feature 20: IPC Integration
- `test_ipc_cycle`: Verify cycling trigger via IPC `cycleOutput` handler.
- `test_ipc_update_volume`: Verify IPC volume updates apply custom volume level.
- `test_ipc_update_mute`: Verify IPC mute updates apply custom mute state.
- `test_ipc_update_invalid`: Verify IPC ignores invalid float values for volume.
- `test_ipc_registration`: Verify IPC handler binds to the `"audio"` channel correctly.

#### Feature 21: Output Device List & Selector
- `test_ui_sink_list_render`: Verify the sink list repeater populates matching `Audio.physicalSinks`.
- `test_ui_sink_checked_state`: Verify that the active sink has its radio button checked.
- `test_ui_sink_click_set`: Verify clicking a sink radio button calls `Audio.setAudioSink`.
- `test_ui_sink_label_binding`: Verify that the radio button text displays the node's description.
- `test_ui_sink_dynamic_update`: Verify the list of radio buttons updates dynamically on hardware hotplug.

#### Feature 22: Input Device List & Selector
- `test_ui_source_list_render`: Verify the source list repeater populates matching `Audio.physicalSources`.
- `test_ui_source_checked_state`: Verify that the active source has its radio button checked.
- `test_ui_source_click_set`: Verify clicking a source radio button calls `Audio.setAudioSource`.
- `test_ui_source_label_binding`: Verify that the radio button text displays the node's description.
- `test_ui_source_dynamic_update`: Verify the list of source radio buttons updates dynamically.

#### Feature 23: Volume Slider Control
- `test_ui_slider_value_binding`: Verify that the slider value reflects the current active volume.
- `test_ui_slider_interaction`: Verify that slider interaction calls `Audio.setVolume`.
- `test_ui_slider_label_volume`: Verify that the header text displays the active volume percentage (e.g. "Volume (55%)").
- `test_ui_slider_label_muted`: Verify that the header text displays "Muted" when the audio is muted.
- `test_ui_slider_layout`: Verify that the slider expands horizontally to fill parent layout space.

#### Feature 24: Mouse Wheel Volume Adjust
- `test_ui_wheel_scroll_up`: Verify that wheel scroll up invokes `Audio.incrementVolume`.
- `test_ui_wheel_scroll_down`: Verify that wheel scroll down invokes `Audio.decrementVolume`.
- `test_ui_wheel_no_scroll`: Verify no action when there is no vertical scroll delta.
- `test_ui_wheel_clamping`: Verify wheel adjustments respect max volume boundaries.
- `test_ui_wheel_custom_area`: Verify wheel events are accepted across the entire volume adjustment container.

#### Feature 25: Popout Control Actions
- `test_ui_popout_detach_click`: Verify that clicking "Open settings" requests popout detachment.
- `test_ui_popout_token_check`: Verify popout dimension tokens (padding, spacing) load correctly.
- `test_ui_popout_layout_vertical`: Verify that UI elements are aligned in a vertical column layout.
- `test_ui_popout_spacing`: Verify spacing between header labels and controls is applied correctly.
- `test_ui_popout_inactive_color`: Verify that the settings button uses the primary container color.

---

### Tier 2: Boundary & Cycle Recovery Tests (125 Cases)
These tests focus on edge cases, limits, malformed inputs, recovery from loops, and environment error states.

#### Feature 1: Variable Declaration Extraction
- `test_t2_var_extract_unbalanced_quotes`: Variables with trailing or unclosed quotes.
- `test_t2_var_extract_empty_definition`: Variable declarations with no values (e.g. `$var = `).
- `test_t2_var_extract_duplicate_declarations`: Resolving duplicate definitions of the same variable (last-write-wins).
- `test_t2_var_extract_special_symbols_names`: Variable names containing unusual characters or numbers at boundaries.
- `test_t2_var_extract_malformed_lines`: Verify parser ignores lines starting with `$` but missing the `=` operator.

#### Feature 2: Recursive Variable Resolution
- `test_t2_var_resolve_deep_chain`: 100-level nested variable resolution check.
- `test_t2_var_resolve_dollar_no_var`: Strings containing raw `$` symbols that don't match variables (e.g. `$100`).
- `test_t2_var_resolve_whitespace_in_ref`: Variable reference with spaces inside name (e.g., `$var name`).
- `test_t2_var_resolve_multiple_duplicate_refs`: Resolving a variable reference multiple times in the same line.
- `test_t2_var_resolve_empty_resolutions`: Resolving variables that evaluate to empty strings.

#### Feature 3: Variable Cycle/Recursion Guard
- `test_t2_cycle_complex_mesh`: Intertwined circular dependencies (e.g., `$a -> $b -> $c`, `$b -> $d -> $b`).
- `test_t2_cycle_extremely_deep_crash`: Verify the parser behaves predictably when exceeding stack recursion limit (1500 depth).
- `test_t2_cycle_partial_resolution`: Chain where part is cyclic and another part is clean (e.g., `$a = $b + $c`, `$b` is cyclic, `$c` is clean).
- `test_t2_cycle_reentry`: Verify that visited variables tracking works and cleans up correctly during recursion unwind.
- `test_t2_cycle_empty_cycle`: Verification of cycle detection for variables with empty circular assignments.

#### Feature 4: Keybinding Line Parse and Split
- `test_t2_bind_split_too_many_commas`: Split lines containing extra trailing commas.
- `test_t2_bind_split_escaped_commas`: Split lines with escaped commas or backslashes.
- `test_t2_bind_split_empty_fields`: Split lines with empty fields (e.g. `bind = SUPER,,exec,`).
- `test_t2_bind_split_tabs_as_delimiter`: Split lines utilizing combinations of tabs and spaces around commas.
- `test_t2_bind_split_missing_dispatcher`: Bindings containing modifiers and keys but no action/dispatcher.

#### Feature 5: Modifier Normalization
- `test_t2_mod_norm_duplicate_mods`: Handling duplicate modifiers (e.g. `super+super` -> `["SUPER"]`).
- `test_t2_mod_norm_trailing_plus`: Modifier string ending with a dangling `+` symbol (e.g. `super+shift+`).
- `test_t2_mod_norm_space_plus_mix`: Mixed spaces and plus symbols as separators (e.g. `super + shift alt+ctrl`).
- `test_t2_mod_norm_non_standard_case`: Handling erratic casing of modifier names (e.g. `SuPeR` -> `SUPER`).
- `test_t2_mod_norm_only_key`: Parsing keybinding containing zero modifiers (e.g., empty modifier field).

#### Feature 6: Internal Keybinding Filtering
- `test_t2_filter_mixed_case`: Case-insensitive verification of filter keywords (e.g., `InTeRrUpT`, `CaTcHaLl`).
- `test_t2_filter_partial_match`: Ensuring filter does not trigger on substring matches (e.g., "exec mousepad" should not filter as mouse action).
- `test_t2_filter_mouse_key_bounds`: Verify filtering of high-range mouse button indices.
- `test_t2_filter_spaces`: Handling leading/trailing spaces in filtered actions.
- `test_t2_filter_all_ignored`: Parsing files containing only filtered keybindings (resulting in clean empty output).

#### Feature 7: Description Association
- `test_t2_desc_multiline_empty_lines`: Block comments separated by empty lines.
- `test_t2_desc_unfriendly_fallback`: Fallback for completely unrecognized dispatchers.
- `test_t2_desc_special_characters`: Verification of escape characters in descriptions.
- `test_t2_desc_empty_comments`: Handling comments that contain only hashes/whitespace.
- `test_t2_desc_very_long_comment`: Truncation or wrapping checks for extremely long comment descriptions.

#### Feature 8: Explicit Section & Category Headers
- `test_t2_header_empty_section_name`: Handling empty section titles (e.g. `## `).
- `test_t2_header_nested_categories`: Deeply nested category headers without intermediate sections.
- `test_t2_header_leading_trailing_junk`: Headers containing trailing punctuation or comments.
- `test_t2_header_category_no_section`: Category headers defined before any section header.
- `test_t2_header_overwrite_implicit`: Section header overriding previous implicit category routes.

#### Feature 9: Implicit Category Auto-Routing
- `test_t2_implicit_route_priority`: Routing comments matching multiple keywords.
- `test_t2_implicit_route_boundary`: Routing short comments right at the 40-character length limit.
- `test_t2_implicit_route_with_actions`: Comments ending with periods or action keywords (which shouldn't route to categories).
- `test_t2_implicit_route_special_chars`: Category matching with non-ASCII or localized keywords.
- `test_t2_implicit_route_mixed_mode`: Mixed explicit categories and implicit auto-routed categories in one file.

#### Feature 10: JSON Serialization & Integration
- `test_t2_json_write_permission_denied`: Handling errors when writing to write-protected directories.
- `test_t2_json_large_payload`: Parsing and serializing 10,000+ keybindings under memory constraints.
- `test_t2_json_existing_file_lock`: Handling situations where target JSON is locked or read-only.
- `test_t2_json_empty_source`: Running the parser with missing or empty configuration files.
- `test_t2_json_output_corruption_recovery`: Verify target file is not left corrupted if parser crashes mid-write.

#### Feature 11: Pipewire Node Tracking & Classification
- `test_t2_pw_track_duplicate_ids`: Handling nodes with conflicting IDs in the Pipewire dictionary.
- `test_t2_pw_track_rapid_churn`: Rapid addition and removal of nodes in a loop.
- `test_t2_pw_track_null_properties`: Nodes missing the `properties` dictionary or having null keys.
- `test_t2_pw_track_type_flipping`: Sinks changing roles to sources dynamically (or vice versa).
- `test_t2_pw_track_unready_nodes`: Sinks/sources remaining in unready state indefinitely.

#### Feature 12: Device Fallback Policy
- `test_t2_fallback_matching_failures`: Sinks matching none of the naming patterns (e.g., empty names).
- `test_t2_fallback_removal_recovery`: Active sink removal causing fallback selection.
- `test_t2_fallback_all_builtin`: Multiple built-in PCIe sinks and sorting them.
- `test_t2_fallback_unicode_names`: Fallback selection when sink descriptions contain complex unicode names.
- `test_t2_fallback_no_valid_sinks`: Sinks exist but have ready state set to false.

#### Feature 13: Active Sink Resolution (Virtual Routing)
- `test_t2_active_sink_virtual_loop`: Safe handling if physical driver ID points to another virtual sink.
- `test_t2_active_sink_driver_disconnect`: Physical driver sink disconnects while virtual sink remains active.
- `test_t2_active_sink_change_mid_stream`: Active sink changing while stream is actively running.
- `test_t2_active_sink_invalid_driver_id`: `physicalDriverId` set to a non-existent node ID.
- `test_t2_active_sink_no_sinks_left`: Virtual and physical sinks all disconnect simultaneously.

#### Feature 14: Volume Control Delegation
- `test_t2_volume_wpctl_failure`: `wpctl` command fails or returns non-zero code.
- `test_t2_volume_wpctl_timeout`: `wpctl` hanging indefinitely during volume change.
- `test_t2_volume_invalid_max_volume`: Configuration with maxVolume set to a negative or extremely high value.
- `test_t2_volume_node_destroyed_mid_set`: Active sink is destroyed while `setVolume` is running.
- `test_t2_volume_rapid_calls`: Calling `setVolume` 100 times in rapid succession (verifying process debouncing).

#### Feature 15: Mute/Unmute Control Delegation
- `test_t2_mute_wpctl_failure`: `wpctl set-mute` command fails.
- `test_t2_mute_rapid_toggles`: Muting and unmuting repeatedly to check for process locks.
- `test_t2_mute_virtual_driver_none`: Toggling mute when virtual sink is active but no physical driver exists.
- `test_t2_mute_missing_audio_interface`: Nodes lacking the `audio` extension object.
- `test_t2_mute_node_destroyed_mid_set`: Target node is destroyed during mute operation.

#### Feature 16: Input Source Management
- `test_t2_source_empty_sources`: Setting preferred source when source list is empty.
- `test_t2_source_preferred_missing`: Setting preferred source to a non-existent node.
- `test_t2_source_volume_wpctl`: Checking fallback to `wpctl` for sources (if virtual sources exist).
- `test_t2_source_rapid_inputs_plug`: Rapidly plugging/unplugging default input device.
- `test_t2_source_mute_sync`: Verifying mute synchronization when hardware switch changes state.

#### Feature 17: Stream Volume & Metadata Management
- `test_t2_stream_meta_invalid_utf8`: Application names with invalid UTF-8 byte sequences.
- `test_t2_stream_volume_boundary`: Setting stream volume beyond the 0 to 1.0 boundary.
- `test_t2_stream_rapid_lifecycle`: Streams opening and closing within milliseconds.
- `test_t2_stream_null_audio_obj`: Stream nodes containing valid metadata but null `audio` fields.
- `test_t2_stream_duplicate_names`: Multiple distinct streams sharing the exact same application name.

#### Feature 18: Desktop Toast Notifications
- `test_t2_toast_rapid_changes`: Rapidly switching output sinks (verifying notification throttling).
- `test_t2_toast_null_names`: Notification behavior when device description and name are both empty.
- `test_t2_toast_toaster_crash`: Handling exceptions or failures in the external `Toaster` component.
- `test_t2_toast_no_icon`: Behavior when notification icon string is invalid or missing.
- `test_t2_toast_utf8_toasts`: Notifications with localized/UTF-8 character device descriptions.

#### Feature 19: Audio Output Cycling
- `test_t2_cycle_sinks_null_in_list`: Sinks list containing null/invalid elements.
- `test_t2_cycle_nodes_not_ready`: Sinks list contains ready and unready physical sinks.
- `test_t2_cycle_active_sink_outside_list`: Current sink is not in the `physicalSinks` list.
- `test_t2_cycle_rapid_cycles`: Invoking output cycling in an infinite loop.
- `test_t2_cycle_state_sync`: Verification that UI radio buttons sync state immediately after cycling.

#### Feature 20: IPC Integration
- `test_t2_ipc_overflow`: Sending extremely large strings or buffer floods to the IPC handler.
- `test_t2_ipc_malformed_command`: Sending malformed commands or incorrect arguments.
- `test_t2_ipc_concurrent_requests`: Concurrent IPC requests targeting the volume service.
- `test_t2_ipc_reconnect`: IPC handler recovery and re-binding after mock socket disconnection.
- `test_t2_ipc_permission`: IPC commands sent from non-authorized desktop contexts.

#### Feature 21: Output Device List & Selector
- `test_t2_ui_sink_list_empty`: UI rendering when `physicalSinks` list is empty.
- `test_t2_ui_sink_duplicate_ids`: UI response to multiple sinks with duplicate IDs.
- `test_t2_ui_sink_rapid_model_changes`: Rapidly modifying `physicalSinks` model backing.
- `test_t2_ui_sink_long_names_wrap`: Behavior of UI layout and text wrapping with long sink names.
- `test_t2_ui_sink_destruction`: UI behavior when the currently checked radio button's node is destroyed.

#### Feature 22: Input Device List & Selector
- `test_t2_ui_source_list_empty`: UI rendering when `physicalSources` list is empty.
- `test_t2_ui_source_duplicate_ids`: UI response to multiple sources with duplicate IDs.
- `test_t2_ui_source_rapid_model_changes`: Rapidly modifying `physicalSources` model backing.
- `test_t2_ui_source_long_names_wrap`: UI layout and text wrapping with long source names.
- `test_t2_ui_source_destruction`: UI behavior when the checked radio button's source node is destroyed.

#### Feature 23: Volume Slider Control
- `test_t2_ui_slider_nan_volume`: Handling `NaN` volume levels.
- `test_t2_ui_slider_out_of_bounds`: Volume levels exceeding `100%` or less than `0%`.
- `test_t2_ui_slider_rapid_drag`: Simulating rapid slider drag back and forth.
- `test_t2_ui_slider_mute_sync`: Slider state and handles disabling/dimming when muted.
- `test_t2_ui_slider_destruction_race`: Slider destroyed while volume interaction event is firing.

#### Feature 24: Mouse Wheel Volume Adjust
- `test_t2_ui_wheel_extreme_delta`: Extremely large scroll delta values (e.g. fast kinetic scroll).
- `test_t2_ui_wheel_reverse_delta`: Mixed scroll delta directions occurring in rapid sequence.
- `test_t2_ui_wheel_volume_boundary`: Adjusting volume via wheel beyond `0.0` or max volume limits.
- `test_t2_ui_wheel_rapid_events`: High-frequency wheel events over the slider.
- `test_t2_ui_wheel_unfocused`: Wheel events firing when the popout is losing focus.

#### Feature 25: Popout Control Actions
- `test_t2_ui_popout_multiple_clicks`: Rapidly double-clicking "Open settings".
- `test_t2_ui_popout_missing_popouts_prop`: Popout behavior if `popouts` property is not supplied.
- `test_t2_ui_popout_null_tokens`: Safety checks when system tokens fail to load (defaulting gracefully).
- `test_t2_ui_popout_resizing_stress`: Verifying UI layout integrity under extreme parent window sizes.
- `test_t2_ui_popout_detach_fail`: Behavior when settings application fails to launch or detach is rejected.

---

### Tier 3: Integration & Pairwise Interaction Tests (25 Cases)
These tests evaluate the correctness of interfaces and message exchanges between the 3 main categories.

1. `test_t3_parse_volume_keybinds_trigger_service`: Verify that simulated execution of volume bindings output by `parse_keybinds.py` correctly triggers matching volume adjustments in `Audio.qml`.
2. `test_t3_parse_mute_keybind_trigger_service`: Verify that parsed microphone mute toggle keybind successfully executes the command which is handled by `Audio.qml` input source mute delegate.
3. `test_t3_parse_output_cycle_trigger_service`: Verify that cheatsheet keybind for audio output cycling triggers `cycleNextAudioOutput()` on the `Audio` singleton via IPC.
4. `test_t3_audio_output_cycling_updates_ui_selector`: Verify that triggering cycling in `Audio.qml` (Feature 19) updates the checked state of radio buttons in the UI popout (Feature 21) dynamically.
5. `test_t3_ui_slider_update_updates_wpctl_virtual`: Verify that dragging the volume slider (Feature 23) updates `Audio.qml` volume which triggers `wpctl` volume delegation (Feature 14) under virtual sink routing.
6. `test_t3_hotplug_headphones_updates_ui_and_toasts`: Verify that plugging in Bluetooth headphones triggers node tracking (Feature 11), updates fallback selection (Feature 12), and sends a desktop toast (Feature 18).
7. `test_t3_ui_mute_action_updates_slider_label`: Verify that muting a stream in the UI (Feature 25) updates the volume slider header text to "Muted" (Feature 23).
8. `test_t3_ipc_volume_update_reflects_on_ui_slider`: Verify that calling IPC `updateVolume` (Feature 20) updates `Audio.qml` volume and reflects on the UI slider position (Feature 23).
9. `test_t3_virtual_routing_fallback_toasts`: Verify that when an active virtual sink is destroyed, `Audio.qml` falls back to the physical device (Feature 13) and triggers the correct toast notifications (Feature 18).
10. `test_t3_stream_destruction_unmounts_ui`: Verify that when an active stream node is destroyed, the stream properties and UI elements associated with it clean up cleanly without memory leaks or UI freeze.
11. `test_t3_input_source_selection_updates_ui_checked`: Verify that changing preferred input source in the service (Feature 16) updates the radio button selection in the input device selector UI (Feature 22).
12. `test_t3_mouse_wheel_adjust_updates_wpctl_virtual`: Verify that scrolling the mouse wheel on the slider (Feature 24) triggers volume updates which are delegated to the physical card via `wpctl` (Feature 14).
13. `test_t3_parse_invalid_vars_does_not_break_json_schema`: Verify that malformed variables in parsing (Feature 3) do not produce invalid JSON schemas that break cheatsheet UI loading (Feature 10).
14. `test_t3_empty_audio_devices_disables_ui_controls`: Verify that when no physical audio output/input devices are tracked (Feature 11), the UI sliders and radio buttons are disabled and display placeholders (Feature 21 & 22).
15. `test_t3_ipc_mute_toggle_syncs_with_ui_checked_state`: Verify that muting via IPC (Feature 20) correctly syncs and updates the muted text display in the popout (Feature 23).
16. `test_t3_bluetooth_unplug_causes_fallback_toast`: Verify that unplugging a bluetooth device causes fallback to built-in audio (Feature 12) and displays a toast naming the new default device (Feature 18).
17. `test_t3_parse_duplicate_categories_consolidates_ui_sections`: Verify that the parser merging duplicate categories (Feature 8) displays consolidated headers in the cheatsheet UI.
18. `test_t3_volume_slider_clamping_prevents_wpctl_overflow`: Verify that dragging the volume slider past max volume clamps values in `Audio.qml` (Feature 14) and prevents spawning `wpctl` with invalid arguments.
19. `test_t3_stream_metadata_change_updates_ui_label`: Verify that if an active stream's application name changes, the corresponding label in the UI updates dynamically.
20. `test_t3_recursive_variables_in_binds_resolve_to_exec_fallback`: Verify that deep recursive variables in keybinds (Feature 2) resolve to the final commands and fallback to proper descriptions (Feature 7).
21. `test_t3_cycle_next_during_device_plug`: Verify that cycling audio outputs (Feature 19) during physical sink hotplugging (Feature 11) resolves to the correct next active sink.
22. `test_t3_ipc_set_volume_to_zero_updates_mute_state`: Verify that IPC setting volume to `0.0` (Feature 20) is reflected as volume `0%` in the UI (Feature 23) but does not automatically flag the device as muted.
23. `test_t3_unready_nodes_ignored_by_fallback_policy`: Verify that unready nodes tracked by Pipewire (Feature 11) are ignored by the device fallback policy (Feature 12) and do not appear in the UI list (Feature 21).
24. `test_t3_wpctl_process_handling_prevents_ui_blocking`: Verify that triggering multiple rapid volume changes from the UI slider (Feature 23) handles `wpctl` processes asynchronously without freezing the UI thread.
25. `test_t3_cheatsheet_parser_ignores_internal_keybinds_but_maps_custom`: Verify that the parser filters internal bindings (Feature 6) but successfully maps custom user bindings to the correct Category/Section layout.

---

## Test Architecture

### Test Runner
- **Cheatsheet Parser Tests**: Executed using **Python `pytest`**. The tests simulate the execution of `parse_keybinds.py` as a subprocess, feeding it test configurations and validating the generated JSON file schema and data structures.
- **Audio Service and UI Components**: Verified using a custom **PySide6/QML engine test runner**. This runner sets up a Qt event loop, registers mocks, loads the QML files (`Audio.qml` and `Audio.qml` popout UI), and asserts state updates and signal emissions.

### Mocking Strategy

#### 1. Pipewire Mock
To test Pipewire-based audio QML services without local Pipewire daemon dependencies, we register custom Python-based mock QObject definitions to the QML context properties before engine load:
- **`Pipewire` Mock**:
  - `nodes`: A dictionary list representation mapping node IDs to mock node properties.
  - `defaultAudioSink`: Points to the active mock sink node.
  - `defaultAudioSource`: Points to the active mock source node.
  - `preferredDefaultAudioSink` and `preferredDefaultAudioSource`: Read/write properties backing choice selections.
- **`PwNode` Mock**:
  - Simulates a Pipewire node. Exposes properties like `id` (int), `name` (string), `description` (string), `ready` (bool), `isSink` (bool), `isStream` (bool), `properties` (variant map).
  - Contains an nested `audio` object (`PwAudio`) containing `volume` (real) and `muted` (bool) properties.
- State transitions are simulated by adding or removing items from the `nodes` collection, updating the properties, and triggering standard signals (e.g. `nodes.onValuesChanged()`).

#### 2. wpctl Mock
For volume and mute delegation testing under virtual routing (which spawns subprocesses):
- The test harness prepends a local mock directory `/tmp/caelestia-test-bin` to the `PATH` environment variable.
- This directory contains a mock executable script named `wpctl`.
- When `Audio.qml` executes `wpctl set-volume <id> <vol>`, the mock script intercepts the call, records the arguments to a temporary tracking file (`/tmp/wpctl_calls.log`), and returns exit code 0.
- The test runner reads the tracking file to assert that correct commands, targets, and volume steps were dispatched.

### Test Case Format
All test cases are written as standard Python functions, running under `pytest`. QML tests use `pytest-qt` or instantiate the `QCommandLineParser` and `QQmlEngine` directly inside a test fixture to load components and drive interactive behaviors.

### Directory Layout
All test files, mock configs, and scripts are published to `/home/execorn/ricing/shell/tests/` (the unified tests directory).

---

## Real-World Application Scenarios (Tier 4)
We define 13 total Tier 4 scenarios, with the first 5 detailed in depth.

### Detailed Scenario 1: Bluetooth Headphones Plug/Unplug While Audio Stream is Active
- **Scenario Description**: The user is playing music through Spotify (an active stream node) outputting to Bluetooth headphones (the preferred default sink). The user powers off their Bluetooth headphones.
- **Steps**:
  1. The Pipewire daemon registers the destruction of the Bluetooth sink node.
  2. `Audio.qml`'s node tracker handles this removal, triggering `onValuesChanged()`.
  3. `updateActiveSink()` is invoked. The fallback policy (`getBestOutputSinkName()`) prioritizes the USB audio interface or the built-in PCIe card.
  4. The active sink `root.sink` updates to the fallback device (e.g. "Built-in Audio").
  5. A desktop toast notification is triggered: "Audio output changed: Now using Built-in Audio".
  6. Spotify stream is automatically re-routed by Pipewire to the new default sink, and the volume slider updates to reflect the built-in audio's volume.

### Detailed Scenario 2: Virtual Sink (EasyEffects) Fallback on Hardware Hotplug
- **Scenario Description**: EasyEffects is running, presenting a virtual sink (`easyeffects_sink`) as the default audio sink. A user hotplugs a USB headset.
- **Steps**:
  1. Pipewire registers the new USB headset sink node.
  2. `Audio.qml` tracks the new physical sink and updates the `physicalSinks` list.
  3. `updateActiveSink()` detects that the default audio sink is virtual (`easyeffects_sink`). It invokes the fallback policy which selects the newly connected USB headset as the best physical device.
  4. `root.physicalDriverId` is updated to the USB headset's node ID.
  5. Any subsequent volume adjustments made in the UI run `wpctl set-volume <USB_headset_ID> <volume>` to modify the hardware volume of the headset, while leaving the virtual EasyEffects volume intact.

### Detailed Scenario 3: Keybindings Config Files Parsing with Mixed Syntaxes
- **Scenario Description**: A user has a complex set of Hyprland configs. The variables file has a mix of standard assignments (`$mod = SUPER`), recursive assignments (`$term = kitty`, `$myTerminal = $term`), and inline comments. The keybinds file uses explicit section/category headers but also contains older un-categorized bindings.
- **Steps**:
  1. `parse_keybinds.py` reads the variables and keybinds configurations.
  2. The parser extracts all variable definitions, resolves `$myTerminal` to `kitty` through recursive lookup, and guards against stack overflow.
  3. In Caelestia mode, it reads explicit section/category comments, routes subsequent binds to them, and uses implicit keyword auto-routing for un-categorized binds (e.g. routing a bind with `wpctl` to the "System" section).
  4. Normalizes modifier strings like `super shift` or `mod4+shift` to `["SUPER", "SHIFT"]`.
  5. Serializes the result to a clean, schema-conforming JSON structure containing all mapped keybinds and friendly descriptions.

### Detailed Scenario 4: Pipewire Node Destruction Race Condition During Rapid Volume Changes
- **Scenario Description**: A user is dragging the volume slider rapidly while an output device (e.g. USB dock) is disconnected.
- **Steps**:
  1. The UI slider continuously fires volume update events, triggering asynchronous `wpctl` processes.
  2. Mid-update, the USB dock is unplugged, causing the active sink node to be destroyed.
  3. `Audio.qml` catches the node removal and immediately sets `root.sink` to null (or fallback).
  4. The `wpctl` process currently executing fails since the node ID no longer exists.
  5. The QML service catches the process failure, resets `root.customVolume` and `root.customMuted` back to `-1`, query-binds to the new active sink, and avoids UI lockup or crash.

### Detailed Scenario 5: Multi-Stream Volume Balancing and App Muting
- **Scenario Description**: The user has Google Chrome (playing video) and Discord (voice call) running simultaneously. They want to mute Chrome while keeping Discord volume active.
- **Steps**:
  1. `Audio.qml` tracks both Chrome and Discord as separate streams in `root.streams`.
  2. The UI popout lists these active application streams with individual sliders/mute buttons.
  3. The user clicks the mute icon next to Google Chrome.
  4. The click handler invokes `Audio.setStreamMuted(chromeStreamNode, true)`.
  5. Since this is a stream node and not the main sink, `Audio.qml` directly sets the `muted` property on the stream's audio interface.
  6. Chrome is muted, while Discord stream volume remains unaffected.

### Additional Scenarios (6-13)
- **Scenario 6: System Boot with Empty Audio Hardware**: VM boot with no audio inputs/outputs. UI renders empty placeholders and disables controls without crashing.
- **Scenario 7: HDMI Audio Hotplug and Stream Route**: HDMI monitor connected. Falls back to HDMI or routes active stream accordingly based on priority list.
- **Scenario 8: Keyboard Volume Hotkeys Spammed Under Heavy System Load**: User spams volume keybindings during 100% CPU spikes. Process debouncer handles calls cleanly.
- **Scenario 9: Corrupted Keybind Config File Recovery**: Hyprland config contains syntax errors and circular loops. Parser resolves valid parts and outputs correct JSON.
- **Scenario 10: Toggle Mute During Active Mic Stream (Discord Call)**: Mic mute toggled via hotkey. Updates QML source state, and Discord indicators reflect mute status.
- **Scenario 11: EasyEffects Process Startup and Handshake**: EasyEffects starts up post-boot. QML detects virtual sink and configures routing.
- **Scenario 12: High-Frequency USB Audio Disconnect/Reconnect**: Loose USB cable causes rapid device churn. Updates are debounced to avoid lockups or notification spam.
- **Scenario 13: Configuration Schema Migration**: Cheatsheet upgrade with new variables format. Parser processes both old and new layouts seamlessly.

---

## Coverage Thresholds
To ensure the test suite is comprehensive and resistant to regressions, the codebase must satisfy the following thresholds:
- **Tier 1 (Functional)**: Must cover **all 25 features** with **at least 5 test cases per feature** (totaling 125 functional cases).
- **Tier 2 (Boundary & Robustness)**: Must cover **all 25 features** with **at least 5 boundary/recovery test cases per feature** (totaling 125 robustness cases).
- **Tier 3 (Integration)**: Must test at least **25 pairwise interactions** of major features.
- **Tier 4 (Scenarios)**: Must test at least **13 real-world application scenarios**.
- **Overall Code Coverage**:
  - `parse_keybinds.py`: **>= 90%** statement coverage.
  - `services/Audio.qml`: **>= 85%** state/path coverage.
  - `modules/bar/popouts/Audio.qml`: **>= 80%** event/interaction coverage.
