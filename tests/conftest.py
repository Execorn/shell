import os
import sys
import shutil
import pathlib
import pytest
from PySide6.QtCore import QObject, Signal, Slot, Property, ClassInfo
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, qmlRegisterType, qmlRegisterSingletonInstance, QmlAttached
from PySide6.QtQuick import QQuickItem

# Set Qt offscreen platform before application creation
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QML_DISABLE_DISK_CACHE"] = "1"

# Setup wpctl mock binary interception mechanism
bin_dir = pathlib.Path("/tmp/caelestia-test-bin")
bin_dir.mkdir(parents=True, exist_ok=True)
wpctl_path = bin_dir / "wpctl"
wpctl_path.write_text("#!/bin/bash\necho \"$@\" >> /tmp/wpctl_calls.log\nexit 0\n")
wpctl_path.chmod(0o755)

wlsunset_path = bin_dir / "wlsunset"
wlsunset_path.write_text("#!/bin/bash\necho \"$@\" >> /tmp/wlsunset_calls.log\nsleep 9999\n")
wlsunset_path.chmod(0o755)

# Prepend mock bin to PATH
original_path = os.environ.get("PATH", "")
os.environ["PATH"] = f"/tmp/caelestia-test-bin:{original_path}"

# Setup dummy QML import modules for testing
base_import_path = pathlib.Path(f"/tmp/qml-imports-audio-mixer-{os.getpid()}")
shutil.rmtree(base_import_path, ignore_errors=True)

