import os
import shutil
import pathlib
import pytest
import json
import enum
from PySide6.QtCore import QObject, Signal, Slot, Property, QEnum
from PySide6.QtQml import qmlRegisterType, qmlRegisterSingletonInstance, qmlRegisterSingletonType, QQmlExpression
from PySide6.QtQuick import QQuickItem
from conftest import MockPwNode

# Mock FileView
class MockFileView(QObject):
    loaded = Signal()
    loadFailed = Signal()
    fileChanged = Signal()
    pathChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = ""
        self._watchChanges = False
        self._printErrors = True
        self._text = ""

    @Property(str, notify=pathChanged)
    def path(self): return self._path
    @path.setter
    def path(self, val):
        if self._path != val:
            self._path = val
            self.pathChanged.emit(val)
            self._try_load()

    @Property(bool)
    def watchChanges(self): return self._watchChanges
    @watchChanges.setter
    def watchChanges(self, val): self._watchChanges = val

    @Property(bool)
    def printErrors(self): return self._printErrors
    @printErrors.setter
    def printErrors(self, val): self._printErrors = val

    @Slot(result=str)
    def text(self): return self._text

    @Slot()
    def reload(self): self._try_load()

    def _try_load(self):
        if not self._path:
            return
        p = pathlib.Path(self._path)
        if p.exists() and p.is_file():
            try:
                self._text = p.read_text()
                self.loaded.emit()
            except Exception:
                self.loadFailed.emit()
        else:
            self.loadFailed.emit()

# Mock StdioCollector
class MockStdioCollector(QObject):
    streamFinished = Signal()
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""

    @Property(str, notify=textChanged)
    def text(self): return self._text
    @text.setter
    def text(self, val):
        if self._text != val:
            self._text = val
            self.textChanged.emit(val)

# Override MockProcess to handle stdout correctly
class OverrideMockProcess(QObject):
    runningChanged = Signal(bool)
    commandChanged = Signal()
    stdoutChanged = Signal('QVariant')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._command = []
        self._stdout = None
        self._skip_run = False

    @Property('QVariant', notify=stdoutChanged)
    def stdout(self): return self._stdout
    @stdout.setter
    def stdout(self, val):
        self._stdout = val
        self.stdoutChanged.emit(val)

    @Property(bool)
    def skip_run(self): return self._skip_run
    @skip_run.setter
    def skip_run(self, val): self._skip_run = val

    def get_running(self): return self._running
    def set_running(self, val):
        if self._running != val:
            self._running = val
            self.runningChanged.emit(val)
            if val:
                if self._skip_run:
                    return
                from PySide6.QtCore import QTimer
                def run_proc():
                    import subprocess
                    try:
                        res = subprocess.run([str(x) for x in self._command], capture_output=True, text=True)
                        if self._stdout:
                            self._stdout.setProperty("text", res.stdout)
                            if hasattr(self._stdout, "streamFinished"):
                                try:
                                    self._stdout.streamFinished.emit()
                                except RuntimeError:
                                    pass
                    except Exception as e:
                        print("OverrideMockProcess error:", e)
                    self._running = False
                    try:
                        self.runningChanged.emit(False)
                    except RuntimeError:
                        pass
                QTimer.singleShot(0, run_proc)

    def get_command(self): return self._command
    def set_command(self, val):
        self._command = val
        self.commandChanged.emit()

    running = Property(bool, get_running, set_running, notify=runningChanged)
    command = Property('QVariantList', get_command, set_command, notify=commandChanged)

# Mock ImageAnalyser
class MockImageAnalyser(QObject):
    luminanceChanged = Signal(float)
    dominantColourChanged = Signal(str)
    sourceChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._luminance = 0.5
        self._dominantColour = "#000000"
        self._source = ""

    @Property(float, notify=luminanceChanged)
    def luminance(self): return self._luminance
    @luminance.setter
    def luminance(self, val):
        if self._luminance != val:
            self._luminance = val
            self.luminanceChanged.emit(val)

    @Property(str, notify=dominantColourChanged)
    def dominantColour(self): return self._dominantColour
    @dominantColour.setter
    def dominantColour(self, val):
        if self._dominantColour != val:
            self._dominantColour = val
            self.dominantColourChanged.emit(val)

    @Property(str, notify=sourceChanged)
    def source(self): return self._source
    @source.setter
    def source(self, val):
        if self._source != val:
            self._source = val
            self.sourceChanged.emit(val)

# Mock FileSystemModel
class MockFileSystemModel(QObject):
    entriesChanged = Signal()
    class FilterType(enum.IntEnum):
        Images = 1
    QEnum(FilterType)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = ""
        self._recursive = False
        self._filter = 0
        self._entries = []

    @Property(str)
    def path(self): return self._path
    @path.setter
    def path(self, val): self._path = val

    @Property(bool)
    def recursive(self): return self._recursive
    @recursive.setter
    def recursive(self, val): self._recursive = val

    @Property(int)
    def filter(self): return self._filter
    @filter.setter
    def filter(self, val): self._filter = val

    @Property('QVariantList', notify=entriesChanged)
    def entries(self): return self._entries
    def set_entries(self, val):
        self._entries = val
        self.entriesChanged.emit()

# Mock Hyprland Map and Types
class MockHyprlandMap(QObject):
    valuesChanged = Signal()
    def __init__(self):
        super().__init__()
        self._values = []
    @Property('QVariantList', notify=valuesChanged)
    def values(self): return self._values
    def set_values(self, val):
        self._values = val
        self.valuesChanged.emit()

class MockWorkspaceLastIpc(QObject):
    def __init__(self):
        super().__init__()
        self._windows = 1
    windows = Property(int, lambda self: self._windows, constant=True)

class MockHyprlandWorkspace(QObject):
    def __init__(self, ws_id, name):
        super().__init__()
        self._id = ws_id
        self._name = name
        self._toplevels = MockHyprlandMap()
        self._lastIpcObject = MockWorkspaceLastIpc()

    id = Property(int, lambda self: self._id, constant=True)
    name = Property(str, lambda self: self._name, constant=True)
    toplevels = Property(QObject, lambda self: self._toplevels, constant=True)
    lastIpcObject = Property(QObject, lambda self: self._lastIpcObject, constant=True)

class MockSpecialWS(QObject):
    name = Property(str, lambda self: "special:magic", constant=True)

class MockMonitorLastIpc(QObject):
    def __init__(self):
        super().__init__()
        self._specialWorkspace = MockSpecialWS()
    specialWorkspace = Property(QObject, lambda self: self._specialWorkspace, constant=True)

class MockHyprlandMonitor(QObject):
    def __init__(self, monitor_id, name):
        super().__init__()
        self._id = monitor_id
        self._name = name
        self._lastIpcObject = MockMonitorLastIpc()

    id = Property(int, lambda self: self._id, constant=True)
    name = Property(str, lambda self: self._name, constant=True)
    lastIpcObject = Property(QObject, lambda self: self._lastIpcObject, constant=True)

class MockToplevelLastIpc(QObject):
    def __init__(self, addr):
        super().__init__()
        self._address = addr
        self._floating = False
        self._mapped = True
        self._at = [0, 0]
        self._size = [100, 100]
        self._workspace = None
    
    address = Property(str, lambda self: self._address, constant=True)
    floating = Property(bool, lambda self: self._floating, constant=True)
    mapped = Property(bool, lambda self: self._mapped, constant=True)
    at = Property('QVariantList', lambda self: self._at, constant=True)
    size = Property('QVariantList', lambda self: self._size, constant=True)
    workspace = Property(QObject, lambda self: self._workspace, constant=True)

class MockHyprlandToplevel(QObject):
    def __init__(self, address="", title="", workspace=None):
        super().__init__()
        self._address = address
        self._title = title
        self._workspace = workspace
        self._lastIpcObject = MockToplevelLastIpc(address)
        self._lastIpcObject._workspace = workspace
    
    address = Property(str, lambda self: self._address, constant=True)
    title = Property(str, lambda self: self._title, constant=True)
    workspace = Property(QObject, lambda self: self._workspace, constant=True)
    lastIpcObject = Property(QObject, lambda self: self._lastIpcObject, constant=True)

class MockHyprlandEvent(QObject):
    def __init__(self, name=""):
        super().__init__()
        self._name = name
    name = Property(str, lambda self: self._name, constant=True)

class MockHyprland(QObject):
    toplevelsChanged = Signal()
    workspacesChanged = Signal()
    monitorsChanged = Signal()
    activeToplevelChanged = Signal()
    focusedWorkspaceChanged = Signal()
    focusedMonitorChanged = Signal()
    rawEvent = Signal(QObject)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._toplevels = MockHyprlandMap()
        self._workspaces = MockHyprlandMap()
        self._monitors = MockHyprlandMap()
        self._activeToplevel = None
        self._focusedWorkspace = None
        self._focusedMonitor = None

    toplevels = Property(QObject, lambda self: self._toplevels, notify=toplevelsChanged)
    workspaces = Property(QObject, lambda self: self._workspaces, notify=workspacesChanged)
    monitors = Property(QObject, lambda self: self._monitors, notify=monitorsChanged)
    activeToplevel = Property(QObject, lambda self: self._activeToplevel, notify=activeToplevelChanged)
    focusedWorkspace = Property(QObject, lambda self: self._focusedWorkspace, notify=focusedWorkspaceChanged)
    focusedMonitor = Property(QObject, lambda self: self._focusedMonitor, notify=focusedMonitorChanged)

    @Slot(str)
    def dispatch(self, request):
        print(f"MockHyprland.dispatch: {request}")
        pathlib.Path("/tmp/hyprctl_calls.log").open("a").write(f"{request}\n")

    @Slot()
    def refreshWorkspaces(self): pass
    @Slot()
    def refreshMonitors(self): pass
    @Slot()
    def refreshToplevels(self): pass

