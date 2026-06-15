import pytest
import time
import pathlib
import shutil
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from PySide6.QtCore import QObject, Signal, Slot, Property, QCoreApplication
from PySide6.QtQml import QJSValue
from conftest import MockPwNode, base_import_path

# --- Mock HTTP Server ---

class MockLLMHandler(BaseHTTPRequestHandler):
    requests = []
    gemini_response = {}
    ollama_response = {}
    gemini_status = 200
    ollama_status = 200

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
        
        MockLLMHandler.requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": json.loads(post_data) if post_data else None
        })
        
        if "generateContent" in self.path:
            self.send_response(MockLLMHandler.gemini_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MockLLMHandler.gemini_response).encode('utf-8'))
        elif "api/chat" in self.path:
            self.send_response(MockLLMHandler.ollama_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MockLLMHandler.ollama_response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def mock_llm_server():
    server = HTTPServer(('127.0.0.1', 0), MockLLMHandler)
    port = server.server_port
    
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    yield f"http://127.0.0.1:{port}"
    
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture(autouse=True)
def clean_server():
    MockLLMHandler.requests.clear()
    MockLLMHandler.gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello from Gemini"}]
                }
            }
        ]
    }
    MockLLMHandler.ollama_response = {
        "message": {
            "content": "Hello from Ollama"
        }
    }
    MockLLMHandler.gemini_status = 200
    MockLLMHandler.ollama_status = 200

@pytest.fixture(autouse=True)
def clean_env():
    import os
    orig_key = os.environ.get("GEMINI_API_KEY")
    yield
    if orig_key is not None:
        os.environ["GEMINI_API_KEY"] = orig_key
    elif "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]

# --- Helper function for async wait ---

def wait_until(condition, timeout_ms=2000):
    start = time.time()
    while not condition():
        QCoreApplication.processEvents()
        time.sleep(0.01)
        if (time.time() - start) * 1000 > timeout_ms:
            raise TimeoutError("Timeout waiting for condition")

# --- Mock Classes for Shell Singletons ---

class MockHypr(QObject):
    def __init__(self):
        super().__init__()
        self.commands = []

    @Slot(str)
    def dispatch(self, cmd):
        self.commands.append(cmd)


class MockNotifs(QObject):
    dndChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self._dnd = False

    def get_dnd(self):
        return self._dnd

    def set_dnd(self, val):
        if self._dnd != val:
            self._dnd = val
            self.dndChanged.emit(val)

    dnd = Property(bool, get_dnd, set_dnd, notify=dndChanged)


class MockToaster(QObject):
    def __init__(self):
        super().__init__()
        self.toasts = []

    @Slot(str, str, str)
    def toast(self, title, msg, icon):
        self.toasts.append((title, msg, icon))


class MockWallpaperItem(QObject):
    def __init__(self, path):
        super().__init__()
        self._path = path

    path = Property(str, lambda self: self._path, constant=True)


class MockWallpapers(QObject):
    def __init__(self):
        super().__init__()
        self.wallpapers = [
            MockWallpaperItem("/path/to/wall1.png"),
            MockWallpaperItem("/path/to/wall2.png"),
        ]
        self.actualCurrent = "/path/to/wall1.png"
        self.random_called = False

    @Slot()
    def setRandom(self):
        self.random_called = True

    @Slot(str)
    def setWallpaper(self, path):
        self.actualCurrent = path

    @Property('QVariantList')
    def list(self):
        return self.wallpapers


class MockVisibilityItem(QObject):
    launcherChanged = Signal(bool)
    dashboardChanged = Signal(bool)
    cheatsheetChanged = Signal(bool)
    sidebarChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self._launcher = False
        self._dashboard = False
        self._cheatsheet = False
        self._sidebar = False

    launcher = Property(bool, lambda self: self._launcher, lambda self, v: setattr(self, '_launcher', v) or self.launcherChanged.emit(v), notify=launcherChanged)
    dashboard = Property(bool, lambda self: self._dashboard, lambda self, v: setattr(self, '_dashboard', v) or self.dashboardChanged.emit(v), notify=dashboardChanged)
    cheatsheet = Property(bool, lambda self: self._cheatsheet, lambda self, v: setattr(self, '_cheatsheet', v) or self.cheatsheetChanged.emit(v), notify=cheatsheetChanged)
    sidebar = Property(bool, lambda self: self._sidebar, lambda self, v: setattr(self, '_sidebar', v) or self.sidebarChanged.emit(v), notify=sidebarChanged)


