import os
import sys
import shutil
import pathlib
import pytest
from PySide6.QtCore import QObject, Signal, Slot, Property, ClassInfo
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, qmlRegisterType, qmlRegisterSingletonInstance
from PySide6.QtQuick import QQuickItem

# Set Qt offscreen platform before application creation
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Setup wpctl mock binary interception mechanism
bin_dir = pathlib.Path("/tmp/caelestia-test-bin")
bin_dir.mkdir(parents=True, exist_ok=True)
wpctl_path = bin_dir / "wpctl"
wpctl_path.write_text("#!/bin/bash\necho \"$@\" >> /tmp/wpctl_calls.log\nexit 0\n")
wpctl_path.chmod(0o755)

# Prepend mock bin to PATH
original_path = os.environ.get("PATH", "")
os.environ["PATH"] = f"/tmp/caelestia-test-bin:{original_path}"

# Setup dummy QML import modules for testing
base_import_path = pathlib.Path("/tmp/qml-imports")
shutil.rmtree(base_import_path, ignore_errors=True)

mocks = {
    'Quickshell': {
        'qmldir': 'module Quickshell\nSingleton 1.0 Singleton.qml\nIpcHandler 1.0 IpcHandler.qml\n',
        'Singleton.qml': 'import QtQuick\nQtObject {\n    default property list<QtObject> data\n}\n',
        'IpcHandler.qml': 'import QtQuick\nQtObject {\n    property string target: \"\"\n}\n'
    },
    'Quickshell/Io': {
        'qmldir': 'module Quickshell.Io\n',
    },
    'Quickshell/Services/Pipewire': {
        'qmldir': 'module Quickshell.Services.Pipewire\nPwObjectTracker 1.0 PwObjectTracker.qml\n',
        'PwObjectTracker.qml': 'import QtQuick\nItem {\n    property var objects: []\n}\n'
    },
    'Caelestia': {
        'qmldir': 'module Caelestia\nDummy 1.0 Dummy.qml\n',
        'Dummy.qml': 'import QtQuick\nItem {}\n',
        'GlobalConfig.qml': 'import QtQuick\nQtObject {\n    property QtObject services: QtObject {\n        property real maxVolume: 1.0\n        property real audioIncrement: 0.05\n        property int visualiserBars: 20\n    }\n    property QtObject utilities: QtObject {\n        property QtObject toasts: QtObject {\n            property bool audioOutputChanged: true\n            property bool audioInputChanged: true\n        }\n    }\n}\n',
        'Tokens.qml': 'import QtQuick\nQtObject {\n    property QtObject padding: QtObject {\n        property real medium: 12.0\n        property real extraSmall: 4.0\n    }\n    property QtObject spacing: QtObject {\n        property real medium: 8.0\n    }\n    property QtObject font: QtObject {\n        property QtObject body: QtObject {\n            property QtObject builders: QtObject {\n                function weight(w) { return builders; }\n                function build() { return "Google Sans"; }\n            }\n        }\n    }\n}\n',
        'Colours.qml': 'import QtQuick\nQtObject {\n    property QtObject palette: QtObject {\n        property string m3primaryContainer: "#000000"\n        property string m3onPrimaryContainer: "#ffffff"\n    }\n}\n'
    },
    'Caelestia/Config': {
        'qmldir': 'module Caelestia.Config\n',
    },
    'Caelestia/Services': {
        'qmldir': 'module Caelestia.Services\nCavaProvider 1.0 CavaProvider.qml\nBeatTracker 1.0 BeatTracker.qml\n',
        'CavaProvider.qml': 'import QtQuick\nItem {\n    property int bars: 0\n}\n',
        'BeatTracker.qml': 'import QtQuick\nItem {}\n'
    },
    'qs/services': {
        'qmldir': 'module qs.services\nsingleton Audio 1.0 Audio.qml\nDummy 1.0 Dummy.qml\n',
        'Dummy.qml': 'import QtQuick\nItem {}\n'
    },
    'qs/components': {
        'qmldir': 'module qs.components\nStyledText 1.0 StyledText.qml\n',
        'StyledText.qml': 'import QtQuick\nText {}\n'
    },
    'qs/components/controls': {
        'qmldir': 'module qs.components.controls\nStyledRadioButton 1.0 StyledRadioButton.qml\nStyledSlider 1.0 StyledSlider.qml\nIconTextButton 1.0 IconTextButton.qml\nCustomMouseArea 1.0 CustomMouseArea.qml\n',
        'StyledRadioButton.qml': 'import QtQuick\nimport QtQuick.Controls\nRadioButton {\n    property var modelData: null\n}\n',
        'StyledSlider.qml': 'import QtQuick\nimport QtQuick.Controls\nSlider {\n    signal interaction(real value)\n}\n',
        'IconTextButton.qml': 'import QtQuick\nItem {\n    property string icon: \"\"\n    property string text: \"\"\n    property var inactiveColour: null\n    property var inactiveOnColour: null\n    property var verticalPadding: null\n    signal clicked()\n}\n',
        'CustomMouseArea.qml': 'import QtQuick\nItem {\n    signal wheel(var event)\n    function simulateWheel(y) {\n        wheel({ angleDelta: { y: y } });\n    }\n}\n'
    }
}

