import json
import pathlib
import pytest
import PySide6.QtCore as QtCore
from PySide6.QtCore import QObject, QMetaObject
from PySide6.QtQml import QQmlComponent, QQmlExpression, QJSValue
from conftest import MockBluetoothDevice, MockConfigState, MockPopoutState, MockPwNode, MockToast

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def unwrap_qobj(val):
    if isinstance(val, QJSValue) and val.isQObject():
        return val.toQObject()
    return val


def get_singleton(engine, uri, name):
    return unwrap_qobj(engine.singletonInstance(uri, name))


def eval_js(engine, root_obj, code, **ctx_vars):
    root_obj = unwrap_qobj(root_obj)
    ctx = engine.rootContext()
    for k, v in ctx_vars.items():
        ctx.setContextProperty(k, unwrap_qobj(v))
    expr = QQmlExpression(ctx, root_obj, code)
    res, _ = expr.evaluate()
    if expr.hasError():
        raise RuntimeError(f"QML eval error for `{code}`: {expr.error().toString()}")
    for k in ctx_vars:
        ctx.setContextProperty(k, None)
    if isinstance(res, QJSValue):
        if res.isQObject():
            return res.toQObject()
        return res.toVariant()
    return res


def create_qml(engine, qml_src, parent=None):
    from PySide6.QtQml import QQmlEngine
    comp = QQmlComponent(engine)
    comp.setData(qml_src.encode("utf-8"), QtCore.QUrl())
    obj = comp.create()
    assert obj is not None, f"create_qml error: {comp.errors()}"
    obj._comp = comp
    QQmlEngine.setObjectOwnership(obj, QQmlEngine.CppOwnership)
    if parent is not None:
        obj.setParent(parent)
    return obj


def test_bluez_scan_refcount_and_blocked_guardrails(qml_engine, mock_bluetooth, mock_toaster):
    bluez = get_singleton(qml_engine, "qs.services", "Bluez")
    assert bluez is not None
    qml_engine.rootContext().setContextProperty("Bluez", bluez)

    adapter = mock_bluetooth.defaultAdapter
    dev_blocked = MockBluetoothDevice("AA:BB:CC:11:22:33", "Blocked Buds", connected=False, paired=True, bonded=True, blocked=True)
    dev_temp = MockBluetoothDevice("AA:BB:CC:44:55:66", "Temp Speaker", connected=False, paired=True, bonded=False, blocked=False)
    mock_bluetooth.devices.set_values([dev_blocked, dev_temp])
    QtCore.QCoreApplication.processEvents()

    # Multi-owner scan refcounting keeps discovering active until all owners release
    bluez.acquireScan("popout", False)
    assert adapter.property("discovering") is True
    assert adapter.property("pairable") is False
    bluez.acquireScan("pairing", True)
    assert adapter.property("discovering") is True
    assert adapter.property("pairable") is True

    bluez.releaseScan("popout")
    assert adapter.property("discovering") is True  # pairing still holds lock
    bluez.releaseScan("pairing")
    assert adapter.property("discovering") is False

    # Blocked device connect/pair refused with warning toast
    eval_js(qml_engine, bluez, "Bluez.toggleDeviceConnection(_dev)", _dev=dev_blocked)
    eval_js(qml_engine, bluez, "Bluez.pairAndConnect(_dev)", _dev=dev_blocked)
    warnings = [t for t in mock_toaster.toasts if t.property("title") == "Device blocked"]
    assert len(warnings) == 2
    assert dev_blocked.calls == []

    # Temp (paired && !bonded) forget invokes dev.forget() and clears cached card profile map
    eval_js(qml_engine, bluez, "Bluez.cardProfilesByAddress = ({'AA:BB:CC:44:55:66': {cardName: 'c'}})")
    eval_js(qml_engine, bluez, "Bluez.forgetDevice(_dev)", _dev=dev_temp)
    assert "forget" in dev_temp.calls
    assert eval_js(qml_engine, bluez, "Bluez.cardInfoFor('AA:BB:CC:44:55:66')") is None


