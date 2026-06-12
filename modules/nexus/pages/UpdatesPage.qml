pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: qsTr("Updates")

    ColumnLayout {
        id: mainLayout
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        // State Variables
        property var updatesList: []
        property var rawPacmanUpdates: []
        property var rawYayUpdates: []
        property var upgradeLogs: []
        property string upgradeStatus: "stopped" // stopped, running, failed, timeout, completed
        property bool checking: false
        property bool statusCheckPending: false

        property bool pacmanDone: false
        property bool yayDone: false

        function checkForUpdates() {
            if (checking) return;
            checking = true;
            pacmanDone = false;
            yayDone = false;
            rawPacmanUpdates = [];
            rawYayUpdates = [];
            updatesList = [];

            pacmanProcess.running = false;
            pacmanProcess.running = true;

            yayProcess.running = false;
            yayProcess.running = true;
        }

        function checkQueryDone() {
            if (pacmanDone && yayDone) {
                let merged = [...rawPacmanUpdates];
                for (let i = 0; i < rawYayUpdates.length; i++) {
                    let item = rawYayUpdates[i];
                    if (!merged.some(u => u.name === item.name)) {
                        merged.push(item);
                    }
                }
                updatesList = merged;
                checking = false;
            }
        }

        function startUpgrade() {
            upgradeLogs = [];
            upgradeStatus = "running";
            upgradeTriggerProcess.running = false;
            upgradeTriggerProcess.running = true;
            logStreamProcess.running = false;
            logStreamProcess.running = true;
        }

        function onUpgradeCompleted() {
            logStreamProcess.running = false;
            checkForUpdates();
        }

        function parseUpdates(stdoutText, source) {
            const lines = stdoutText.trim().split("\n");
            const list = [];
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;
                const parts = trimmed.split(/\s+/);
                if (parts.length >= 4 && parts[2] === "->") {
                    const name = parts[0];
                    list.push({
                        name: name,
                        source: source,
                        old_version: parts[1],
                        new_version: parts[3],
                        description: source === "pacman" ? `System package ${name}` : `AUR package ${name}`,
                        size: "Unknown"
                    });
                }
            }
            return list;
        }

        // Process Definitions
        Process {
            id: pacmanProcess
            command: ["checkupdates"]
            // qmllint disable incompatible-type
            environment: ({
                    // qmllint enable incompatible-type
                    LANG: "C.UTF-8",
                    LC_ALL: "C.UTF-8"
                })
            stdout: StdioCollector {
                onStreamFinished: {
                    mainLayout.rawPacmanUpdates = mainLayout.parseUpdates(text, "pacman");
                }
            }
            onExited: exitCode => { // qmllint disable signal-handler-parameters
                mainLayout.pacmanDone = true;
                mainLayout.checkQueryDone();
            }
        }

        Process {
            id: yayProcess
            command: ["yay", "-Qua"]
            // qmllint disable incompatible-type
            environment: ({
                    // qmllint enable incompatible-type
                    LANG: "C.UTF-8",
                    LC_ALL: "C.UTF-8"
                })
            stdout: StdioCollector {
                onStreamFinished: {
                    mainLayout.rawYayUpdates = mainLayout.parseUpdates(text, "yay");
                }
            }
            onExited: exitCode => { // qmllint disable signal-handler-parameters
                mainLayout.yayDone = true;
                mainLayout.checkQueryDone();
            }
        }

        Process {
            id: upgradeTriggerProcess
            command: ["systemctl", "--user", "start", "caelestia-upgrade.service"]
            // qmllint disable incompatible-type
            environment: ({
                    // qmllint enable incompatible-type
                    LANG: "C.UTF-8",
                    LC_ALL: "C.UTF-8"
                })
            onExited: exitCode => { // qmllint disable signal-handler-parameters
                if (exitCode !== 0) {
                    mainLayout.upgradeStatus = "failed";
                    logStreamProcess.running = false;
                }
            }
        }

        Timer {
            id: statusPollTimer
            interval: 1000
            repeat: true
            running: mainLayout.upgradeStatus === "running" && !mainLayout.statusCheckPending
            onTriggered: {
                mainLayout.statusCheckPending = true;
                statusCheckProcess.running = false;
                statusCheckProcess.running = true;
                statusCheckWatchdog.start();
            }
        }

        Timer {
            id: statusCheckWatchdog
            interval: 2000
            repeat: false
            onTriggered: {
                if (mainLayout.statusCheckPending) {
                    statusCheckProcess.running = false;
                    mainLayout.statusCheckPending = false;
                    mainLayout.upgradeStatus = "timeout";
                    logStreamProcess.running = false;
                }
            }
        }

        Process {
            id: statusCheckProcess
            command: ["systemctl", "--user", "is-active", "caelestia-upgrade.service"]
            // qmllint disable incompatible-type
            environment: ({
                    // qmllint enable incompatible-type
                    LANG: "C.UTF-8",
                    LC_ALL: "C.UTF-8"
                })
            stdout: StdioCollector {
                onStreamFinished: {
                    if (!mainLayout.statusCheckPending) return;
                    statusCheckWatchdog.stop();
                    mainLayout.statusCheckPending = false;

                    const status = text.trim();
                    const recognized = ["active", "inactive", "failed", "activating", "deactivating", "reloading", "maintenance"];
                    if (!status || recognized.indexOf(status) === -1) {
                        if (mainLayout.upgradeStatus === "running") {
                            mainLayout.upgradeStatus = "failed";
                            mainLayout.onUpgradeCompleted();
                        }
                    } else if (status === "active") {
                        mainLayout.upgradeStatus = "running";
                        if (!logStreamProcess.running) {
                            logStreamProcess.running = true;
                        }
                    } else if (status === "failed") {
                        if (mainLayout.upgradeStatus === "running") {
                            mainLayout.upgradeStatus = "failed";
                            mainLayout.onUpgradeCompleted();
                        }
                    } else if (status === "inactive") {
                        if (mainLayout.upgradeStatus === "running") {
                            mainLayout.upgradeStatus = "stopped";
                            mainLayout.onUpgradeCompleted();
                        }
                    }
                }
            }
        }

        Process {
            id: logStreamProcess
            command: ["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f", "-n", "0"]
            // qmllint disable incompatible-type
            environment: ({
                    // qmllint enable incompatible-type
                    LANG: "C.UTF-8",
                    LC_ALL: "C.UTF-8"
                })
            stdout: SplitParser {
                onRead: line => {
                    const cleanedLine = line.trim();
                    if (!cleanedLine) return;

                    const logs = [...mainLayout.upgradeLogs];
                    logs.push(cleanedLine);

                    if (cleanedLine.indexOf("Could not resolve host") !== -1 || 
                        cleanedLine.indexOf("Network is unreachable") !== -1 || 
                        cleanedLine.toLowerCase().indexOf("failed") !== -1) {
                        
                        logs.push("Error: Upgrade failed due to network disconnect.");
                        mainLayout.upgradeLogs = logs;
                        mainLayout.upgradeStatus = "failed";
                        logStreamProcess.running = false;
                        return;
                    }

                    mainLayout.upgradeLogs = logs;
                }
            }
        }

        Component.onCompleted: {
            mainLayout.checkForUpdates();
            // Check if upgrade is already active
            mainLayout.statusCheckPending = true;
            statusCheckProcess.running = false;
            statusCheckProcess.running = true;
            statusCheckWatchdog.start();
        }

        // 1. Control Panel
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall / 2

                StyledText {
                    Layout.fillWidth: true
                    text: {
                        if (mainLayout.checking) {
                            return qsTr("Checking for updates...");
                        }
                        if (mainLayout.upgradeStatus === "running") {
                            return qsTr("Upgrading system...");
                        }
                        if (mainLayout.upgradeStatus === "timeout") {
                            return qsTr("Upgrade check timed out");
                        }
                        if (mainLayout.upgradeStatus === "failed") {
                            return qsTr("Upgrade failed");
                        }
                        if (mainLayout.updatesList.length > 0) {
                            return qsTr("%1 update(s) available").arg(mainLayout.updatesList.length);
                        }
                        return qsTr("Your system is up to date");
                    }
                    font: Tokens.font.title.medium
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    visible: mainLayout.updatesList.length > 0 && mainLayout.upgradeStatus !== "running"
                    text: qsTr("We recommend installing updates regularly to keep your system secure.")
                    color: Colours.palette.m3outline
                    font: Tokens.font.label.small
                    wrapMode: Text.WordWrap
                }
            }

            TextButton {
                text: qsTr("Check")
                type: ButtonBase.Tonal
                disabled: mainLayout.checking || mainLayout.upgradeStatus === "running"
                onClicked: mainLayout.checkForUpdates()
            }

            TextButton {
                text: qsTr("Upgrade")
                type: ButtonBase.Filled
                disabled: mainLayout.checking || mainLayout.upgradeStatus === "running" || mainLayout.updatesList.length === 0
                onClicked: mainLayout.startUpgrade()
            }
        }

        // 2. Pending Updates List
        ItemList {
            id: updatesItemList
            showList: mainLayout.updatesList.length > 0 && mainLayout.upgradeStatus !== "running"
            placeholderIcon: "update"
            placeholderText: mainLayout.checking ? qsTr("Loading updates list...") : qsTr("No updates available")
            first: true
            last: true

            model: ScriptModel {
                values: mainLayout.updatesList
            }

            delegate: Item {
                id: itemDelegate
                required property var modelData
                required property int index

                anchors.left: updatesItemList.list.contentItem.left
                anchors.right: updatesItemList.list.contentItem.right
                implicitHeight: itemLayout.implicitHeight + Tokens.padding.medium * 2

                StyledRect {
                    anchors.fill: parent
                    radius: Tokens.rounding.extraSmall
                    color: "transparent"

                    RowLayout {
                        id: itemLayout
                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium
                        spacing: Tokens.spacing.medium

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            StyledText {
                                text: itemDelegate.modelData?.name ?? ""
                                font: Tokens.font.body.medium
                            }
                            
                            StyledText {
                                text: itemDelegate.modelData?.description ?? ""
                                font: Tokens.font.label.small
                                color: Colours.palette.m3outline
                            }
                        }

                        ColumnLayout {
                            spacing: 2
                            Layout.alignment: Qt.AlignRight

                            StyledText {
                                text: "%1 -> %2".arg(itemDelegate.modelData?.old_version ?? "").arg(itemDelegate.modelData?.new_version ?? "")
                                font: Tokens.font.body.small
                                color: Colours.palette.m3primary
                            }

                            StyledText {
                                text: "%1 • Size: %2".arg(itemDelegate.modelData?.source === "pacman" ? "Arch Repository" : "AUR").arg(itemDelegate.modelData?.size ?? "")
                                font: Tokens.font.label.small
                                color: Colours.palette.m3outline
                                Layout.alignment: Qt.AlignRight
                            }
                        }
                    }
                }
            }
        }

        // 3. Upgrade Log
        SectionHeader {
            text: qsTr("Upgrade Log")
            visible: mainLayout.upgradeLogs.length > 0 || mainLayout.upgradeStatus === "running"
        }

        ConnectedRect {
            id: logContainer
            Layout.fillWidth: true
            visible: mainLayout.upgradeLogs.length > 0 || mainLayout.upgradeStatus === "running"
            first: true
            last: true
            color: Colours.tPalette.m3surfaceContainer
            implicitHeight: 250

            Flickable {
                id: logFlickable
                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                contentHeight: logText.implicitHeight
                clip: true

                StyledText {
                    id: logText
                    width: logFlickable.width
                    text: mainLayout.upgradeLogs.join("\n")
                    font: Tokens.font.body.small
                    wrapMode: Text.Wrap
                    color: mainLayout.upgradeStatus === "failed" ? Colours.palette.m3error : Colours.palette.m3onSurface

                    onTextChanged: {
                        logFlickable.contentY = Math.max(0, logText.implicitHeight - logFlickable.height);
                    }
                }
            }
        }
    }
}
