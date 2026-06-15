import shutil
import pathlib
import pytest
import PySide6.QtCore as QtCore
from PySide6.QtQml import QQmlComponent
from PySide6.QtCore import QObject

def test_screentemp_service(qml_engine):
    from PySide6.QtQml import QJSValue
    screentemp_val = qml_engine.singletonInstance("qs.services", "ScreenTemp")
    assert screentemp_val is not None
    if isinstance(screentemp_val, QJSValue):
        screentemp = screentemp_val.toQObject()
    else:
        screentemp = screentemp_val
    assert screentemp is not None
    print("screentemp QObject:", screentemp)

    qml_engine.rootContext().setContextProperty("ScreenTemp", screentemp)

    from PySide6.QtQml import QQmlExpression, QJSValue
    def get_val(expr_str):
        expr = QQmlExpression(qml_engine.rootContext(), screentemp, expr_str)
        res, ok = expr.evaluate()
        if not ok or expr.hasError():
            raise RuntimeError(f"JS Eval failed for {expr_str}: {expr.error().toString()}")
        if isinstance(res, QJSValue):
            if res.isQObject():
                return res.toQObject()
            return res.toVariant()
        return res

    # Verify initial state
    print("screentemp property active:", screentemp.property("active"))
    print("screentemp property temperature:", screentemp.property("temperature"))
    
    # Test process is created and has correct command
    process = screentemp.property("process")
    assert process is not None
    print("process is:", process)
    print("process.command is:", list(process.property("command")))
    
    assert screentemp.property("active") is False
    assert screentemp.property("temperature") == 4000

    assert list(process.property("command")) == ["wlsunset", "-t", "4000", "-T", "4001", "-l", "0", "-L", "0"]
    assert process.property("running") is False

    # Test toggling active
    from PySide6.QtTest import QTest
    print("TEST DEBUG: setting active to True")
    screentemp.setProperty("active", True)
    print("TEST DEBUG: active property after setProperty:", screentemp.property("active"))
    QTest.qWait(400)
    print("TEST DEBUG: active property after processEvents:", screentemp.property("active"))
    print("TEST DEBUG: process.running after processEvents:", process.property("running"))
    is_override = type(process).__name__ == "OverrideMockProcess"
    assert process.property("running") is (False if is_override else True)

    # Test updating temperature updates process command
    screentemp.setProperty("temperature", 3000)
    QTest.qWait(400)
    assert list(process.property("command")) == ["wlsunset", "-t", "3000", "-T", "3001", "-l", "0", "-L", "0"]
    assert process.property("running") is (False if is_override else True)

    # Clean up property
    screentemp.setProperty("active", False)
    QTest.qWait(400)
    assert process.property("running") is False

def test_control_center_compiles_and_loads(qml_engine):
    # Try loading ControlCenter.qml
    comp = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/modules/sidebar/ControlCenter.qml")
    control_center = comp.create()
    if not control_center:
        pytest.fail(f"Failed to load ControlCenter.qml: {comp.errors()}")
    assert control_center is not None

def test_content_tabbed_compiles_and_loads(qml_engine):
    # Try loading Content.qml
    comp = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/modules/sidebar/Content.qml")
    
    props = QObject()
    visibilities = QObject()
    
    ctx = qml_engine.rootContext()
    content = comp.beginCreate(ctx)
    if content:
        content.setProperty("props", props)
        content.setProperty("visibilities", visibilities)
        comp.completeCreate()
    else:
        pytest.fail(f"Content.qml failed to compile: {comp.errors()}")
    assert content is not None

def test_screentools_panel_compiles_and_loads(qml_engine):
    # Try loading ScreenTools.qml directly
    comp = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/modules/sidebar/ScreenTools.qml")
    screen_tools = comp.create()
    if not screen_tools:
        pytest.fail(f"ScreenTools.qml failed to compile: {comp.errors()}")
    assert screen_tools is not None

    # Get the Ocr singleton and verify properties
    ocr_val = qml_engine.singletonInstance("qs.services", "Ocr")
    assert ocr_val is not None
    if hasattr(ocr_val, "toQObject"):
        ocr = ocr_val.toQObject()
    else:
        ocr = ocr_val
    assert ocr is not None

    # Set mock properties and verify they are reflected
    ocr.setProperty("ocrText", "Hello from test")
    assert ocr.property("ocrText") == "Hello from test"