for mod, files in mocks.items():
    d = base_import_path / mod
    d.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (d / fname).write_text(content)

# Copy the real Audio.qml to qs/services/Audio.qml
shutil.copy("/home/execorn/ricing/shell/services/Audio.qml", "/tmp/qml-imports/qs/services/Audio.qml")

# Mock Pipewire and QML Classes
class MockPwAudio(QObject):
    volumeChanged = Signal(float)
    mutedChanged = Signal(bool)

    def __init__(self, volume=0.5, muted=False):
        super().__init__()
        self._volume = volume
        self._muted = muted

    def get_volume(self):
        return self._volume

    def set_volume(self, val):
        if self._volume != val:
            self._volume = val
            self.volumeChanged.emit(val)

    def get_muted(self):
        return self._muted

    def set_muted(self, val):
        if self._muted != val:
            self._muted = val
            self.mutedChanged.emit(val)

    volume = Property(float, get_volume, set_volume, notify=volumeChanged)
    muted = Property(bool, get_muted, set_muted, notify=mutedChanged)


class MockPwNode(QObject):
    idChanged = Signal(int)
    nameChanged = Signal(str)
    descriptionChanged = Signal(str)
    readyChanged = Signal(bool)
    isSinkChanged = Signal(bool)
    isStreamChanged = Signal(bool)
    propertiesChanged = Signal('QVariantMap')
    audioChanged = Signal(QObject)

    def __init__(self, node_id, name, description, ready=True, is_sink=False, is_stream=False, properties=None, volume=0.5, muted=False, has_audio=True):
        super().__init__()
        self._id = node_id
        self._name = name
        self._description = description
        self._ready = ready
        self._is_sink = is_sink
        self._is_stream = is_stream
        self._properties = properties or {}
        self._audio = MockPwAudio(volume, muted) if has_audio else None

    def __eq__(self, other):
        if other is None:
            return False
        try:
            if hasattr(other, "property"):
                return self.property("id") == other.property("id")
        except Exception:
            pass
        return False

    id = Property(int, lambda self: self._id, notify=idChanged)
    name = Property(str, lambda self: self._name, notify=nameChanged)
    description = Property(str, lambda self: self._description, notify=descriptionChanged)
    
    def get_ready(self):
        return self._ready

    def set_ready(self, val):
        if self._ready != val:
            self._ready = val
            self.readyChanged.emit(val)

    ready = Property(bool, get_ready, set_ready, notify=readyChanged)
    isSink = Property(bool, lambda self: self._is_sink, notify=isSinkChanged)
    isStream = Property(bool, lambda self: self._is_stream, notify=isStreamChanged)
    
    def get_properties(self):
        return self._properties

    def set_properties(self, val):
        self._properties = val
        self.propertiesChanged.emit(val)

    properties = Property('QVariantMap', get_properties, set_properties, notify=propertiesChanged)
    
    def get_audio(self):
        return self._audio

    def set_audio(self, val):
        self._audio = val
        self.audioChanged.emit(val)

    audio = Property(QObject, get_audio, set_audio, notify=audioChanged)


