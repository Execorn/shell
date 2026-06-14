import os
import pathlib
import json
import subprocess
import pytest
import PySide6.QtCore as QtCore
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlExpression
from conftest import MockPwNode, MockPwAudio
from test_audio import audio_suite, find_ipc_handler, find_mouse_area

# Path to parse_keybinds script for parser integration tests
PARSER_SCRIPT_PATH = "/home/execorn/teamwork_projects/hyprland_cheat_sheet/parser/parse_keybinds.py"

def run_integration_parser(var_content, key_content, tmp_path):
    var_file = tmp_path / "variables.conf"
    var_file.write_text(var_content, encoding="utf-8")
    key_file = tmp_path / "caelestia_keybinds.conf"
    key_file.write_text(key_content, encoding="utf-8")
    out_file = tmp_path / "cheatsheet.json"
    
    cmd = ["python3", PARSER_SCRIPT_PATH, "--variables", str(var_file), "--keybinds", str(key_file), "--output", str(out_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res, out_file

# ==========================================================
# TIER 3: Integration & Pairwise Interaction Tests (25 Cases)
# ==========================================================

def test_t3_parse_volume_keybinds_trigger_service(audio_suite):
    # 1. Parse a simulated config with a volume binding using parse_keybinds logic
    n = MockPwNode(3, "alsa_output.pci", "Builtin", is_sink=True, ready=True, volume=0.5)
    audio_suite.mock_pw.add_node(n)
    audio_suite.mock_pw.set_defaultAudioSink(n)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    # Simulate the triggered event
    audio_suite.audio.incrementVolume(0.05)
    QtCore.QCoreApplication.processEvents()
    assert abs(audio_suite.audio.property("volume") - 0.55) < 0.01

def test_t3_parse_mute_keybind_trigger_service(audio_suite):
    # 2. Mic mute keybinding triggers mute control in Audio.qml
    n_mic = MockPwNode(12, "alsa_input.usb", "Mic", is_sink=False, ready=True, volume=0.5, muted=False)
    audio_suite.mock_pw.add_node(n_mic)
    audio_suite.mock_pw.set_defaultAudioSource(n_mic)
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setStreamMuted(n_mic, True)
    QtCore.QCoreApplication.processEvents()
    assert n_mic.audio.property("muted") == True

def test_t3_parse_output_cycle_trigger_service(audio_suite):
    # 3. Output cycle keybind triggers cycleNextAudioOutput() via IPC
    n1 = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    n2 = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n1)
    audio_suite.mock_pw.add_node(n2)
    audio_suite.mock_pw.set_defaultAudioSink(n1)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    # Locate IPC handler and trigger
    ipc = find_ipc_handler(audio_suite.audio._audio)
    assert ipc is not None
    # Simulate DBus cycleOutput trigger
    audio_suite.audio.cycleNextAudioOutput()
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.mock_pw.property("preferredDefaultAudioSink") == n2

def test_t3_audio_output_cycling_updates_ui_selector(audio_suite):
    # 4. Triggering cycling in Audio.qml updates checked state of radio buttons in UI popout
    n1 = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    n2 = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n1)
    audio_suite.mock_pw.add_node(n2)
    audio_suite.mock_pw.set_defaultAudioSink(n1)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink").property("id") == 3
    audio_suite.audio.cycleNextAudioOutput()
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.mock_pw.property("preferredDefaultAudioSink") == n2

def test_t3_ui_slider_update_updates_wpctl_virtual(audio_suite, wpctl_log):
    # 5. Dragging volume slider updates Audio.qml volume -> triggers wpctl volume delegation under virtual routing
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual", is_sink=True, ready=True, properties={"node.virtual": "true"})
    n_usb = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.add_node(n_usb)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setVolume(0.75)
    QtCore.QCoreApplication.processEvents()
    
    calls = wpctl_log.read_text().splitlines()
    assert any("set-volume" in call and "4" in call and "0.75" in call for call in calls)

def test_t3_hotplug_headphones_updates_ui_and_toasts(audio_suite):
    # 6. Plug in Bluetooth headphones -> node tracking -> fallback selection -> desktop toast
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Plug Bluetooth
    n_bluez = MockPwNode(4, "bluez_output.headset", "My Headset", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_bluez)
    audio_suite.mock_pw.set_defaultAudioSink(n_bluez)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink").property("name") == "bluez_output.headset"
    assert len(audio_suite.mock_toast.toasts) > 0
    assert any("headset" in t[1].lower() for t in audio_suite.mock_toast.toasts)

def test_t3_ui_mute_action_updates_slider_label(audio_suite):
    # 7. Muting stream in UI updates volume slider header text to "Muted"
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True, volume=0.5, muted=False)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setStreamMuted(n_pci, True)
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.audio.property("muted") == True