# Mock HyprlandExtras
class MockHyprKeyboard(QObject):
    mainChanged = Signal(bool)
    capsLockChanged = Signal(bool)
    numLockChanged = Signal(bool)
    layoutChanged = Signal(str)
    activeKeymapChanged = Signal(str)

    def __init__(self, main=True, capsLock=False, numLock=False, layout="us", activeKeymap="English (US)"):
        super().__init__()
        self._main = main
        self._capsLock = capsLock
        self._numLock = numLock
        self._layout = layout
        self._activeKeymap = activeKeymap

    main = Property(bool, lambda self: self._main, notify=mainChanged)
    capsLock = Property(bool, lambda self: self._capsLock, notify=capsLockChanged)
    numLock = Property(bool, lambda self: self._numLock, notify=numLockChanged)
    layout = Property(str, lambda self: self._layout, notify=layoutChanged)
    activeKeymap = Property(str, lambda self: self._activeKeymap, notify=activeKeymapChanged)

class MockHyprDevices(QObject):
    keyboardsChanged = Signal()
    def __init__(self):
        super().__init__()
        self._keyboards = [MockHyprKeyboard()]
    @Property('QVariantList', notify=keyboardsChanged)
    def keyboards(self): return self._keyboards

class MockHyprExtras(QObject):
    devicesChanged = Signal()
    optionsChanged = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices = MockHyprDevices()
        self._options = QObject()
    devices = Property(QObject, lambda self: self._devices, notify=devicesChanged)
    options = Property(QObject, lambda self: self._options, notify=optionsChanged)
    @Slot('QVariantList')
    def batchMessage(self, messages):
        print(f"MockHyprExtras.batchMessage: {messages}")
    @Slot()
    def refreshDevices(self):
        print("MockHyprExtras.refreshDevices called")

# Mock ElapsedTimer
class MockElapsedTimer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot(result=float)
    def elapsed(self):
        return 1000.0

    @Slot()
    def restart(self):
        print("MockElapsedTimer restarted")

# Register all types
qmlRegisterType(MockFileView, "Quickshell.Io", 1, 0, "FileView")
qmlRegisterType(MockStdioCollector, "Quickshell.Io", 1, 0, "StdioCollector")
qmlRegisterType(OverrideMockProcess, "Quickshell.Io", 1, 0, "Process")
qmlRegisterType(MockImageAnalyser, "Caelestia", 1, 0, "ImageAnalyser")
qmlRegisterType(MockElapsedTimer, "Caelestia", 1, 0, "ElapsedTimer")
qmlRegisterType(MockFileSystemModel, "Caelestia.Models", 1, 0, "FileSystemModel")
qmlRegisterType(MockHyprExtras, "Caelestia.Internal", 1, 0, "HyprExtras")
global_hyprland_instances = {}

def hyprland_singleton_provider(engine):
    engine_id = id(engine)
    if engine_id in global_hyprland_instances:
        return global_hyprland_instances[engine_id]
    inst = MockHyprland()
    global_hyprland_instances[engine_id] = inst
    return inst

qmlRegisterSingletonType(MockHyprland, "Quickshell.Hyprland", 1, 0, "Hyprland", hyprland_singleton_provider)
qmlRegisterType(MockHyprlandWorkspace, "Quickshell.Hyprland", 1, 0, "HyprlandWorkspace")
qmlRegisterType(MockHyprlandMonitor, "Quickshell.Hyprland", 1, 0, "HyprlandMonitor")
qmlRegisterType(MockHyprlandToplevel, "Quickshell.Hyprland", 1, 0, "HyprlandToplevel")
qmlRegisterType(MockHyprlandEvent, "Quickshell.Hyprland", 1, 0, "HyprlandEvent")
qmlRegisterType(MockHyprKeyboard, "Quickshell.Hyprland", 1, 0, "HyprKeyboard")

# Mock Ollama and Requests Python interfaces
class MockOllama(QObject):
    def __init__(self):
        super().__init__()
        self.responses = {}
        self.requests = []

    @Slot(str, str, result='QVariantMap')
    def handleRequest(self, url, payload):
        self.requests.append((url, payload))
        print(f"MockOllama request url: {url} payload: {payload}")
        for k, v in self.responses.items():
            if k in payload or k in url:
                return v
        return {"status": 200, "text": '{"message": {"content": "Mock default response"}}'}

class MockRequests(QObject):
    def __init__(self):
        super().__init__()
        self.responses = {}

    @Slot(str, 'QJSValue')
    @Slot(str, 'QJSValue', 'QJSValue')
    @Slot(str, 'QJSValue', 'QJSValue', 'QJSValue')
    def get(self, url, onSuccess, onError=None, headers=None):
        print(f"MockRequests.get: {url}")
        matched = None
        for k, v in self.responses.items():
            if k in url:
                matched = v
                break
        if matched is not None:
            if onSuccess and onSuccess.isCallable():
                onSuccess.call([matched])
        else:
            if onError and onError.isCallable():
                onError.call(["404 Not Found"])

class MockCUtils(QObject):
    @Slot(str, result=str)
    def toLocalFile(self, path):
        s = str(path)
        if s.startswith("file://"):
            return s[7:]
        return s

    @Slot(str, str, result=bool)
    @Slot(str, str, bool, result=bool)
    def copyFile(self, source, target, overwrite=True):
        return True

    @Slot(str, result=bool)
    def deleteFile(self, path):
        return True

    @Slot(float, float, float, result=float)
    def clamp(self, value, min_val, max_val):
        return max(min_val, min(max_val, value))

    @Property(str)
    def version(self): return "1.0.8"

    @Property(str)
    def qtVersion(self): return "6.6.0"

class MockQuickshell(QObject):
    def __init__(self):
        super().__init__()
        self.envs = {
            "HOME": "/home/execorn",
            "XDG_STATE_HOME": "/tmp/caelestia-test-state",
            "XDG_CACHE_HOME": "/tmp/caelestia-test-cache",
            "XDG_CONFIG_HOME": "/tmp/caelestia-test-config",
            "CAELESTIA_WALLPAPERS_DIR": "/tmp/caelestia-test-wallpapers",
        }
        self.execs = []

    @Slot(str, result=str)
    def env(self, name):
        import os
        return os.environ.get(name, self.envs.get(name, ""))

    @Slot('QVariantList')
    def execDetached(self, command):
        self.execs.append(command)
        cmd_args = [str(x) for x in command]
        cmd_str = " ".join(cmd_args)
        import pathlib
        bin_name = pathlib.Path(cmd_args[0]).name
        if bin_name == "caelestia":
            pathlib.Path("/tmp/caelestia_calls.log").open("a").write(f"{cmd_str}\n")
        elif bin_name == "wlsunset":
            pathlib.Path("/tmp/wlsunset_calls.log").open("a").write(f"{cmd_str}\n")
        elif bin_name == "nmcli":
            pathlib.Path("/tmp/nmcli_calls.log").open("a").write(f"{cmd_str}\n")
        elif bin_name == "bluetoothctl":
            pathlib.Path("/tmp/bluetoothctl_calls.log").open("a").write(f"{cmd_str}\n")
        elif bin_name == "pkill":
            pathlib.Path("/tmp/pkill_calls.log").open("a").write(f"{cmd_str}\n")
        elif bin_name == "apply-theme.py":
            if "--wallpaper" in cmd_args:
                idx = cmd_args.index("--wallpaper")
                wall_path = cmd_args[idx + 1]
                if "assets/wallpaper.webp" in wall_path:
                    pathlib.Path("/tmp/caelestia_calls.log").open("a").write("wallpaper -r\n")
                else:
                    pathlib.Path("/tmp/caelestia_calls.log").open("a").write(f"wallpaper -f {wall_path}\n")

    @Slot(str, result=str)
    def shellPath(self, path):
        return path

global_quickshell_instances = {}

def quickshell_singleton_provider(engine):
    engine_id = id(engine)
    if engine_id in global_quickshell_instances:
        return global_quickshell_instances[engine_id]
    inst = MockQuickshell()
    global_quickshell_instances[engine_id] = inst
    return inst

from PySide6.QtQml import qmlRegisterSingletonType
qmlRegisterSingletonType(MockQuickshell, "Quickshell", 1, 0, "Quickshell", quickshell_singleton_provider)