mocks = {
    'Quickshell': {
        'qmldir': 'module Quickshell\nSingleton 1.0 Singleton.qml\nIpcHandler 1.0 IpcHandler.qml\nScope 1.0 Scope.qml\nLazyLoader 1.0 LazyLoader.qml\nVariants 1.0 Variants.qml\nShellScreen 1.0 ShellScreen.qml\nScriptModel 1.0 ScriptModel.qml\nClippingRectangle 1.0 ClippingRectangle.qml\nTransformWatcher 1.0 TransformWatcher.qml\nNotifData 1.0 NotifData.qml\nRegion 1.0 Region.qml\nPanelWindow 1.0 PanelWindow.qml\nPersistentProperties 1.0 PersistentProperties.qml\n',
        'Singleton.qml': 'import QtQuick\nQtObject {\n    default property var children\n}\n',
        'IpcHandler.qml': 'import QtQuick\nQtObject {\n    property string target: \"\"\n}\n',
        'Scope.qml': 'import QtQuick\nItem {\n    default property var data\n}\n',
        'LazyLoader.qml': 'import QtQuick\nItem {\n    property bool active: false\n    default property var data\n}\n',
        'Variants.qml': 'import QtQuick\nItem {\n    id: customVar\n    property var model\n    default property Component delegateComponent\n    property alias instances: customVar.instantiatedObjects\n    property var instantiatedObjects: []\n    function recreateObjects() {\n        if (!model || !delegateComponent) return;\n        for (var i = 0; i < instantiatedObjects.length; i++) {\n            if (instantiatedObjects[i]) instantiatedObjects[i].destroy();\n        }\n        instantiatedObjects = [];\n        var temp = [];\n        for (var index = 0; index < model.length; index++) {\n            var itemData = model[index];\n            var obj = delegateComponent.createObject(customVar, {\n                "modelData": itemData\n            });\n            if (obj) {\n                temp.push(obj);\n                if (obj.dummyItem) {\n                    obj.dummyItem.parent = customVar;\n                }\n            }\n        }\n        instantiatedObjects = temp;\n    }\n    onModelChanged: recreateObjects()\n    onDelegateComponentChanged: recreateObjects()\n    Component.onCompleted: recreateObjects()\n}\n',
        'ShellScreen.qml': 'import QtQuick\nQtObject {\n    property string name: \"\"\n    property int x: 0\n    property int y: 0\n    property int width: 1920\n    property int height: 1080\n}\n',
        'ScriptModel.qml': 'import QtQuick\nListModel {\n    property var values: []\n    onValuesChanged: {\n        clear();\n        if (values) {\n            for (var i = 0; i < values.length; i++) {\n                append({"modelData": values[i]});\n            }\n        }\n    }\n}\n',
        'ClippingRectangle.qml': 'import QtQuick\nRectangle {}\n',
        'TransformWatcher.qml': 'import QtQuick\nQtObject {\n    property var target\n    property var a\n    property var b\n    property var transform\n}\n',
        'NotifData.qml': 'import QtQuick\nQtObject {\n    property var actions: []\n    property string body: ""\n    property bool resident: false\n    property bool hasActionIcons: false\n    signal close()\n}\n',
        'Region.qml': 'import QtQuick\nQtObject {}\n',
        'PanelWindow.qml': 'import QtQuick\nItem {\n    property color color: "transparent"\n    property var mask\n}\n',
        'PersistentProperties.qml': 'import QtQuick\nQtObject {\n    property string reloadableId: ""\n}\n'
    },
    'Quickshell/Io': {
        'qmldir': 'module Quickshell.Io\nFileView 1.0 FileView.qml\n',
        'FileView.qml': 'import QtQuick\nItem {\n    enum Error {\n        FileNotFound\n    }\n    property bool printErrors: false\n    property string path: ""\n    property bool watchChanges: false\n    signal loaded()\n    signal loadFailed(int err)\n    function text() { return "[]"; }\n    function setText(t) {}\n}\n'
    },
    'Quickshell/Services/Pipewire': {
        'qmldir': 'module Quickshell.Services.Pipewire\nPwObjectTracker 1.0 PwObjectTracker.qml\n',
        'PwObjectTracker.qml': 'import QtQuick\nItem {\n    property var objects: []\n}\n'
    },
    'Quickshell/Services/Notifications': {
        'qmldir': 'module Quickshell.Services.Notifications\nDummyNotif 1.0 DummyNotif.qml\nNotifData 1.0 NotifData.qml\nNotificationServer 1.0 NotificationServer.qml\nNotification 1.0 Notification.qml\n',
        'DummyNotif.qml': 'import QtQuick\nItem {}\n',
        'NotifData.qml': 'import QtQuick\nQtObject {}\n',
        'NotificationServer.qml': 'import QtQuick\nItem {\n    property bool keepOnReload: false\n    property bool actionsSupported: false\n    property bool bodyHyperlinksSupported: false\n    property bool bodyImagesSupported: false\n    property bool bodyMarkupSupported: false\n    property bool imageSupported: false\n    property bool persistenceSupported: false\n    signal notification(var notif)\n}\n',
        'Notification.qml': 'import QtQuick\nQtObject {\n    property string id: ""\n    property string summary: ""\n    property string body: ""\n    property string appIcon: ""\n    property string appName: ""\n    property string image: ""\n    property real expireTimeout: 0\n    property var hints: ({})\n    property int urgency: 0\n    property bool resident: false\n    property bool hasActionIcons: false\n    property list<var> actions: []\n    signal closed()\n    signal summaryChanged()\n    signal bodyChanged()\n    signal appIconChanged()\n    signal appNameChanged()\n    signal imageChanged()\n    signal expireTimeoutChanged()\n    signal urgencyChanged()\n    signal residentChanged()\n    signal hasActionIconsChanged()\n    signal actionsChanged()\n    signal hintsChanged()\n    function dismiss() {}\n}\n'
    },
    'Caelestia': {
        'qmldir': 'module Caelestia\nDummy 1.0 Dummy.qml\n',
        'Dummy.qml': 'import QtQuick\nItem {}\n',
        'GlobalConfig.qml': 'import QtQuick\nQtObject {\n    property var services: ({\n        maxVolume: 1.0,\n        audioIncrement: 0.05,\n        visualiserBars: 20\n    })\n    property var utilities: ({\n        toasts: {\n            audioOutputChanged: true,\n            audioInputChanged: true\n        }\n    })\n    property var notifs: ({\n        defaultExpireTimeout: 5000,\n        fullscreenExpireTimeout: 10000,\n        expire: true\n    })\n}\n',
        'Tokens.qml': 'import QtQuick\nQtObject {\n    property var padding: ({\n        medium: 12.0,\n        extraSmall: 4.0\n    })\n    property var spacing: ({\n        medium: 8.0,\n        small: 4.0\n    })\n    property var rounding: ({\n        full: 9999.0,\n        medium: 8.0,\n        small: 4.0\n    })\n    property var anim: ({\n        durations: {\n            normal: 200,\n            fast: 100,\n            slow: 300\n        }\n    })\n    property var font: ({\n        body: {\n            builders: {\n                medium: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                },\n                small: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                }\n            }\n        },\n        title: {\n            builders: {\n                medium: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                },\n                small: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                }\n            }\n        },\n        headline: {\n            builders: {\n                medium: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                },\n                small: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                }\n            }\n        },\n        label: {\n            large: {\n                weight: function(w) { return this; },\n                build: function() { return "Google Sans"; }\n            },\n            builders: {\n                medium: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                },\n                small: {\n                    weight: function(w) { return this; },\n                    build: function() { return "Google Sans"; }\n                }\n            }\n        }\n    })\n}\n',
        'Colours.qml': 'import QtQuick\nQtObject {\n    property var palette: ({\n        m3primaryContainer: "#000000",\n        m3onPrimaryContainer: "#ffffff"\n    })\n    property var tPalette: ({\n        m3surfaceContainerLow: "#000000",\n        m3surfaceContainer: "#000000",\n        m3outline: "#000000",\n        m3outlineVariant: "#000000"\n    })\n}\n'
    },
    'Caelestia/Config': {
        'qmldir': 'module Caelestia.Config\nsingleton TokenConfig 1.0 TokenConfig.qml\n',
        'TokenConfig.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    readonly property var sizes: ({\n        notifs: {\n            image: 48\n        }\n    })\n}\n'
    },
    'Caelestia/Services': {
        'qmldir': 'module Caelestia.Services\nCavaProvider 1.0 CavaProvider.qml\nBeatTracker 1.0 BeatTracker.qml\n',
        'CavaProvider.qml': 'import QtQuick\nItem {\n    property int bars: 0\n}\n',
        'BeatTracker.qml': 'import QtQuick\nItem {}\n'
    },
    'qs/services': {
        'qmldir': 'module qs.services\nsingleton Audio 1.0 Audio.qml\nsingleton Hypr 1.0 Hypr.qml\nsingleton Screens 1.0 Screens.qml\nsingleton Weather 1.0 Weather.qml\nsingleton Nmcli 1.0 Nmcli.qml\nsingleton Notifs 1.0 Notifs.qml\nsingleton ScreenTemp 1.0 ScreenTemp.qml\nsingleton Copilot 1.0 Copilot.qml\nsingleton Ocr 1.0 Ocr.qml\nDummy 1.0 Dummy.qml\n',
        'Dummy.qml': 'import QtQuick\nItem {}\n',
        'Copilot.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    property bool loading: false\n    property string lastError: ""\n    property ListModel chatHistory: ListModel {}\n    function clearChat() {}\n    function sendMessage(text) {}\n}\n',
        'Ocr.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    property string ocrText: ""\n    property string translatedText: ""\n    property bool running: false\n    property string lastError: ""\n    function startOcr() {}\n    function translateText(targetLang) {}\n    function explainText() {}\n}\n',
        'Hypr.qml': 'import QtQuick\npragma Singleton\nQtObject {\n    id: root\n    property int activeWsId: 1\n    property var toplevels: QtObject {\n        property var values: []\n    }\n    property var workspaces: QtObject {\n        property var values: []\n    }\n    property var monitors: QtObject {\n        property var values: []\n    }\n    signal dispatched(string request)\n    function dispatch(request) {\n        dispatched(request);\n        if (typeof Hyprland !== "undefined" && Hyprland) {\n            Hyprland.dispatch(request);\n        }\n    }\n}\n',
        'Screens.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    id: root\n    property var screens: [\n        {\n            name: "DP-1",\n            x: 0,\n            y: 0,\n            width: 1920,\n            height: 1080\n        }\n    ]\n}\n',
        'Weather.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    property string city: "Mock City"\n    property string temp: "20°C"\n    property string icon: "cloudy"\n    property string description: "Partly Cloudy"\n    signal fetchCoordsFromCity(string cityName)\n}\n',
        'Nmcli.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    property bool wifiEnabled: true\n    property var active: QtObject { property string ssid: "Mock-Wifi" }\n    property var networks: []\n    signal enableWifi(bool checked)\n}\n',
        'Notifs.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    property var list: []\n    property bool dnd: false\n    property string mutedAppsJson: "{}"\n    function isAppMuted(appName) { return false; }\n    function muteApp(appName, hours) {}\n    function unmuteApp(appName) {}\n}\n',
    },
    'qs/components': {
        'qmldir': 'module qs.components\nStyledText 1.0 StyledText.qml\nStyledRect 1.0 StyledRect.qml\nDashboardState 1.0 DashboardState.qml\nSectionHeader 1.0 SectionHeader.qml\nMaterialIcon 1.0 MaterialIcon.qml\nAnim 1.0 Anim.qml\nStyledClippingRect 1.0 StyledClippingRect.qml\nDrawerVisibilities 1.0 DrawerVisibilities.qml\n',
        'StyledText.qml': 'import QtQuick\nText {\n    property bool animate: false\n}\n',
        'StyledRect.qml': 'import QtQuick\nRectangle {\n    property color color: "transparent"\n}\n',
        'DashboardState.qml': 'import QtQuick\nQtObject {\n    property int currentTab: 0\n    property date currentDate: new Date()\n}\n',
        'SectionHeader.qml': 'import QtQuick\nItem {\n    property string title: ""\n}\n',
        'MaterialIcon.qml': 'import QtQuick\nText {\n    property string fontStyle: ""\n    property bool animate: false\n}\n',
        'Anim.qml': 'import QtQuick\nNumberAnimation {\n    enum Type {\n        StandardSmall = 0,\n        Standard,\n        StandardLarge,\n        StandardExtraLarge,\n        EmphasizedSmall,\n        Emphasized,\n        EmphasizedLarge,\n        EmphasizedExtraLarge,\n        FastSpatial,\n        DefaultSpatial,\n        SlowSpatial,\n        FastEffects,\n        DefaultEffects,\n        SlowEffects\n    }\n    property int type: Anim.DefaultSpatial\n}\n',
        'StyledClippingRect.qml': 'import QtQuick\nItem {\n    property real radius: 0\n    property color color: "transparent"\n}\n',
        'DrawerVisibilities.qml': 'import QtQuick\nQtObject {\n    property bool bar: false\n    property bool osd: false\n    property bool session: false\n    property bool launcher: false\n    property bool dashboard: false\n    property bool utilities: false\n    property bool sidebar: false\n    property bool cheatsheet: false\n    property bool dashboardFocused: false\n}\n'
    },
    'qs/components/controls': {
        'qmldir': 'module qs.components.controls\nStyledRadioButton 1.0 StyledRadioButton.qml\nStyledSlider 1.0 StyledSlider.qml\nIconTextButton 1.0 IconTextButton.qml\nCustomMouseArea 1.0 CustomMouseArea.qml\nIconButton 1.0 IconButton.qml\nButtonBase 1.0 ButtonBase.qml\nTextButton 1.0 TextButton.qml\nStyledScrollBar 1.0 StyledScrollBar.qml\nLoadingIndicator 1.0 LoadingIndicator.qml\nStyledInputField 1.0 StyledInputField.qml\nSwitchRow 1.0 SwitchRow.qml\nStyledSwitch 1.0 StyledSwitch.qml\nSplitButton 1.0 SplitButton.qml\nMenuItem 1.0 MenuItem.qml\nMenu 1.0 Menu.qml\n',
        'StyledRadioButton.qml': 'import QtQuick\nimport QtQuick.Controls\nRadioButton {\n    property var modelData: null\n}\n',
        'StyledSlider.qml': 'import QtQuick\nimport QtQuick.Controls\nSlider {\n    signal interaction(real value)\n}\n',
        'IconTextButton.qml': 'import QtQuick\nItem {\n    property string icon: \"\"\n    property string text: \"\"\n    property var inactiveColour: null\n    property var inactiveOnColour: null\n    property var verticalPadding: null\n    property bool disabled: false\n    signal clicked()\n}\n',
        'CustomMouseArea.qml': 'import QtQuick\nItem {\n    signal wheel(var event)\n    function simulateWheel(y) {\n        wheel({ angleDelta: { y: y } });\n    }\n}\n',
        'IconButton.qml': 'import QtQuick\nimport qs.components\nimport qs.components.effects\nItem {\n    property string icon: \"\"\n    property int type: 0\n    property var font\n    property alias stateLayer: internalStateLayer\n    property alias label: internalLabel\n    property color inactiveColour\n    property color inactiveOnColour\n    property bool shapeMorph\n    property bool isRound\n    property bool isToggle\n    property bool checked\n    property bool internalChecked\n    signal clicked()\n    StateLayer {\n        id: internalStateLayer\n        property bool containsMouse: false\n    }\n    MaterialIcon {\n        id: internalLabel\n    }\n}\n',
        'ButtonBase.qml': 'import QtQuick\nItem {\n    property bool disabled: false\n    enum Type {\n        Filled,\n        Tonal,\n        Text\n    }\n    enum ButtonType {\n        Filled,\n        Tonal,\n        Text\n    }\n}\n',
        'TextButton.qml': 'import QtQuick\nimport qs.components.controls\nButtonBase {\n    property string text: \"\"\n    property int type: 0\n    signal clicked()\n}\n',
        'StyledScrollBar.qml': 'import QtQuick.Controls\nScrollBar {\n    property var flickable: null\n}',
        'LoadingIndicator.qml': 'import QtQuick\nItem {\n    property bool animated: false\n}',
        'StyledInputField.qml': 'import QtQuick\nItem {\n    property string text: \"\"\n    property string placeholderText: \"\"\n    signal editingFinished()\n    function clear() {\n        text = \"\"\n    }\n}',
        'SwitchRow.qml': 'import QtQuick\nimport QtQuick.Controls\nRow {\n    property string label: \"\"\n    property bool checked: false\n    signal toggled(bool checked)\n    Switch {\n        checked: parent.checked\n        onCheckedChanged: parent.toggled(checked)\n    }\n}',
        'StyledSwitch.qml': 'import QtQuick\nimport QtQuick.Controls\nSwitch {}',
        'SplitButton.qml': 'import QtQuick\nRow {\n    enum Type {\n        Filled,\n        Tonal\n    }\n    property int type: SplitButton.Filled\n    property bool disabled\n    property list<QtObject> menuItems\n    property var active\n    property bool expanded\n    property Menu menu: Menu {}\n}',
        'MenuItem.qml': 'import QtQuick\nQtObject {\n    property string text: \"\"\n    property string icon: \"\"\n    property string trailingIcon: \"\"\n    property string activeIcon: icon\n    property string activeText: text\n    signal clicked()\n}',
        'Menu.qml': 'import QtQuick\nItem {\n    property list<QtObject> items\n    property var active\n    property bool expanded\n    signal itemSelected(var item)\n}',
    },
    'qs/components/effects': {
        'qmldir': 'module qs.components.effects\nStateLayer 1.0 StateLayer.qml\nColouriser 1.0 Colouriser.qml\nElevation 1.0 Elevation.qml\nColouredIcon 1.0 ColouredIcon.qml\nMask 1.0 Mask.qml\n',
        'StateLayer.qml': 'import QtQuick\nItem {\n    signal clicked()\n    property bool disabled: false\n    property bool shapeMorph: false\n    property bool pressed: false\n    property bool containsMouse: false\n    property color color: "transparent"\n}\n',
        'Colouriser.qml': 'import QtQuick\nItem {\n    property color color: "transparent"\n    property var colorizationColor\n    property real brightness: 0\n}\n',
        'Elevation.qml': 'import QtQuick\nItem {\n    property int depth: 0\n    property int level: 0\n    property real radius: 0\n}\n',
        'ColouredIcon.qml': 'import QtQuick\nItem {\n    property var colour\n    property var name: ""\n    property var source: ""\n    property real implicitSize: 0\n}\n',
        'Mask.qml': 'import QtQuick\nItem {\n    property bool maskEnabled: true\n    property var maskSource\n    property var maskSpreadAtMin: 1\n    property var maskThresholdMin: 0.5\n}\n'
    },
    'Quickshell/Widgets': {
        'qmldir': 'module Quickshell.Widgets\nDummyWidget 1.0 DummyWidget.qml\nIconImage 1.0 IconImage.qml\nWrapperMouseArea 1.0 WrapperMouseArea.qml\n',
        'DummyWidget.qml': 'import QtQuick\nItem {}\n',
        'IconImage.qml': 'import QtQuick\nImage {}\n',
        'WrapperMouseArea.qml': 'import QtQuick\nMouseArea {}\n',
    },
    'Quickshell/Bluetooth': {
        'qmldir': 'module Quickshell.Bluetooth\nDummyBt 1.0 DummyBt.qml\n',
        'DummyBt.qml': 'import QtQuick\nItem {}\n',
    },
    'qs/components/containers': {
        'qmldir': 'module qs.components.containers\nStyledWindow 1.0 StyledWindow.qml\nStyledFlickable 1.0 StyledFlickable.qml\nWindowAnchors 1.0 WindowAnchors.qml\nStyledListView 1.0 StyledListView.qml\n',
        'StyledWindow.qml': 'import QtQuick\nQtObject {\n    id: root\n    required property string name\n    property var screen: null\n    property WindowAnchors anchors: WindowAnchors {}\n    property Item dummyItem: Item {\n        id: dummy\n        width: root.screen ? root.screen.width : 1920\n        height: root.screen ? root.screen.height : 1080\n    }\n    property alias width: dummy.width\n    property alias height: dummy.height\n    default property alias data: dummy.data\n}\n',
        'WindowAnchors.qml': 'import QtQuick\nQtObject {\n    property bool top: false\n    property bool bottom: false\n    property bool left: false\n    property bool right: false\n}\n',
        'StyledFlickable.qml': 'import QtQuick\nFlickable {\n    property alias horizontalScrollBar: horiz\n    property alias verticalScrollBar: vert\n    Item { id: horiz }\n    Item { id: vert }\n}\n',
        'StyledListView.qml': 'import QtQuick\nListView {}\n',
    },
    'qs/components/misc': {
        'qmldir': 'module qs.components.misc\nCustomShortcut 1.0 CustomShortcut.qml\n',
        'CustomShortcut.qml': 'import QtQuick\nItem {\n    property string name\n    property string description\n    signal pressed()\n    signal released()\n}\n'
    },
    'qs/utils': {
        'qmldir': 'module qs.utils\nsingleton NetworkConnection 1.0 NetworkConnection.qml\nsingleton Icons 1.0 Icons.qml\n',
        'NetworkConnection.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    signal handleConnect(var network, var session, var callback)\n}\n',
        'Icons.qml': 'pragma Singleton\nimport QtQuick\nQtObject {\n    function getNetworkIcon(strength) { return "wifi" }\n    function getBluetoothIcon(icon) { return "bluetooth" }\n    function getBatteryIcon(battery) { return "battery_std" }\n    function getNotifIcon(summary, urgency) { return "notifications" }\n    function getVolumeIcon(vol, muted) { return "volume_up" }\n    function getMicVolumeIcon(vol, muted) { return "mic" }\n    function getSpecialWsIcon(name) { return "desktop_windows" }\n    function getAppCategoryIcon(className, fallback) { return fallback || "star" }\n    function getAppIcon(className, fallback) { return fallback || "image" }\n    function getTrayIcon(id, icon) { return "image" }\n    function getWeatherIcon(code) { return "cloudy" }\n}\n'
    },
    'qs/modules/dashboard/dash': {
        'qmldir': 'module qs.modules.dashboard.dash\nCalendar 1.0 Calendar.qml\n',
        'Calendar.qml': 'import QtQuick\nItem {\n    required property var dashState\n}\n'
    },
    'Quickshell/Wayland': {
        'qmldir': 'module Quickshell.Wayland\nsingleton ExclusionMode 1.0 ExclusionMode.qml\nsingleton WlrLayer 1.0 WlrLayer.qml\nsingleton WlrKeyboardFocus 1.0 WlrKeyboardFocus.qml\n',
        'ExclusionMode.qml': 'import QtQuick\npragma Singleton\nQtObject {\n    enum Type {\n        Ignore = 0\n    }\n}\n',
        'WlrLayer.qml': 'import QtQuick\npragma Singleton\nQtObject {\n    enum Type {\n        Overlay = 0\n    }\n}\n',
        'WlrKeyboardFocus.qml': 'import QtQuick\npragma Singleton\nQtObject {\n    enum Type {\n        Exclusive = 0\n    }\n}\n',
    }
}

