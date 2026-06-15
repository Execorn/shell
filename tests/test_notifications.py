import pytest
import PySide6.QtCore as QtCore
from PySide6.QtQml import QQmlComponent
from PySide6.QtCore import QObject

def test_notifs_muting_service(qml_engine):
    from PySide6.QtQml import QJSValue
    notifs_val = qml_engine.singletonInstance("qs.services", "Notifs")
    assert notifs_val is not None
    notifs = notifs_val.toQObject() if hasattr(notifs_val, "toQObject") else notifs_val
    assert notifs is not None

    # Initial state
    assert notifs.property("mutedAppsJson") == "{}"
    assert notifs.isAppMuted("someApp") is False

    # Test muting for 1 hour
    notifs.muteApp("someApp", 1)
    assert notifs.isAppMuted("someApp") is True

    # Test unmute
    notifs.unmuteApp("someApp")
    assert notifs.isAppMuted("someApp") is False

    # Test muting forever
    notifs.muteApp("anotherApp", 0)
    assert notifs.isAppMuted("anotherApp") is True

def test_notif_data_is_critical(qml_engine):
    # Load NotifData component
    comp = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/services/NotifData.qml")
    notif_data = comp.create()
    if not notif_data:
        pytest.fail(f"Failed to load NotifData.qml: {comp.errors()}")
    assert notif_data is not None

    # NotificationUrgency enum constants: Low = 0, Normal = 1, Critical = 2
    # Verify default is normal urgency and not critical
    assert notif_data.property("urgency") == 1
    assert notif_data.property("isCritical") is False

    # Test critical urgency
    notif_data.setProperty("urgency", 2)
    assert notif_data.property("isCritical") is True

    # Reset urgency
    notif_data.setProperty("urgency", 1)
    assert notif_data.property("isCritical") is False

    # Test system application name
    notif_data.setProperty("appName", "systemd")
    assert notif_data.property("isCritical") is True

    notif_data.setProperty("appName", "some-app")
    assert notif_data.property("isCritical") is False

    # Test keywords
    notif_data.setProperty("summary", "An error occurred")
    assert notif_data.property("isCritical") is True

    notif_data.setProperty("summary", "Everything is fine")
    assert notif_data.property("isCritical") is False

    notif_data.setProperty("body", "Fatal exception happened")
    assert notif_data.property("isCritical") is True

def test_notification_ui_components_compile(qml_engine):
    # Test compilation of NotifDock.qml
    comp1 = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/modules/sidebar/NotifDock.qml")
    props = QObject()
    visibilities = QObject()
    ctx = qml_engine.rootContext()
    
    dock = comp1.beginCreate(ctx)
    if dock:
        dock.setProperty("props", props)
        dock.setProperty("visibilities", visibilities)
        comp1.completeCreate()
    else:
        pytest.fail(f"NotifDock.qml failed to compile: {comp1.errors()}")
    assert dock is not None

    # Test compilation of Notif.qml
    comp2 = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/modules/sidebar/Notif.qml")
    # Stub model data
    notif_data = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/services/NotifData.qml").create()
    
    notif_card = comp2.beginCreate(ctx)
    if notif_card:
        notif_card.setProperty("modelData", notif_data)
        notif_card.setProperty("props", props)
        notif_card.setProperty("expanded", False)
        notif_card.setProperty("visibilities", visibilities)
        comp2.completeCreate()
    else:
        pytest.fail(f"Notif.qml failed to compile: {comp2.errors()}")
    assert notif_card is not None

    # Test compilation of NotifActionList.qml
    comp3 = QQmlComponent(qml_engine, "/home/execorn/ricing/shell/modules/sidebar/NotifActionList.qml")
    action_list = comp3.beginCreate(ctx)
    if action_list:
        action_list.setProperty("notif", notif_data)
        comp3.completeCreate()
    else:
        pytest.fail(f"NotifActionList.qml failed to compile: {comp3.errors()}")
    assert action_list is not None