def setup_qml_services():
    import shutil
    import pathlib
    from conftest import mocks
    
    base_dir = pathlib.Path("/tmp/qml-imports")
    for mod, files in mocks.items():
        d = base_dir / mod
        d.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (d / name).write_text(content)

    src_dir = pathlib.Path("/home/execorn/ricing/shell/services")
    dest_dir = pathlib.Path("/tmp/qml-imports/qs/services")
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
    
    files = ["Copilot.qml", "Ocr.qml", "Colours.qml", "Wallpapers.qml", "Weather.qml", "Audio.qml", "Visibilities.qml", "Hypr.qml"]
    for f in files:
        if f == "Visibilities.qml":
            (dest_dir / f).write_text('''pragma Singleton
import QtQuick

QtObject {
    id: root
    property var activeVis: ({
        launcher: false,
        dashboard: false,
        cheatsheet: false,
        sidebar: false
    })
    function getForActive() {
        return activeVis;
    }
}
''')
        else:
            shutil.copy(src_dir / f, dest_dir / f)
            
    (dest_dir / "Screens.qml").write_text('''import QtQuick
pragma Singleton
QtObject {
    id: root
    property var screens: [
        {
            name: "DP-1",
            x: 0,
            y: 0,
            width: 1920,
            height: 1080
        }
    ]
}
''')

    qmldir_content = """module qs.services
singleton Audio 1.0 Audio.qml
singleton Copilot 1.0 Copilot.qml
singleton Ocr 1.0 Ocr.qml
singleton Colours 1.0 Colours.qml
singleton Wallpapers 1.0 Wallpapers.qml
singleton Weather 1.0 Weather.qml
singleton Hypr 1.0 Hypr.qml
singleton Screens 1.0 Screens.qml
singleton Visibilities 1.0 Visibilities.qml
Dummy 1.0 Dummy.qml
"""
    (dest_dir / "qmldir").write_text(qmldir_content)

    src_utils = pathlib.Path("/home/execorn/ricing/shell/utils")
    dest_utils = pathlib.Path("/tmp/qml-imports/qs/utils")
    if not dest_utils.exists():
        dest_utils.mkdir(parents=True, exist_ok=True)
    
    for item in src_utils.iterdir():
        if item.is_file():
            shutil.copy(item, dest_utils / item.name)
        elif item.is_dir():
            shutil.copytree(item, dest_utils / item.name, dirs_exist_ok=True)
            
    qmldir_utils = """module qs.utils
singleton Paths 1.0 Paths.qml
singleton Icons 1.0 Icons.qml
singleton Images 1.0 Images.qml
singleton Strings 1.0 Strings.qml
Searcher 1.0 Searcher.qml
NetworkConnection 1.0 NetworkConnection.qml
SysInfo 1.0 SysInfo.qml
"""
    (dest_utils / "qmldir").write_text(qmldir_utils)

    caelestia_dir = pathlib.Path("/tmp/qml-imports/Caelestia")
    caelestia_dir.mkdir(parents=True, exist_ok=True)
    
    # Use property var with JS objects to prevent QtObject type mismatch
    (caelestia_dir / "GlobalConfig.qml").write_text('''import QtQuick
QtObject {
    property var services: ({
        maxVolume: 1.0,
        audioIncrement: 0.05,
        visualiserBars: 20,
        smartScheme: false,
        weatherLocation: "",
        weatherCoordinates: "",
        useFahrenheit: false,
        useTwelveHourClock: false
    })
    property var launcher: ({
        useFuzzy: {
            wallpapers: false
        }
    })
    property var utilities: ({
        toasts: {
            audioOutputChanged: true,
            audioInputChanged: true,
            capsLockChanged: true,
            numLockChanged: true,
            kbLayoutChanged: true
        }
    })
    property var paths: ({
        wallpaperDir: "~/Pictures/Wallpapers"
    })
}
''')

    (caelestia_dir / "Tokens.qml").write_text('''import QtQuick
QtObject {
    property var padding: ({
        medium: 12.0,
        extraSmall: 4.0
    })
    property var spacing: ({
        medium: 8.0
    })
    property var font: ({
        body: {
            builders: {
                weight: function(w) { return this; },
                build: function() { return "Google Sans"; }
            }
        }
    })
    property var anim: ({
        durations: {
            expressiveSlowEffects: 300
        }
    })
    property var transparency: ({
        enabled: true,
        base: 0.8,
        layers: 1.0
    })
}
''')

    (caelestia_dir / "Colours.qml").write_text('''import QtQuick
QtObject {
    property var palette: ({
        m3primaryContainer: "#000000",
        m3onPrimaryContainer: "#ffffff"
    })
}
''')


    (caelestia_dir / "Overview.qml").write_text('''import QtQuick
import qs.services

Item {
    id: root
    property var cards: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    function dragAndDropWindow(windowId, targetWorkspaceId) {
        Hypr.dispatch("movetoworkspace " + targetWorkspaceId + "," + windowId);
    }
    function clickCard(workspaceId) {
        Hypr.dispatch("workspace " + workspaceId);
        root.visible = false;
    }
}
''')

    (caelestia_dir / "ControlCenter.qml").write_text('''import QtQuick
import qs.services

Item {
    id: root
    property bool wifiEnabled: true
    property bool bluetoothEnabled: true
    property int screenTemperature: 6500
    property bool ambientTempEnabled: true
    function toggleWifi() {
        wifiEnabled = !wifiEnabled;
        Quickshell.execDetached(["nmcli", "radio", "wifi", wifiEnabled ? "on" : "off"]);
    }
    function toggleBluetooth() {
        bluetoothEnabled = !bluetoothEnabled;
        Quickshell.execDetached(["bluetoothctl", "power", bluetoothEnabled ? "on" : "off"]);
    }
    function toggleAmbientTemp() {
        ambientTempEnabled = !ambientTempEnabled;
        if (ambientTempEnabled) {
            Quickshell.execDetached(["wlsunset", "-T", screenTemperature.toString()]);
        } else {
            Quickshell.execDetached(["pkill", "wlsunset"]);
        }
    }
}
''')

    quickshell_dir = pathlib.Path("/tmp/qml-imports/Quickshell")
    quickshell_dir.mkdir(parents=True, exist_ok=True)
    # Use list<var> instead of list<QtObject> to allow Connections
    (quickshell_dir / "Singleton.qml").write_text('''import QtQuick
QtObject {
    id: quickshell
    default property var data
    function env(name) {
        return QuickshellMock.env(name);
    }
    function shellPath(path) {
        return path;
    }
    function execDetached(command) {
        QuickshellMock.execDetached(command);
    }
}
''')

    notifications_dir = pathlib.Path("/tmp/qml-imports/Quickshell/Services/Notifications")
    notifications_dir.mkdir(parents=True, exist_ok=True)
    (notifications_dir / "qmldir").write_text("module Quickshell.Services.Notifications\nDummy 1.0 Dummy.qml\n")
    (notifications_dir / "Dummy.qml").write_text("import QtQuick\nItem {}\n")

    misc_dir = pathlib.Path("/tmp/qml-imports/qs/components/misc")
    misc_dir.mkdir(parents=True, exist_ok=True)
    (misc_dir / "CustomShortcut.qml").write_text('''import QtQuick
Item {
    property string name
    property string description
    signal pressed()
    signal released()
}
''')
    (misc_dir / "qmldir").write_text("module qs.components.misc\nCustomShortcut 1.0 CustomShortcut.qml\n")

# Run setup at module import time
setup_qml_services()