def test_bluez_card_profiles_codec_ranking_and_ipc(qml_engine, mock_bluetooth, pactl_state, tmp_path, monkeypatch):
    state_file, pactl_log = pactl_state
    mac = "08:F0:B6:35:49:16"
    state_file.write_text(json.dumps({
        "cards": [
            {
                "name": "bluez_card.08_F0_B6_35_49_16",
                "active_profile": "a2dp-sink",
                "properties": {"device.api": "bluez5", "api.bluez5.address": mac, "device.string": mac},
                "profiles": {
                    "off": {"description": "Off", "priority": 0, "available": True},
                    "headset-head-unit": {"description": "Headset Head Unit (HSP/HFP, codec MSBC)", "priority": 8, "available": True},
                    "a2dp-sink-sbc": {"description": "High Fidelity Playback (A2DP Sink, codec SBC)", "priority": 132, "available": True},
                    "a2dp-sink": {"description": "High Fidelity Playback (A2DP Sink, codec aptX HD)", "priority": 135, "available": True},
                },
            }
        ],
        "sinks": [
            {
                "name": "bluez_output.08_F0_B6_35_49_16.1",
                "properties": {"api.bluez5.address": mac, "api.bluez5.codec": "aptx_hd"},
            }
        ],
    }))

    bluez = get_singleton(qml_engine, "qs.services", "Bluez")
    assert bluez is not None
    dev = MockBluetoothDevice(mac, "STAX SPIRIT S3", connected=True, paired=True, bonded=True)
    mock_bluetooth.devices.set_values([dev])
    qml_engine.rootContext().setContextProperty("Bluez", bluez)

    eval_js(qml_engine, bluez, "Bluez.refreshAudioProfiles()")
    from PySide6.QtTest import QTest
    QTest.qWait(400)

    assert eval_js(qml_engine, bluez, f"Bluez.activeCodecFor({mac!r})") == "aptX HD"
    assert eval_js(qml_engine, bluez, f"Bluez.activeProfileFor({mac!r})") == "a2dp-sink"
    profiles = eval_js(qml_engine, bluez, f"Bluez.profilesFor({mac!r})")
    names = [p["name"] for p in profiles]
    assert names[0] == "a2dp-sink"
    assert names[-1] == "off"
    assert names.index("a2dp-sink-sbc") < names.index("headset-head-unit")

    # IPC handler status / profiles / setProfile
    ipc = None
    for child in bluez.findChildren(QObject):
        if "IpcHandler" in child.metaObject().className():
            ipc = child
            break
    assert ipc is not None
    st = eval_js(qml_engine, bluez, "_ipc.status()", _ipc=ipc)
    assert "STAX SPIRIT S3 [aptX HD]" in st
    assert "agentRegistered=true" in st
    prof_str = eval_js(qml_engine, bluez, "_ipc.profiles('STAX SPIRIT S3')", _ipc=ipc)
    assert "*a2dp-sink" in prof_str

    res = eval_js(qml_engine, bluez, "_ipc.setProfile('STAX SPIRIT S3', 'a2dp-sink-sbc')", _ipc=ipc)
    assert "a2dp-sink-sbc" in res
    QTest.qWait(100)
    assert "set-card-profile bluez_card.08_F0_B6_35_49_16 a2dp-sink-sbc" in pactl_log.read_text()


def test_bluez_agent_pairing_requests_and_toaster_suppression(qml_engine, mock_agent, mock_bluetooth, mock_toaster):
    bluez = get_singleton(qml_engine, "qs.services", "Bluez")
    assert bluez is not None
    qml_engine.rootContext().setContextProperty("Bluez", bluez)

    dev = MockBluetoothDevice("11:22:33:44:55:66", "Keychron K3", connected=False, paired=False, bonded=False)
    mock_bluetooth.devices.set_values([dev])

    # When pairing UI is NOT open, requestReceived pops a pairing toast
    mock_agent.trigger_request("confirm", "11:22:33:44:55:66", "Keychron K3", "123456")
    assert any(t.property("title") == "Bluetooth pairing request" and "123456" in t.property("message") for t in mock_toaster.toasts)
    assert eval_js(qml_engine, bluez, "Bluez.agentDeviceName") == "Keychron K3"

    bluez.respondAgentConfirmation(True)
    assert ("confirm", True) in mock_agent.responses

    # When pairing UI IS open, toast is suppressed to avoid obstructing modal
    mock_toaster.toasts.clear()
    bluez.setProperty("pairingUiActive", True)
    mock_agent.trigger_request("pin", "11:22:33:44:55:66", "Keychron K3")
    assert len(mock_toaster.toasts) == 0
    bluez.respondAgentPin("0000")
    assert ("pin", "0000") in mock_agent.responses

    bluez.cancelAgentPending()
    assert ("cancel", None) in mock_agent.responses


