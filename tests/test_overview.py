import pytest
import pathlib
from PySide6.QtQml import QQmlComponent
from PySide6.QtCore import QObject, Property, Signal

OVERVIEW_QML_PATH = "/home/execorn/ricing/shell/modules/overview/Overview.qml"

class MockWindow(QObject):
    def __init__(self, address, title, ws_id, x=100, y=100, width=800, height=600):
        super().__init__()
        self._address = address
        self._title = title
        
        class MockWorkspace(QObject):
            def __init__(self, wid):
                super().__init__()
                self._id = wid
            id = Property(int, lambda s: s._id, constant=True)
            
        self._workspace = MockWorkspace(ws_id)
        self._lastIpcObject = {
            "at": [x, y],
            "size": [width, height],
            "address": address,
            "title": title
        }
        
    address = Property(str, lambda s: s._address, constant=True)
    title = Property(str, lambda s: s._title, constant=True)
    workspace = Property(QObject, lambda s: s._workspace, constant=True)
    lastIpcObject = Property('QVariantMap', lambda s: s._lastIpcObject, constant=True)


def test_overview_toggle(qapp, qml_engine):
    comp = QQmlComponent(qml_engine, OVERVIEW_QML_PATH)
    overview = comp.create()
    if not overview:
        raise RuntimeError(f"Failed to load Overview: {comp.errors()}")
        
    assert overview.property("active") is False
    
    overview.setProperty("active", True)
    qapp.processEvents()
    assert overview.property("active") is True
    
    overview.setProperty("active", False)
    qapp.processEvents()
    assert overview.property("active") is False


def test_workspace_card_rendering(qapp, qml_engine):
    comp = QQmlComponent(qml_engine, OVERVIEW_QML_PATH)
    overview = comp.create()
    if not overview:
        raise RuntimeError(f"Failed to load Overview: {comp.errors()}")
        
    hypr = qml_engine.singletonInstance("qs.services", "Hypr")
    
    # Create some mock windows on different workspaces
    win1 = MockWindow("111", "kitty", 1, x=50, y=50, width=500, height=400)
    win2 = MockWindow("222", "firefox", 3, x=100, y=100, width=600, height=500)
    
    toplevels_obj = hypr.property("toplevels")
    toplevels_obj.setProperty("values", [win1, win2])
    
    # Set active to True to load LazyLoader/Variants
    overview.setProperty("active", True)

    import shiboken6
    def find_all_objects(root_obj, name, visited=None):
        if visited is None:
            visited = set()
        try:
            val = shiboken6.getCppPointer(root_obj)[0]
        except Exception:
            val = id(root_obj)
        if val in visited:
            return []
        visited.add(val)
        
        results = []
        try:
            if root_obj.objectName() == name:
                results.append(root_obj)
        except Exception:
            pass
            
        try:
            for child in root_obj.children():
                results.extend(find_all_objects(child, name, visited))
        except Exception:
            pass
            
        try:
            if hasattr(root_obj, "childItems"):
                for child in root_obj.childItems():
                    results.extend(find_all_objects(child, name, visited))
        except Exception:
            pass
            
        return results

    import time
    start_time = time.time()
    cards = []
    while time.time() - start_time < 2.0:
        qapp.processEvents()
        all_cards = find_all_objects(overview, "workspaceCard")
        
        from collections import defaultdict
        groups = defaultdict(list)
        for card in all_cards:
            parent = card.parentItem()
            if parent:
                try:
                    parent_ptr = shiboken6.getCppPointer(parent)[0]
                except Exception:
                    parent_ptr = id(parent)
                groups[parent_ptr].append(card)
            
        for parent_ptr, group in groups.items():
            if len(group) == 10:
                cards = group
                break
        if len(cards) == 10:
            break
        time.sleep(0.05)

    assert len(cards) == 10
    card_ids = [card.property("wsId") for card in cards]
    assert sorted(card_ids) == list(range(1, 11))



def test_click_card_switches_workspace(qapp, qml_engine):
    comp = QQmlComponent(qml_engine, OVERVIEW_QML_PATH)
    overview = comp.create()
    if not overview:
        raise RuntimeError(f"Failed to load Overview: {comp.errors()}")
        
    hypr = qml_engine.singletonInstance("qs.services", "Hypr")
    dispatched_calls = []
    hypr.dispatched.connect(lambda req: dispatched_calls.append(req))
    
    # Set active to True
    overview.setProperty("active", True)
    qapp.processEvents()
    
    # Call clickCard method on workspace 5
    overview.clickCard(5)
    qapp.processEvents()
    
    # Verify workspace switch was dispatched
    assert "workspace 5" in dispatched_calls
    
    # Verify overview is closed
    assert overview.property("active") is False


def test_drag_and_drop_moves_window(qapp, qml_engine):
    comp = QQmlComponent(qml_engine, OVERVIEW_QML_PATH)
    overview = comp.create()
    if not overview:
        raise RuntimeError(f"Failed to load Overview: {comp.errors()}")
        
    hypr = qml_engine.singletonInstance("qs.services", "Hypr")
    dispatched_calls = []
    hypr.dispatched.connect(lambda req: dispatched_calls.append(req))
    
    # Set active to True
    overview.setProperty("active", True)
    qapp.processEvents()
    
    # Simulate moving window hex address "12345" to workspace 8
    overview.dragAndDropWindow("12345", 8)
    qapp.processEvents()
    
    # Verify dispatch command was sent
    assert "movetoworkspace 8,address:0x12345" in dispatched_calls
    
    # Simulate moving window name "kitty" to workspace 5
    overview.dragAndDropWindow("kitty", 5)
    qapp.processEvents()
    
    # Verify dispatch command was sent
    assert "movetoworkspace 5,kitty" in dispatched_calls