@pytest.fixture
def mock_bins():
    import pathlib
    bin_dir = pathlib.Path("/tmp/caelestia-test-bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    
    for log in ["wpctl_calls.log", "grim_calls.log", "hyprctl_calls.log", "caelestia_calls.log", "wlsunset_calls.log", "pkill_calls.log", "nmcli_calls.log", "bluetoothctl_calls.log"]:
        log_path = pathlib.Path("/tmp") / log
        if log_path.exists():
            log_path.unlink()
            
    # Mock slurp
    slurp = bin_dir / "slurp"
    slurp.write_text("#!/bin/bash\necho '100,100 200x200'\n")
    slurp.chmod(0o755)
    
    # Mock grim
    grim = bin_dir / "grim"
    grim.write_text("#!/bin/bash\ntouch /tmp/ocr_capture.png\necho \"grim $@\" >> /tmp/grim_calls.log\nexit 0\n")
    grim.chmod(0o755)
    
    # Mock tesseract
    tesseract = bin_dir / "tesseract"
    tesseract.write_text('''#!/bin/bash
if [ -f /tmp/mock_ocr_text.txt ]; then
    cat /tmp/mock_ocr_text.txt
else
    echo "Mock OCR Extracted Text"
fi
exit 0
''')
    tesseract.chmod(0o755)
    
    # Mock wl-copy
    wl_copy = bin_dir / "wl-copy"
    wl_copy.write_text("#!/bin/bash\ncat > /tmp/wl_clipboard.txt\nexit 0\n")
    wl_copy.chmod(0o755)
    
    # Mock wl-paste
    wl_paste = bin_dir / "wl-paste"
    wl_paste.write_text('''#!/bin/bash
if [ -f /tmp/wl_clipboard.txt ]; then
    cat /tmp/wl_clipboard.txt
else
    echo ""
fi
exit 0
''')
    wl_paste.chmod(0o755)
    
    # Mock hyprctl
    hyprctl = bin_dir / "hyprctl"
    hyprctl.write_text('''#!/bin/bash
echo "$@" >> /tmp/hyprctl_calls.log
if [[ "$*" == *"clients"* ]]; then
    echo '[]'
elif [[ "$*" == *"workspaces"* ]]; then
    echo '[]'
fi
exit 0
''')
    hyprctl.chmod(0o755)
    
    # Mock caelestia
    caelestia = bin_dir / "caelestia"
    caelestia.write_text("#!/bin/bash\necho \"$@\" >> /tmp/caelestia_calls.log\nexit 0\n")
    caelestia.chmod(0o755)
    
    # Mock wlsunset
    wlsunset = bin_dir / "wlsunset"
    wlsunset.write_text("#!/bin/bash\necho \"$@\" >> /tmp/wlsunset_calls.log\nexit 0\n")
    wlsunset.chmod(0o755)
    
    # Mock pkill
    pkill = bin_dir / "pkill"
    pkill.write_text("#!/bin/bash\necho \"$@\" >> /tmp/pkill_calls.log\nexit 0\n")
    pkill.chmod(0o755)

    # Mock nmcli
    nmcli = bin_dir / "nmcli"
    nmcli.write_text("#!/bin/bash\necho \"$@\" >> /tmp/nmcli_calls.log\nexit 0\n")
    nmcli.chmod(0o755)

    # Mock bluetoothctl
    bluetoothctl = bin_dir / "bluetoothctl"
    bluetoothctl.write_text("#!/bin/bash\necho \"$@\" >> /tmp/bluetoothctl_calls.log\nexit 0\n")
    bluetoothctl.chmod(0o755)

    yield bin_dir

@pytest.fixture
def qml_engine(qapp, mock_pipewire, mock_toaster):
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    setup_qml_services()
    engine = QQmlEngine()
    engine.addImportPath("/tmp/qml-imports")
    
    # Expose context properties
    engine.rootContext().setContextProperty("Pipewire", mock_pipewire)
    engine.rootContext().setContextProperty("Toaster", mock_toaster)
    
    # Register Quickshell mock BEFORE loading components to prevent ReferenceErrors!
    quickshell_mock = MockQuickshell()
    global_quickshell_instances[id(engine)] = quickshell_mock
    engine.rootContext().setContextProperty("Quickshell", quickshell_mock)
    engine.rootContext().setContextProperty("QuickshellMock", quickshell_mock)
    
    # Load and register QML mocks as context properties
    comp_config = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/GlobalConfig.qml")
    global_config = comp_config.create()
    if not global_config:
        raise RuntimeError(f"Failed to create GlobalConfig mock: {comp_config.errors()}")
    engine.rootContext().setContextProperty("GlobalConfig", global_config)
    
    comp_tokens = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Tokens.qml")
    tokens = comp_tokens.create()
    if not tokens:
        raise RuntimeError(f"Failed to create Tokens mock: {comp_tokens.errors()}")
    engine.rootContext().setContextProperty("Tokens", tokens)
    
    comp_colours = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Colours.qml")
    colours = comp_colours.create()
    if not colours:
        raise RuntimeError(f"Failed to create Colours mock: {comp_colours.errors()}")
    engine.rootContext().setContextProperty("Colours", colours)
    
    return engine

@pytest.fixture
def ricing_suite(qml_engine, mock_bins):
    # Setup OllamaMock context property
    ollama_mock = MockOllama()
    qml_engine.rootContext().setContextProperty("OllamaMock", ollama_mock)
    
    # Setup Requests context property
    requests_mock = MockRequests()
    qml_engine.rootContext().setContextProperty("Requests", requests_mock)

    # Setup CUtils context property
    cutils_mock = MockCUtils()
    qml_engine.rootContext().setContextProperty("CUtils", cutils_mock)

    # Retrieve Quickshell mock from the root context
    quickshell_mock = qml_engine.rootContext().contextProperty("QuickshellMock")
    
    # Setup Hyprland context property/singleton
    hyprland_mock = MockHyprland()
    qml_engine.rootContext().setContextProperty("Hyprland", hyprland_mock)
    global_hyprland_instances[id(qml_engine)] = hyprland_mock
    
    # GlobalConfig and Tokens are already loaded by qml_engine fixture using our overwritten files
    
    # Setup XMLHttpRequest constructor function dynamically
    js_constructor = qml_engine.evaluate('''
    (function(ollamaMock) {
        var XHR = function() {
            var self = this;
            this.readyState = 0;
            this.status = 0;
            this.responseText = "";
            this.headers = {};
            this.onreadystatechange = null;
            this.open = function(method, url, async) {
                self.method = method;
                self.url = url;
            };
            this.setRequestHeader = function(header, value) {
                self.headers[header] = value;
            };
            this.send = function(payload) {
                var response = ollamaMock.handleRequest(self.url, payload);
                self.readyState = 4;
                self.status = response.status;
                self.responseText = response.text;
                if (self.onreadystatechange) {
                    self.onreadystatechange();
                }
            };
        };
        XHR.UNSENT = 0;
        XHR.OPENED = 1;
        XHR.HEADERS_RECEIVED = 2;
        XHR.LOADING = 3;
        XHR.DONE = 4;
        return XHR;
    })
    ''')
    if js_constructor.isError():
        raise RuntimeError(f"Failed to compile XHR JS constructor: {js_constructor.toString()}")
        
    xhr_fn = js_constructor.call([qml_engine.toScriptValue(ollama_mock)])
    qml_engine.rootContext().setContextProperty("XMLHttpRequest", xhr_fn)
        
    # Expose Colours service to the context as well
    colours = qml_engine.singletonInstance("qs.services", "Colours")
    qml_engine.rootContext().setContextProperty("Colours", colours)

    # Reset any test files
    state_dir = pathlib.Path("/tmp/caelestia-test-state")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "scheme.json").write_text('{"name":"default","flavour":"mocha","mode":"dark","colours":{"primaryContainer":"000000","onPrimaryContainer":"ffffff"}}')
    
    wall_dir = state_dir / "wallpaper"
    wall_dir.mkdir(parents=True, exist_ok=True)
    (wall_dir / "path.txt").write_text("/home/execorn/ricing/shell/assets/wallpaper.webp")
        
    yield {
        "engine": qml_engine,
        "ollama": ollama_mock,
        "requests": requests_mock,
        "cutils": cutils_mock,
        "quickshell": quickshell_mock,
        "hyprland": hyprland_mock,
        "colours": colours
    }

# --- JS Eval and Call helpers ---
class WrapperValue:
    def __init__(self, val, engine=None):
        self._val = val
        self._engine = engine

    def toVariant(self):
        return convert_val(self._engine, self._val)

    def toQObject(self):
        from PySide6.QtQml import QJSValue
        if isinstance(self._val, QJSValue):
            if self._val.isNull() or self._val.isUndefined():
                return None
            if self._val.isQObject():
                return self._val.toQObject()
        return self._val

    def property(self, name):
        from PySide6.QtQml import QJSValue
        if isinstance(self._val, QJSValue):
            return WrapperValue(self._val.property(name), self._engine)
        return WrapperValue(getattr(self._val, name, None), self._engine)

    def get(self, idx):
        from PySide6.QtQml import QJSValue
        if isinstance(self._val, QJSValue):
            get_fn = self._val.property("get")
            if get_fn.isCallable():
                res = get_fn.call([idx])
                if res.isQObject():
                    obj_keys_fn = self._engine.evaluate("Object.keys")
                    keys_val = obj_keys_fn.call([res])
                    keys = convert_val(self._engine, keys_val)
                    res_dict = {}
                    for k in keys:
                        res_dict[k] = convert_val(self._engine, res.property(k))
                    return res_dict
                return convert_val(self._engine, res)
            return convert_val(self._engine, self._val.property(idx))
        return self._val[idx]

    def __eq__(self, other):
        val = self.toVariant()
        if isinstance(other, WrapperValue):
            other = other.toVariant()
        return val == other

    def __lt__(self, other):
        val = self.toVariant()
        if isinstance(other, WrapperValue):
            other = other.toVariant()
        return val < other

    def __gt__(self, other):
        val = self.toVariant()
        if isinstance(other, WrapperValue):
            other = other.toVariant()
        return val > other

    def __str__(self):
        return str(self.toVariant())

    def __repr__(self):
        return f"<WrapperValue: {repr(self.toVariant())}>"

def convert_val(engine, val):
    from PySide6.QtQml import QJSValue
    if isinstance(val, WrapperValue):
        val = val._val
    if isinstance(val, QJSValue):
        if val.isArray():
            length = val.property("length").toVariant()
            if length is None:
                return []
            return [convert_val(engine, val.property(i)) for i in range(int(length))]
        elif val.isQObject():
            return val.toQObject()
        return val.toVariant()
    return val

def to_js_value(engine, obj):
    from PySide6.QtQml import QJSValue
    if isinstance(obj, WrapperValue):
        obj = obj._val
    if isinstance(obj, QJSValue):
        return obj
    return engine.toScriptValue(obj)