class MockVisibilities(QObject):
    def __init__(self):
        super().__init__()
        self.active_vis = MockVisibilityItem()

    @Slot(result=QObject)
    def getForActive(self):
        return self.active_vis


class MockQuickshell(QObject):
    def __init__(self):
        super().__init__()
        self.env_vars = {}
        self.detached_commands = []

    @Slot(str, result=str)
    def env(self, name):
        import os
        return os.environ.get(name, self.env_vars.get(name, ""))

    @Slot(list)
    def execDetached(self, args):
        self.detached_commands.append(args)

# --- Environment Setup Fixture ---

@pytest.fixture
def mock_copilot_env(qml_engine):
    # Copy Copilot.qml and register it in the QML engine's import path
    qmldir_path = base_import_path / "qs/services/qmldir"
    content = qmldir_path.read_text()
    if "singleton Copilot" not in content:
        content += "\nsingleton Copilot 1.0 Copilot.qml\n"
        qmldir_path.write_text(content)
    
    shutil.copy("/home/execorn/ricing/shell/services/Copilot.qml", str(base_import_path / "qs/services/Copilot.qml"))
    
    mock_hypr = MockHypr()
    mock_notifs = MockNotifs()
    mock_toaster = MockToaster()
    mock_wallpapers = MockWallpapers()
    mock_visibilities = MockVisibilities()
    mock_quickshell = MockQuickshell()
    
    ctx = qml_engine.rootContext()
    ctx.setContextProperty("Hypr", mock_hypr)
    ctx.setContextProperty("Notifs", mock_notifs)
    ctx.setContextProperty("Toaster", mock_toaster)
    ctx.setContextProperty("Wallpapers", mock_wallpapers)
    ctx.setContextProperty("Visibilities", mock_visibilities)
    ctx.setContextProperty("Quickshell", mock_quickshell)
    
    # Get the singleton instance to ensure clean initial state
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    if copilot_val:
        copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
        ctx.setContextProperty("Copilot", copilot)
        copilot.clearChat()

    # Connect Hypr singleton dispatched signal to mock_hypr dispatch
    hypr_val = qml_engine.singletonInstance("qs.services", "Hypr")
    if hypr_val:
        hypr_obj = hypr_val.toQObject() if isinstance(hypr_val, QJSValue) else hypr_val
        hypr_obj.dispatched.connect(mock_hypr.dispatch)
        
    return mock_hypr, mock_notifs, mock_toaster, mock_wallpapers, mock_visibilities, mock_quickshell

# --- Tests ---

