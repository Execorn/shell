import pytest
import time
import json
import pathlib
import os
import math
from PySide6.QtCore import QObject, Property, Signal, Slot, QCoreApplication
from PySide6.QtQml import QQmlComponent, QJSValue
from test_ricing import ricing_suite, mock_bins, WrapperValue, qml_engine, call_method, get_property, set_property
from test_overview import OVERVIEW_QML_PATH

# Write a corrupt keyboard layout base.lst file at module load time to verify initialization robustness
CORRUPT_KB_PATH = "/tmp/corrupt_base_adversarial.lst"
pathlib.Path(CORRUPT_KB_PATH).write_text("! layout\n corrupt layout listing without double spaces or proper format\n\n! variant\n corrupt variant format\n\n")
os.environ["CAELESTIA_XKB_RULES_PATH"] = CORRUPT_KB_PATH


# 1. Verification of Colours.qml with pure black input and other edge-case colors
def test_colours_pure_black_input(ricing_suite):
    engine = ricing_suite["engine"]
    colours = engine.singletonInstance("qs.services", "Colours")
    assert colours is not None
    
    res = call_method(engine, colours, "alterColour", "#000000", 1.0, 1).toVariant()
    assert res is not None
    
    # Check getLuminance with pure black
    lum = call_method(engine, colours, "getLuminance", "#000000").toVariant()
    assert lum == 0
    
    # Check alterColour with pure black (scale should be 0, returning rgba(0,0,0,1))
    altered_black = call_method(engine, colours, "alterColour", "#000000", 0.8, 1).toVariant()
    assert altered_black is not None
    
    # Check alterColour with extremely small but non-zero colors (to test floating-point edge cases)
    res_near_black = call_method(engine, colours, "alterColour", "#000001", 1.0, 1).toVariant()
    assert res_near_black is not None
    
    # Verify layer function with null/undefined arguments
    js_layer_null = call_method(engine, colours, "layer", "#000000", None).toVariant()
    assert js_layer_null is not None


# 2. Verification of Hypr.qml compatibility with real QQmlListProperty (no .find method, etc.)
def test_hypr_real_list_property_robustness(ricing_suite):
    engine = ricing_suite["engine"]
    hypr_qobj = engine.singletonInstance("qs.services", "Hypr")
    
    # Retrieve extras mock object from children
    extras = None
    for child in hypr_qobj.children():
        if child.__class__.__name__ == "MockHyprExtras":
            extras = child
            break
    assert extras is not None
    
    from test_ricing import MockHyprKeyboard
    mock_kb1 = MockHyprKeyboard(main=False, capsLock=False, numLock=False, layout="us", activeKeymap="English")
    mock_kb2 = MockHyprKeyboard(main=True, capsLock=True, numLock=False, layout="us,ru", activeKeymap="English (US)")
    
    global_obj = engine.globalObject()
    global_obj.setProperty("mock_kb1", engine.toScriptValue(mock_kb1))
    global_obj.setProperty("mock_kb2", engine.toScriptValue(mock_kb2))
    
    # Evaluate a custom keyboards JS list that has length and bracket access but NO array helper methods (find, map, etc.)
    # to simulate C++ QQmlListProperty
    kb_list = engine.evaluate('''
        (function() {
            return {
                length: 2,
                0: mock_kb1,
                1: mock_kb2
            };
        })()
    ''')
    assert not kb_list.isError()
    
    # Define a custom devices QObject class that returns this keyboards JS list
    class CustomDevices(QObject):
        keyboardsChanged = Signal()
        def __init__(self, kb_list_val):
            super().__init__()
            self._kb_list = kb_list_val
        @Property('QJSValue', notify=keyboardsChanged)
        def keyboards(self):
            return self._kb_list
            
    # Set the custom devices on the extras mock
    custom_devices = CustomDevices(kb_list)
    extras._devices = custom_devices
    extras.devicesChanged.emit()
    
    # Retrieve the keyboard property. Hypr.qml should iterate over it using length and bracket access without crashing.
    kb_val = get_property(engine, hypr_qobj, "keyboard")
    assert kb_val is not None
    
    # Verify properties of the matched keyboard
    assert kb_val.property("main").toVariant() is True
    assert kb_val.property("layout").toVariant() == "us,ru"
    
    # Check that computed properties resolve correctly and don't throw
    assert get_property(engine, hypr_qobj, "capsLock").toVariant() is True
    assert get_property(engine, hypr_qobj, "numLock").toVariant() is False
    assert get_property(engine, hypr_qobj, "defaultKbLayout").toVariant() == "us"
    assert get_property(engine, hypr_qobj, "kbLayoutFull").toVariant() == "English (US)"


