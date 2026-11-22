import pytest
import json
import PySide6.QtCore as QtCore
from conftest import MockPwNode, MockPipewire, MockToaster
from test_audio import find_ipc_handler
from test_integration import run_integration_parser

def test_pipewire_restart_resilience(qml_engine, mock_pipewire):
    # 1. Initialize audio singleton
    audio = qml_engine.singletonInstance("qs.services", "Audio")
    assert audio is not None
    
    # Create some mock physical nodes
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.7)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_phys)
    QtCore.QCoreApplication.processEvents()
    
    # Verify initial state
    assert audio.property("volume") == 0.7
    
    # 2. Simulate Pipewire service crash/restart
    # Set the Pipewire context property to None to simulate the global service being cleared/unbound
    qml_engine.rootContext().setContextProperty("Pipewire", None)
    QtCore.QCoreApplication.processEvents()
    
    # Access volume and muted properties - they should fallback/fail gracefully
    # rather than crashing the PySide6 / Python execution.
    vol = audio.property("volume")
    muted = audio.property("muted")
    
    # 3. Restore Pipewire service
    new_mock_pw = MockPipewire()
    n_phys_new = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.8)
    new_mock_pw.add_node(n_phys_new)
    new_mock_pw.set_defaultAudioSink(n_phys_new)
    
    qml_engine.rootContext().setContextProperty("Pipewire", new_mock_pw)
    QtCore.QCoreApplication.processEvents()
    
    # Trigger active sink update
    audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # 4. Verify recovery
    new_vol = audio.property("volume")
    assert abs(new_vol - 0.8) < 0.01

def test_virtual_sink_robustness(qml_engine, mock_pipewire):
    audio = qml_engine.singletonInstance("qs.services", "Audio")
    assert audio is not None
    
    # Test behavior under virtual routing
    # Add virtual sink and a physical driver
    n_virt = MockPwNode(5, "easyeffects_sink", "Virtual Sink", is_sink=True, ready=True, properties={"node.virtual": "true"})
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.6)
    
    mock_pipewire.add_node(n_virt)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_virt)
    QtCore.QCoreApplication.processEvents()
    
    audio.updateActiveSink()
    QtCore.QCoreApplication.processEvents()
    
    # Physical driver ID should resolve to n_phys (4)
    assert audio.property("physicalDriverId") == 4
    
    # Active resolved sink should be n_phys
    sink = audio.property("sink")
    assert sink is not None
    assert sink.property("id") == 4

def test_malformed_json_cheatsheet_parser(tmp_path):
    # Verify that the parser handles malformed config file syntaxes gracefully (e.g. keybind lines with missing arguments)
    bad_config = """
    $mod = SUPER
    bind = $mod, 
    """
    res, out_file = run_integration_parser("", bad_config, tmp_path)
    assert res.returncode == 0
    data = json.loads(out_file.read_text())
    # The output should compile to an empty list or ignore the malformed binding
    assert isinstance(data, list)
    if len(data) > 0:
        for section in data:
            assert len(section["categories"]) == 0 or len(section["categories"][0]["keybinds"]) == 0


def _qlist(val):
    if hasattr(val, "toVariant"):
        return list(val.toVariant() or [])
    return list(val or [])


def test_pipewire_nodes_drain_and_id_reuse_resilience(qml_engine, mock_pipewire):
    val = qml_engine.singletonInstance("qs.services", "Audio")
    audio = val.toQObject() if hasattr(val, "toQObject") else val
    assert audio is not None

    n_old = MockPwNode(42, "alsa_output.pci", "Old Speakers", is_sink=True, ready=True, volume=0.65)
    mock_pipewire.add_node(n_old)
    mock_pipewire.set_defaultAudioSink(n_old)
    QtCore.QCoreApplication.processEvents()
    assert len(_qlist(audio.property("physicalSinks"))) == 1

    # Simulate real PipeWire daemon restart: empty nodes drain first
    mock_pipewire.clear_nodes()
    mock_pipewire.set_defaultAudioSink(None)
    QtCore.QCoreApplication.processEvents()
    assert len(_qlist(audio.property("physicalSinks"))) == 0
    assert audio.property("lastRoutedPhysicalSink") == ""
    assert audio.property("lastConfiguredPhysicalSink") == ""

    # New node reuses exact integer ID 42, initially unready (readyOnceNodes must NOT treat it as ready!)
    n_reused_unready = MockPwNode(42, "bluez_output.08_F0_B6.1", "Reused Unready BT", is_sink=True, ready=False)
    mock_pipewire.add_node(n_reused_unready)
    QtCore.QCoreApplication.processEvents()
    assert len(_qlist(audio.property("physicalSinks"))) == 0

    # Once ready flips true, node becomes active
    n_reused_unready.setProperty("ready", True)
    mock_pipewire.set_defaultAudioSink(n_reused_unready)
    QtCore.QCoreApplication.processEvents()
    assert [n.property("name") for n in _qlist(audio.property("physicalSinks"))] == ["bluez_output.08_F0_B6.1"]
    sink_val = audio.property("sink")
    sink_obj = sink_val.toQObject() if hasattr(sink_val, "toQObject") else sink_val
    assert sink_obj == n_reused_unready