def test_bluetooth_popout_compiles_and_cleans_up_scan_on_destruction(qml_engine, mock_bluetooth):
    comp = QQmlComponent(qml_engine, str(REPO_ROOT / "modules/bar/popouts/Bluetooth.qml"))
    popouts = MockPopoutState()
    item = comp.beginCreate(qml_engine.rootContext())
    assert item is not None, f"Bluetooth.qml compile error: {comp.errors()}"
    item.setProperty("popouts", popouts)
    comp.completeCreate()

    bluez = get_singleton(qml_engine, "qs.services", "Bluez")
    bluez.acquireScan("popout", False)
    assert mock_bluetooth.defaultAdapter.property("discovering") is True
    item.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    QtCore.QCoreApplication.processEvents()
    # Component.onDestruction calls Bluez.releaseScan("popout")
    assert mock_bluetooth.defaultAdapter.property("discovering") is False


def test_osd_wrapper_no_startup_false_osd_and_mic_config_gate(qml_engine, mock_pipewire):
    # Add initial sink/source BEFORE OSD Wrapper mounts
    n_sink = MockPwNode(3, "alsa_output.pci", "Speakers", is_sink=True, ready=True, volume=0.5)
    n_src = MockPwNode(4, "alsa_input.pci", "Mic", is_sink=False, ready=True, volume=0.7)
    mock_pipewire.add_node(n_sink)
    mock_pipewire.add_node(n_src)
    mock_pipewire.set_defaultAudioSink(n_sink)
    mock_pipewire.set_defaultAudioSource(n_src)
    QtCore.QCoreApplication.processEvents()

    audio = get_singleton(qml_engine, "qs.services", "Audio")
    assert audio is not None
    qml_engine.rootContext().setContextProperty("Audio", audio)

    screen = create_qml(qml_engine, 'import Quickshell\nShellScreen { name: "DP-1" }\n')
    vis = create_qml(qml_engine, 'import qs.components\nDrawerVisibilities {}\n')

    comp = QQmlComponent(qml_engine, str(REPO_ROOT / "modules/osd/Wrapper.qml"))
    wrapper = comp.beginCreate(qml_engine.rootContext())
    assert wrapper is not None, f"osd/Wrapper.qml errors: {comp.errors()}"
    wrapper.setProperty("screen", screen)
    wrapper.setProperty("visibilities", vis)
    wrapper.setProperty("sidebarOrSessionVisible", False)
    comp.completeCreate()
    QtCore.QCoreApplication.processEvents()

    assert vis.property("osd") is False

    # Hotplug/sink swap syncs baseline cleanly without flashing OSD when trigger wasn't user volume/mute
    n_bt = MockPwNode(5, "bluez_output.AA.1", "BT", is_sink=True, ready=True, volume=0.6)
    mock_pipewire.add_node(n_bt)
    mock_pipewire.set_defaultAudioSink(n_bt)
    QtCore.QCoreApplication.processEvents()
    assert vis.property("osd") is False

    # User volume change on settled sink DOES show OSD
    audio.setVolume(0.65)
    QtCore.QCoreApplication.processEvents()
    assert vis.property("osd") is True

    # Source OSD trigger suppressed while Config.osd.enableMicrophone == False
    vis.setProperty("osd", False)
    audio.setSourceMuted(True)
    QtCore.QCoreApplication.processEvents()
    assert vis.property("osd") is False

    wrapper.deleteLater()