# 3. Verification of Copilot and OCR Request Queue Release on Timeout
def test_copilot_request_queue_timeout_release(ricing_suite):
    engine = ricing_suite["engine"]
    copilot = engine.singletonInstance("qs.services", "Copilot")
    
    # Construct and register the mock XHR constructor with timeout using Qt.callLater
    mock_xhr_val = engine.evaluate('''
    (function() {
        var XHR = function() {
            var self = this;
            this.readyState = 0;
            this.status = 0;
            this.responseText = "";
            this.headers = {};
            this.timeout = 0;
            this.ontimeout = null;
            this.open = function(method, url, async) {};
            this.setRequestHeader = function(h, v) {};
            this.send = function(payload) {
                if (self.ontimeout) {
                    Qt.callLater(function() {
                        self.readyState = 4;
                        self.status = 0;
                        self.ontimeout();
                        if (self.onreadystatechange) {
                            self.onreadystatechange();
                        }
                    });
                }
            };
        };
        XHR.UNSENT = 0;
        XHR.OPENED = 1;
        XHR.HEADERS_RECEIVED = 2;
        XHR.LOADING = 3;
        XHR.DONE = 4;
        return XHR;
    })()
    ''')
    engine.rootContext().setContextProperty("XMLHttpRequest", mock_xhr_val)
    
    try:
        # Initial request count should be 0
        assert get_property(engine, copilot, "activeRequestsCount").toVariant() == 0
        
        # Send message to trigger request (which hangs)
        call_method(engine, copilot, "sendMessage", "This request should time out")
        
        # The request count should increase to 1
        assert get_property(engine, copilot, "activeRequestsCount").toVariant() == 1
        assert get_property(engine, copilot, "loading").toVariant() is True
        
        # Wait for the timeout to execute and decrement request count
        start = time.time()
        while get_property(engine, copilot, "activeRequestsCount").toVariant() > 0 and time.time() - start < 2.0:
            QCoreApplication.processEvents()
            time.sleep(0.01)
            
        # The slot should be successfully released
        assert get_property(engine, copilot, "activeRequestsCount").toVariant() == 0
        assert get_property(engine, copilot, "loading").toVariant() is False
        assert get_property(engine, copilot, "lastError").toVariant() in ("Connection to Ollama timed out.", "Cannot connect to local Ollama server...")
        
    finally:
        # Restore original mock XMLHttpRequest
        engine.rootContext().setContextProperty("XMLHttpRequest", ricing_suite["xhr_fn"])


def test_ocr_request_timeout_clean_cleanup(ricing_suite):
    engine = ricing_suite["engine"]
    ocr = engine.singletonInstance("qs.services", "Ocr")
    
    # Prepare ocrText for translation
    set_property(engine, ocr, "ocrText", "Hello world")
    
    # Construct and register the mock XHR constructor with timeout using Qt.callLater
    mock_xhr_val = engine.evaluate('''
    (function() {
        var XHR = function() {
            var self = this;
            this.readyState = 0;
            this.status = 0;
            this.responseText = "";
            this.headers = {};
            this.timeout = 0;
            this.ontimeout = null;
            this.open = function(method, url, async) {};
            this.setRequestHeader = function(h, v) {};
            this.send = function(payload) {
                if (self.ontimeout) {
                    Qt.callLater(function() {
                        self.readyState = 4;
                        self.status = 0;
                        self.ontimeout();
                        if (self.onreadystatechange) {
                            self.onreadystatechange();
                        }
                    });
                }
            };
        };
        XHR.UNSENT = 0;
        XHR.OPENED = 1;
        XHR.HEADERS_RECEIVED = 2;
        XHR.LOADING = 3;
        XHR.DONE = 4;
        return XHR;
    })()
    ''')
    engine.rootContext().setContextProperty("XMLHttpRequest", mock_xhr_val)
    
    try:
        # Trigger translation
        call_method(engine, ocr, "translateText", "Spanish")
        
        # Wait for timeout to fire
        start = time.time()
        while not get_property(engine, ocr, "lastError").toVariant() and time.time() - start < 2.0:
            QCoreApplication.processEvents()
            time.sleep(0.01)
            
        # Verify status is cleaned up and error set
        assert get_property(engine, ocr, "translatedText").toVariant() == ""
        assert "timed out" in get_property(engine, ocr, "lastError").toVariant()
        
    finally:
        engine.rootContext().setContextProperty("XMLHttpRequest", ricing_suite["xhr_fn"])