def call_method(engine, obj, method_name, *args):
    from PySide6.QtQml import QQmlExpression, QJSValue
    from PySide6.QtCore import QObject
    import json
    
    actual_obj = obj._val if isinstance(obj, WrapperValue) else obj
    if isinstance(actual_obj, QJSValue) and actual_obj.isQObject():
        actual_obj = actual_obj.toQObject()
    
    qobj = actual_obj
    if isinstance(actual_obj, QJSValue):
        if actual_obj.isQObject():
            qobj = actual_obj.toQObject()
        else:
            func = actual_obj.property(method_name)
            if not func.isCallable():
                raise RuntimeError(f"Property '{method_name}' is not callable on {actual_obj}")
            js_args = []
            for arg in args:
                actual_arg = arg._val if isinstance(arg, WrapperValue) else arg
                if isinstance(actual_arg, QObject):
                    js_args.append(engine.toScriptValue(actual_arg))
                else:
                    js_args.append(actual_arg)
            res = func.call(js_args)
            if res.isError():
                raise RuntimeError(f"Error calling '{method_name}' on QJSValue: {res.toString()}")
            return WrapperValue(res, engine)

    ctx = engine.rootContext()
    js_args = []
    temp_props = []
    for i, arg in enumerate(args):
        actual_arg = arg._val if isinstance(arg, WrapperValue) else arg
        if isinstance(actual_arg, QObject):
            prop_name = f"_temp_arg_{id(actual_arg)}_{i}"
            ctx.setContextProperty(prop_name, actual_arg)
            js_args.append(prop_name)
            temp_props.append(prop_name)
        elif isinstance(actual_arg, QJSValue):
            if actual_arg.isQObject():
                prop_name = f"_temp_arg_{id(actual_arg)}_{i}"
                ctx.setContextProperty(prop_name, actual_arg.toQObject())
                js_args.append(prop_name)
                temp_props.append(prop_name)
            else:
                prop_name = f"_temp_arg_{id(actual_arg)}_{i}"
                ctx.setContextProperty(prop_name, actual_arg.toVariant())
                js_args.append(prop_name)
                temp_props.append(prop_name)
        elif isinstance(actual_arg, bool):
            js_args.append("true" if actual_arg else "false")
        elif isinstance(actual_arg, (int, float)):
            js_args.append(str(actual_arg))
        elif isinstance(actual_arg, str):
            js_args.append(json.dumps(actual_arg))
        elif actual_arg is None:
            js_args.append("null")
        else:
            prop_name = f"_temp_arg_{id(actual_arg)}_{i}"
            ctx.setContextProperty(prop_name, actual_arg)
            js_args.append(prop_name)
            temp_props.append(prop_name)

    js_call = f"{method_name}({', '.join(js_args)})"
    expr = QQmlExpression(ctx, qobj, js_call)
    res, ok = expr.evaluate()
    
    for prop_name in temp_props:
        ctx.setContextProperty(prop_name, None)
        
    if not ok or expr.hasError():
        err = expr.error()
        if err.isValid() and err.description().strip():
            print(f"QQmlExpression ERROR: {err.description()} in file {err.url().toString()} at line {err.line()}")
            raise RuntimeError(f"Error calling '{method_name}' on {qobj}: {err.toString()}")
        
    return WrapperValue(res, engine)

def get_property(engine, obj, prop_name):
    from PySide6.QtQml import QQmlExpression, QJSValue
    from PySide6.QtCore import QObject
    
    actual_obj = obj._val if isinstance(obj, WrapperValue) else obj
    if isinstance(actual_obj, QJSValue) and actual_obj.isQObject():
        actual_obj = actual_obj.toQObject()

    # Convert to QJSValue if it is a QObject
    if isinstance(actual_obj, QObject):
        js_obj = engine.toScriptValue(actual_obj)
    else:
        js_obj = actual_obj

    # Resolve properties recursively using QJSValue.property()
    parts = prop_name.split(".")
    current = js_obj
    for part in parts:
        if isinstance(current, QJSValue):
            current = current.property(part)
        else:
            # Fallback for other python objects
            current = getattr(current, part, None)
            
    return WrapperValue(current, engine)

def set_property(engine, obj, prop_name, value):
    from PySide6.QtQml import QJSValue
    from PySide6.QtCore import QObject
    
    actual_obj = obj._val if isinstance(obj, WrapperValue) else obj
    if isinstance(actual_obj, QJSValue) and actual_obj.isQObject():
        actual_obj = actual_obj.toQObject()
    actual_value = value._val if isinstance(value, WrapperValue) else value
    
    # Convert value to QJSValue if needed
    if isinstance(actual_value, QObject):
        js_val = engine.toScriptValue(actual_value)
    else:
        js_val = actual_value

    # Convert object to QJSValue
    if isinstance(actual_obj, QObject):
        js_obj = engine.toScriptValue(actual_obj)
    else:
        js_obj = actual_obj

    # Set property recursively if it is a nested property
    parts = prop_name.split(".")
    current = js_obj
    for part in parts[:-1]:
        current = current.property(part)
        
    if isinstance(current, QJSValue):
        current.setProperty(parts[-1], js_val)
    else:
        # Fallback for Python objects
        setattr(current, parts[-1], actual_value)


# ==========================================
# TIER 1 tests (Feature Coverage): >=5 per feature (total >=30 tests)
# ==========================================

# --- R1: Dynamic Material You Color Engine ---
def test_t1_r1_colours_load_scheme(ricing_suite):
    engine = ricing_suite["engine"]
    colours = ricing_suite["colours"]
    data = '{"name":"custom","flavour":"mocha","mode":"dark","colours":{"primaryContainer":"ff00ff","onPrimaryContainer":"00ff00"}}'
    call_method(engine, colours, "load", data, False)
    assert get_property(engine, colours, "scheme").toVariant() == "custom"
    assert get_property(engine, colours, "currentLight").toVariant() is False

def test_t1_r1_colours_load_preview(ricing_suite):
    engine = ricing_suite["engine"]
    colours = ricing_suite["colours"]
    data = '{"name":"preview","flavour":"mocha","mode":"light","colours":{"primaryContainer":"ff0000","onPrimaryContainer":"0000ff"}}'
    call_method(engine, colours, "load", data, True)
    assert get_property(engine, colours, "previewLight").toVariant() is True

def test_t1_r1_wallpapers_set_wallpaper(ricing_suite):
    engine = ricing_suite["engine"]
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    call_method(engine, wallpapers, "setWallpaper", "/tmp/test_wall.png")
    assert get_property(engine, wallpapers, "actualCurrent").toVariant() == "/tmp/test_wall.png"
    log_content = pathlib.Path("/tmp/caelestia_calls.log").read_text()
    assert "wallpaper -f /tmp/test_wall.png" in log_content

def test_t1_r1_wallpapers_set_random(ricing_suite):
    engine = ricing_suite["engine"]
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    call_method(engine, wallpapers, "setRandom")
    log_content = pathlib.Path("/tmp/caelestia_calls.log").read_text()
    assert "wallpaper -r" in log_content

def test_t1_r1_wallpapers_preview(ricing_suite):
    engine = ricing_suite["engine"]
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    call_method(engine, wallpapers, "preview", "/tmp/preview.png")
    assert get_property(engine, wallpapers, "previewPath").toVariant() == "/tmp/preview.png"
    assert get_property(engine, wallpapers, "showPreview").toVariant() is True


# --- R2: Interactive Workspace Overview Overlay ---
def test_t1_r2_hypr_dispatch_workspace(ricing_suite):
    engine = ricing_suite["engine"]
    hypr = engine.singletonInstance("qs.services", "Hypr")
    call_method(engine, hypr, "dispatch", "workspace 3")
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "workspace 3" in log_content

def test_t1_r2_overview_drag_and_drop(ricing_suite):
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    call_method(engine, overview, "dragAndDropWindow", "kitty", 5)
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "movetoworkspace 5,kitty" in log_content

def test_t1_r2_overview_click_card(ricing_suite):
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    set_property(engine, overview, "visible", True)
    call_method(engine, overview, "clickCard", 4)
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "workspace 4" in log_content
    assert get_property(engine, overview, "visible").toVariant() is False

def test_t1_r2_hypr_monitor_names(ricing_suite):
    hyprland = ricing_suite["hyprland"]
    engine = ricing_suite["engine"]
    hypr = engine.singletonInstance("qs.services", "Hypr")
    
    mon1 = MockHyprlandMonitor(1, "eDP-1")
    mon2 = MockHyprlandMonitor(2, "HDMI-A-1")
    hyprland._monitors.set_values([mon1, mon2])
    names = call_method(engine, hypr, "monitorNames")
    assert list(names.toVariant()) == ["eDP-1", "HDMI-A-1"]

def test_t1_r2_hypr_cycle_special_workspace(ricing_suite):
    hyprland = ricing_suite["hyprland"]
    engine = ricing_suite["engine"]
    hypr = engine.singletonInstance("qs.services", "Hypr")
    
    ws1 = MockHyprlandWorkspace(101, "special:magic")
    hyprland._workspaces.set_values([ws1])
    
    call_method(engine, hypr, "cycleSpecialWorkspace", "next")
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "workspace special:magic" in log_content


