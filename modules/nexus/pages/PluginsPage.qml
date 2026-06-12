pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: qsTr("Plugins")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        // 1. Title bar & Scan Action
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall / 2

                StyledText {
                    Layout.fillWidth: true
                    text: PluginManager.scanning ? qsTr("Scanning plugins...") : qsTr("Plugin Management")
                    font: Tokens.font.title.medium
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    text: qsTr("Manage shell plugins and resolve their dependencies.")
                    color: Colours.palette.m3outline
                    font: Tokens.font.label.small
                    wrapMode: Text.WordWrap
                }
            }

            TextButton {
                text: qsTr("Scan")
                type: ButtonBase.Tonal
                disabled: PluginManager.scanning
                onClicked: PluginManager.scan()
            }
        }

        // 2. Global Dependency Resolution Error Banner
        ConnectedRect {
            id: errorBanner
            Layout.fillWidth: true
            visible: !!PluginManager.resolutionError
            color: Colours.palette.m3errorContainer
            implicitHeight: errorText.implicitHeight + Tokens.padding.medium * 2
            first: true
            last: true

            StyledText {
                id: errorText
                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                text: PluginManager.resolutionError
                color: Colours.palette.m3onErrorContainer
                font: Tokens.font.body.medium
                wrapMode: Text.Wrap
            }
        }

        // 3. Plugins List
        ItemList {
            id: pluginsItemList
            showList: PluginManager.pluginsList.length > 0
            placeholderIcon: "extension"
            placeholderText: PluginManager.scanning ? qsTr("Scanning user plugins...") : qsTr("No plugins installed")
            first: true
            last: true

            model: ScriptModel {
                values: PluginManager.pluginsList
            }

            delegate: Item {
                id: itemDelegate
                required property var modelData
                required property int index

                anchors.left: pluginsItemList.list.contentItem.left
                anchors.right: pluginsItemList.list.contentItem.right
                implicitHeight: itemLayout.implicitHeight

                ColumnLayout {
                    id: itemLayout
                    anchors.fill: parent
                    spacing: 0

                    ToggleRow {
                        Layout.fillWidth: true
                        text: itemDelegate.modelData?.name ?? ""
                        subtext: {
                            let ver = itemDelegate.modelData?.version ?? "0.0.0";
                            let auth = itemDelegate.modelData?.author ?? "Unknown";
                            let deps = itemDelegate.modelData?.dependencies || [];
                            let desc = "v" + ver + " • " + qsTr("by") + " " + auth;
                            if (deps.length > 0) {
                                desc += " • " + qsTr("Depends: ") + deps.join(", ");
                            }
                            return desc;
                        }
                        checked: itemDelegate.modelData?.status === "enabled"
                        enabled: itemDelegate.modelData?.status !== "corrupt" && 
                                 itemDelegate.modelData?.status !== "invalid" && 
                                 itemDelegate.modelData?.status !== "error"

                        first: itemDelegate.index === 0
                        last: itemDelegate.index === pluginsItemList.list.count - 1 && !errorContainer.visible

                        onCheckedChanged: {
                            if (checked !== (itemDelegate.modelData?.status === "enabled")) {
                                if (checked) {
                                    PluginManager.enablePlugin(itemDelegate.modelData.id);
                                } else {
                                    PluginManager.disablePlugin(itemDelegate.modelData.id);
                                }
                            }
                        }
                    }

                    // Error Box
                    Rectangle {
                        id: errorContainer
                        Layout.fillWidth: true
                        visible: !!itemDelegate.modelData?.error
                        color: Colours.tPalette.m3errorContainer
                        radius: Tokens.rounding.small
                        Layout.leftMargin: Tokens.padding.largeIncreased
                        Layout.rightMargin: Tokens.padding.largeIncreased
                        Layout.topMargin: Tokens.padding.small
                        Layout.bottomMargin: Tokens.padding.medium
                        implicitHeight: errorLayout.implicitHeight + Tokens.padding.medium * 2

                        ColumnLayout {
                            id: errorLayout
                            anchors.fill: parent
                            anchors.margins: Tokens.padding.medium
                            spacing: Tokens.spacing.extraSmall

                            RowLayout {
                                spacing: Tokens.spacing.small
                                MaterialIcon {
                                    text: "warning"
                                    color: Colours.palette.m3error
                                    font: Tokens.font.icon.small
                                }
                                StyledText {
                                    text: {
                                        let status = itemDelegate.modelData?.status ?? "unknown";
                                        return qsTr("Plugin Error (%1)").arg(status.toUpperCase());
                                    }
                                    font: Tokens.font.title.small
                                    color: Colours.palette.m3onErrorContainer
                                }
                            }

                            StyledText {
                                Layout.fillWidth: true
                                text: itemDelegate.modelData?.error ?? qsTr("Unknown error occurred.")
                                font: Tokens.font.body.small
                                color: Colours.palette.m3onErrorContainer
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }
        }
    }
}
