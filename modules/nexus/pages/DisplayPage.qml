import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Caelestia
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus.common

PageBase {
    id: root

    title: qsTr("Display")

    property var monitorsConfig: []
    property var activeMonitors: []
    property var selectedMonitor: null

    property string selectedResolution: ""
    property real selectedRefreshRate: 60.0
    property int selectedRotation: 0
    property real selectedScale: 1.0

    property int countdown: 15
    property var previousConfig: []
    property bool loadingState: false

    readonly property list<MenuItem> rotationItems: [
        MenuItem {
            text: qsTr("Normal")
        },
        MenuItem {
            text: "90°"
        },
        MenuItem {
            text: "180°"
        },
        MenuItem {
            text: "270°"
        }
    ]

    readonly property var availableResolutions: {
        if (!selectedMonitor) return [];
        var modes = selectedMonitor.availableModes;
        if (!modes || modes.length === 0) {
            return ["1920x1080", "1600x900", "1280x720", "2560x1440", "3840x2160"];
        }
        var resSet = {};
        for (var i = 0; i < modes.length; i++) {
            var mode = modes[i];
            var parts = mode.split("@");
            if (parts.length > 0) {
                resSet[parts[0]] = true;
            }
        }
        return Object.keys(resSet);
    }

    readonly property var availableRefreshRates: {
        if (!selectedMonitor || !selectedResolution) return [];
        var modes = selectedMonitor.availableModes;
        if (!modes || modes.length === 0) {
            return [60.0, 75.0, 120.0, 144.0];
        }
        var rates = [];
        for (var i = 0; i < modes.length; i++) {
            var mode = modes[i];
            var parts = mode.split("@");
            if (parts.length === 2 && parts[0] === selectedResolution) {
                var hzStr = parts[1].replace("Hz", "");
                var val = parseFloat(hzStr);
                if (!isNaN(val)) {
                    rates.push(val);
                }
            }
        }
        if (rates.length === 0 && selectedMonitor.refreshRate) {
            rates.push(selectedMonitor.refreshRate);
        }
        return rates;
    }

    onSelectedMonitorChanged: {
        if (selectedMonitor) {
            loadingState = true;
            selectedResolution = selectedMonitor.width + "x" + selectedMonitor.height;
            selectedRefreshRate = selectedMonitor.refreshRate;
            selectedRotation = selectedMonitor.transform !== undefined ? selectedMonitor.transform : 0;
            selectedScale = selectedMonitor.scale !== undefined ? Math.max(1.0, Math.min(2.0, selectedMonitor.scale)) : 1.0;
            loadingState = false;
        }
    }

    onActiveMonitorsChanged: {
        if (!selectedMonitor && activeMonitors.length > 0) {
            selectedMonitor = activeMonitors[0];
        }
    }

    function queueApply() {
        if (loadingState) return;
        applyDebounceTimer.restart();
    }

    onSelectedResolutionChanged: queueApply()
    onSelectedRefreshRateChanged: queueApply()
    onSelectedRotationChanged: queueApply()
    onSelectedScaleChanged: queueApply()

    Timer {
        id: applyDebounceTimer
        interval: 300
        repeat: false
        onTriggered: {
            root.applyChanges();
        }
    }

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.countdown--;
            if (root.countdown <= 0) {
                countdownTimer.stop();
                root.revertChanges();
            }
        }
    }

    FileView {
        id: monitorsFile
        path: Paths.config + "/monitors.json"

        onReadyChanged: {
            if (ready) {
                root.loadConfig(text);
            }
        }
        onTextChanged: {
            if (ready) {
                root.loadConfig(text);
            }
        }
    }

    Process {
        id: getMonitorsProcess
        running: true
        command: ["hyprctl", "monitors", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var parsed = JSON.parse(text);
                    root.activeMonitors = parsed;
                    if (!monitorsFile.exists || monitorsFile.text.trim() === "") {
                        root.recoverCorrupted(parsed);
                    } else {
                        try {
                            var saved = JSON.parse(monitorsFile.text);
                            if (!Array.isArray(saved)) {
                                root.recoverCorrupted(parsed);
                            } else {
                                root.monitorsConfig = saved;
                            }
                        } catch (e) {
                            root.recoverCorrupted(parsed);
                        }
                    }
                } catch (e) {
                    console.log("Failed to parse hyprctl output:", e);
                }
            }
        }
    }

    function loadConfig(text) {
        if (!text || text.trim() === "") {
            if (activeMonitors.length > 0) {
                recoverCorrupted(activeMonitors);
            } else {
                root.refreshActiveMonitors();
            }
            return;
        }
        try {
            var parsed = JSON.parse(text);
            if (!Array.isArray(parsed)) {
                if (activeMonitors.length > 0) {
                    recoverCorrupted(activeMonitors);
                } else {
                    root.refreshActiveMonitors();
                }
            } else {
                root.monitorsConfig = parsed;
                if (!root.selectedMonitor && parsed.length > 0) {
                    root.selectedMonitor = parsed[0];
                }
            }
        } catch (e) {
            if (activeMonitors.length > 0) {
                recoverCorrupted(activeMonitors);
            } else {
                root.refreshActiveMonitors();
            }
        }
    }

    function recoverCorrupted(active) {
        console.log("Recovering corrupted or missing monitors.json...");
        var recoveredConfig = [];
        for (var i = 0; i < active.length; i++) {
            var m = active[i];
            recoveredConfig.push({
                id: m.id !== undefined ? m.id : i,
                name: m.name,
                width: m.width !== undefined ? m.width : 1920,
                height: m.height !== undefined ? m.height : 1080,
                refreshRate: m.refreshRate !== undefined ? m.refreshRate : 60.0,
                transform: m.transform !== undefined ? m.transform : 0,
                scale: m.scale !== undefined ? Math.max(1.0, Math.min(2.0, m.scale)) : 1.0
            });
        }
        root.monitorsConfig = recoveredConfig;
        if (recoveredConfig.length > 0 && !root.selectedMonitor) {
            root.selectedMonitor = recoveredConfig[0];
        }
        writeConfig(recoveredConfig, false);
    }

    function refreshActiveMonitors() {
        getMonitorsProcess.running = false;
        getMonitorsProcess.running = true;
    }

    function writeConfig(config, triggerReload) {
        if (triggerReload === undefined) triggerReload = true;
        var jsonStr = JSON.stringify(config, null, 2);
        var cmd = [
            "sh",
            "-c",
            triggerReload ? "echo \"$1\" > \"$2\" && hyprctl reload" : "echo \"$1\" > \"$2\"",
            "sh",
            jsonStr,
            Paths.config + "/monitors.json"
        ];
        Quickshell.execDetached(cmd);
    }

    function applyChanges() {
        if (!selectedMonitor) return;

        var widthAndHeight = selectedResolution.split("x");
        if (widthAndHeight.length !== 2) return;
        var newWidth = parseInt(widthAndHeight[0]);
        var newHeight = parseInt(widthAndHeight[1]);

        var newConfig = [];
        var targetMonitorId = selectedMonitor.id;

        // Make sure we have a valid monitorsConfig
        var currentConfig = monitorsConfig && monitorsConfig.length > 0 ? monitorsConfig : activeMonitors;
        var monitorFound = false;

        for (var i = 0; i < currentConfig.length; i++) {
            var m = currentConfig[i];
            // Match by id or name
            var isTarget = (m.id !== undefined && m.id === targetMonitorId) || (m.name !== undefined && m.name === selectedMonitor.name);
            if (isTarget) {
                monitorFound = true;
                var newScale = Math.max(1.0, Math.min(2.0, selectedScale));
                newConfig.push({
                    id: m.id !== undefined ? m.id : targetMonitorId,
                    name: m.name || selectedMonitor.name,
                    width: newWidth,
                    height: newHeight,
                    refreshRate: selectedRefreshRate,
                    transform: selectedRotation,
                    scale: newScale
                });
            } else {
                newConfig.push({
                    id: m.id !== undefined ? m.id : i,
                    name: m.name,
                    width: m.width,
                    height: m.height,
                    refreshRate: m.refreshRate,
                    transform: m.transform !== undefined ? m.transform : 0,
                    scale: m.scale !== undefined ? Math.max(1.0, Math.min(2.0, m.scale)) : 1.0
                });
            }
        }

        if (!monitorFound) {
            newConfig.push({
                id: targetMonitorId,
                name: selectedMonitor.name,
                width: newWidth,
                height: newHeight,
                refreshRate: selectedRefreshRate,
                transform: selectedRotation,
                scale: Math.max(1.0, Math.min(2.0, selectedScale))
            });
        }

        // Check optimization
        var configIsIdentical = false;
        if (monitorsConfig && monitorsConfig.length === newConfig.length) {
            configIsIdentical = true;
            for (var k = 0; k < newConfig.length; k++) {
                var n = newConfig[k];
                var o = monitorsConfig[k];
                if (n.name !== o.name ||
                    n.width !== o.width ||
                    n.height !== o.height ||
                    n.refreshRate !== o.refreshRate ||
                    n.transform !== o.transform ||
                    n.scale !== o.scale) {
                    configIsIdentical = false;
                    break;
                }
            }
        }

        if (configIsIdentical) {
            console.log("Configuration is identical to current file on disk. Optimization triggered: skipping write and reload.");
            return;
        }

        root.previousConfig = JSON.parse(JSON.stringify(currentConfig));
        root.monitorsConfig = newConfig;

        writeConfig(newConfig, true);

        countdown = 15;
        revertModal.visible = true;
        countdownTimer.restart();
    }

    function revertChanges() {
        console.log("Reverting changes...");
        revertModal.visible = false;
        countdownTimer.stop();

        if (previousConfig && previousConfig.length > 0) {
            root.monitorsConfig = previousConfig;
            if (selectedMonitor) {
                var prev = previousConfig.find(function(m) {
                    return (m.id !== undefined && m.id === selectedMonitor.id) || (m.name === selectedMonitor.name);
                });
                if (prev) {
                    loadingState = true;
                    selectedResolution = prev.width + "x" + prev.height;
                    selectedRefreshRate = prev.refreshRate;
                    selectedRotation = prev.transform !== undefined ? prev.transform : 0;
                    selectedScale = prev.scale !== undefined ? Math.max(1.0, Math.min(2.0, prev.scale)) : 1.0;
                    loadingState = false;
                }
            }
            writeConfig(previousConfig, true);
        }
        root.refreshActiveMonitors();
    }

    function keepChanges() {
        console.log("Keeping changes...");
        revertModal.visible = false;
        countdownTimer.stop();
        root.refreshActiveMonitors();
    }

    Variants {
        id: resolutionItems
        model: root.availableResolutions
        MenuItem {
            required property var modelData
            text: modelData
        }
    }

    Variants {
        id: refreshRateItems
        model: root.availableRefreshRates
        MenuItem {
            required property var modelData
            text: modelData.toFixed(2) + "Hz"
        }
    }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: qsTr("Monitor Layout")
        }

        ConnectedRect {
            Layout.fillWidth: true
            implicitHeight: 240

            Item {
                id: layoutMapContainer
                anchors.fill: parent
                anchors.margins: Tokens.padding.large

                readonly property real minX: {
                    if (!root.activeMonitors || root.activeMonitors.length === 0) return 0;
                    return Math.min(...root.activeMonitors.map(function(m) { return m.x !== undefined ? m.x : 0; }));
                }
                readonly property real minY: {
                    if (!root.activeMonitors || root.activeMonitors.length === 0) return 0;
                    return Math.min(...root.activeMonitors.map(function(m) { return m.y !== undefined ? m.y : 0; }));
                }
                readonly property real maxX: {
                    if (!root.activeMonitors || root.activeMonitors.length === 0) return 1920;
                    return Math.max(...root.activeMonitors.map(function(m) { return (m.x !== undefined ? m.x : 0) + (m.width !== undefined ? m.width : 1920); }));
                }
                readonly property real maxY: {
                    if (!root.activeMonitors || root.activeMonitors.length === 0) return 1080;
                    return Math.max(...root.activeMonitors.map(function(m) { return (m.y !== undefined ? m.y : 0) + (m.height !== undefined ? m.height : 1080); }));
                }
                readonly property real totalWidth: Math.max(1, maxX - minX)
                readonly property real totalHeight: Math.max(1, maxY - minY)
                readonly property real scaleFactor: Math.min(width / totalWidth, height / totalHeight)
                readonly property real offsetX: (width - totalWidth * scaleFactor) / 2
                readonly property real offsetY: (height - totalHeight * scaleFactor) / 2

                Repeater {
                    model: root.activeMonitors

                    delegate: Rectangle {
                        property var monitor: modelData
                        property real mx: monitor.x !== undefined ? monitor.x : 0
                        property real my: monitor.y !== undefined ? monitor.y : 0
                        property real mw: monitor.width !== undefined ? monitor.width : 1920
                        property real mh: monitor.height !== undefined ? monitor.height : 1080

                        x: layoutMapContainer.offsetX + (mx - layoutMapContainer.minX) * layoutMapContainer.scaleFactor
                        y: layoutMapContainer.offsetY + (my - layoutMapContainer.minY) * layoutMapContainer.scaleFactor
                        width: mw * layoutMapContainer.scaleFactor
                        height: mh * layoutMapContainer.scaleFactor

                        color: root.selectedMonitor && root.selectedMonitor.name === monitor.name
                               ? Colours.palette.m3primaryContainer
                               : Colours.palette.m3surfaceContainerHigh

                        border.color: (root.selectedMonitor && root.selectedMonitor.name === monitor.name) || monitor.focused
                                      ? Colours.palette.m3primary
                                      : Colours.palette.m3outline
                        border.width: 2
                        radius: Tokens.rounding.small

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                root.selectedMonitor = monitor;
                            }
                        }

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2

                            StyledText {
                                text: monitor.name
                                font: Tokens.font.title.small
                                color: root.selectedMonitor && root.selectedMonitor.name === monitor.name
                                       ? Colours.palette.m3onPrimaryContainer
                                       : Colours.palette.m3onSurface
                                Layout.alignment: Qt.AlignHCenter
                            }

                            StyledText {
                                text: mw + "x" + mh
                                font: Tokens.font.body.small
                                color: root.selectedMonitor && root.selectedMonitor.name === monitor.name
                                       ? Colours.palette.m3onPrimaryContainer
                                       : Colours.palette.m3outline
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }
        }

        SectionHeader {
            text: qsTr("Monitor Settings")
        }

        SelectRow {
            Layout.fillWidth: true
            first: true
            label: qsTr("Resolution")
            menuItems: resolutionItems.instances
            active: menuItems.find(function(i) { return i.text === root.selectedResolution; }) ?? null
            fallbackText: root.selectedResolution || qsTr("Auto")
            onSelected: item => {
                root.selectedResolution = item.text;
            }
        }

        SelectRow {
            Layout.fillWidth: true
            label: qsTr("Refresh rate")
            menuItems: refreshRateItems.instances
            active: menuItems.find(function(i) { return parseFloat(i.text) === root.selectedRefreshRate; }) ?? null
            fallbackText: root.selectedRefreshRate.toFixed(2) + "Hz"
            onSelected: item => {
                root.selectedRefreshRate = parseFloat(item.text);
            }
        }

        SelectRow {
            Layout.fillWidth: true
            label: qsTr("Rotation")
            menuItems: root.rotationItems
            active: root.rotationItems[root.selectedRotation] ?? root.rotationItems[0]
            onSelected: item => {
                root.selectedRotation = root.rotationItems.indexOf(item);
            }
        }

        SliderRow {
            Layout.fillWidth: true
            last: true
            label: qsTr("System scaling")
            value: root.selectedScale - 1.0
            valueLabel: (root.selectedScale).toFixed(2) + "x"
            onMoved: v => {
                root.selectedScale = Math.max(1.0, Math.min(2.0, 1.0 + v));
            }
        }
    }

    Item {
        id: revertModal
        visible: false

        Component.onCompleted: {
            parent = root;
        }

        anchors.fill: parent
        z: 9999

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            onWheel: e => e.accepted = true
            onClicked: {}
            onPressed: {}
            onReleased: {}
        }

        Rectangle {
            anchors.fill: parent
            color: Colours.palette.m3scrim
            opacity: 0.6
        }

        Elevation {
            anchors.centerIn: parent
            width: Math.min(400, parent.width - 40)
            height: 200
            radius: Tokens.rounding.large
            level: 3

            StyledRect {
                anchors.fill: parent
                radius: parent.radius
                color: Colours.palette.m3surfaceContainerHighest

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.largeIncreased
                    spacing: Tokens.spacing.medium

                    StyledText {
                        text: qsTr("Confirm Display Changes")
                        font: Tokens.font.title.large
                        color: Colours.palette.m3onSurface
                        Layout.alignment: Qt.AlignHCenter
                    }

                    StyledText {
                        text: qsTr("Reverting display settings in %1 seconds...").arg(root.countdown)
                        font: Tokens.font.body.medium
                        color: Colours.palette.m3onSurfaceVariant
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }

                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: Tokens.spacing.medium

                        TextButton {
                            text: qsTr("Revert")
                            onClicked: {
                                root.revertChanges();
                            }
                        }

                        TextButton {
                            text: qsTr("Keep Changes")
                            onClicked: {
                                root.keepChanges();
                            }
                        }
                    }
                }
            }
        }
    }
}