class MockPipewireNodes(QObject):
    valuesChanged = Signal()

    def __init__(self):
        super().__init__()
        self._values = []

    def get_values(self):
        return self._values

    values = Property('QVariantList', get_values, notify=valuesChanged)

    @Slot(QObject, result=int)
    def indexOf(self, node):
        print("DEBUG SLOTS: indexOf called with node:", node)
        if not node:
            return -1
        try:
            target_id = node.property("id")
            print("DEBUG SLOTS: target_id:", target_id)
            for idx, val in enumerate(self._values):
                val_id = val.property("id")
                print(f"DEBUG SLOTS: comparing target_id {target_id} with val_id {val_id}")
                if val_id == target_id:
                    print("DEBUG SLOTS: Match found at index:", idx)
                    return idx
        except Exception as e:
            print("DEBUG SLOTS: exception in indexOf:", e)
            pass
        print("DEBUG SLOTS: No match found, returning -1")
        return -1


class MockPipewire(QObject):
    defaultAudioSinkChanged = Signal()
    defaultAudioSourceChanged = Signal()
    preferredDefaultAudioSinkChanged = Signal()
    preferredDefaultAudioSourceChanged = Signal()

    def __init__(self):
        super().__init__()
        self._nodes = MockPipewireNodes()
        self._defaultAudioSink = None
        self._defaultAudioSource = None
        self._preferredDefaultAudioSink = None
        self._preferredDefaultAudioSource = None

    nodes = Property(QObject, lambda self: self._nodes, constant=True)

    def get_defaultAudioSink(self):
        return self._defaultAudioSink

    def set_defaultAudioSink(self, val):
        if self._defaultAudioSink != val:
            self._defaultAudioSink = val
            self.defaultAudioSinkChanged.emit()

    defaultAudioSink = Property(QObject, get_defaultAudioSink, set_defaultAudioSink, notify=defaultAudioSinkChanged)

    def get_defaultAudioSource(self):
        return self._defaultAudioSource

    def set_defaultAudioSource(self, val):
        if self._defaultAudioSource != val:
            self._defaultAudioSource = val
            self.defaultAudioSourceChanged.emit()

    defaultAudioSource = Property(QObject, get_defaultAudioSource, set_defaultAudioSource, notify=defaultAudioSourceChanged)

    def get_preferredDefaultAudioSink(self):
        return self._preferredDefaultAudioSink

    def set_preferredDefaultAudioSink(self, val):
        if self._preferredDefaultAudioSink != val:
            self._preferredDefaultAudioSink = val
            self.preferredDefaultAudioSinkChanged.emit()

    preferredDefaultAudioSink = Property(QObject, get_preferredDefaultAudioSink, set_preferredDefaultAudioSink, notify=preferredDefaultAudioSinkChanged)

    def get_preferredDefaultAudioSource(self):
        return self._preferredDefaultAudioSource

    def set_preferredDefaultAudioSource(self, val):
        if self._preferredDefaultAudioSource != val:
            self._preferredDefaultAudioSource = val
            self.preferredDefaultAudioSourceChanged.emit()

    preferredDefaultAudioSource = Property(QObject, get_preferredDefaultAudioSource, set_preferredDefaultAudioSource, notify=preferredDefaultAudioSourceChanged)

    # Helper methods for tests
    def add_node(self, node):
        if node not in self._nodes._values:
            self._nodes._values.append(node)
            self._nodes.valuesChanged.emit()

    def remove_node(self, node):
        if node in self._nodes._values:
            self._nodes._values.remove(node)
            self._nodes.valuesChanged.emit()

    def clear_nodes(self):
        self._nodes._values.clear()
        self._nodes.valuesChanged.emit()





class MockProcess(QObject):
    runningChanged = Signal(bool)
    commandChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._command = []

    def get_running(self):
        return self._running

    def set_running(self, val):
        if self._running != val:
            self._running = val
            self.runningChanged.emit(val)
            if val:
                import subprocess
                try:
                    subprocess.run(self._command, capture_output=True)
                except Exception as e:
                    print("MockProcess error running command:", self._command, e)
                self._running = False
                self.runningChanged.emit(False)

    def get_command(self):
        return self._command

    def set_command(self, val):
        self._command = val
        self.commandChanged.emit()

    running = Property(bool, get_running, set_running, notify=runningChanged)
    command = Property('QVariantList', get_command, set_command, notify=commandChanged)





