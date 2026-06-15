import pytest
import json
import math
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSValue
from conftest import MockPwNode

# Import fixtures directly from test_copilot
from test_copilot import mock_copilot_env, clean_env, clean_server, mock_llm_server

@pytest.fixture
def copilot_service(qml_engine, mock_copilot_env):
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.clearChat()
    return copilot

# 1. Malformed JSON blocks
def test_edge_malformed_json_unbalanced_braces(copilot_service, mock_copilot_env):
    mock_hypr, _, _, _, _, _ = mock_copilot_env
    # Unbalanced braces in the block, JSON.parse will fail but it should catch and ignore it
    copilot_service.executeActionsFromText('```json\n{"action": "workspace", "id": 3\n```')
    assert len(mock_hypr.commands) == 0

def test_edge_malformed_json_incorrect_action_keys(copilot_service, mock_copilot_env):
    mock_hypr, _, _, _, _, _ = mock_copilot_env
    # Incorrect action key name (e.g. "act" instead of "action")
    copilot_service.executeActionsFromText('```json\n{"act": "workspace", "id": 3}\n```')
    assert len(mock_hypr.commands) == 0

def test_edge_malformed_json_nested_lists(copilot_service, mock_copilot_env):
    mock_hypr, _, _, _, _, _ = mock_copilot_env
    # Nested list of objects
    copilot_service.executeActionsFromText('```json\n[[{"action": "workspace", "id": 3}]]\n```')
    assert len(mock_hypr.commands) == 0

def test_edge_malformed_json_missing_id_workspace(copilot_service, mock_copilot_env):
    mock_hypr, _, _, _, _, _ = mock_copilot_env
    # Missing required 'id' for workspace action
    copilot_service.executeActionsFromText('```json\n{"action": "workspace"}\n```')
    assert len(mock_hypr.commands) == 0

def test_edge_malformed_json_missing_value_volume(qml_engine, copilot_service, mock_copilot_env, mock_pipewire):
    # Missing required 'value' for volume action
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.5)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_phys)
    
    audio_val = qml_engine.singletonInstance("qs.services", "Audio")
    audio = audio_val.toQObject() if isinstance(audio_val, QJSValue) else audio_val
    audio.setProperty("sink", n_phys)

    copilot_service.executeActionsFromText('```json\n{"action": "volume"}\n```')
    assert n_phys.audio.volume == 0.5

def test_edge_malformed_json_primitive_types(copilot_service, mock_copilot_env):
    mock_hypr, _, _, _, _, _ = mock_copilot_env
    # Non-object primitive values
    copilot_service.executeActionsFromText('```json\nnull\n```')
    copilot_service.executeActionsFromText('```json\n42\n```')
    copilot_service.executeActionsFromText('```json\n"hello"\n```')
    copilot_service.executeActionsFromText('```json\n{}\n```')
    assert len(mock_hypr.commands) == 0

# 2. Extreme Boundary Values
def test_edge_boundary_volume_negative(qml_engine, copilot_service, mock_copilot_env, mock_pipewire):
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.5)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_phys)
    
    audio_val = qml_engine.singletonInstance("qs.services", "Audio")
    audio = audio_val.toQObject() if isinstance(audio_val, QJSValue) else audio_val
    audio.setProperty("sink", n_phys)

    # Negative volume -10% -> volReal -0.1 -> clamps to 0.0 in Audio.qml
    copilot_service.executeActionsFromText('```json\n{"action": "volume", "value": -10}\n```')
    assert n_phys.audio.volume == 0.0

def test_edge_boundary_volume_overflow(qml_engine, copilot_service, mock_copilot_env, mock_pipewire):
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.5)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_phys)
    
    audio_val = qml_engine.singletonInstance("qs.services", "Audio")
    audio = audio_val.toQObject() if isinstance(audio_val, QJSValue) else audio_val
    audio.setProperty("sink", n_phys)

    # Volume overflow 150% -> volReal 1.5 -> clamps to maxVolume (1.0) in Audio.qml
    copilot_service.executeActionsFromText('```json\n{"action": "volume", "value": 150}\n```')
    assert n_phys.audio.volume == 1.0

def test_edge_boundary_workspace_out_of_bounds(copilot_service, mock_copilot_env):
    mock_hypr, _, _, _, _, _ = mock_copilot_env
    # Workspace IDs out of bounds: 0, 11, -1
    copilot_service.executeActionsFromText('```json\n{"action": "workspace", "id": 0}\n```')
    copilot_service.executeActionsFromText('```json\n{"action": "workspace", "id": 11}\n```')
    copilot_service.executeActionsFromText('```json\n{"action": "workspace", "id": -1}\n```')
    
    assert "workspace 0" in mock_hypr.commands
    assert "workspace 11" in mock_hypr.commands
    assert "workspace -1" in mock_hypr.commands

def test_edge_boundary_exec_empty_command(copilot_service, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    # Empty/null command for exec
    copilot_service.executeActionsFromText('```json\n{"action": "exec", "command": ""}\n```')
    copilot_service.executeActionsFromText('```json\n{"action": "exec", "command": null}\n```')
    assert len(mock_quickshell.detached_commands) == 0

def test_edge_boundary_drawer_invalid_name(copilot_service, mock_copilot_env):
    _, _, _, _, mock_visibilities, _ = mock_copilot_env
    # Invalid drawer name
    copilot_service.executeActionsFromText('```json\n{"action": "drawer", "name": "invalid_drawer", "state": true}\n```')
    copilot_service.executeActionsFromText('```json\n{"action": "drawer", "name": "", "state": true}\n```')
    
    # Assert all valid drawer properties remain False (their initial state)
    assert mock_visibilities.active_vis.launcher is False
    assert mock_visibilities.active_vis.dashboard is False
    assert mock_visibilities.active_vis.cheatsheet is False
    assert mock_visibilities.active_vis.sidebar is False

def test_edge_boundary_drawer_special_property(copilot_service, mock_copilot_env):
    _, _, _, _, mock_visibilities, _ = mock_copilot_env
    # What if drawer name is "toString" or similar built-in name?
    # It should not crash or corrupt standard properties
    copilot_service.executeActionsFromText('```json\n{"action": "drawer", "name": "toString", "state": true}\n```')
    assert mock_visibilities.active_vis.launcher is False

def test_edge_boundary_wallpaper_invalid_direction(copilot_service, mock_copilot_env):
    _, _, _, mock_wallpapers, _, _ = mock_copilot_env
    # Invalid direction for wallpaper
    initial_wallpaper = mock_wallpapers.actualCurrent
    copilot_service.executeActionsFromText('```json\n{"action": "wallpaper", "direction": "invalid_dir"}\n```')
    assert mock_wallpapers.actualCurrent == initial_wallpaper
    assert mock_wallpapers.random_called is False

def test_edge_boundary_mute_invalid_type(qml_engine, copilot_service, mock_copilot_env, mock_pipewire):
    # If type is invalid, mute sets the sink mute state instead
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.5, muted=False)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_phys)
    
    audio_val = qml_engine.singletonInstance("qs.services", "Audio")
    audio = audio_val.toQObject() if isinstance(audio_val, QJSValue) else audio_val
    audio.setProperty("sink", n_phys)

    # Send mute with invalid type: defaults to Audio.sink muted
    copilot_service.executeActionsFromText('```json\n{"action": "mute", "type": "invalid_type", "state": true}\n```')
    assert n_phys.audio.muted is True
