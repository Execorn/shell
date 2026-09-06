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

    readonly property BluetoothAdapter adapter: Bluetooth.defaultAdapter // qmllint disable unresolved-type
    property BluetoothDevice pairingDevice: null
    property bool pairFailed: false

    function setScan(on: bool): void {
        if (adapter?.enabled) {
            adapter.pairable = on;
            adapter.discovering = on;
        }
    }

    title: qsTr("Pair new device")
    isSubPage: true

    Component.onCompleted: setScan(true)
    Component.onDestruction: setScan(false)
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
                    root.pairingDevice.trusted = true;
                    root.pairingDevice.connect();
                }
            }

            function onPairingChanged(): void {
                if (root.pairingDevice && !root.pairingDevice.pairing && !root.pairingDevice.paired) {
                    root.pairFailed = true;
                    failTimer.restart();
                }
            }

            function onConnectedChanged(): void {
                if (root.pairingDevice?.connected) {
                    closeTimer.restart();
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
                root.pairingDevice = null;
            }
        }

        Connections {
            function onEnabledChanged(): void {
                if (root.adapter && !root.adapter.enabled)
                    root.nState.closeSubPage();
            }

            target: root.adapter
        }

        ConnectedRect {
            Layout.fillWidth: true
            implicitHeight: headerText.implicitHeight + Tokens.padding.medium * 2
            first: true

            StyledText {
                id: headerText

                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Tokens.padding.large
                anchors.verticalCenterOffset: Math.round(fontInfo.pointSize * 0.2)

                text: qsTr("Available devices")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
            }
        }

        ItemList {
            id: deviceList

            Layout.fillWidth: true
            showList: true
            extraHeight: scanIndicator.implicitHeight
            last: true
            placeholderIcon: "bluetooth_searching"
            placeholderText: qsTr("Searching for devices…")
            list.anchors.top: scanIndicator.bottom

            model: ScriptModel {
                values: Bluetooth.devices.values.filter(d => !d.bonded || d === root.pairingDevice).sort((a, b) => (b.pairing - a.pairing) || a.name.localeCompare(b.name)) // qmllint disable unresolved-type
            }

            delegate: Item {
                id: newDevice

                required property BluetoothDevice modelData
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
                    bottomLeftRadius: newDevice.index === deviceList?.list.count - 1 ? Tokens.rounding.extraLarge : radius
                    bottomRightRadius: newDevice.index === deviceList?.list.count - 1 ? Tokens.rounding.extraLarge : radius
                    disabled: newDevice.isBusy

                    onClicked: {
                        root.pairFailed = false;
                        root.pairingDevice = newDevice.modelData;
                        if (newDevice.modelData) {
                            newDevice.modelData.trusted = true;
                            newDevice.modelData.pair();
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
                            text: newDevice.modelData?.name || qsTr("Unknown device")
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: {
                                if (newDevice.isThisPairing && root.pairFailed)
                                    return qsTr("Pairing failed");
                                if (newDevice.isConnected)
                                    return qsTr("Connected");
                                if (newDevice.isConnecting)
                                    return qsTr("Connecting…");
                                if (newDevice.modelData?.pairing)
                                    return qsTr("Pairing…");
                                return newDevice.modelData?.address ?? "";
                            }
                            color: (newDevice.isThisPairing && root.pairFailed) ? Colours.palette.m3error : Colours.palette.m3outline
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
                implicitHeight: Tokens.rounding.extraSmall
                indeterminate: true

                Behavior on implicitHeight {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }
        }
    }
}
