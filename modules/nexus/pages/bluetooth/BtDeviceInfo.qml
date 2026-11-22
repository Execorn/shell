pragma ComponentBehavior: Bound

import QtQuick
import QtQml
import QtQuick.Layouts
import Quickshell.Bluetooth
import Caelestia
import Caelestia.Components
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    readonly property BluetoothDevice device: nState.selectedBtDevice // qmllint disable unresolved-type
    readonly property bool connected: !!device && (device.connected || device.state === BluetoothDeviceState.Connected) // qmllint disable unresolved-type
    readonly property bool loading: !!device && (device.pairing
        || device.state === BluetoothDeviceState.Connecting // qmllint disable unresolved-type
        || device.state === BluetoothDeviceState.Disconnecting // qmllint disable unresolved-type
        || (Bluez.enabling && (Bluez.pendingConnectDevice === device || Bluez.pendingPairDevice === device)))
    readonly property string deviceAddress: device?.address ?? ""
    readonly property var cardInfo: Bluez.cardInfoFor(deviceAddress)
    readonly property var deviceProfiles: cardInfo?.profiles ?? []
    readonly property string activeProfile: cardInfo?.activeProfile ?? ""
    readonly property string activeCodec: connected ? (cardInfo?.codecLabel ?? "") : ""
    property list<MenuItem> profileMenuItems: []
    property bool _closing: false

    readonly property MenuItem activeProfileMenuItem: {
        for (const item of profileMenuItems) {
            if (item && item.profileName === activeProfile)
                return item;
        }
        return null;
    }

    readonly property string statusText: {
        if (!device)
            return "";
        const parts = [];
        if (device.pairing)
            parts.push(qsTr("Pairing…"));
        else if (device.state === BluetoothDeviceState.Connecting) // qmllint disable unresolved-type
            parts.push(qsTr("Connecting…"));
        else if (device.state === BluetoothDeviceState.Disconnecting) // qmllint disable unresolved-type
            parts.push(qsTr("Disconnecting…"));
        else if (connected)
            parts.push(qsTr("Connected"));
        else if (device.bonded)
            parts.push(qsTr("Paired"));
        else if (device.paired)
            parts.push(qsTr("Temporary (unbonded)"));
        else
            parts.push(qsTr("Not paired"));

        if (connected && device.batteryAvailable)
            parts.push(Math.round(device.battery * 100) + "%");
        if (connected && activeCodec)
            parts.push(activeCodec);
        if (connected && device.paired && !device.bonded)
            parts.push(qsTr("Temporary"));
        if (device.blocked)
            parts.push(qsTr("Blocked"));
        return parts.join(" • ");
    }

    function rebuildProfileMenuItems(): void {
        const next = [];
        for (let i = 0; i < profileMenuInstantiator.count; i++) {
            const obj = profileMenuInstantiator.objectAt(i);
            if (obj)
                next.push(obj);
        }
        profileMenuItems = next;
    }

    Component.onCompleted: Bluez.refreshAudioProfiles()

    onDeviceChanged: {
        if (!device) {
            if (!_closing) {
                _closing = true;
                nState.closeSubPage();
            }
        } else {
            _closing = false;
            Bluez.refreshAudioProfiles();
        }
    }

    title: device?.name || device?.address || qsTr("Device")
    isSubPage: true

    Instantiator {
        id: profileMenuInstantiator

        model: root.deviceProfiles
        onObjectAdded: root.rebuildProfileMenuItems()
        onObjectRemoved: root.rebuildProfileMenuItems()

        delegate: MenuItem {
            required property var modelData
            readonly property string profileName: modelData.name ?? ""

            text: modelData.label ?? modelData.name ?? ""
            activeText: modelData.shortLabel ?? modelData.name ?? ""
            icon: modelData.name === "off" ? "volume_off" : (modelData.isHeadset ? "headset_mic" : "headphones")
        }
    }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        StyledText {
            visible: root.statusText !== ""
            Layout.fillWidth: true
            Layout.bottomMargin: Tokens.spacing.medium
            horizontalAlignment: Text.AlignHCenter
            text: root.statusText
            color: root.device?.blocked ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.medium
            wrapMode: Text.WordWrap
        }

        // Big buttons
        ButtonRow {
            Layout.bottomMargin: Tokens.spacing.large - parent.spacing
            Layout.alignment: Qt.AlignHCenter
            Layout.minimumWidth: Math.round(root.cappedWidth * 0.7)
            spacing: Tokens.spacing.small

            ButtonBase {
                id: forgetBtn

                fillWidth: true
                shapeMorph: true
                isRound: true

                inactiveColour: Colours.palette.m3errorContainer
                inactiveOnColour: Colours.palette.m3onErrorContainer
                stateLayer.disabled: root.loading
                opacity: root.loading ? 0.5 : 1

                implicitWidth: forgetBtnLayout.implicitWidth + Tokens.padding.extraLarge * 2
                implicitHeight: forgetBtnLayout.implicitHeight + Tokens.padding.medium * 2

                onClicked: {
                    if (!root.device || root.loading)
                        return;
                    Bluez.forgetDevice(root.device);
                    if (!root._closing) {
                        root._closing = true;
                        root.nState.closeSubPage();
                    }
                }

                ColumnLayout {
                    id: forgetBtnLayout

                    anchors.centerIn: parent
                    spacing: 0

                    MaterialIcon {
                        Layout.alignment: Qt.AlignHCenter
                        text: "delete"
                        color: forgetBtn.onColour
                        fontStyle: Tokens.font.icon.medium
                    }

                    StyledText {
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("Forget")
                        color: forgetBtn.onColour
                    }
                }
            }

            ButtonBase {
                id: connectBtn

                fillWidth: true
                shapeMorph: true
                isRound: true

                inactiveColour: Colours.palette.m3primaryContainer
                inactiveOnColour: Colours.palette.m3onPrimaryContainer
                stateLayer.disabled: root.loading || (root.device?.blocked ?? false)
                opacity: (root.device?.blocked ?? false) ? 0.5 : 1

                implicitWidth: connectBtnContent.implicitWidth + Tokens.padding.extraLarge * 2
                implicitHeight: connectBtnContent.implicitHeight + Tokens.padding.medium * 2

                onClicked: {
                    if (root.device)
                        Bluez.toggleDeviceConnection(root.device);
                }

                AnimLoader {
                    id: connectBtnContent

                    anchors.centerIn: parent
                    sourceComp: root.loading ? loadingComp : textComp
                    outAnimType: Anim.SlowEffects
                    inAnimType: Anim.SlowEffects
                }

                Component {
                    id: loadingComp

                    LoadingIndicator {
                        implicitSize: connectBtn.height - Tokens.padding.large * 2
                    }
                }

                Component {
                    id: textComp

                    ColumnLayout {
                        spacing: 0

                        MaterialIcon {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.connected ? "close" : ((root.device?.paired || root.device?.bonded) ? "add" : "bluetooth")
                            color: connectBtn.inactiveOnColour
                            fontStyle: Tokens.font.icon.medium
                            animate: true
                        }

                        StyledText {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.connected ? qsTr("Disconnect") : ((root.device?.paired || root.device?.bonded) ? qsTr("Connect") : qsTr("Pair"))
                            color: connectBtn.inactiveOnColour
                            animate: true
                        }
                    }
                }
            }
        }

        // Temporary (unbonded) pairing warning & quick re-pair action
        ConnectedRect {
            visible: !!root.device && root.device.paired && !root.device.bonded
            Layout.fillWidth: true
            Layout.bottomMargin: Tokens.spacing.medium
            implicitHeight: unbondedRow.implicitHeight + Tokens.padding.large * 2
            first: true
            last: true
            color: Colours.layer(Colours.palette.m3surfaceContainerHigh, 1)

            RowLayout {
                id: unbondedRow

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: Tokens.padding.large
                spacing: Tokens.spacing.medium

                MaterialIcon {
                    text: "warning"
                    color: Colours.palette.m3tertiary
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    StyledText {
                        Layout.fillWidth: true
                        text: qsTr("Temporary pairing (unbonded)")
                        font: Tokens.font.body.small
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: qsTr("Pairing keys are not persisted permanently. Forget and re-pair to bond this device.")
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.label.small
                        wrapMode: Text.WordWrap
                    }
                }

                TextButton {
                    type: TextButton.Tonal
                    text: qsTr("Re-pair")
                    disabled: root.loading
                    onClicked: {
                        if (!root.device || root.loading)
                            return;
                        Bluez.forgetDevice(root.device);
                        Toaster.toast(qsTr("Device forgotten"), qsTr("Open 'Pair new device' to create a permanent bond"), "bluetooth_searching", Toast.Info);
                        if (!root._closing) {
                            root._closing = true;
                            root.nState.closeSubPage();
                        }
                    }
                }
            }
        }

        // Audio profile & codec selection (PipeWire BlueZ card)
        SectionHeader {
            visible: root.deviceProfiles.length > 0
            first: true
            text: qsTr("Audio profile & codec")
        }

        SelectRow {
            id: profileSelect

            visible: root.deviceProfiles.length > 0
            first: true
            last: root.activeCodec === ""
            label: qsTr("Audio profile")
            subtext: qsTr("Switch A2DP codec or headset microphone mode")
            menuItems: root.profileMenuItems
            active: root.activeProfileMenuItem
            fallbackText: qsTr("Unavailable")
            fallbackIcon: "headphones"
            onSelected: item => {
                active = Qt.binding(() => root.activeProfileMenuItem);
                if (item && item.profileName)
                    Bluez.setDeviceProfile(root.deviceAddress, item.profileName);
            }
        }

        InfoRow {
            visible: root.deviceProfiles.length > 0 && root.activeCodec !== ""
            last: true
            label: qsTr("Active codec")
            subtext: root.cardInfo?.activeProfileDesc ?? ""
            value: root.activeCodec
            icon: "graphic_eq"
        }

        // Connection group
        SectionHeader {
            first: root.deviceProfiles.length === 0
            text: qsTr("Connection")
        }

        ToggleRow {
            verticalPadding: Tokens.padding.large
            first: true
            text: qsTr("Trusted")
            subtext: qsTr("Allow this device to connect automatically")
            checked: root.device?.trusted ?? false
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.device?.trusted ?? false);
                if (root.device)
                    root.device.trusted = next;
            }
        }

        ToggleRow {
            verticalPadding: Tokens.padding.large
            text: qsTr("Blocked")
            subtext: qsTr("Prevent this device from connecting")
            checked: root.device?.blocked ?? false
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.device?.blocked ?? false);
                if (root.device)
                    root.device.blocked = next;
            }
        }

        ToggleRow {
            verticalPadding: Tokens.padding.large
            last: true
            text: qsTr("Wake allowed")
            subtext: qsTr("Allow this device to wake the system")
            checked: root.device?.wakeAllowed ?? false
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.device?.wakeAllowed ?? false);
                if (root.device)
                    root.device.wakeAllowed = next;
            }
        }

        // Information
        SectionHeader {
            text: qsTr("Information")
        }

        ConnectedRect {
            Layout.fillWidth: true
            implicitHeight: batteryLayout.implicitHeight + Tokens.padding.large * 2
            first: true

            ColumnLayout {
                id: batteryLayout

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: Tokens.padding.large
                spacing: Tokens.spacing.small

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.medium

                    StyledText {
                        Layout.fillWidth: true
                        text: qsTr("Battery")
                    }

                    StyledText {
                        text: root.device?.batteryAvailable ? Math.round(root.device.battery * 100) + "%" : qsTr("Unavailable")
                        color: Colours.palette.m3outline
                        font: Tokens.font.body.small
                    }
                }

                Loader {
                    Layout.fillWidth: true
                    active: root.device?.batteryAvailable ?? false
                    visible: active
                    asynchronous: true

                    sourceComponent: StyledProgressBar {
                        implicitHeight: Tokens.padding.medium
                        value: root.device.battery
                    }
                }
            }
        }

        ConnectedRect {
            Layout.fillWidth: true
            implicitHeight: addrLayout.implicitHeight + Tokens.padding.large * 2
            last: true

            RowLayout {
                id: addrLayout

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: Tokens.padding.large
                spacing: Tokens.spacing.medium

                StyledText {
                    Layout.fillWidth: true
                    text: qsTr("Address")
                }

                StyledText {
                    text: root.device?.address ?? ""
                    color: Colours.palette.m3outline
                    font: Tokens.font.body.small
                }
            }
        }
    }
}