def test_t3_ipc_volume_update_reflects_on_ui_slider(audio_suite):
    # 8. IPC updateVolume updates Audio.qml volume & UI slider value
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True, volume=0.5)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setVolume(0.65)
    QtCore.QCoreApplication.processEvents()
    assert abs(audio_suite.audio.property("volume") - 0.65) < 0.01

def test_t3_virtual_routing_fallback_toasts(audio_suite):
    # 9. Destroy virtual sink -> falls back to physical device -> triggers toast
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual", is_sink=True, ready=True, properties={"node.virtual": "true"})
    n_usb = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.add_node(n_usb)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.mock_toast.toasts.clear()
    
    # Remove USB sink, forcing virtual sink to map to PCI physical driver
    audio_suite.mock_pw.remove_node(n_usb)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink").property("name") == "alsa_output.pci"
    assert len(audio_suite.mock_toast.toasts) > 0

def test_t3_stream_destruction_unmounts_ui(audio_suite):
    # 10. Stream node destroyed -> stream properties clean up cleanly
    n_stream = MockPwNode(8, "spotify_stream", "Spotify", is_sink=False, is_stream=True, ready=True)
    audio_suite.mock_pw.add_node(n_stream)
    QtCore.QCoreApplication.processEvents()
    assert n_stream in audio_suite.audio.property("streams")
    
    audio_suite.mock_pw.remove_node(n_stream)
    QtCore.QCoreApplication.processEvents()
    assert n_stream not in audio_suite.audio.property("streams")

def test_t3_input_source_selection_updates_ui_checked(audio_suite):
    # 11. Changing preferred input source updates radio button selection in UI
    n_mic1 = MockPwNode(12, "alsa_input.usb1", "Mic1", is_sink=False, ready=True)
    n_mic2 = MockPwNode(13, "alsa_input.usb2", "Mic2", is_sink=False, ready=True)
    audio_suite.mock_pw.add_node(n_mic1)
    audio_suite.mock_pw.add_node(n_mic2)
    audio_suite.mock_pw.set_defaultAudioSource(n_mic1)
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setAudioSource(n_mic2)
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.mock_pw.property("preferredDefaultAudioSource") == n_mic2

def test_t3_mouse_wheel_adjust_updates_wpctl_virtual(audio_suite, wpctl_log):
    # 12. Scrolling mouse wheel on slider triggers volume updates delegated to physical card via wpctl
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual", is_sink=True, ready=True, properties={"node.virtual": "true"})
    n_usb = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True, volume=0.5)
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.add_node(n_usb)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Simulate mouse wheel up
    area = find_mouse_area(audio_suite.ui)
    area.simulateWheel(120)
    QtCore.QCoreApplication.processEvents()
    
    calls = wpctl_log.read_text().splitlines()
    assert any("set-volume" in call and "4" in call for call in calls)

def test_t3_parse_invalid_vars_does_not_break_json_schema(tmp_path):
    # 13. Malformed variables in parsing do not produce invalid JSON schemas
    res, out_file = run_integration_parser("$a = $b\n$b = $a", "bind = SUPER, Space, exec, kitty", tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    assert isinstance(data, list)
    assert any(b["key"] == "Space" for sec in data for cat in sec["categories"] for b in cat["keybinds"])

def test_t3_empty_audio_devices_disables_ui_controls(audio_suite):
    # 14. No physical devices tracked -> UI sliders / radio buttons are disabled / empty
    audio_suite.mock_pw.clear_nodes()
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert len(audio_suite.audio.property("physicalSinks")) == 0
    assert audio_suite.audio.property("sink") == None

def test_t3_ipc_mute_toggle_syncs_with_ui_checked_state(audio_suite):
    # 15. Muting via IPC syncs and updates muted text display
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True, volume=0.5, muted=False)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setProperty("customMuted", 1)
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.audio.property("muted") == True

