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

ColumnLayout {
    id: root

    required property PopoutState popouts

    width: 300
    spacing: Tokens.spacing.small

    Component.onCompleted: Bluez.refreshAudioProfiles()
    Component.onDestruction: Bluez.releaseScan("popout")

    StyledText {
        Layout.topMargin: Tokens.padding.medium
        Layout.rightMargin: Tokens.padding.extraSmall
        text: qsTr("Bluetooth")
        font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
    }

    Toggle {
        label: qsTr("Enabled")
        checked: Bluez.enabled
        enabled: Bluez.hasAdapter && !Bluez.hardBlocked
        onToggled: checked => Bluez.setEnabled(checked)
    }

    Toggle {
        label: qsTr("Discovering")
        checked: Bluez.discovering
        enabled: Bluez.hasAdapter && !Bluez.hardBlocked
        onToggled: checked => {
            if (checked) {
                Bluez.acquireScan("popout", false);
            } else {
                Bluez.releaseScan("popout");
                if (Bluez.discovering)
                    Bluez.setDiscovering(false);
            }
        }
    }

    StyledText {
        visible: !Bluez.hasAdapter || Bluez.hardBlocked
        Layout.fillWidth: true
        Layout.rightMargin: Tokens.padding.extraSmall
        text: !Bluez.hasAdapter ? qsTr("No Bluetooth adapter found") : qsTr("Disabled by hardware kill switch")
        color: Colours.palette.m3error
        font: Tokens.font.body.small
        wrapMode: Text.WordWrap
    }

    StyledText {
        Layout.topMargin: Tokens.spacing.small
        Layout.rightMargin: Tokens.padding.extraSmall
        text: {
            const devices = Bluetooth.devices?.values ?? []; // qmllint disable unresolved-type
            let available = qsTr("%1 device%2 available").arg(devices.length).arg(devices.length === 1 ? "" : "s");
            const connected = devices.filter(d => d.connected).length;
            if (connected > 0)
                available += qsTr(" (%1 connected)").arg(connected);
            return available;
        }
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.small
    }

    Repeater {
        model: ScriptModel {
            values: [...(Bluetooth.devices?.values ?? [])] // qmllint disable unresolved-type
                .sort((a, b) => {
                    const aNamed = a.name && a.name !== (a.address ?? "").replace(/:/g, "-");
                    const bNamed = b.name && b.name !== (b.address ?? "").replace(/:/g, "-");
                    return (b.connected - a.connected)
                        || (b.bonded - a.bonded)
                        || (b.paired - a.paired)
                        || (bNamed - aNamed)
                        || (a.name || a.address || "").localeCompare(b.name || b.address || "");
                })
                .slice(0, 5)
        }

        RowLayout {
            id: device

            required property BluetoothDevice modelData // qmllint disable unresolved-type
            readonly property bool isConnected: modelData.connected || modelData.state === BluetoothDeviceState.Connected // qmllint disable unresolved-type
            readonly property bool isSaved: modelData.bonded || modelData.paired || modelData.connected
            readonly property string activeCodec: isConnected ? Bluez.activeCodecFor(modelData.address) : ""
            readonly property string metaText: {
                const parts = [];
                if (activeCodec)
                    parts.push(activeCodec);
                if (modelData.paired && !modelData.bonded)
                    parts.push(qsTr("Temporary"));
                return parts.join(" • ");
            }
            readonly property bool loading: modelData.pairing
                || modelData.state === BluetoothDeviceState.Connecting // qmllint disable unresolved-type
                || modelData.state === BluetoothDeviceState.Disconnecting // qmllint disable unresolved-type
                || (Bluez.enabling && (Bluez.pendingConnectDevice === modelData || Bluez.pendingPairDevice === modelData))

            Layout.fillWidth: true
            Layout.rightMargin: Tokens.padding.extraSmall
            spacing: Tokens.spacing.small

            opacity: 0
            scale: 0.7

            Component.onCompleted: {
                opacity = 1;
                scale = 1;
            }

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            Behavior on scale {
                Anim {}
            }

            MaterialIcon {
                text: Icons.getBluetoothIcon(device.modelData.icon)
            }

            ColumnLayout {
                Layout.leftMargin: Tokens.spacing.extraSmall
                Layout.rightMargin: Tokens.spacing.extraSmall
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    Layout.fillWidth: true
                    text: device.modelData.name || device.modelData.address
                    elide: Text.ElideRight
                }

                StyledText {
                    visible: device.metaText !== ""
                    Layout.fillWidth: true
                    text: device.metaText
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.small
                    elide: Text.ElideRight
                }
            }

            MaterialIcon {
                visible: device.isConnected && device.modelData.batteryAvailable
                text: Icons.getBatteryIcon(device.modelData.battery)
                color: device.modelData.battery < 0.2 ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
            }

            StyledRect {
                id: connectBtn

                implicitWidth: implicitHeight
                implicitHeight: connectIcon.implicitHeight + Tokens.padding.extraSmall

                radius: Tokens.rounding.full
                color: Qt.alpha(Colours.palette.m3primary, device.isConnected ? 1 : 0)

                CircularIndicator {
                    anchors.fill: parent
                    running: device.loading
                }

                StateLayer {
                    color: device.isConnected ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
                    disabled: device.loading || device.modelData.blocked
                    onClicked: Bluez.toggleDeviceConnection(device.modelData)
                }

                MaterialIcon {
                    id: connectIcon

                    anchors.centerIn: parent
                    animate: true
                    text: device.isConnected ? "link_off" : (device.isSaved ? "link" : "bluetooth")
                    color: device.isConnected ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface

                    opacity: device.loading ? 0 : 1

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                }
            }

            Loader {
                visible: status === Loader.Ready
                asynchronous: true
                active: device.modelData.bonded || device.modelData.paired
                sourceComponent: Item {
                    implicitWidth: connectBtn.implicitWidth
                    implicitHeight: connectBtn.implicitHeight

                    StateLayer {
                        radius: Tokens.rounding.full
                        disabled: device.loading
                        onClicked: Bluez.forgetDevice(device.modelData)
                    }

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: "delete"
                        opacity: device.loading ? 0.38 : 1
                    }
                }
            }
        }
    }

    IconTextButton {
        Layout.fillWidth: true
        Layout.topMargin: Tokens.spacing.medium
        inactiveColour: Colours.palette.m3primaryContainer
        inactiveOnColour: Colours.palette.m3onPrimaryContainer
        verticalPadding: Tokens.padding.extraSmall
        text: qsTr("Open settings")
        icon: "settings"

        onClicked: root.popouts.detachRequested("bluetooth")
    }

    component Toggle: RowLayout {
        id: toggleRow

        required property string label
        required property bool checked
        property alias toggle: toggle

        signal toggled(checked: bool)

        Layout.fillWidth: true
        Layout.rightMargin: Tokens.padding.extraSmall
        spacing: Tokens.spacing.medium
        opacity: enabled ? 1 : 0.38

        StyledText {
            Layout.fillWidth: true
            text: toggleRow.label
        }

        StyledSwitch {
            id: toggle

            enabled: toggleRow.enabled
            checked: toggleRow.checked
            onToggled: {
                const next = checked;
                checked = Qt.binding(() => toggleRow.checked);
                toggleRow.toggled(next);
            }
        }
    }
}
