pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Bluetooth
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus.common

PageBase {
    id: root

    readonly property BluetoothAdapter adapter: Bluez.adapter // qmllint disable unresolved-type
    property BluetoothDevice pairingDevice: null // qmllint disable unresolved-type
    property bool pairFailed: false
    property bool connectFailed: false
    property bool showUnnamedDevices: false
    property bool _pairableSnapshotValid: false
    property bool _priorPairable: false
    property bool _scanAcquired: false
    property bool _connectPending: false

    function isNamedDevice(dev: BluetoothDevice): bool {
        if (!dev)
            return false;
        const addr = (dev.address ?? "").toUpperCase();
        const dashMac = addr.replace(/:/g, "-");
        const dn = (dev.deviceName ?? "").trim();
        if (dn && dn.toUpperCase() !== addr && dn.toUpperCase() !== dashMac)
            return true;
        const n = (dev.name ?? "").trim();
        if (!n)
            return false;
        const nu = n.toUpperCase();
        return nu !== addr && nu !== dashMac && !/^([0-9A-F]{2}[:-]){5}[0-9A-F]{2}$/i.test(n);
    }

    function setScan(on: bool): void {
        if (on) {
            if (_scanAcquired)
                return;
            _scanAcquired = true;
            if (!_pairableSnapshotValid && adapter) {
                _priorPairable = adapter.pairable;
                _pairableSnapshotValid = true;
            }
            Bluez.acquireScan("pairing", true);
        } else {
            if (!_scanAcquired)
                return;
            _scanAcquired = false;
            Bluez.releaseScan("pairing");
            Bluez.pendingPairable = null;
            if (_pairableSnapshotValid) {
                _pairableSnapshotValid = false;
                if (adapter?.enabled && adapter.pairable !== _priorPairable)
                    adapter.pairable = _priorPairable;
            }
        }
    }

    title: qsTr("Pair new device")
    isSubPage: true

    Component.onCompleted: {
        Bluez.pairingUiActive = true;
        if (visible)
            setScan(true);
    }
    Component.onDestruction: {
        Bluez.pairingUiActive = false;
        setScan(false);
    }
    onVisibleChanged: setScan(visible)

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        Connections {
            target: root.pairingDevice

            function onPairedChanged(): void {
                if (root.pairingDevice?.paired) {
                    root.pairFailed = false;
                    failTimer.stop();
                    root.pairingDevice.trusted = true;
                    root._connectPending = true;
                    root.pairingDevice.connect();
                }
            }

            function onPairingChanged(): void {
                if (root.pairingDevice && !root.pairingDevice.pairing && !root.pairingDevice.paired) {
                    root._connectPending = false;
                    root.pairFailed = true;
                    failTimer.restart();
                }
            }

            function onConnectedChanged(): void {
                if (root.pairingDevice?.connected) {
                    root._connectPending = false;
                    root.connectFailed = false;
                    closeTimer.restart();
                }
            }

            function onStateChanged(): void {
                if (root.pairingDevice && root._connectPending && root.pairingDevice.state === BluetoothDeviceState.Disconnected && !root.pairingDevice.connected) { // qmllint disable unresolved-type
                    root._connectPending = false;
                    root.connectFailed = true;
                    failTimer.restart();
                }
            }
        }

        Timer {
            id: closeTimer
            interval: 800
            onTriggered: {
                root.pairingDevice = null;
                root.nState.closeSubPage();
            }
        }

        Timer {
            id: failTimer
            interval: 3000
            onTriggered: {
                root.pairFailed = false;
                root.connectFailed = false;
                root.pairingDevice = null;
            }
        }

        Connections {
            target: root.adapter

            function onEnabledChanged(): void {
                if (root.adapter && !root.adapter.enabled && !Bluez.enabling)
                    root.nState.closeSubPage();
            }
        }

        Connections {
            target: Bluez

            function onAgentRequestTypeChanged(): void {
                codeInput.clear();
            }

            function onAgentDeviceAddressChanged(): void {
                codeInput.clear();
            }
        }

        // Interactive BlueZ Agent1 prompt card (PIN, Passkey, Numeric Confirmation, Authorize)
        ConnectedRect {
            visible: Bluez.agentPending
            Layout.fillWidth: true
            Layout.bottomMargin: Tokens.spacing.small
            implicitHeight: agentLayout.implicitHeight + agentLayout.anchors.margins * 2
            first: true
            last: true
            color: Colours.layer(Colours.palette.m3surfaceContainerHigh, 1)

            ColumnLayout {
                id: agentLayout

                anchors.fill: parent
                anchors.margins: Tokens.padding.largeIncreased
                spacing: Tokens.spacing.small

                StyledText {
                    Layout.fillWidth: true
                    text: {
                        const devName = Bluez.agentDeviceName || Bluez.agentDeviceAddress;
                        switch (Bluez.agentRequestType) {
                        case "confirm":
                            return qsTr("Confirm pairing passkey for %1").arg(devName);
                        case "pin":
                            return qsTr("Enter PIN code for %1").arg(devName);
                        case "passkey":
                            return qsTr("Enter 6-digit passkey for %1").arg(devName);
                        case "displayPin":
                        case "displayPasskey":
                            return qsTr("Enter passkey on %1").arg(devName);
                        case "authorize":
                        case "authorizeService":
                            return qsTr("Authorize connection for %1").arg(devName);
                        default:
                            return qsTr("Pairing prompt for %1").arg(devName);
                        }
                    }
                    font: Tokens.font.title.small
                    wrapMode: Text.WordWrap
                }

                StyledText {
                    visible: Bluez.agentRequestType === "confirm" || Bluez.agentRequestType === "displayPasskey" || Bluez.agentRequestType === "displayPin"
                    Layout.fillWidth: true
                    text: Bluez.agentPasskey
                    font: Tokens.font.display.small
                    color: Colours.palette.m3primary
                }

                StyledText {
                    visible: Bluez.agentRequestType === "displayPasskey" || Bluez.agentRequestType === "displayPin" || Bluez.agentRequestType === "authorizeService" || Bluez.agentRequestType === "confirm"
                    Layout.fillWidth: true
                    text: {
                        if (Bluez.agentRequestType === "confirm")
                            return qsTr("Verify this 6-digit code matches the number shown on the remote device.");
                        if (Bluez.agentRequestType === "displayPasskey")
                            return qsTr("Type this passkey on the keyboard and press Enter (%1/6 digits entered).").arg(Bluez.agentEntered);
                        if (Bluez.agentRequestType === "displayPin")
                            return qsTr("Type this PIN on the device and press Enter.");
                        if (Bluez.agentRequestType === "authorizeService")
                            return qsTr("Service UUID: %1").arg(Bluez.agentServiceUuid);
                        return "";
                    }
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.small
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    visible: Bluez.agentRequestType === "pin" || Bluez.agentRequestType === "passkey"
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    StyledInputField {
                        id: codeInput

                        Layout.fillWidth: true
                        horizontalAlignment: TextInput.AlignLeft
                        placeholderText: Bluez.agentRequestType === "passkey" ? qsTr("6-digit passkey") : qsTr("PIN code")
                        validator: RegularExpressionValidator {
                            regularExpression: Bluez.agentRequestType === "passkey" ? /^[0-9]{0,6}$/ : /^.{0,16}$/
                        }

                        Keys.onReturnPressed: {
                            if (Bluez.agentRequestType === "passkey" && text.length === 6)
                                Bluez.respondAgentPasskey(parseInt(text, 10));
                            else if (Bluez.agentRequestType === "pin" && text.trim().length > 0)
                                Bluez.respondAgentPin(text);
                        }
                    }

                    TextButton {
                        type: TextButton.Filled
                        text: qsTr("Submit")
                        disabled: Bluez.agentRequestType === "passkey" ? codeInput.text.length !== 6 : codeInput.text.trim().length === 0
                        onClicked: {
                            if (Bluez.agentRequestType === "passkey")
                                Bluez.respondAgentPasskey(parseInt(codeInput.text, 10));
                            else
                                Bluez.respondAgentPin(codeInput.text);
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    TextButton {
                        visible: Bluez.agentRequestType === "confirm" || Bluez.agentRequestType === "authorize" || Bluez.agentRequestType === "authorizeService"
                        type: TextButton.Filled
                        text: Bluez.agentRequestType === "confirm" ? qsTr("Matches & Pair") : qsTr("Authorize")
                        onClicked: Bluez.respondAgentConfirmation(true)
                    }

                    TextButton {
                        type: TextButton.Tonal
                        text: Bluez.agentNeedsReply && Bluez.agentRequestType !== "pin" && Bluez.agentRequestType !== "passkey" ? qsTr("Reject") : qsTr("Cancel")
                        onClicked: {
                            if (Bluez.agentRequestType === "confirm" || Bluez.agentRequestType === "authorize" || Bluez.agentRequestType === "authorizeService")
                                Bluez.respondAgentConfirmation(false);
                            else
                                Bluez.cancelAgentPending();
                        }
                    }
                }
            }
        }

        ConnectedRect {
            Layout.fillWidth: true
            implicitHeight: headerRow.implicitHeight + Tokens.padding.medium * 2
            first: true

            RowLayout {
                id: headerRow

                anchors.fill: parent
                anchors.leftMargin: Tokens.padding.large
                anchors.rightMargin: Tokens.padding.medium

                StyledText {
                    id: headerText

                    Layout.fillWidth: true
                    text: Bluez.discovering ? qsTr("Available devices (scanning…)") : qsTr("Available devices")
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.small
                }

                TextButton {
                    visible: !Bluez.discovering && Bluez.enabled
                    type: TextButton.Text
                    text: qsTr("Scan again")
                    onClicked: Bluez.acquireScan("pairing", true)
                }
            }
        }

        ItemList {
            id: deviceList

            Layout.fillWidth: true
            showList: true
            extraHeight: scanIndicator.implicitHeight
            placeholderIcon: Bluez.discovering ? "bluetooth_searching" : "devices_other"
            placeholderText: Bluez.discovering ? qsTr("Searching for devices…") : qsTr("No new devices found")
            list.anchors.top: scanIndicator.bottom

            model: ScriptModel {
                values: [...(Bluetooth.devices?.values ?? [])] // qmllint disable unresolved-type
                    .filter(d => (!(d.bonded || d.paired) || d === root.pairingDevice)
                        && (root.showUnnamedDevices || d === root.pairingDevice || root.isNamedDevice(d)))
                    .sort((a, b) =>
                        ((b === root.pairingDevice ? 1 : 0) - (a === root.pairingDevice ? 1 : 0))
                        || (b.pairing - a.pairing)
                        || (a.name || a.address || "").localeCompare(b.name || b.address || ""))
            }

            delegate: Item {
                id: newDevice

                required property BluetoothDevice modelData // qmllint disable unresolved-type
                required property int index

                readonly property bool isThisPairing: root.pairingDevice === modelData
                readonly property bool isConnecting: modelData?.state === BluetoothDeviceState.Connecting // qmllint disable unresolved-type
                readonly property bool isConnected: modelData?.state === BluetoothDeviceState.Connected // qmllint disable unresolved-type
                readonly property bool isBusy: (modelData?.pairing ?? false) || isConnecting || (isThisPairing && isConnected)

                property real textOpacity: isBusy ? 0.5 : 1

                anchors.left: deviceList.list.contentItem.left
                anchors.right: deviceList.list.contentItem.right
                implicitHeight: newLayout.implicitHeight + newLayout.anchors.margins * 2

                Behavior on textOpacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }

                StateLayer {
                    radius: Tokens.rounding.extraSmall
                    disabled: newDevice.isBusy || (newDevice.modelData?.blocked ?? false)

                    onClicked: {
                        failTimer.stop();
                        closeTimer.stop();
                        root.pairFailed = false;
                        root.connectFailed = false;
                        root._connectPending = false;
                        root.pairingDevice = newDevice.modelData;
                        if (newDevice.modelData) {
                            if (newDevice.modelData.paired) {
                                newDevice.modelData.trusted = true;
                                root._connectPending = true;
                                newDevice.modelData.connect();
                            } else {
                                newDevice.modelData.pair();
                            }
                        }
                    }
                }

                RowLayout {
                    id: newLayout

                    anchors.fill: parent
                    anchors.margins: Tokens.padding.medium
                    anchors.leftMargin: Tokens.padding.largeIncreased
                    anchors.rightMargin: Tokens.padding.largeIncreased
                    spacing: Tokens.spacing.medium

                    MaterialIcon {
                        text: Icons.getBluetoothIcon(newDevice.modelData?.icon ?? "")
                        color: Colours.palette.m3onSurfaceVariant
                        fontStyle: Tokens.font.icon.medium
                        opacity: newDevice.textOpacity
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        opacity: newDevice.textOpacity

                        StyledText {
                            Layout.fillWidth: true
                            text: newDevice.modelData?.name || newDevice.modelData?.address || qsTr("Unknown device")
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: {
                                if (newDevice.isThisPairing && root.pairFailed)
                                    return qsTr("Pairing failed");
                                if (newDevice.isThisPairing && root.connectFailed)
                                    return qsTr("Paired, connection failed");
                                if (newDevice.isConnected)
                                    return qsTr("Connected");
                                if (newDevice.isConnecting)
                                    return qsTr("Connecting…");
                                if (newDevice.modelData?.pairing)
                                    return qsTr("Pairing…");
                                return newDevice.modelData?.address ?? "";
                            }
                            color: (newDevice.isThisPairing && (root.pairFailed || root.connectFailed)) ? Colours.palette.m3error : Colours.palette.m3outline
                            font: Tokens.font.label.small
                            elide: Text.ElideRight
                            animate: true
                        }
                    }

                    Loader {
                        asynchronous: true
                        active: opacity > 0
                        opacity: ((newDevice.modelData?.pairing ?? false) || newDevice.isConnecting) ? 1 : 0

                        sourceComponent: LoadingIndicator {
                            implicitSize: Math.round(Tokens.font.icon.medium.pointSize * 1.3)
                        }

                        Behavior on opacity {
                            Anim {
                                type: Anim.DefaultEffects
                            }
                        }
                    }
                }
            }

            StyledProgressBar {
                id: scanIndicator

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 1
                implicitHeight: Bluez.discovering ? Tokens.rounding.extraSmall : 0
                indeterminate: Bluez.discovering

                Behavior on implicitHeight {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }
        }

        ToggleRow {
            last: true
            text: qsTr("Show unnamed devices")
            subtext: qsTr("Include unnamed Bluetooth LE beacons")
            checked: root.showUnnamedDevices
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.showUnnamedDevices);
                root.showUnnamedDevices = next;
            }
        }
    }
}