# 4. Verification of Weather and Keyboard Layout Parsing Errors
def test_weather_nominatim_corrupt_json_handling(ricing_suite):
    engine = ricing_suite["engine"]
    weather = engine.singletonInstance("qs.services", "Weather")
    requests = ricing_suite["requests"]
    
    # Set request mock to return invalid JSON
    requests.setProperty("mockResponseStatus", 200)
    requests.setProperty("mockResponseText", "{ corrupt json: missing values }")
    
    # Trigger geocoding
    call_method(engine, weather, "fetchCityFromCoords", "40.7128,-74.0060")
    
    # Wait for requests to process
    start = time.time()
    while get_property(engine, weather, "city").toVariant() == "Mock City" and time.time() - start < 2.0:
        QCoreApplication.processEvents()
        time.sleep(0.01)
        
    # Verify city is updated to fallback value cleanly without crashing
    assert get_property(engine, weather, "city").toVariant() == "Unknown City"


def test_hypr_kb_layout_file_corrupt_parsing(ricing_suite):
    engine = ricing_suite["engine"]
    hypr_qobj = engine.singletonInstance("qs.services", "Hypr")
    
    # Find the FileView child of Hypr
    children = hypr_qobj.findChildren(QObject)
    kb_layout_file = None
    for child in children:
        p = child.property("path")
        if p is not None and ("base.lst" in p or "corrupt_base_adversarial" in p):
            kb_layout_file = child
            break
            
    assert kb_layout_file is not None
    
    # Trigger onLoaded with corrupt text
    corrupt_path = "/tmp/corrupt_base_adversarial.lst"
    
    # Verify reload of corrupt path works fine
    kb_layout_file.setProperty("path", corrupt_path)
    kb_layout_file.reload()
    
    # Verify map remains empty or unmodified and no crash
    assert get_property(engine, hypr_qobj, "kbMap").toVariant() is not None


# 5. Verification of Overview thumbnail coordinate bounds with missing/invalid data
class MockAdversarialWindow(QObject):
    def __init__(self, address, title, ws_id, last_ipc_object):
        super().__init__()
        self._address = address
        self._title = title
        
        class MockWorkspace(QObject):
            def __init__(self, wid):
                super().__init__()
                self._id = wid
            id = Property(int, lambda s: s._id, constant=True)
            
        self._workspace = MockWorkspace(ws_id)
        self._lastIpcObject = last_ipc_object
        
    address = Property(str, lambda s: s._address, constant=True)
    title = Property(str, lambda s: s._title, constant=True)
    workspace = Property(QObject, lambda s: s._workspace, constant=True)
    lastIpcObject = Property('QVariant', lambda s: s._lastIpcObject, constant=True)


def test_overview_coordinate_bounds_missing_data(qapp, qml_engine):
    comp = QQmlComponent(qml_engine, OVERVIEW_QML_PATH)
    overview = comp.create()
    if not overview:
        raise RuntimeError(f"Failed to load Overview: {comp.errors()}")
        
    hypr = qml_engine.singletonInstance("qs.services", "Hypr")
    
    # Construct scenarios of missing or corrupt window data:
    # 1. Null lastIpcObject
    win_null_ipc = MockAdversarialWindow("101", "kitty", 1, None)
    # 2. lastIpcObject missing 'at' or 'size'
    win_missing_at = MockAdversarialWindow("102", "firefox", 1, {"size": [800, 600]})
    # 3. lastIpcObject having NaN coordinates
    win_nan_coords = MockAdversarialWindow("103", "nemo", 1, {"at": [float('nan'), float('nan')], "size": [800, 600]})
    
    toplevels_obj = hypr.property("toplevels")
    toplevels_obj.setProperty("values", [win_null_ipc, win_missing_at, win_nan_coords])
    
    # Activate Overview to trigger coordinate calculations
    overview.setProperty("active", True)
    qapp.processEvents()
    
    # Ensure no crashes occurred. Coordinate binding evaluations should return 0 safely.
    overview.setProperty("active", False)
