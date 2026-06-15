import pytest
import time
import pathlib
import shutil
import threading
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PySide6.QtCore import QObject, Signal, Slot, Property, QCoreApplication
from PySide6.QtQml import QJSValue
from conftest import MockPwNode, base_import_path

# Import fixtures/helpers from test_copilot
from test_copilot import (
    mock_copilot_env,
    clean_env,
    wait_until,
    MockHypr,
    MockNotifs,
    MockToaster,
    MockWallpapers,
    MockVisibilities,
    MockQuickshell
)

# --- Custom Mock HTTP Server for Stress Testing (Multithreaded) ---

class MockStressLLMHandler(BaseHTTPRequestHandler):
    requests = []
    gemini_response = {}
    raw_gemini_response = None  # If set, write these raw bytes directly
    ollama_response = {}
    gemini_status = 200
    ollama_status = 200

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
        
        MockStressLLMHandler.requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": json.loads(post_data) if post_data and "application/json" in self.headers.get('Content-Type', '') else post_data
        })
        
        if "generateContent" in self.path:
            self.send_response(MockStressLLMHandler.gemini_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if MockStressLLMHandler.raw_gemini_response is not None:
                self.wfile.write(MockStressLLMHandler.raw_gemini_response)
            else:
                self.wfile.write(json.dumps(MockStressLLMHandler.gemini_response).encode('utf-8'))
        elif "api/chat" in self.path:
            self.send_response(MockStressLLMHandler.ollama_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MockStressLLMHandler.ollama_response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def mock_stress_llm_server():
    server = ThreadingHTTPServer(('127.0.0.1', 0), MockStressLLMHandler)
    port = server.server_port
    
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    yield f"http://127.0.0.1:{port}"
    
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture(autouse=True)
def clean_stress_server():
    MockStressLLMHandler.requests.clear()
    MockStressLLMHandler.gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello from Gemini"}]
                }
            }
        ]
    }
    MockStressLLMHandler.raw_gemini_response = None
    MockStressLLMHandler.ollama_response = {
        "message": {
            "content": "Hello from Ollama"
        }
    }
    MockStressLLMHandler.gemini_status = 200
    MockStressLLMHandler.ollama_status = 200

# --- Stress and Fallback Tests ---