for mod, files in mocks.items():
    d = base_import_path / mod
    d.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (d / fname).write_text(content)

# Copy the real Audio.qml and ScreenTemp.qml to qs/services/
shutil.copy("/home/execorn/ricing/shell/services/Audio.qml", base_import_path / "qs/services/Audio.qml")
shutil.copy("/home/execorn/ricing/shell/services/ScreenTemp.qml", base_import_path / "qs/services/ScreenTemp.qml")

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


class MockLazyListViewAttached(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self._preferredHeight = 0.0
        self._visibleHeight = 0.0
        self._trackViewport = False
        self._ready = True
        self._adding = False
        self._removing = False

    @Property(float)
    def preferredHeight(self): return self._preferredHeight
    @preferredHeight.setter
    def preferredHeight(self, val): self._preferredHeight = val

    @Property(float)
    def visibleHeight(self): return self._visibleHeight
    @visibleHeight.setter
    def visibleHeight(self, val): self._visibleHeight = val

    @Property(bool)
    def trackViewport(self): return self._trackViewport
    @trackViewport.setter
    def trackViewport(self, val): self._trackViewport = val

    @Property(bool)
    def ready(self): return self._ready
    @ready.setter
    def ready(self, val): self._ready = val

    @Property(bool)
    def adding(self): return self._adding
    @adding.setter
    def adding(self, val): self._adding = val

    @Property(bool)
    def removing(self): return self._removing
    @removing.setter
    def removing(self, val): self._removing = val

@QmlAttached(MockLazyListViewAttached)
class MockLazyListView(QQuickItem):
    delegateChanged = Signal()
    modelChanged = Signal()
    viewportChanged = Signal()
    useCustomViewportChanged = Signal(bool)
    asynchronousChanged = Signal(bool)
    readyDelayChanged = Signal(int)
    cacheBufferChanged = Signal(int)
    removeDurationChanged = Signal(int)
    spacingChanged = Signal(float)
    viewportAdjustNeeded = Signal('QVariant')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._delegate = None
        self._model = None
        self._viewport = None
        self._useCustomViewport = False
        self._asynchronous = False
        self._readyDelay = 0
        self._cacheBuffer = 0
        self._removeDuration = 0
        self._spacing = 0.0

    @Property(QObject, notify=delegateChanged)
    def delegate(self): return self._delegate
    @delegate.setter
    def delegate(self, val):
        self._delegate = val
        self.delegateChanged.emit()

    @Property('QVariant', notify=modelChanged)
    def model(self): return self._model
    @model.setter
    def model(self, val):
        self._model = val
        self.modelChanged.emit()

    @Property('QVariant', notify=viewportChanged)
    def viewport(self): return self._viewport
    @viewport.setter
    def viewport(self, val):
        self._viewport = val
        self.viewportChanged.emit()

    @Property(bool, notify=useCustomViewportChanged)
    def useCustomViewport(self): return self._useCustomViewport
    @useCustomViewport.setter
    def useCustomViewport(self, val):
        self._useCustomViewport = val
        self.useCustomViewportChanged.emit(val)

    @Property(bool, notify=asynchronousChanged)
    def asynchronous(self): return self._asynchronous
    @asynchronous.setter
    def asynchronous(self, val):
        self._asynchronous = val
        self.asynchronousChanged.emit(val)

    @Property(int, notify=readyDelayChanged)
    def readyDelay(self): return self._readyDelay
    @readyDelay.setter
    def readyDelay(self, val):
        self._readyDelay = val
        self.readyDelayChanged.emit(val)

    @Property(int, notify=cacheBufferChanged)
    def cacheBuffer(self): return self._cacheBuffer
    @cacheBuffer.setter
    def cacheBuffer(self, val):
        self._cacheBuffer = val
        self.cacheBufferChanged.emit(val)

    @Property(int, notify=removeDurationChanged)
    def removeDuration(self): return self._removeDuration
    @removeDuration.setter
    def removeDuration(self, val):
        self._removeDuration = val
        self.removeDurationChanged.emit(val)

    @Property(float, notify=spacingChanged)
    def spacing(self): return self._spacing
    @spacing.setter
    def spacing(self, val):
        self._spacing = val
        self.spacingChanged.emit(val)

    @staticmethod
    def qmlAttachedProperties(cls, target):
        return MockLazyListViewAttached(target)

class MockButtonRow(QQuickItem):
    spacingChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spacing = 0.0

    @Property(float, notify=spacingChanged)
    def spacing(self): return self._spacing
    @spacing.setter
    def spacing(self, val):
        self._spacing = val
        self.spacingChanged.emit(val)

class MockBluetoothAdapter(QObject):
    enabledChanged = Signal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
    def get_enabled(self): return self._enabled
    def set_enabled(self, val):
        self._enabled = val
        self.enabledChanged.emit(val)
    enabled = Property(bool, get_enabled, set_enabled, notify=enabledChanged)

class MockBluetoothDevices(QObject):
    valuesChanged = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = []
    values = Property('QVariantList', lambda self: self._values, notify=valuesChanged)

class MockBluetooth(QObject):
    defaultAdapterChanged = Signal()
    devicesChanged = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._adapter = MockBluetoothAdapter(self)
        self._devices = MockBluetoothDevices(self)
    defaultAdapter = Property(QObject, lambda self: self._adapter, notify=defaultAdapterChanged)
    devices = Property(QObject, lambda self: self._devices, notify=devicesChanged)

class MockUrgency(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
    Low = Property(int, lambda self: 0, constant=True)
    Normal = Property(int, lambda self: 1, constant=True)
    Critical = Property(int, lambda self: 2, constant=True)

mock_urgency = MockUrgency()

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
import enum
from PySide6.QtCore import QEnum

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
        self._nameFilters = []
        self._sortReverse = False

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

    @Property('QStringList')
    def nameFilters(self): return self._nameFilters
    @nameFilters.setter
    def nameFilters(self, val): self._nameFilters = val

    @Property(bool)
    def sortReverse(self): return self._sortReverse
    @sortReverse.setter
    def sortReverse(self, val): self._sortReverse = val

    @Property('QVariantList', notify=entriesChanged)
    def entries(self): return self._entries
    def set_entries(self, val):
        self._entries = val
        self.entriesChanged.emit()

class MockFileSystemEntry(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = ""
        self._relativePath = ""
        self._name = ""
        self._baseName = ""
        self._parentDir = ""
        self._suffix = ""
        self._size = 0
        self._isDir = False
        self._isImage = False
        self._mimeType = ""

    @Property(str)
    def path(self): return self._path
    @Property(str)
    def relativePath(self): return self._relativePath
    @Property(str)
    def name(self): return self._name
    @Property(str)
    def baseName(self): return self._baseName
    @Property(str)
    def parentDir(self): return self._parentDir
    @Property(str)
    def suffix(self): return self._suffix
    @Property(int)
    def size(self): return self._size
    @Property(bool)
    def isDir(self): return self._isDir
    @Property(bool)
    def isImage(self): return self._isImage
    @Property(str)
    def mimeType(self): return self._mimeType

# Mock ElapsedTimer
class MockElapsedTimer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot(result=float)
    def elapsed(self): return 1000.0
    @Slot()
    def restart(self): print("MockElapsedTimer restarted")

# Mock HyprKeyboard
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

# Mock HyprDevices
class MockHyprDevices(QObject):
    keyboardsChanged = Signal()
    def __init__(self):
        super().__init__()
        self._keyboards = [MockHyprKeyboard()]
    @Property('QVariantList', notify=keyboardsChanged)
    def keyboards(self): return self._keyboards

# Mock HyprExtras
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
    def batchMessage(self, messages): print(f"MockHyprExtras.batchMessage: {messages}")
    @Slot()
    def refreshDevices(self): print("MockHyprExtras.refreshDevices called")


class MockProcess(QObject):
    runningChanged = Signal(bool)
    commandChanged = Signal()
    stdoutChanged = Signal(QObject)
    stderrChanged = Signal(QObject)
    stdinChanged = Signal(QObject)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._command = []
        self._stdout = None
        self._stderr = None
        self._stdin = None

    def get_running(self):
        return self._running

    def set_running(self, val):
        print(f"DEBUG MockProcess set_running: val={val}, current_running={self._running}, command={self._command}")
        if self._running != val:
            self._running = val
            self.runningChanged.emit(val)
            if val:
                import subprocess
                try:
                    self._proc = subprocess.Popen([str(x) for x in self._command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        self._proc.communicate(timeout=1.0)
                    except Exception:
                        pass
                except Exception as e:
                    print("MockProcess error running command:", self._command, e)
            else:
                if hasattr(self, '_proc') and self._proc:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
                    self._proc = None

    def get_command(self):
        return self._command

    def set_command(self, val):
        self._command = val
        self.commandChanged.emit()

    running = Property(bool, get_running, set_running, notify=runningChanged)
    command = Property('QVariantList', get_command, set_command, notify=commandChanged)
    stdout = Property(QObject, lambda self: self._stdout, lambda self, val: setattr(self, '_stdout', val), notify=stdoutChanged)
    stderr = Property(QObject, lambda self: self._stderr, lambda self, val: setattr(self, '_stderr', val), notify=stderrChanged)
    stdin = Property(QObject, lambda self: self._stdin, lambda self, val: setattr(self, '_stdin', val), notify=stdinChanged)


class MockToast(QObject):
    closedChanged = Signal()
    def __init__(self, t, m, i):
        super().__init__()
        self._title = t
        self._message = m
        self._icon = i
        self._closed = False
    
    title = Property(str, lambda self: self._title, constant=True)
    message = Property(str, lambda self: self._message, constant=True)
    icon = Property(str, lambda self: self._icon, constant=True)
    closed = Property(bool, lambda self: self._closed, notify=closedChanged)
    
    @Slot()
    def close(self):
        self._closed = True
        self.closedChanged.emit()

    def __getitem__(self, idx):
        if idx == 0:
            return self._title
        elif idx == 1:
            return self._message
        elif idx == 2:
            return self._icon
        raise IndexError

class MockToaster(QObject):
    toastsChanged = Signal()
    
    @Slot(str, str, str)
    def toast(self, title, message, icon):
        self._toasts.append(MockToast(title, message, icon))
        self.toastsChanged.emit()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._toasts = []

    toasts = Property('QVariantList', lambda self: self._toasts, notify=toastsChanged)


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
        self._small = MockFontBuilder()

    builders = Property(QObject, lambda self: self, constant=True)
    medium = Property(QObject, lambda self: self._medium, constant=True)
    small = Property(QObject, lambda self: self._small, constant=True)

class MockFontHeadline(QObject):
    def __init__(self):
        super().__init__()
        self._medium = MockFontBuilder()
        self._small = MockFontBuilder()

    builders = Property(QObject, lambda self: self, constant=True)
    medium = Property(QObject, lambda self: self._medium, constant=True)
    small = Property(QObject, lambda self: self._small, constant=True)

class MockFontTitle(QObject):
    def __init__(self):
        super().__init__()
        self._medium = MockFontBuilder()
        self._small = MockFontBuilder()

    builders = Property(QObject, lambda self: self, constant=True)
    medium = Property(QObject, lambda self: self._medium, constant=True)
    small = Property(QObject, lambda self: self._small, constant=True)

class MockFontLabel(QObject):
    def __init__(self):
        super().__init__()
        self._large = MockFontBuilder()
        self._medium = MockFontBuilder()
        self._small = MockFontBuilder()

    builders = Property(QObject, lambda self: self, constant=True)
    large = Property(QObject, lambda self: self._large, constant=True)
    medium = Property(QObject, lambda self: self._medium, constant=True)
    small = Property(QObject, lambda self: self._small, constant=True)

class MockFontTokens(QObject):
    def __init__(self):
        super().__init__()
        self._body = MockFontBody()
        self._title = MockFontTitle()
        self._headline = MockFontHeadline()
        self._label = MockFontLabel()

    body = Property(QObject, lambda self: self._body, constant=True)
    title = Property(QObject, lambda self: self._title, constant=True)
    headline = Property(QObject, lambda self: self._headline, constant=True)
    label = Property(QObject, lambda self: self._label, constant=True)

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

class MockTPalette(QObject):
    m3surfaceContainerLow = Property(str, lambda self: "#000000", constant=True)
    m3surfaceContainer = Property(str, lambda self: "#000000", constant=True)
    m3outline = Property(str, lambda self: "#000000", constant=True)
    m3outlineVariant = Property(str, lambda self: "#000000", constant=True)

class MockColours(QObject):
    def __init__(self):
        super().__init__()
        self._palette = MockPalette()
        self._tPalette = MockTPalette()

    palette = Property(QObject, lambda self: self._palette, constant=True)
    tPalette = Property(QObject, lambda self: self._tPalette, constant=True)


class MockPopoutState(QObject):
    detachRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)


class MockNotifData(QObject):
    closedChanged = Signal(bool)
    popupChanged = Signal(bool)
    actionsChanged = Signal(list)
    bodyChanged = Signal(str)
    residentChanged = Signal(bool)
    hasActionIconsChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._closed = False
        self._popup = False
        self._actions = []
        self._body = ""
        self._resident = False
        self._hasActionIcons = False

    @Property(bool, notify=closedChanged)
    def closed(self): return self._closed
    @closed.setter
    def closed(self, val):
        if self._closed != val:
            self._closed = val
            self.closedChanged.emit(val)

    @Property(bool, notify=popupChanged)
    def popup(self): return self._popup
    @popup.setter
    def popup(self, val):
        if self._popup != val:
            self._popup = val
            self.popupChanged.emit(val)

    @Property('QVariantList', notify=actionsChanged)
    def actions(self): return self._actions
    @actions.setter
    def actions(self, val):
        if self._actions != val:
            self._actions = val
            self.actionsChanged.emit(val)

    @Property(str, notify=bodyChanged)
    def body(self): return self._body
    @body.setter
    def body(self, val):
        if self._body != val:
            self._body = val
            self.bodyChanged.emit(val)

    @Property(bool, notify=residentChanged)
    def resident(self): return self._resident
    @resident.setter
    def resident(self, val):
        if self._resident != val:
            self._resident = val
            self.residentChanged.emit(val)

    @Property(bool, notify=hasActionIconsChanged)
    def hasActionIcons(self): return self._hasActionIcons
    @hasActionIcons.setter
    def hasActionIcons(self, val):
        if self._hasActionIcons != val:
            self._hasActionIcons = val
            self.hasActionIconsChanged.emit(val)

    @Slot()
    def close(self):
        self.closed = True

    @Slot(QObject)
    def unlock(self, obj):
        pass


class MockPopoutState(QObject):
    detachRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)


# Register types to QML before QGuiApplication starts
from PySide6.QtQml import QmlAttached

class WlrLayershellAttached(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self._exclusionMode = 0
        self._layer = 0
        self._keyboardFocus = 0
        self._namespace = ""

    @Property(int)
    def exclusionMode(self): return self._exclusionMode
    @exclusionMode.setter
    def exclusionMode(self, val): self._exclusionMode = val

    @Property(int)
    def layer(self): return self._layer
    @layer.setter
    def layer(self, val): self._layer = val

    @Property(int)
    def keyboardFocus(self): return self._keyboardFocus
    @keyboardFocus.setter
    def keyboardFocus(self, val): self._keyboardFocus = val

    @Property(str)
    def namespace(self): return self._namespace
    @namespace.setter
    def namespace(self, val): self._namespace = val

@QmlAttached(WlrLayershellAttached)
class WlrLayershell(QObject):
    @staticmethod
    def qmlAttachedProperties(cls, target):
        return WlrLayershellAttached(target)

qmlRegisterType(WlrLayershell, "Quickshell.Wayland", 1, 0, "WlrLayershell")

qmlRegisterType(MockProcess, "Quickshell.Io", 1, 0, "Process")
qmlRegisterType(MockPwNode, "Quickshell.Services.Pipewire", 1, 0, "PwNode")
qmlRegisterType(MockPopoutState, "Caelestia.Config", 1, 0, "PopoutState")
qmlRegisterType(MockLazyListView, "Caelestia.Components", 1, 0, "LazyListView")
qmlRegisterType(MockButtonRow, "Caelestia.Components", 1, 0, "ButtonRow")

qmlRegisterType(MockFileView, "Quickshell.Io", 1, 0, "FileView")
qmlRegisterType(MockStdioCollector, "Quickshell.Io", 1, 0, "StdioCollector")
qmlRegisterType(MockImageAnalyser, "Caelestia", 1, 0, "ImageAnalyser")
qmlRegisterType(MockElapsedTimer, "Caelestia", 1, 0, "ElapsedTimer")
qmlRegisterType(MockFileSystemModel, "Caelestia.Models", 1, 0, "FileSystemModel")
qmlRegisterType(MockFileSystemEntry, "Caelestia.Models", 1, 0, "FileSystemEntry")
qmlRegisterType(MockHyprExtras, "Caelestia.Internal", 1, 0, "HyprExtras")

qmlRegisterType(MockNotifData, "Quickshell", 1, 0, "NotifData")
qmlRegisterType(MockNotifData, "Quickshell.Services.Notifications", 1, 0, "NotifData")
qmlRegisterType(MockNotifData, "Caelestia", 1, 0, "NotifData")
qmlRegisterType(MockNotifData, "qs.services", 1, 0, "NotifData")

mock_bt = MockBluetooth()
qmlRegisterSingletonInstance(MockBluetooth, "Quickshell.Bluetooth", 1, 0, "Bluetooth", mock_bt)
qmlRegisterSingletonInstance(MockUrgency, "Quickshell.Services.Notifications", 1, 0, "NotificationUrgency", mock_urgency)

@pytest.fixture(scope="session")
def qapp():
    import shutil
    shutil.rmtree(base_import_path, ignore_errors=True)
    
    # Write all mocks
    for mod, files in mocks.items():
        d = base_import_path / mod
        d.mkdir(parents=True, exist_ok=True)
        for fname, content in files.items():
            (d / fname).write_text(content)
            
    # Delete polluted service files
    services_dir = base_import_path / "qs/services"
    polluted_files = ["Colours.qml", "Wallpapers.qml", "Visibilities.qml"]
    for f in polluted_files:
        (services_dir / f).unlink(missing_ok=True)

    # Copy Audio.qml and ScreenTemp.qml to isolated services path
    shutil.copy("/home/execorn/ricing/shell/services/Audio.qml", base_import_path / "qs/services/Audio.qml")
    shutil.copy("/home/execorn/ricing/shell/services/ScreenTemp.qml", base_import_path / "qs/services/ScreenTemp.qml")
    shutil.copy("/home/execorn/ricing/shell/services/Notifs.qml", base_import_path / "qs/services/Notifs.qml")

    # Copy ScreenTemp to global qml-imports (for compatibility)
    global_services = pathlib.Path("/tmp/qml-imports/qs/services")
    global_services.mkdir(parents=True, exist_ok=True)
    shutil.copy("/home/execorn/ricing/shell/services/ScreenTemp.qml", str(global_services / "ScreenTemp.qml"))

    # Instantiate the application instance once per test session
    app = QGuiApplication.instance()
    if not app:
        app = QGuiApplication([])
    yield app
    
    # Teardown unique base_import_path
    shutil.rmtree(base_import_path, ignore_errors=True)


@pytest.fixture
def mock_pipewire():
    return MockPipewire()


@pytest.fixture
def mock_toaster():
    return MockToaster()


@pytest.fixture
def qml_engine(qapp, mock_pipewire, mock_toaster):
    try:
        import sys
        # Clear global_quickshell_instances to handle engine id reuse
        if "test_ricing" in sys.modules:
            import test_ricing
            test_ricing.global_quickshell_instances.clear()
    except Exception:
        pass

    print("DEBUG: base_import_path =", base_import_path)
    print("DEBUG: base_import_path exists =", base_import_path.exists())
    print("DEBUG: GlobalConfig.qml exists =", (base_import_path / "Caelestia/GlobalConfig.qml").exists())
    if base_import_path.exists():
        print("DEBUG: contents =", os.listdir(str(base_import_path)))
        print("DEBUG: ALL FILES IN base_import_path:")
        for p in base_import_path.glob("**/*"):
            print("  -", p)
    engine = QQmlEngine()
    engine.clearComponentCache()
    engine.addImportPath(str(base_import_path))
    
    # Expose context properties
    engine.rootContext().setContextProperty("Pipewire", mock_pipewire)
    engine.rootContext().setContextProperty("Toaster", mock_toaster)
    
    # Load and register QML mocks as context properties
    from PySide6.QtQml import QQmlComponent
    comp_config = QQmlComponent(engine, str(base_import_path / "Caelestia/GlobalConfig.qml"))
    global_config = comp_config.create()
    if not global_config:
        raise RuntimeError(f"Failed to create GlobalConfig mock: {comp_config.errors()}")
    engine.rootContext().setContextProperty("GlobalConfig", global_config)
    
    comp_tokens = QQmlComponent(engine, str(base_import_path / "Caelestia/Tokens.qml"))
    tokens = comp_tokens.create()
    if not tokens:
        raise RuntimeError(f"Failed to create Tokens mock: {comp_tokens.errors()}")
    engine.rootContext().setContextProperty("Tokens", tokens)
    
    comp_colours = QQmlComponent(engine, str(base_import_path / "Caelestia/Colours.qml"))
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