def test_toasts_fullscreen_policy_and_config_toasts_signals(qml_engine, mock_toaster):
    config_comp = QQmlComponent(qml_engine, str(REPO_ROOT / "modules/ConfigToasts.qml"))
    cfg_scope = config_comp.create()
    assert cfg_scope is not None, f"ConfigToasts.qml errors: {config_comp.errors()}"

    # Trigger unknownOption warning on TokenConfig -> emits Warning toast cleanly
    token_cfg = get_singleton(qml_engine, "Caelestia.Config", "TokenConfig")
    token_cfg.unknownOption.emit("foo.bar", "DP-1")
    QtCore.QCoreApplication.processEvents()
    assert any("Unknown option" in t.property("title") for t in mock_toaster.toasts)
    cfg_scope.deleteLater()

    # Now verify Toasts.qml shouldShowToast fullscreen filtering
    import sys
    hypr = get_singleton(qml_engine, "qs.services", "Hypr")
    qml_engine.rootContext().setContextProperty("Hypr", hypr)
    if "test_ricing" in sys.modules:
        import test_ricing
        mon = test_ricing.MockHyprlandMonitor(1, "DP-1")
        mon2 = test_ricing.MockHyprlandMonitor(2, "HDMI-A-1")
        ws = create_qml(qml_engine, 'import QtQuick\nQtObject { property string name: "special:magic"; property bool hasFullscreen: true; property var toplevels: QtObject { property var values: [] } }\n')
        eval_js(qml_engine, hypr, "Hypr.workspaces.values = [_w]", _w=ws)
    else:
        mon = create_qml(qml_engine, 'import QtQuick\nimport Quickshell.Hyprland\nHyprlandMonitor { name: "DP-1"; lastIpcObject: ({}); activeWorkspace: QtObject { property bool hasFullscreen: true; property var toplevels: QtObject { property var values: [] } } }\n')
        mon2 = create_qml(qml_engine, 'import Quickshell.Hyprland\nHyprlandMonitor { name: "HDMI-A-1" }\n')
    hypr.setProperty("focusedMonitor", mon)
    eval_js(qml_engine, hypr, "Hypr.monitors.values = [_m]", _m=mon)

    screen = create_qml(qml_engine, 'import Quickshell\nShellScreen { name: "DP-1" }\n')
    comp = QQmlComponent(qml_engine, str(REPO_ROOT / "modules/utilities/toasts/Toasts.qml"))
    toasts_ui = comp.beginCreate(qml_engine.rootContext())
    assert toasts_ui is not None, f"Toasts.qml errors: {comp.errors()}"
    toasts_ui.setProperty("screen", screen)
    comp.completeCreate()

    t_info = create_qml(qml_engine, 'import Caelestia\nToast { title: "Info"; message: "msg"; type: Toast.Info }\n')
    t_warn = create_qml(qml_engine, 'import Caelestia\nToast { title: "Warn"; message: "msg"; type: Toast.Warning }\n')
    t_err = create_qml(qml_engine, 'import Caelestia\nToast { title: "Err"; message: "msg"; type: Toast.Error }\n')
    qml_engine.rootContext().setContextProperty("_t_info", t_info)
    qml_engine.rootContext().setContextProperty("_t_warn", t_warn)
    qml_engine.rootContext().setContextProperty("_t_err", t_err)

    # Fullscreen policy == "important": Info hidden, Warning and Error allowed
    assert eval_js(qml_engine, toasts_ui, "shouldShowToast(_t_info)") is False
    assert eval_js(qml_engine, toasts_ui, "shouldShowToast(_t_warn)") is True
    assert eval_js(qml_engine, toasts_ui, "shouldShowToast(_t_err)") is True

    # Focused monitor mismatch suppresses all toasts on non-focused screen
    hypr.setProperty("focusedMonitor", mon2)
    assert eval_js(qml_engine, toasts_ui, "shouldShowToast(_t_err)") is False

    toasts_ui.deleteLater()
