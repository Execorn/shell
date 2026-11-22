pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import Quickshell.Bluetooth
import Caelestia.Config
import qs.components
import qs.components.containers
import qs.components.controls
import qs.components.effects
import qs.services
import qs.utils
import "../utilities/cards"

Item {
    id: root

    property string activeBtDeviceName: qsTr("Select Bluetooth...")

    function updateConnectedDeviceName() {
        if (!Bluez.hasAdapter) {
            activeBtDeviceName = qsTr("No Bluetooth adapter");
            return;
        }
        if (Bluez.hardBlocked) {
            activeBtDeviceName = qsTr("Bluetooth hardware blocked");
            return;
        }
        const connectedDevice = [...(Bluetooth.devices?.values ?? [])].find(d => d.connected);
        activeBtDeviceName = connectedDevice ? (connectedDevice.name || connectedDevice.address) : qsTr("Select Bluetooth...");
    }

    anchors.fill: parent
    anchors.margins: Tokens.padding.medium

    Component.onCompleted: {
        updateConnectedDeviceName();
    }

    Connections {
        target: Bluez

        function onHasAdapterChanged() {
            root.updateConnectedDeviceName();
        }

        function onHardBlockedChanged() {
            root.updateConnectedDeviceName();
        }
    }

    Connections {
        function onValuesChanged() {
            root.updateConnectedDeviceName();
        }

        target: Bluetooth.devices
    }

    Repeater {
        model: [...(Bluetooth.devices?.values ?? [])].filter(d => d.bonded || d.paired || d.connected) // qmllint disable unresolved-type

        delegate: Connections {
            function onConnectedChanged() {
                root.updateConnectedDeviceName();
            }

            target: modelData
        }
    }

    StyledFlickable {
        id: view

        anchors.fill: parent
        flickableDirection: Flickable.VerticalFlick
        contentWidth: width
        contentHeight: contentLayout.implicitHeight

        StyledScrollBar.vertical: StyledScrollBar {
            flickable: view
        }

        ColumnLayout {
            id: contentLayout

            width: parent.width
            spacing: Tokens.spacing.medium

            SectionHeader {
                title: qsTr("Connectivity")
            }

            // Wi-Fi Widget
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                SwitchRow {
                    label: qsTr("Wi-Fi")
                    checked: Nmcli.wifiEnabled
                    onToggled: checked => Nmcli.enableWifi(checked)
                }

                // Dropdown Button
                StyledRect {
                    id: wifiDropdownBtn

                    property bool expanded: false

                    Layout.fillWidth: true
                    implicitHeight: dropdownRow.implicitHeight + Tokens.padding.medium * 2
                    radius: Tokens.rounding.medium
                    color: Colours.layer(Colours.palette.m3surfaceContainer, 1)

                    StateLayer {
                        onClicked: wifiDropdownBtn.expanded = !wifiDropdownBtn.expanded
                    }

                    RowLayout {
                        id: dropdownRow

                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium
                        spacing: Tokens.spacing.small

                        MaterialIcon {
                            text: "wifi"
                            color: Nmcli.wifiEnabled ? Colours.palette.m3primary : Colours.palette.m3outline
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: Nmcli.active?.ssid ?? qsTr("Select Wi-Fi Network...")
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                        }

                        MaterialIcon {
                            text: wifiDropdownBtn.expanded ? "expand_less" : "expand_more"
                        }
                    }
                }

                // Expanded network list
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: wifiDropdownBtn.expanded
                    spacing: Tokens.spacing.extraSmall

                    Repeater {
                        model: ScriptModel {
                            values: [...Nmcli.networks].sort((a, b) => b.active - a.active || b.strength - a.strength).slice(0, 5)
                        }

                        delegate: StyledRect {
                            required property var modelData

                            Layout.fillWidth: true
                            implicitHeight: itemRow.implicitHeight + Tokens.padding.small * 2
                            radius: Tokens.rounding.small
                            color: modelData.active ? Colours.palette.m3primaryContainer : Colours.layer(Colours.palette.m3surfaceContainer, 1)

                            StateLayer {
                                onClicked: NetworkConnection.handleConnect(modelData, null, null)
                            }

                            RowLayout {
                                id: itemRow

                                anchors.fill: parent
                                anchors.margins: Tokens.padding.small
                                anchors.leftMargin: Tokens.padding.medium
                                anchors.rightMargin: Tokens.padding.medium
                                spacing: Tokens.spacing.small

                                MaterialIcon {
                                    text: Icons.getNetworkIcon(modelData.strength)
                                    color: modelData.active ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
                                }

                                StyledText {
                                    Layout.fillWidth: true
                                    text: modelData.ssid || qsTr("Unknown SSID")
                                    color: modelData.active ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface
                                    font: Tokens.font.body.small
                                    elide: Text.ElideRight
                                }

                                MaterialIcon {
                                    visible: modelData.isSecure
                                    text: "lock"
                                    color: modelData.active ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
                                    fontStyle: Tokens.font.icon.small
                                }
                            }
                        }
                    }
                }
            }

            // Bluetooth Widget
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                SwitchRow {
                    label: qsTr("Bluetooth")
                    checked: Bluez.enabled
                    enabled: Bluez.hasAdapter && !Bluez.hardBlocked
                    opacity: enabled ? 1 : 0.38
                    onToggled: checked => Bluez.setEnabled(checked)
                }

                // Dropdown Button
                StyledRect {
                    id: btDropdownBtn

                    property bool expanded: false

                    Layout.fillWidth: true
                    implicitHeight: btDropdownRow.implicitHeight + Tokens.padding.medium * 2
                    radius: Tokens.rounding.medium
                    color: Colours.layer(Colours.palette.m3surfaceContainer, 1)
                    opacity: Bluez.hasAdapter && !Bluez.hardBlocked ? 1 : 0.38

                    StateLayer {
                        disabled: !Bluez.hasAdapter || Bluez.hardBlocked
                        onClicked: btDropdownBtn.expanded = !btDropdownBtn.expanded
                    }

                    RowLayout {
                        id: btDropdownRow

                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium
                        spacing: Tokens.spacing.small

                        MaterialIcon {
                            text: "bluetooth"
                            color: Bluez.enabled ? Colours.palette.m3primary : Colours.palette.m3outline
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: root.activeBtDeviceName
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                        }

                        MaterialIcon {
                            text: btDropdownBtn.expanded ? "expand_less" : "expand_more"
                        }
                    }
                }

                // Expanded Bluetooth device list
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: btDropdownBtn.expanded && Bluez.hasAdapter && !Bluez.hardBlocked
                    spacing: Tokens.spacing.extraSmall

                    Repeater {
                        model: ScriptModel {
                            values: [...(Bluetooth.devices?.values ?? [])] // qmllint disable unresolved-type
                                .filter(d => d.bonded || d.paired || d.connected)
                                .sort((a, b) => (b.connected - a.connected) || (a.name || a.address || "").localeCompare(b.name || b.address || ""))
                        }

                        delegate: StyledRect {
                            id: btItem

                            required property BluetoothDevice modelData // qmllint disable unresolved-type
                            readonly property bool isConnected: modelData.connected || modelData.state === BluetoothDeviceState.Connected // qmllint disable unresolved-type
                            readonly property bool loading: modelData.pairing
                                || modelData.state === BluetoothDeviceState.Connecting // qmllint disable unresolved-type
                                || modelData.state === BluetoothDeviceState.Disconnecting // qmllint disable unresolved-type
                                || (Bluez.enabling && (Bluez.pendingConnectDevice === modelData || Bluez.pendingPairDevice === modelData))

                            Layout.fillWidth: true
                            implicitHeight: btItemRow.implicitHeight + Tokens.padding.small * 2
                            radius: Tokens.rounding.small
                            color: btItem.isConnected ? Colours.palette.m3primaryContainer : Colours.layer(Colours.palette.m3surfaceContainer, 1)
                            opacity: modelData.blocked ? 0.45 : 1

                            StateLayer {
                                disabled: btItem.loading || btItem.modelData.blocked
                                onClicked: Bluez.toggleDeviceConnection(btItem.modelData)
                            }

                            RowLayout {
                                id: btItemRow

                                anchors.fill: parent
                                anchors.margins: Tokens.padding.small
                                anchors.leftMargin: Tokens.padding.medium
                                anchors.rightMargin: Tokens.padding.medium
                                spacing: Tokens.spacing.small

                                MaterialIcon {
                                    text: Icons.getBluetoothIcon(btItem.modelData.icon)
                                    color: btItem.isConnected ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
                                }

                                StyledText {
                                    Layout.fillWidth: true
                                    text: (btItem.modelData.name || btItem.modelData.address || qsTr("Unknown Device")) + (btItem.modelData.paired && !btItem.modelData.bonded ? qsTr(" (Temp)") : "")
                                    color: btItem.isConnected ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface
                                    font: Tokens.font.body.small
                                    elide: Text.ElideRight
                                }

                                CircularIndicator {
                                    visible: btItem.loading
                                    running: btItem.loading
                                    implicitSize: 16
                                    strokeWidth: 2
                                }

                                MaterialIcon {
                                    visible: !btItem.loading && btItem.isConnected && btItem.modelData.batteryAvailable
                                    text: Icons.getBatteryIcon(btItem.modelData.battery)
                                    color: btItem.isConnected ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
                                    fontStyle: Tokens.font.icon.small
                                }
                            }
                        }
                    }
                }
            }

            SectionHeader {
                title: qsTr("Display")
            }

            // Screen Temperature Widget
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                SwitchRow {
                    label: qsTr("Screen Temperature")
                    checked: ScreenTemp.active
                    onToggled: checked => ScreenTemp.active = checked
                }

                StyledSlider {
                    visible: ScreenTemp.active
                    Layout.fillWidth: true
                    Layout.topMargin: Tokens.spacing.small
                    Layout.bottomMargin: Tokens.spacing.small
                    Layout.leftMargin: Tokens.padding.medium
                    Layout.rightMargin: Tokens.padding.medium

                    value: ScreenTemp.temperature
                    from: 2500
                    to: 6500
                    onInteraction: v => ScreenTemp.temperature = Math.round(from + v * (to - from))
                }
            }

            SectionHeader {
                title: qsTr("Power")
            }

            IdleInhibit {}

            SectionHeader {
                title: qsTr("Weather")
            }

            // Geocoded Weather Card
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.small

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    StyledInputField {
                        id: weatherSearchInput

                        Layout.fillWidth: true
                        placeholderText: qsTr("Search city...")
                        onEditingFinished: {
                            if (text.trim().length > 0) {
                                Weather.fetchCoordsFromCity(text.trim());
                            }
                        }
                    }

                    IconButton {
                        icon: "search"
                        type: IconButton.Tonal
                        onClicked: {
                            if (weatherSearchInput.text.trim().length > 0) {
                                Weather.fetchCoordsFromCity(weatherSearchInput.text.trim());
                            }
                        }
                    }
                }

                StyledRect {
                    Layout.fillWidth: true
                    implicitHeight: weatherDisplayLayout.implicitHeight + Tokens.padding.medium * 2
                    radius: Tokens.rounding.medium
                    color: Colours.layer(Colours.palette.m3surfaceContainer, 1)

                    RowLayout {
                        id: weatherDisplayLayout

                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium
                        spacing: Tokens.spacing.medium

                        MaterialIcon {
                            text: Weather.icon
                            fontStyle: Tokens.font.icon.large
                            color: Colours.palette.m3primary
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            StyledText {
                                Layout.fillWidth: true
                                text: Weather.city || qsTr("No location")
                                font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
                                elide: Text.ElideRight
                            }

                            StyledText {
                                Layout.fillWidth: true
                                text: Weather.description
                                color: Colours.palette.m3outline
                                font: Tokens.font.label.small
                                elide: Text.ElideRight
                            }
                        }

                        StyledText {
                            text: Weather.temp
                            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
                        }
                    }
                }
            }

        }
    }
}