def test_ollama_request_format(qml_engine, mock_llm_server, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("ollamaEndpoint", f"{mock_llm_server}/api/chat")
    
    # Ensure GEMINI_API_KEY is not set
    mock_quickshell.env_vars.clear()
    import os
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    
    copilot.sendMessage("Hello local model")
    
    wait_until(lambda: not copilot.property("loading"))
    
    assert len(MockLLMHandler.requests) == 1
    req = MockLLMHandler.requests[0]
    assert "api/chat" in req["path"]
    
    body = req["body"]
    assert body["model"] == "llama3:latest"
    assert body["stream"] is False
    
    messages = body["messages"]
    assert len(messages) == 3  # system instruction, welcome greeting, and user message
    assert messages[0]["role"] == "system"
    assert "Caelestia AI Copilot" in messages[0]["content"]
    assert "dnd" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Hello local model"
    
    # Check history contains response
    assert copilot.getChatHistoryCount() == 3
    item = json.loads(copilot.getChatHistoryItemJson(2))
    assert item["role"] == "assistant"
    assert item["message"] == "Hello from Ollama"


def test_gemini_request_format(qml_engine, mock_llm_server, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("geminiEndpoint", f"{mock_llm_server}/generateContent")
    
    # Set GEMINI_API_KEY
    mock_quickshell.env_vars["GEMINI_API_KEY"] = "fake-key-999"
    import os
    os.environ["GEMINI_API_KEY"] = "fake-key-999"
    
    copilot.sendMessage("Hi Gemini")
    
    wait_until(lambda: not copilot.property("loading"))
    
    assert len(MockLLMHandler.requests) == 1
    req = MockLLMHandler.requests[0]
    assert "generateContent" in req["path"]
    assert "key=fake-key-999" in req["path"]
    
    body = req["body"]
    assert "systemInstruction" in body
    system_text = body["systemInstruction"]["parts"][0]["text"]
    assert "Caelestia AI Copilot" in system_text
    assert "dnd" in system_text
    
    contents = body["contents"]
    # Welcome greeting (index 0) must be excluded from contents array
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "Hi Gemini"
    
    assert copilot.getChatHistoryCount() == 3
    item = json.loads(copilot.getChatHistoryItemJson(2))
    assert item["role"] == "assistant"
    assert item["message"] == "Hello from Gemini"


def test_fallback_behavior(qml_engine, mock_llm_server, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("geminiEndpoint", f"{mock_llm_server}/generateContent")
    copilot.setProperty("ollamaEndpoint", f"{mock_llm_server}/api/chat")
    
    # Set GEMINI_API_KEY but force Gemini endpoint to fail with 500
    mock_quickshell.env_vars["GEMINI_API_KEY"] = "fake-key-500"
    import os
    os.environ["GEMINI_API_KEY"] = "fake-key-500"
    MockLLMHandler.gemini_status = 500
    
    copilot.sendMessage("Hi Fallback")
    
    wait_until(lambda: not copilot.property("loading"))
    
    # Verify both requests were tried: Gemini first (failed), then Ollama fallback
    assert len(MockLLMHandler.requests) == 2
    assert "generateContent" in MockLLMHandler.requests[0]["path"]
    assert "api/chat" in MockLLMHandler.requests[1]["path"]
    
    assert copilot.getChatHistoryCount() == 3
    item = json.loads(copilot.getChatHistoryItemJson(2))
    assert item["role"] == "assistant"
    assert item["message"] == "Hello from Ollama"


def test_system_actions(qml_engine, mock_llm_server, mock_copilot_env, mock_pipewire):
    mock_hypr, mock_notifs, mock_toaster, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("ollamaEndpoint", f"{mock_llm_server}/api/chat")
    mock_quickshell.env_vars.clear()
    import os
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    
    # Setup mock default audio sink inside mock_pipewire
    n_phys = MockPwNode(4, "alsa_output.pci", "PCI Speakers", is_sink=True, ready=True, volume=0.5)
    mock_pipewire.add_node(n_phys)
    mock_pipewire.set_defaultAudioSink(n_phys)
    
    # Explicitly set the Audio singleton's sink so it gets resolved immediately without waiting for async bindings
    audio_val = qml_engine.singletonInstance("qs.services", "Audio")
    audio = audio_val.toQObject() if isinstance(audio_val, QJSValue) else audio_val
    audio.setProperty("sink", n_phys)
    
    QCoreApplication.processEvents()
    
    # 1. Test volume action
    MockLLMHandler.ollama_response = {
        "message": {
            "content": "Sure, setting volume to 75%.\n```json\n{\"action\": \"volume\", \"value\": 75}\n```"
        }
    }
    copilot.sendMessage("set volume")
    wait_until(lambda: not copilot.property("loading"))
    assert abs(n_phys.audio.volume - 0.75) < 0.01
    
    # 2. Test workspace action
    MockLLMHandler.ollama_response = {
        "message": {
            "content": "Switching to workspace 4.\n```json\n{\"action\": \"workspace\", \"id\": 4}\n```"
        }
    }
    copilot.sendMessage("switch workspace")
    wait_until(lambda: not copilot.property("loading"))
    assert "workspace 4" in mock_hypr.commands
    
    # 3. Test DND action
    MockLLMHandler.ollama_response = {
        "message": {
            "content": "Enabling DND now.\n```json\n{\"action\": \"dnd\", \"state\": true}\n```"
        }
    }
    copilot.sendMessage("enable dnd")
    wait_until(lambda: not copilot.property("loading"))
    notifs_val = qml_engine.singletonInstance("qs.services", "Notifs")
    notifs = notifs_val.toQObject() if isinstance(notifs_val, QJSValue) else notifs_val
    assert notifs.property("dnd") is True
    assert len(mock_toaster.toasts) > 0
    assert "disturb" in mock_toaster.toasts[-1][0].lower()