class MockToaster(QObject):
    @Slot(str, str, str)
    def toast(self, title, message, icon):
        self.toasts.append((title, message, icon))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.toasts = []


class MockToasts(QObject):
    audioOutputChanged = Property(bool, lambda self: True, constant=True)
    audioInputChanged = Property(bool, lambda self: True, constant=True)


class MockUtilities(QObject):
    def __init__(self):
        super().__init__()
        self._toasts = MockToasts()
    toasts = Property(QObject, lambda self: self._toasts, constant=True)


class MockServicesConfig(QObject):
    maxVolume = Property(float, lambda self: 1.0, constant=True)
    audioIncrement = Property(float, lambda self: 0.05, constant=True)
    visualiserBars = Property(int, lambda self: 20, constant=True)


class MockGlobalConfig(QObject):
    def __init__(self):
        super().__init__()
        self._services = MockServicesConfig()
        self._utilities = MockUtilities()
    
    services = Property(QObject, lambda self: self._services, constant=True)
    utilities = Property(QObject, lambda self: self._utilities, constant=True)


# Mock Tokens and Colours properties
class MockFontBuilder(QObject):
    def __init__(self):
        super().__init__()
    @Slot(int, result=QObject)
    def weight(self, w): return self
    @Slot(result=str)
    def build(self): return "Google Sans"

class MockFontBody(QObject):
    def __init__(self):
        super().__init__()
        self._medium = MockFontBuilder()

    builders = Property(QObject, lambda self: self, constant=True)
    medium = Property(QObject, lambda self: self._medium, constant=True)

class MockFontTokens(QObject):
    def __init__(self):
        super().__init__()
        self._body = MockFontBody()

    body = Property(QObject, lambda self: self._body, constant=True)

class MockPaddingTokens(QObject):
    medium = Property(float, lambda self: 12.0, constant=True)
    extraSmall = Property(float, lambda self: 4.0, constant=True)

class MockSpacingTokens(QObject):
    medium = Property(float, lambda self: 8.0, constant=True)

class MockTokens(QObject):
    def __init__(self):
        super().__init__()
        self._padding = MockPaddingTokens()
        self._spacing = MockSpacingTokens()
        self._font = MockFontTokens()

    padding = Property(QObject, lambda self: self._padding, constant=True)
    spacing = Property(QObject, lambda self: self._spacing, constant=True)
    font = Property(QObject, lambda self: self._font, constant=True)


class MockPalette(QObject):
    m3primaryContainer = Property(str, lambda self: "#000000", constant=True)
    m3onPrimaryContainer = Property(str, lambda self: "#ffffff", constant=True)

class MockColours(QObject):
    def __init__(self):
        super().__init__()
        self._palette = MockPalette()

    palette = Property(QObject, lambda self: self._palette, constant=True)


class MockPopoutState(QObject):
    detachRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)





# Register types to QML before QGuiApplication starts
qmlRegisterType(MockProcess, "Quickshell.Io", 1, 0, "Process")
qmlRegisterType(MockPwNode, "Quickshell.Services.Pipewire", 1, 0, "PwNode")
qmlRegisterType(MockPopoutState, "Caelestia.Config", 1, 0, "PopoutState")


@pytest.fixture(scope="session")
def qapp():
    # Instantiate the application instance once per test session
    app = QGuiApplication.instance()
    if not app:
        app = QGuiApplication([])
    yield app


@pytest.fixture
def mock_pipewire():
    return MockPipewire()


@pytest.fixture
def mock_toaster():
    return MockToaster()


@pytest.fixture
def qml_engine(qapp, mock_pipewire, mock_toaster):
    engine = QQmlEngine()
    engine.addImportPath("/tmp/qml-imports")
    
    # Expose context properties
    engine.rootContext().setContextProperty("Pipewire", mock_pipewire)
    engine.rootContext().setContextProperty("Toaster", mock_toaster)
    
    # Load and register QML mocks as context properties
    from PySide6.QtQml import QQmlComponent
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
def wpctl_log():
    log_path = pathlib.Path("/tmp/wpctl_calls.log")
    if log_path.exists():
        log_path.unlink()
    yield log_path
    if log_path.exists():
        log_path.unlink()
