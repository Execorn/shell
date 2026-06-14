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
from test_integration import run_integration_parser

# ==========================================================
# TIER 4: Real-World Application Scenarios (13 Cases)
# ==========================================================

def test_scenario_1_bluetooth_headphones(audio_suite):
    # Spotify stream playing. Preferred output is Bluetooth headset. Unplug Bluetooth headset.
    n_bluez = MockPwNode(4, "bluez_output.headset", "Bluetooth Headset", is_sink=True, ready=True, volume=0.8)
    n_pci = MockPwNode(3, "alsa_output.pci", "Built-in Audio", is_sink=True, ready=True, volume=0.5)
    n_stream = MockPwNode(8, "spotify_stream", "Spotify", is_sink=False, is_stream=True, ready=True)
    
    audio_suite.mock_pw.add_node(n_bluez)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.add_node(n_stream)
    audio_suite.mock_pw.set_defaultAudioSink(n_bluez)
    
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink") == n_bluez
    
    # Power off Bluetooth headphones
    audio_suite.mock_pw.remove_node(n_bluez)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Fallback to Built-in Audio
    assert audio_suite.audio.property("sink") == n_pci
    # Toast notification triggered
    assert len(audio_suite.mock_toast.toasts) > 0
    assert any("built-in" in t[1].lower() for t in audio_suite.mock_toast.toasts)

def test_scenario_2_virtual_sink_fallback(audio_suite, wpctl_log):
    # EasyEffects running, presents a virtual sink. User hotplugs a USB headset.
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual Sink", is_sink=True, ready=True, properties={"node.virtual": "true"})
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Hotplug USB headset
    n_usb = MockPwNode(4, "alsa_output.usb", "USB Headset", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_usb)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("physicalDriverId") == 4
    
    # subsequent volume updates run wpctl set-volume on physical driver
    audio_suite.audio.setVolume(0.70)
    QtCore.QCoreApplication.processEvents()
    
    calls = wpctl_log.read_text().splitlines()
    assert any("set-volume" in call and "4" in call and "0.70" in call for call in calls)