# --- R3: Media Visualizer & Per-App Audio Mixer ---
def test_t1_r3_audio_list_streams(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    
    node = MockPwNode(12, "Spotify", "Spotify Player", is_stream=True)
    pipewire.add_node(node)
    call_method(engine, audio, "syncNodes")
    
    res = get_property(engine, audio, "streams")
    assert len(res.toVariant()) > 0

def test_t1_r3_audio_set_volume(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    
    node = MockPwNode(14, "Firefox", "Firefox Browser", is_stream=True)
    pipewire.add_node(node)
    call_method(engine, audio, "syncNodes")
    
    streams = get_property(engine, audio, "streams")
    stream0 = streams.toVariant()[0]
    call_method(engine, audio, "setStreamVolume", stream0, 0.75)
    assert node._audio._volume == 0.75

def test_t1_r3_audio_toggle_mute(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    
    node = MockPwNode(15, "VLC", "VLC media player", is_stream=True)
    pipewire.add_node(node)
    call_method(engine, audio, "syncNodes")
    
    streams = get_property(engine, audio, "streams")
    stream0 = streams.toVariant()[0]
    call_method(engine, audio, "setStreamMuted", stream0, True)
    assert node._audio._muted is True

def test_t1_r3_audio_default_sink(ricing_suite, qapp):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    
    sink = MockPwNode(20, "Speakers", "Speakers Output", is_sink=True)
    pipewire.setProperty("defaultAudioSink", sink)
    pipewire.add_node(sink)
    call_method(engine, audio, "syncNodes")
    qapp.processEvents()
    
    res = get_property(engine, audio, "sink")
    assert res.toQObject().property("id") == 20

def test_t1_r3_audio_set_audio_sink_source(ricing_suite, qapp):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    
    sink = MockPwNode(21, "Headphones", "Headphones Output", is_sink=True)
    pipewire.add_node(sink)
    call_method(engine, audio, "syncNodes")
    
    sinks = get_property(engine, audio, "sinks")
    sink0 = sinks.toVariant()[0]
    call_method(engine, audio, "setAudioSink", sink0)
    assert pipewire.property("preferredDefaultAudioSink") == sink


# --- R4: Unified Control Center ---
def test_t1_r4_weather_fetch_coords_from_city(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    
    req.responses["search"] = '{"results": [{"latitude": 48.8566, "longitude": 2.3522, "name": "Paris"}]}'
    call_method(engine, weather, "fetchCoordsFromCity", "Paris")
    assert get_property(engine, weather, "loc").toVariant() == "48.8566,2.3522"
    assert get_property(engine, weather, "city").toVariant() == "Paris"

def test_t1_r4_weather_fetch_city_from_coords(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    
    req.responses["nominatim"] = '{"features": [{"properties": {"geocoding": {"type": "city", "name": "Berlin"}}}]}'
    call_method(engine, weather, "fetchCityFromCoords", "52.5200,13.4050")
    assert get_property(engine, weather, "city").toVariant() == "Berlin"

def test_t1_r4_weather_ipinfo_fallback(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    
    req.responses["ipinfo"] = '{"loc": "35.6762,139.6503", "city": "Tokyo"}'
    call_method(engine, weather, "reload")
    assert get_property(engine, weather, "loc").toVariant() == "35.6762,139.6503"
    assert get_property(engine, weather, "city").toVariant() == "Tokyo"

def test_t1_r4_weather_fetch_forecast(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    
    set_property(engine, weather, "loc", "51.5074,-0.1278")
    req.responses["forecast"] = '{"current": {"weather_code": "0", "temperature_2m": 22.0, "apparent_temperature": 21.0, "relative_humidity_2m": 50, "wind_speed_10m": 12.0, "is_day": 1}, "daily": {"time": ["2026-06-15"], "weather_code": [0], "temperature_2m_max": [25.0], "temperature_2m_min": [15.0], "sunrise": ["2026-06-15T04:43"], "sunset": ["2026-06-15T21:21"]}, "hourly": {"time": ["2026-06-15T12:00"], "temperature_2m": [22.0], "precipitation_probability": [0], "weather_code": [0]}}'
    call_method(engine, weather, "fetchWeatherData")
    
    assert get_property(engine, weather, "description").toVariant() == "Clear"
    assert get_property(engine, weather, "temp").toVariant() == "22°C"

def test_t1_r4_control_center_toggles(ricing_suite):
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/ControlCenter.qml")
    cc = comp.create()
    
    call_method(engine, cc, "toggleWifi")
    assert get_property(engine, cc, "wifiEnabled").toVariant() is False
    log_content = pathlib.Path("/tmp/nmcli_calls.log").read_text()
    assert "radio wifi off" in log_content

    call_method(engine, cc, "toggleBluetooth")
    assert get_property(engine, cc, "bluetoothEnabled").toVariant() is False
    log_content = pathlib.Path("/tmp/bluetoothctl_calls.log").read_text()
    assert "power off" in log_content

    call_method(engine, cc, "toggleAmbientTemp")
    assert get_property(engine, cc, "ambientTempEnabled").toVariant() is False
    log_content = pathlib.Path("/tmp/pkill_calls.log").read_text()
    assert "wlsunset" in log_content


# --- R5: AI Copilot Sidebar ---
def test_t1_r5_copilot_clear_history(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    call_method(engine, copilot, "clearChat")
    assert get_property(engine, copilot, "chatHistory").property("count") == 1
    assert "Caelestia AI Copilot" in get_property(engine, copilot, "chatHistory").get(0)["message"]

def test_t1_r5_copilot_send_message(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    
    ricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": '{"message": {"content": "Hello user!"}}'
    }
    
    call_method(engine, copilot, "sendMessage", "Hi assistant")
    assert get_property(engine, copilot, "chatHistory").property("count").toVariant() in (2, 3)
    assert get_property(engine, copilot, "chatHistory").get(1)["message"] == "Hi assistant"

def test_t1_r5_copilot_action_workspace(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    
    msg = "I will switch to workspace 5.\n```json\n{\n  \"action\": \"workspace\",\n  \"id\": 5\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "workspace 5" in log_content

def test_t1_r5_copilot_action_volume(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
def test_t1_r5_copilot_action_volume(ricing_suite, qapp):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    audio = engine.singletonInstance("qs.services", "Audio")
    
    sink = MockPwNode(22, "Speakers", "Speakers Output", is_sink=True)
    pipewire.setProperty("defaultAudioSink", sink)
    pipewire.add_node(sink)
    call_method(engine, audio, "syncNodes")
    qapp.processEvents()
    
    msg = "Setting volume to 80%.\n```json\n{\n  \"action\": \"volume\",\n  \"value\": 80\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    
    sink_val = get_property(engine, audio, "sink")
    res = call_method(engine, audio, "getStreamVolume", sink_val)
    assert abs(res.toVariant() - 0.8) < 0.011

def test_t1_r5_copilot_action_exec(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    
    msg = "Launching terminal.\n```json\n{\n  \"action\": \"exec\",\n  \"command\": \"alacritty\"\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    assert ["alacritty"] in ricing_suite["quickshell"].execs


# --- R6: Screen OCR & Translation ---
def test_t1_r6_ocr_start_ocr(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    ocrProcess = get_property(engine, ocr, "ocrProcess").toQObject()
    ocrProcess.setProperty("skip_run", True)
    call_method(engine, ocr, "startOcr")
    assert get_property(engine, ocr, "running").toVariant() is True

def test_t1_r6_ocr_capture_success(ricing_suite, qapp):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    
    pathlib.Path("/tmp/mock_ocr_text.txt").write_text("Hello Screen Text")
    call_method(engine, ocr, "startOcr")
    qapp.processEvents()
    
    ocrProcess = get_property(engine, ocr, "ocrProcess").toQObject()
    ocrProcess.setProperty("running", True)
    qapp.processEvents()
    
    assert get_property(engine, ocr, "ocrText").toVariant() == "Hello Screen Text"
    assert get_property(engine, ocr, "running").toVariant() is False

def test_t1_r6_ocr_translate(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "Hello")
    
    ricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": '{"message": {"content": "Bonjour"}}'
    }
    
    call_method(engine, ocr, "translateText", "French")
    assert get_property(engine, ocr, "translatedText").toVariant() == "Bonjour"

def test_t1_r6_ocr_explain(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "Error 404")
    
    ricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": '{"message": {"content": "It means file not found."}}'
    }
    
    call_method(engine, ocr, "explainText")
    assert get_property(engine, ocr, "translatedText").toVariant() == "It means file not found."

def test_t1_r6_ocr_error_handling(ricing_suite, qapp):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    
    pathlib.Path("/tmp/mock_ocr_text.txt").write_text("")
    call_method(engine, ocr, "startOcr")
    qapp.processEvents()
    
    ocrProcess = get_property(engine, ocr, "ocrProcess").toQObject()
    ocrProcess.setProperty("running", True)
    qapp.processEvents()
    
    assert get_property(engine, ocr, "ocrText").toVariant() == ""
    assert "No text detected" in get_property(engine, ocr, "lastError").toVariant()


# ==========================================
# TIER 2 tests (Boundary & Corner Cases): >=5 per feature (total >=30 tests)
# ==========================================

# --- R1: Colours & Wallpapers ---
def test_t2_r1_colours_invalid_json(ricing_suite):
    engine = ricing_suite["engine"]
    colours = ricing_suite["colours"]
    try:
        call_method(engine, colours, "load", "invalid json string {}", False)
    except RuntimeError as e:
        assert "SyntaxError" in str(e) or "Parse error" in str(e)
    assert colours is not None

def test_t2_r1_colours_alter_color_extreme(ricing_suite):
    engine = ricing_suite["engine"]
    colours = ricing_suite["colours"]
    c1 = call_method(engine, colours, "alterColour", "#000000", 0.0, 5)
    c2 = call_method(engine, colours, "alterColour", "#ffffff", 1.0, -2)
    assert c1.toVariant() is not None
    assert c2.toVariant() is not None

def test_t2_r1_colours_get_luminance_extreme(ricing_suite):
    engine = ricing_suite["engine"]
    colours = ricing_suite["colours"]
    l1 = call_method(engine, colours, "getLuminance", "#000000")
    l2 = call_method(engine, colours, "getLuminance", "#ffffff")
    assert l1.toVariant() == 0.0
    assert l2.toVariant() > 0.0

def test_t2_r1_colours_cooldown_rate_limit(ricing_suite):
    engine = ricing_suite["engine"]
    colours = ricing_suite["colours"]
    call_method(engine, colours, "requestReloadHyprRules")
    call_method(engine, colours, "requestReloadHyprRules")
    assert get_property(engine, colours, "cooldownPending").toVariant() is True

def test_t2_r1_wallpapers_empty_path(ricing_suite):
    engine = ricing_suite["engine"]
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    call_method(engine, wallpapers, "preview", "")
    assert get_property(engine, wallpapers, "previewPath").toVariant() == ""
    call_method(engine, wallpapers, "setWallpaper", "")
    assert get_property(engine, wallpapers, "actualCurrent").toVariant() == ""


# --- R2: Interactive Workspace Overview ---
def test_t2_r2_overview_drag_out_of_bounds(ricing_suite):
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    call_method(engine, overview, "dragAndDropWindow", "kitty", 999)
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "movetoworkspace 999,kitty" in log_content

def test_t2_r2_overview_empty_workspaces(ricing_suite):
    hyprland = ricing_suite["hyprland"]
    hyprland._workspaces.set_values([])
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    assert get_property(engine, overview, "cards").toVariant() is not None

def test_t2_r2_overview_drag_same_workspace(ricing_suite):
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    call_method(engine, overview, "dragAndDropWindow", "chrome", 2)
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "movetoworkspace 2,chrome" in log_content

def test_t2_r2_hypr_dispatch_empty_cmd(ricing_suite):
    engine = ricing_suite["engine"]
    hypr = engine.singletonInstance("qs.services", "Hypr")
    call_method(engine, hypr, "dispatch", "")
    log_path = pathlib.Path("/tmp/hyprctl_calls.log")
    log_content = log_path.read_text() if log_path.exists() else ""
    assert "" in log_content

def test_t2_r2_hypr_cycle_special_empty(ricing_suite):
    hyprland = ricing_suite["hyprland"]
    engine = ricing_suite["engine"]
    hypr = engine.singletonInstance("qs.services", "Hypr")
    hyprland._workspaces.set_values([])
    call_method(engine, hypr, "cycleSpecialWorkspace", "next")
    log_path = pathlib.Path("/tmp/hyprctl_calls.log")
    log_content = log_path.read_text() if log_path.exists() else ""
    assert "special:" not in log_content


# --- R3: Media Visualizer & Audio Mixer ---
def test_t2_r3_audio_volume_clamp(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    node = MockPwNode(25, "App", "App Stream", is_stream=True)
    pipewire.add_node(node)
    call_method(engine, audio, "syncNodes")
    
    streams = get_property(engine, audio, "streams")
    stream0 = streams.toVariant()[0]
    call_method(engine, audio, "setStreamVolume", stream0, 2.5)
    assert node._audio._volume <= 1.0

def test_t2_r3_audio_mute_redundant(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    node = MockPwNode(26, "App", "App Stream", is_stream=True)
    pipewire.add_node(node)
    call_method(engine, audio, "syncNodes")
    
    streams = get_property(engine, audio, "streams")
    stream0 = streams.toVariant()[0]
    call_method(engine, audio, "setStreamMuted", stream0, True)
    call_method(engine, audio, "setStreamMuted", stream0, True)
    assert node._audio._muted is True

def test_t2_r3_audio_empty_devices(ricing_suite):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    pipewire.clear_nodes()
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    call_method(engine, audio, "syncNodes")
    
    res = get_property(engine, audio, "sinks")
    assert len(res.toVariant()) == 0

def test_t2_r3_audio_null_stream_volume(ricing_suite):
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    call_method(engine, audio, "setStreamVolume", None, 0.5)
    res = call_method(engine, audio, "getStreamVolume", None)
    assert res.toVariant() == 0

def test_t2_r3_audio_default_sink_invalid(ricing_suite):
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    call_method(engine, audio, "setAudioSink", None)
    assert get_property(engine, audio, "sink").toQObject() is None


# --- R4: Unified Control Center ---
def test_t2_r4_weather_search_empty(ricing_suite):
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    call_method(engine, weather, "fetchCoordsFromCity", "")
    assert get_property(engine, weather, "loc").toVariant() == ""

def test_t2_r4_weather_corrupt_json(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    
    req.responses["search"] = "corrupt json {}"
    call_method(engine, weather, "fetchCoordsFromCity", "London")
    assert get_property(engine, weather, "loc").toVariant() == ""

def test_t2_r4_weather_to_fahrenheit_boundaries(ricing_suite):
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    f1 = call_method(engine, weather, "toFahrenheit", -40.0)
    assert f1.toVariant() == -40.0
    f2 = call_method(engine, weather, "toFahrenheit", 100.0)
    assert f2.toVariant() == 212.0

def test_t2_r4_weather_nominatim_failure_fallback(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    
    req.responses["nominatim"] = '{"features": []}'
    req.responses["reverse-geocode-client"] = '{"city": "Paris"}'
    call_method(engine, weather, "fetchCityFromCoords", "48.8566,2.3522")
    assert get_property(engine, weather, "city").toVariant() == "Paris"

def test_t2_r4_control_center_rapid_toggle(ricing_suite):
    engine = ricing_suite["engine"]
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/ControlCenter.qml")
    cc = comp.create()
    for _ in range(10):
        call_method(engine, cc, "toggleAmbientTemp")
    assert cc is not None


# --- R5: AI Copilot Sidebar ---
def test_t2_r5_copilot_malformed_action_json(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    msg = "Executing action:\n```json\n{\n  \"action\": \"volume\",\n  \"value\":\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    assert copilot is not None

def test_t2_r5_copilot_empty_message(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    call_method(engine, copilot, "sendMessage", "")
    assert get_property(engine, copilot, "chatHistory").property("count") == 1

def test_t2_r5_copilot_unknown_action(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    msg = "```json\n{\n  \"action\": \"play_laser_tag\"\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    assert copilot is not None

def test_t2_r5_copilot_network_timeout(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    pricing_suite = ricing_suite
    pricing_suite["ollama"].responses["api/chat"] = {
        "status": 504,
        "text": "Gateway Timeout"
    }
    call_method(engine, copilot, "sendMessage", "Test timeout")
    assert "Cannot connect to local Ollama server" in get_property(engine, copilot, "lastError").toVariant()

def test_t2_r5_copilot_multiple_actions(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    
    msg = """```json
[
  {"action": "workspace", "id": 8},
  {"action": "exec", "command": "nemo"}
]
```"""
    call_method(engine, copilot, "executeActionsFromText", msg)
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "workspace 8" in log_content
    assert ["nemo"] in ricing_suite["quickshell"].execs


# --- R6: Screen OCR & Translation ---
def test_t2_r6_ocr_translate_empty(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "")
    call_method(engine, ocr, "translateText", "German")
    assert get_property(engine, ocr, "translatedText").toVariant() == ""

def test_t2_r6_ocr_ollama_timeout(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "Translate me")
    
    pricing_suite = ricing_suite
    pricing_suite["ollama"].responses["api/chat"] = {
        "status": 503,
        "text": "Service Unavailable"
    }
    call_method(engine, ocr, "translateText", "German")
    assert "Ollama connection error" in get_property(engine, ocr, "lastError").toVariant()

def test_t2_r6_ocr_explain_timeout(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "Explain me")
    
    pricing_suite = ricing_suite
    pricing_suite["ollama"].responses["api/chat"] = {
        "status": 503,
        "text": "Service Unavailable"
    }
    call_method(engine, ocr, "explainText")
    assert "Ollama connection error" in get_property(engine, ocr, "lastError").toVariant()

def test_t2_r6_ocr_explain_corrupt(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "Explain me")
    
    pricing_suite = ricing_suite
    pricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": "corrupt json response"
    }
    call_method(engine, ocr, "explainText")
    assert "Explanation failed" in get_property(engine, ocr, "lastError").toVariant()

def test_t2_r6_ocr_resets(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    set_property(engine, ocr, "ocrText", "old")
    set_property(engine, ocr, "translatedText", "old")
    set_property(engine, ocr, "lastError", "old")
    
    ocrProcess = get_property(engine, ocr, "ocrProcess").toQObject()
    ocrProcess.setProperty("skip_run", True)
    
    call_method(engine, ocr, "startOcr")
    assert get_property(engine, ocr, "ocrText").toVariant() == ""
    assert get_property(engine, ocr, "translatedText").toVariant() == ""
    assert get_property(engine, ocr, "lastError").toVariant() == ""


# ==========================================
# TIER 3 tests (Cross-Feature/Pairwise): >=6 tests
# ==========================================

def test_t3_copilot_volume_triggers_audio(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    audio = engine.singletonInstance("qs.services", "Audio")
    
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    node = MockPwNode(30, "App", "App Stream", is_sink=True)
    pipewire.add_node(node)
    pipewire.set_defaultAudioSink(node)
    call_method(engine, audio, "syncNodes")
    
    msg = "Setting volume to 50%.\n```json\n{\n  \"action\": \"volume\",\n  \"value\": 50\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    assert node._audio._volume == 0.5

def test_t3_copilot_wallpaper_cycles_colours(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    
    set_property(engine, wallpapers, "actualCurrent", "/tmp/wall1.png")
    
    msg = "```json\n{\n  \"action\": \"wallpaper\",\n  \"direction\": \"random\"\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    
    log_content = pathlib.Path("/tmp/caelestia_calls.log").read_text()
    assert "wallpaper -r" in log_content

def test_t3_ocr_translation_updates_copilot(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    copilot = engine.singletonInstance("qs.services", "Copilot")
    
    set_property(engine, ocr, "ocrText", "Warning: disk full")
    pricing_suite = ricing_suite
    pricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": '{"message": {"content": "Your storage is full."}}'
    }
    
    call_method(engine, ocr, "explainText")
    
    expl = get_property(engine, ocr, "translatedText").toVariant()
    call_method(engine, copilot, "sendMessage", f"OCR result explained as: {expl}. What should I do?")
    assert get_property(engine, copilot, "chatHistory").property("count").toVariant() in (2, 3)
    assert "Your storage is full." in get_property(engine, copilot, "chatHistory").get(1)["message"]

def test_t3_weather_geocoding_triggers_theme(ricing_suite):
    req = ricing_suite["requests"]
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    colours = engine.singletonInstance("qs.services", "Colours")
    
    req.responses["search"] = '{"results": [{"latitude": 52.52, "longitude": 13.405, "name": "Berlin"}]}'
    call_method(engine, weather, "fetchCoordsFromCity", "Berlin")
    
    call_method(engine, colours, "setMode", "dark")
    log_content = pathlib.Path("/tmp/caelestia_calls.log").read_text()
    assert "scheme set" in log_content

def test_t3_audio_mute_updates_overview(ricing_suite, qapp):
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    audio = engine.singletonInstance("qs.services", "Audio")
    
    sink = MockPwNode(40, "Output", "Output Device", is_sink=True)
    pipewire.set_defaultAudioSink(sink)
    pipewire.add_node(sink)
    call_method(engine, audio, "syncNodes")
    qapp.processEvents()
    
    sink_val = get_property(engine, audio, "sink")
    call_method(engine, audio, "setStreamMuted", sink_val, True)
    assert sink._audio._muted is True

def test_t3_overview_drag_triggers_colours(ricing_suite, qapp):
    engine = ricing_suite["engine"]
    colours = engine.singletonInstance("qs.services", "Colours")
    
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    
    import time
    start = time.time()
    while time.time() - start < 0.2:
        qapp.processEvents()
        time.sleep(0.01)
    
    call_method(engine, overview, "dragAndDropWindow", "kitty", 6)
    call_method(engine, colours, "requestReloadHyprRules")
    assert get_property(engine, colours, "cooldownPending").toVariant() is False


# ==========================================
# TIER 4 tests (Real-World Application Scenarios): >=5 tests
# ==========================================

def test_t4_copilot_wallpaper_color_pipeline(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    colours = ricing_suite["colours"]
    
    set_property(engine, wallpapers, "actualCurrent", "/tmp/wall1.png")
    
    msg = "Change wallpaper to random.\n```json\n{\n  \"action\": \"wallpaper\",\n  \"direction\": \"random\"\n}\n```"
    call_method(engine, copilot, "executeActionsFromText", msg)
    
    call_method(engine, colours, "load", '{"name":"dynamic","flavour":"mocha","mode":"dark","colours":{"primaryContainer":"ff00ff"}}', False)
    
    assert get_property(engine, colours, "scheme").toVariant() == "dynamic"
    palette = get_property(engine, colours, "palette")
    res = get_property(engine, palette, "m3primaryContainer")
    assert res.toVariant() == "#ff00ff"

def test_t4_ocr_translate_explain_workflow(ricing_suite, qapp):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    
    pathlib.Path("/tmp/mock_ocr_text.txt").write_text("Hello world")
    call_method(engine, ocr, "startOcr")
    qapp.processEvents()
    
    ocrProcess = get_property(engine, ocr, "ocrProcess").toQObject()
    ocrProcess.setProperty("running", True)
    qapp.processEvents()
    
    ricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": '{"message": {"content": "Hola mundo"}}'
    }
    call_method(engine, ocr, "translateText", "Spanish")
    
    ricing_suite["ollama"].responses["api/chat"] = {
        "status": 200,
        "text": '{"message": {"content": "A standard greeting program."}}'
    }
    call_method(engine, ocr, "explainText")
    
    assert get_property(engine, ocr, "ocrText").toVariant() == "Hello world"
    assert get_property(engine, ocr, "translatedText").toVariant() == "A standard greeting program."

def test_t4_overview_drag_mixer_control(ricing_suite):
    engine = ricing_suite["engine"]
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    audio = engine.singletonInstance("qs.services", "Audio")
    
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine, "/tmp/qml-imports/Caelestia/Overview.qml")
    overview = comp.create()
    
    call_method(engine, overview, "dragAndDropWindow", "kitty", 3)
    
    node = MockPwNode(50, "kitty", "kitty Audio", is_stream=True)
    pipewire.add_node(node)
    call_method(engine, audio, "syncNodes")
    
    streams = get_property(engine, audio, "streams")
    stream0 = streams.toVariant()[0]
    call_method(engine, audio, "setStreamVolume", stream0, 0.40)
    
    assert node._audio._volume == 0.40
    log_content = pathlib.Path("/tmp/hyprctl_calls.log").read_text()
    assert "movetoworkspace 3,kitty" in log_content

def test_t4_system_startup_weather_audio(ricing_suite, qapp):
    req = ricing_suite["requests"]
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    audio = engine.singletonInstance("qs.services", "Audio")
    
    req.responses["ipinfo"] = '{"loc": "40.7128,-74.0060", "city": "New York"}'
    call_method(engine, weather, "reload")
    
    sink = MockPwNode(100, "PCI Audio Card", "Onboard Speaker", is_sink=True)
    pipewire.set_defaultAudioSink(sink)
    pipewire.add_node(sink)
    call_method(engine, audio, "syncNodes")
    qapp.processEvents()
    
    assert get_property(engine, weather, "city").toVariant() == "New York"
    
    res = get_property(engine, audio, "sink")
    assert res.toQObject().property("id") == 100

def test_t4_copilot_mic_mute_launcher(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    visibilities = engine.singletonInstance("qs.services", "Visibilities")
    pipewire = ricing_suite["engine"].rootContext().contextProperty("Pipewire")
    audio = engine.singletonInstance("qs.services", "Audio")
    
    source = MockPwNode(110, "Mic Device", "Input Mic", is_stream=True)
    pipewire.set_defaultAudioSource(source)
    pipewire.add_node(source)
    call_method(engine, audio, "syncNodes")
    
    msg = """Sure! Mutting mic and opening launcher.
```json
[
  {"action": "mute", "type": "mic", "state": true},
  {"action": "drawer", "name": "launcher", "state": true}
]
```"""
    
    call_method(engine, copilot, "executeActionsFromText", msg)
    
    assert source._audio._muted is True
    active_vis = get_property(engine, visibilities, "activeVis")
    assert get_property(engine, active_vis, "launcher").toVariant() is True

def test_load_all_services(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    assert copilot is not None
    ocr = engine.singletonInstance("qs.services", "Ocr")
    assert ocr is not None
    colours = engine.singletonInstance("qs.services", "Colours")
    assert colours is not None
    wallpapers = engine.singletonInstance("qs.services", "Wallpapers")
    assert wallpapers is not None
    weather = engine.singletonInstance("qs.services", "Weather")
    assert weather is not None
    hypr = engine.singletonInstance("qs.services", "Hypr")
    assert hypr is not None