def test_stress_rapid_send_message(qml_engine, mock_stress_llm_server, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("geminiEndpoint", f"{mock_stress_llm_server}/generateContent")
    copilot.setProperty("ollamaEndpoint", f"{mock_stress_llm_server}/api/chat")
    
    # Set GEMINI_API_KEY in both quickshell and OS env
    mock_quickshell.env_vars["GEMINI_API_KEY"] = "fake-key"
    import os
    os.environ["GEMINI_API_KEY"] = "fake-key"
    
    # Rapid back-to-back sendMessage calls on the main thread
    num_messages = 20
    for i in range(num_messages):
        copilot.sendMessage(f"Rapid message {i}")
    
    # Wait until all 20 responses are fully processed and appended to chatHistory
    expected_count = 1 + num_messages * 2
    wait_until(lambda: copilot.getChatHistoryCount() == expected_count, timeout_ms=10000)
    
    # Ensure there are no crashes and all requests went through
    assert len(MockStressLLMHandler.requests) == num_messages
    assert copilot.property("loading") is False


def test_stress_large_input_message(qml_engine, mock_stress_llm_server, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("geminiEndpoint", f"{mock_stress_llm_server}/generateContent")
    copilot.setProperty("ollamaEndpoint", f"{mock_stress_llm_server}/api/chat")
    
    # Set GEMINI_API_KEY in both quickshell and OS env
    mock_quickshell.env_vars["GEMINI_API_KEY"] = "fake-key"
    import os
    os.environ["GEMINI_API_KEY"] = "fake-key"
    
    # Send a large 5MB message to stress JSON serialization and memory bounds
    large_payload = "A" * (5 * 1024 * 1024)
    copilot.sendMessage(large_payload)
    
    # Wait until response is appended
    wait_until(lambda: copilot.getChatHistoryCount() == 3, timeout_ms=10000)
    
    # Verify the message was received by the mock server
    assert len(MockStressLLMHandler.requests) == 1
    req = MockStressLLMHandler.requests[0]
    contents = req["body"]["contents"]
    assert len(contents) == 1
    assert contents[0]["parts"][0]["text"] == large_payload


@pytest.mark.parametrize("malformed_response", [
    {},  # Empty response
    {"candidates": []},  # Empty candidates
    {"candidates": [{}]},  # Missing content
    {"candidates": [{"content": {}}]},  # Missing parts
    {"candidates": [{"content": {"parts": []}}]},  # Empty parts
    {"candidates": [{"content": {"parts": [{"text": None}]}}]},  # Null text
    {"candidates": [{"content": {"parts": [{"text": 12345}]}}]},  # Incorrect type (int)
    {"candidates": [{"content": {"parts": [{"text": ["nested", "list"]}]}}]},  # Incorrect type (list)
])
def test_gemini_malformed_json_fallback(qml_engine, mock_stress_llm_server, mock_copilot_env, malformed_response):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("geminiEndpoint", f"{mock_stress_llm_server}/generateContent")
    copilot.setProperty("ollamaEndpoint", f"{mock_stress_llm_server}/api/chat")
    
    # Set GEMINI_API_KEY in both quickshell and OS env
    mock_quickshell.env_vars["GEMINI_API_KEY"] = "fake-key"
    import os
    os.environ["GEMINI_API_KEY"] = "fake-key"
    MockStressLLMHandler.gemini_response = malformed_response
    
    copilot.sendMessage("Testing malformed Gemini JSON structures")
    
    # Wait until history count is 3 (1 welcome + 1 user + 1 assistant from fallback)
    # Note: If fallback fails to trigger, this will timeout after 5000ms.
    wait_until(lambda: copilot.getChatHistoryCount() == 3, timeout_ms=5000)
    
    # Verify fallback to Ollama was triggered: Gemini requested first, then Ollama
    assert len(MockStressLLMHandler.requests) == 2
    assert "generateContent" in MockStressLLMHandler.requests[0]["path"]
    assert "api/chat" in MockStressLLMHandler.requests[1]["path"]
    
    # Check that the Ollama response was appended to history
    item = json.loads(copilot.getChatHistoryItemJson(2))
    assert item["role"] == "assistant"
    assert item["message"] == "Hello from Ollama"


def test_gemini_raw_invalid_json_fallback(qml_engine, mock_stress_llm_server, mock_copilot_env):
    _, _, _, _, _, mock_quickshell = mock_copilot_env
    copilot_val = qml_engine.singletonInstance("qs.services", "Copilot")
    copilot = copilot_val.toQObject() if isinstance(copilot_val, QJSValue) else copilot_val
    copilot.setProperty("geminiEndpoint", f"{mock_stress_llm_server}/generateContent")
    copilot.setProperty("ollamaEndpoint", f"{mock_stress_llm_server}/api/chat")
    
    # Set GEMINI_API_KEY in both quickshell and OS env
    mock_quickshell.env_vars["GEMINI_API_KEY"] = "fake-key"
    import os
    os.environ["GEMINI_API_KEY"] = "fake-key"
    
    # Send raw invalid bytes that fail JSON.parse completely
    MockStressLLMHandler.raw_gemini_response = b"{invalid raw json: missing braces and quotes"
    
    copilot.sendMessage("Testing raw invalid JSON response")
    
    # Wait until fallback finishes
    wait_until(lambda: copilot.getChatHistoryCount() == 3, timeout_ms=5000)
    
    # Verify fallback to Ollama was triggered
    assert len(MockStressLLMHandler.requests) == 2
    assert "generateContent" in MockStressLLMHandler.requests[0]["path"]
    assert "api/chat" in MockStressLLMHandler.requests[1]["path"]
    
    # Check Ollama response was appended
    item = json.loads(copilot.getChatHistoryItemJson(2))
    assert item["role"] == "assistant"
    assert item["message"] == "Hello from Ollama"