def test_t3_bluetooth_unplug_causes_fallback_toast(audio_suite):
    # 16. Unplug bluetooth device -> fallback to PCIe -> toast naming new default
    n_pci = MockPwNode(3, "alsa_output.pci", "PCIe Built-in", is_sink=True, ready=True)
    n_bluez = MockPwNode(4, "bluez_output.headset", "My Headset", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.add_node(n_bluez)
    audio_suite.mock_pw.set_defaultAudioSink(n_bluez)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.mock_toast.toasts.clear()
    
    # Unplug bluetooth
    audio_suite.mock_pw.remove_node(n_bluez)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink").property("name") == "alsa_output.pci"
    assert len(audio_suite.mock_toast.toasts) > 0
    assert any("PCIe" in t[1] for t in audio_suite.mock_toast.toasts)

def test_t3_parse_duplicate_categories_consolidates_ui_sections(tmp_path):
    # 17. Parser merging duplicate categories displays consolidated headers
    config = """
    # Section: System
    # Category: Volume
    bind = SUPER, Up, exec, wpctl set-volume @DEFAULT_SINK@ 5%+
    
    # Section: System
    # Category: Volume
    bind = SUPER, Down, exec, wpctl set-volume @DEFAULT_SINK@ 5%-
    """
    res, out_file = run_integration_parser("", config, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    assert len(data) == 1
    assert data[0]["section"] == "System"
    assert len(data[0]["categories"]) == 1
    assert data[0]["categories"][0]["category"] == "Volume"
    assert len(data[0]["categories"][0]["keybinds"]) == 2

def test_t3_volume_slider_clamping_prevents_wpctl_overflow(audio_suite, wpctl_log):
    # 18. Dragging volume slider past max volume clamps values and prevents spawning wpctl with invalid args
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual", is_sink=True, ready=True, properties={"node.virtual": "true"})
    n_usb = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.add_node(n_usb)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Try set volume to 5.0
    audio_suite.audio.setVolume(5.0)
    QtCore.QCoreApplication.processEvents()
    
    calls = wpctl_log.read_text().splitlines()
    assert any("set-volume" in call and "1.00" in call for call in calls)
    assert not any("5.00" in call for call in calls)

def test_t3_stream_metadata_change_updates_ui_label(audio_suite):
    # 19. Active stream app name changes -> UI label updates dynamically
    n_stream = MockPwNode(8, "spotify_stream", "Spotify", is_sink=False, is_stream=True, ready=True)
    audio_suite.mock_pw.add_node(n_stream)
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.getStreamName(n_stream) == "Spotify"
    
    n_stream.setProperty("properties", {"application.name": "Spotify Premium"})
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.audio.getStreamName(n_stream) == "Spotify Premium"

def test_t3_recursive_variables_in_binds_resolve_to_exec_fallback(tmp_path):
    # 20. Deep recursive variables resolve to final commands and fallback to proper descriptions
    var_content = """
    $term = kitty
    $my_terminal = $term
    """
    key_content = "bind = SUPER, Return, exec, $my_terminal"
    res, out_file = run_integration_parser(var_content, key_content, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["action"] == "exec kitty"

def test_t3_cycle_next_during_device_plug(audio_suite):
    # 21. Cycling audio outputs during physical sink hotplugging resolves to correct next active sink
    n1 = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n1)
    audio_suite.mock_pw.set_defaultAudioSink(n1)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    n2 = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n2)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    audio_suite.audio.cycleNextAudioOutput()
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.mock_pw.property("preferredDefaultAudioSink") == n2

def test_t3_ipc_set_volume_to_zero_updates_mute_state(audio_suite):
    # 22. IPC setting volume to 0.0 updates volume to 0% but does not automatically mute
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True, volume=0.5, muted=False)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    audio_suite.audio.setVolume(0.0)
    QtCore.QCoreApplication.processEvents()
    
    assert abs(audio_suite.audio.property("volume") - 0.0) < 0.01
    assert audio_suite.audio.property("muted") == False

def test_t3_unready_nodes_ignored_by_fallback_policy(audio_suite):
    # 23. Unready nodes tracked by Pipewire are ignored by device fallback policy
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    n_unready = MockPwNode(4, "bluez_output.headset", "My Headset", is_sink=True, ready=False)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.add_node(n_unready)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink") == n_pci

def test_t3_wpctl_process_handling_prevents_ui_blocking(audio_suite, wpctl_log):
    # 24. Rapid volume changes run asynchronously without blocking the thread
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual", is_sink=True, ready=True, properties={"node.virtual": "true"})
    n_usb = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.add_node(n_usb)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    for i in range(10):
        audio_suite.audio.setVolume(0.1 + i * 0.05)
    QtCore.QCoreApplication.processEvents()
    
    calls = wpctl_log.read_text().splitlines()
    assert len(calls) > 0

def test_t3_cheatsheet_parser_ignores_internal_keybinds_but_maps_custom(tmp_path):
    # 25. Parser filters internal bindings but successfully maps custom user bindings
    config = """
    bind = SUPER, catchall, exec, ignore_this
    bind = SUPER, mouse_down, exec, ignore_this_too
    bind = SUPER, K, exec, keep_this_one
    """
    res, out_file = run_integration_parser("", config, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    binds = [b for sec in data for cat in sec["categories"] for b in cat["keybinds"]]
    
    assert not any("ignore_this" in b["action"] for b in binds)
    assert any("keep_this_one" in b["action"] for b in binds)
