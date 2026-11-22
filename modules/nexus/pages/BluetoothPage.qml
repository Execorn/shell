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
    readonly property bool btEnabled: Bluez.enabled
    readonly property bool adapterUsable: Bluez.hasAdapter && !Bluez.hardBlocked

    title: qsTr("Connected devices")

    Component.onCompleted: Bluez.refreshAudioProfiles()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        ToggleRow {
            first: true
            last: !root.adapterUsable
            text: qsTr("Bluetooth")
            subtext: !Bluez.hasAdapter ? qsTr("No Bluetooth adapter detected") : (Bluez.hardBlocked ? qsTr("Blocked by hardware kill switch") : "")
            font: Tokens.font.body.medium
            horizontalPadding: Tokens.padding.largeIncreased
            enabled: root.adapterUsable
            opacity: root.adapterUsable ? 1 : 0.5
            checked: root.btEnabled
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.btEnabled);
                Bluez.setEnabled(next);
            }
        }

        ConnectedRect {
            visible: Bluez.agentPending
            Layout.fillWidth: true
            Layout.topMargin: Tokens.spacing.small
            implicitHeight: agentBannerLayout.implicitHeight + agentBannerLayout.anchors.margins * 2
            first: true
            last: true
            color: Colours.layer(Colours.palette.m3surfaceContainerHigh, 1)

            ColumnLayout {
                id: agentBannerLayout

                anchors.fill: parent
                anchors.margins: Tokens.padding.largeIncreased
                spacing: Tokens.spacing.small

                StyledText {
                    Layout.fillWidth: true
                    text: qsTr("Pairing request: %1").arg(Bluez.agentDeviceName || Bluez.agentDeviceAddress)
                    font: Tokens.font.title.small
                    elide: Text.ElideRight
                }

                StyledText {
                    visible: Bluez.agentPasskey !== ""
                    Layout.fillWidth: true
                    text: Bluez.agentRequestType === "displayPasskey" || Bluez.agentRequestType === "displayPin"
                        ? qsTr("Type passkey %1 on the remote device").arg(Bluez.agentPasskey)
                        : qsTr("Passkey: %1").arg(Bluez.agentPasskey)
                    color: Colours.palette.m3primary
                    font: Tokens.font.title.medium
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    TextButton {
                        visible: Bluez.agentRequestType === "confirm" || Bluez.agentRequestType === "authorize" || Bluez.agentRequestType === "authorizeService"
                        type: TextButton.Filled
                        text: qsTr("Accept")
                        onClicked: Bluez.respondAgentConfirmation(true)
                    }

                    TextButton {
                        visible: Bluez.agentNeedsReply && Bluez.agentRequestType !== "pin" && Bluez.agentRequestType !== "passkey"
                        type: TextButton.Tonal
                        text: qsTr("Reject")
                        onClicked: Bluez.respondAgentConfirmation(false)
                    }

                    TextButton {
                        visible: Bluez.agentRequestType === "pin" || Bluez.agentRequestType === "passkey"
                        type: TextButton.Filled
                        text: qsTr("Enter code")
                        onClicked: root.nState.openSubPage(2)
                    }

                    TextButton {
                        visible: !Bluez.agentNeedsReply
                        type: TextButton.Tonal
                        text: qsTr("Dismiss")
                        onClicked: Bluez.cancelAgentPending()
                    }
                }
            }
        }

        ItemList {
            id: savedList

            showList: root.btEnabled && root.adapterUsable
            placeholderIcon: !root.adapterUsable || !root.btEnabled ? "bluetooth_disabled" : "devices_other"
            placeholderText: {
                if (!Bluez.hasAdapter)
                    return qsTr("No Bluetooth adapter found");
                if (Bluez.hardBlocked)
                    return qsTr("Disabled by hardware switch");
                return root.btEnabled ? qsTr("No saved devices") : qsTr("Bluetooth disabled");
            }

            model: ScriptModel {
                values: [...(Bluetooth.devices?.values ?? [])] // qmllint disable unresolved-type
                    .filter(d => d.bonded || d.paired || d.connected)
                    .sort((a, b) => (b.connected - a.connected) || (b.bonded - a.bonded) || (a.name || a.address || "").localeCompare(b.name || b.address || ""))
            }

            delegate: StyledRect {
                id: device

                required property BluetoothDevice modelData // qmllint disable unresolved-type
                readonly property bool connected: !!modelData && (modelData.connected || modelData.state === BluetoothDeviceState.Connected) // qmllint disable unresolved-type
                readonly property bool loading: !!modelData && (modelData.pairing
                    || modelData.state === BluetoothDeviceState.Connecting // qmllint disable unresolved-type
                    || modelData.state === BluetoothDeviceState.Disconnecting // qmllint disable unresolved-type
                    || (Bluez.enabling && (Bluez.pendingConnectDevice === modelData || Bluez.pendingPairDevice === modelData)))
                readonly property string codecLabel: connected ? Bluez.activeCodecFor(modelData?.address ?? "") : ""
                property real textOpacity: loading ? 0.5 : 1

                anchors.left: savedList.list.contentItem.left
                anchors.right: savedList.list.contentItem.right
                implicitHeight: deviceLayout.implicitHeight + deviceLayout.anchors.margins * 2
                radius: Tokens.rounding.extraSmall
                color: "transparent"

                Behavior on textOpacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }

                StateLayer {
                    disabled: device.loading || (device.modelData?.blocked ?? false)
                    onClicked: {
                        if (!device.modelData || device.loading)
                            return;
                        Bluez.toggleDeviceConnection(device.modelData);
                    }
                }

                RowLayout {
                    id: deviceLayout

                    anchors.fill: parent
                    anchors.margins: Tokens.padding.medium
                    anchors.leftMargin: Tokens.padding.largeIncreased
                    anchors.rightMargin: Tokens.padding.largeIncreased
                    spacing: Tokens.spacing.medium

                    StyledRect {
                        implicitWidth: implicitHeight
                        implicitHeight: deviceIcon.implicitHeight + Tokens.padding.small * 2
                        radius: Tokens.rounding.full
                        color: device.connected ? Colours.palette.m3primary : Colours.palette.m3secondaryContainer

                        MaterialIcon {
                            id: deviceIcon

                            anchors.centerIn: parent
                            text: Icons.getBluetoothIcon(device.modelData?.icon ?? "")
                            color: device.connected ? Colours.palette.m3onPrimary : Colours.palette.m3onSecondaryContainer
                            fontStyle: Tokens.font.icon.medium
                            fill: device.connected ? 1 : 0
                            opacity: device.textOpacity

                            Behavior on fill {
                                Anim {}
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        opacity: device.textOpacity

                        StyledText {
                            Layout.fillWidth: true
                            text: device.modelData?.name || device.modelData?.address || qsTr("Unknown")
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: {
                                if (!device.modelData)
                                    return "";
                                const parts = [];
                                if (device.connected) {
                                    parts.push(qsTr("Connected"));
                                    if (device.modelData.batteryAvailable)
                                        parts.push(Math.round(device.modelData.battery * 100) + "%");
                                    if (device.codecLabel)
                                        parts.push(device.codecLabel);
                                } else {
                                    parts.push(device.modelData.bonded ? qsTr("Saved") : qsTr("Temporary (unbonded)"));
                                }
                                if (device.connected && !device.modelData.bonded)
                                    parts.push(qsTr("Temporary"));
                                if (device.modelData.blocked)
                                    parts.push(qsTr("Blocked"));
                                return parts.join(" • ");
                            }
                            color: Colours.palette.m3outline
                            font: Tokens.font.label.small
                            elide: Text.ElideRight
                            animate: true
                        }
                    }

                    Item {
                        Layout.fillHeight: true
                        implicitWidth: height

                        AnimLoader {
                            anchors.centerIn: parent
                            sourceComp: device.loading ? loadingComp : btnComp

                            Component {
                                id: btnComp

                                IconButton {
                                    icon: "settings"
                                    type: IconButton.Text
                                    padding: Tokens.padding.small
                                    inactiveOnColour: device.connected ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
                                    label.fill: 0

                                    onClicked: {
                                        root.nState.selectedBtDevice = device.modelData;
                                        root.nState.openSubPage(1); // Per device info page
                                    }
                                }
                            }

                            Component {
                                id: loadingComp

                                LoadingIndicator {
                                    implicitSize: Math.round(Tokens.font.icon.medium.pointSize * 1.3)
                                }
                            }
                        }
                    }
                }
            }
        }

        ConnectedRect {
            Layout.fillWidth: true
            implicitHeight: pairLayout.implicitHeight + pairLayout.anchors.margins * 2
            last: true

            StateLayer {
                disabled: !root.btEnabled || !root.adapterUsable
                onClicked: root.nState.openSubPage(2)
            }

            RowLayout {
                id: pairLayout

                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                anchors.leftMargin: Tokens.padding.largeIncreased
                anchors.rightMargin: Tokens.padding.largeIncreased
                spacing: Tokens.spacing.medium
                opacity: root.btEnabled && root.adapterUsable ? 1 : 0.5

                Behavior on opacity {
                    Anim {}
                }

                MaterialIcon {
                    text: "add"
                    fontStyle: Tokens.font.icon.medium
                }

                StyledText {
                    Layout.fillWidth: true
                    text: qsTr("Pair new device")
                    font: Tokens.font.body.small
                    elide: Text.ElideRight
                }
            }
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.large - parent.spacing

            first: true
            text: qsTr("Discoverable")
            subtext: qsTr("Allow nearby devices to find this one")
            enabled: !!(root.adapter?.enabled) && !Bluez.hardBlocked
            opacity: enabled ? 1 : 0.5
            checked: root.adapter?.discoverable ?? false
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.adapter?.discoverable ?? false);
                if (root.adapter?.enabled)
                    root.adapter.discoverable = next;
            }

            Behavior on opacity {
                Anim {}
            }
        }

        ToggleRow {
            last: true
            text: qsTr("Pairable")
            subtext: qsTr("Allow nearby devices to pair with this one")
            enabled: !!(root.adapter?.enabled) && !Bluez.hardBlocked
            opacity: enabled ? 1 : 0.5
            checked: root.adapter?.pairable ?? false
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => root.adapter?.pairable ?? false);
                if (root.adapter?.enabled)
                    root.adapter.pairable = next;
            }

            Behavior on opacity {
                Anim {}
            }
        }
    }
}