def test_scenario_3_mixed_syntaxes(tmp_path):
    # Complex Hyprland configs with mixed syntaxes
    vars_content = """
    $mod = SUPER
    $term = kitty
    $myTerminal = $term
    """
    key_content = """
    # Section: General
    # Category: Terminal
    bind = $mod, Return, exec, $myTerminal # Launch kitty terminal
    
    # Category: Volume
    bind = , XF86AudioRaiseVolume, exec, wpctl set-volume @DEFAULT_SINK@ 5%+
    """
    res, out_file = run_integration_parser(vars_content, key_content, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    assert len(data) == 2
    sec_apps = next(s for s in data if s["section"] == "Applications")
    cat_term = next(c for c in sec_apps["categories"] if c["category"] == "Terminal")
    assert cat_term["keybinds"][0]["action"] == "exec kitty"
    assert cat_term["keybinds"][0]["desc"] == "Launch kitty terminal"

def test_scenario_4_destruction_race(audio_suite):
    # Drag volume rapidly while USB headset unplugged
    n_usb = MockPwNode(4, "alsa_output.usb", "USB Headset", is_sink=True, ready=True, volume=0.5)
    audio_suite.mock_pw.add_node(n_usb)
    audio_suite.mock_pw.set_defaultAudioSink(n_usb)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Rapid updates
    audio_suite.audio.setVolume(0.6)
    audio_suite.mock_pw.remove_node(n_usb)
    audio_suite.mock_pw.set_defaultAudioSink(None)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Recover cleanly without crashing
    assert audio_suite.audio.property("sink") == None

def test_scenario_5_multistream_balance(audio_suite):
    # Balance Spotify/Chrome/Discord streams
    n_chrome = MockPwNode(8, "chrome_stream", "Google Chrome", is_sink=False, is_stream=True, ready=True, volume=0.7, muted=False)
    n_discord = MockPwNode(9, "discord_stream", "Discord", is_sink=False, is_stream=True, ready=True, volume=0.8, muted=False)
    audio_suite.mock_pw.add_node(n_chrome)
    audio_suite.mock_pw.add_node(n_discord)
    QtCore.QCoreApplication.processEvents()
    
    # Mute Chrome only
    audio_suite.audio.setStreamMuted(n_chrome, True)
    QtCore.QCoreApplication.processEvents()
    
    assert n_chrome.audio.property("muted") == True
    assert n_discord.audio.property("muted") == False

def test_scenario_6_system_boot_empty(audio_suite):
    # System boot with no audio hardware detected
    audio_suite.mock_pw.clear_nodes()
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Renders empty state gracefully
    assert audio_suite.audio.property("sink") == None
    assert len(audio_suite.audio.property("physicalSinks")) == 0
    assert len(audio_suite.audio.property("physicalSources")) == 0

def test_scenario_7_hdmi_hotplug(audio_suite):
    # HDMI Audio Monitor hotplugged
    n_pci = MockPwNode(3, "alsa_output.pci", "Built-in", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    n_hdmi = MockPwNode(4, "alsa_output.pci.hdmi-stereo", "HDMI Digital Stereo", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_hdmi)
    audio_suite.mock_pw.set_defaultAudioSink(n_hdmi)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("sink") == n_hdmi

def test_scenario_8_volume_hotkeys_spam(audio_suite):
    # Keyboard volume hotkeys spammed
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True, volume=0.5)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    # Spam
    for i in range(100):
        audio_suite.audio.incrementVolume(0.01)
    QtCore.QCoreApplication.processEvents()
    
    assert audio_suite.audio.property("volume") > 0.5

def test_scenario_9_corrupted_config(tmp_path):
    # Corrupted keybind config file recovery
    bad_config = """
    $mod = 
    $term = kitty
    $circular = $circular
    bind = SUPER, K, exec, $term
    bind = SUPER, #$!@, invalid_dispatcher
    """
    res, out_file = run_integration_parser("", bad_config, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    # The valid bind SUPER, K should still parse correctly
    assert len(data) > 0
    assert any(b["key"] == "K" for sec in data for cat in sec["categories"] for b in cat["keybinds"])

def test_scenario_10_toggle_mute_discord(audio_suite):
    # Toggle Mute during Discord Call
    n_mic = MockPwNode(12, "alsa_input.usb", "USB Microphone", is_sink=False, ready=True, volume=0.6, muted=False)
    audio_suite.mock_pw.add_node(n_mic)
    audio_suite.mock_pw.set_defaultAudioSource(n_mic)
    QtCore.QCoreApplication.processEvents()
    
    # Toggle mute
    audio_suite.audio.setStreamMuted(n_mic, True)
    QtCore.QCoreApplication.processEvents()
    assert n_mic.audio.property("muted") == True

def test_scenario_11_easyeffects_handshake(audio_suite):
    # EasyEffects starts up post-boot
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    # EasyEffects starts
    n_virt = MockPwNode(5, "easyeffects_sink", "EasyEffects Sink", is_sink=True, ready=True, properties={"node.virtual": "true"})
    audio_suite.mock_pw.add_node(n_virt)
    audio_suite.mock_pw.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # QML detects virtual sink
    assert audio_suite.audio.property("physicalDriverId") == 3

def test_scenario_12_rapid_usb_churn(audio_suite):
    # High-frequency USB Audio Disconnect/Reconnect
    n_pci = MockPwNode(3, "alsa_output.pci", "PCI", is_sink=True, ready=True)
    audio_suite.mock_pw.add_node(n_pci)
    audio_suite.mock_pw.set_defaultAudioSink(n_pci)
    QtCore.QCoreApplication.processEvents()
    audio_suite.audio.updateActiveSink()
    
    for _ in range(5):
        n_usb = MockPwNode(4, "alsa_output.usb", "USB", is_sink=True, ready=True)
        audio_suite.mock_pw.add_node(n_usb)
        audio_suite.mock_pw.set_defaultAudioSink(n_usb)
        QtCore.QCoreApplication.processEvents()
        audio_suite.audio.updateActiveSink()
        
        audio_suite.mock_pw.remove_node(n_usb)
        audio_suite.mock_pw.set_defaultAudioSink(n_pci)
        QtCore.QCoreApplication.processEvents()
        audio_suite.audio.updateActiveSink()
        
    QtCore.QCoreApplication.processEvents()
    assert audio_suite.audio.property("sink") == n_pci

def test_scenario_13_schema_migration(tmp_path):
    # Migration containing old and new variable config styles
    vars_old = """
    $terminal = kitty
    """
    key_new = """
    # Section: Launchers
    bind = SUPER, Space, exec, rofi -show drun
    bind = SUPER, Return, exec, $terminal
    """
    res, out_file = run_integration_parser(vars_old, key_new, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    assert len(data) == 1
    binds = [b for cat in data[0]["categories"] for b in cat["keybinds"]]
    assert any(b["action"] == "exec kitty" for b in binds)
    assert any("rofi" in b["action"] for b in binds)
