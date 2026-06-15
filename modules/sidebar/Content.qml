import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

Item {
    id: rootRange

    required property Props props
    required property DrawerVisibilities visibilities
    required property var utilitiesProps

    property string activeTab: "notifications" // "notifications", "control_center", or "screen_tools"

    ColumnLayout {
        id: layout

        anchors.fill: parent
        spacing: Tokens.spacing.medium

        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: rootRange.activeTab === "notifications" ? parent.height * 0.65 : parent.height

            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainerLow
            clip: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Tab Bar
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: Tokens.padding.medium
                    Layout.leftMargin: Tokens.padding.medium
                    Layout.rightMargin: Tokens.padding.medium
                    spacing: Tokens.spacing.small

                    TextButton {
                        Layout.fillWidth: true
                        text: qsTr("Notifications")
                        type: rootRange.activeTab === "notifications" ? ButtonBase.Filled : ButtonBase.Tonal
                        onClicked: rootRange.activeTab = "notifications"
                    }

                    TextButton {
                        Layout.fillWidth: true
                        text: qsTr("Control Center")
                        type: rootRange.activeTab === "control_center" ? ButtonBase.Filled : ButtonBase.Tonal
                        onClicked: rootRange.activeTab = "control_center"
                    }

                    TextButton {
                        Layout.fillWidth: true
                        text: qsTr("Screen Tools")
                        type: rootRange.activeTab === "screen_tools" ? ButtonBase.Filled : ButtonBase.Tonal
                        onClicked: rootRange.activeTab = "screen_tools"
                    }
                }

                // Tab Content Area
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Loader {
                        id: contentLoader

                        anchors.fill: parent
                        sourceComponent: {
                            if (rootRange.activeTab === "notifications") return notifDockComponent;
                            if (rootRange.activeTab === "control_center") return controlCenterComponent;
                            if (rootRange.activeTab === "screen_tools") return screenToolsComponent;
                            return null;
                        }
                    }
                }
            }

            Component {
                id: notifDockComponent

                NotifDock {
                    props: rootRange.props
                    visibilities: rootRange.visibilities
                }
            }

            Component {
                id: controlCenterComponent

                ControlCenter {}
            }

            Component {
                id: screenToolsComponent

                ScreenTools {
                    props: rootRange.utilitiesProps
                    visibilities: rootRange.visibilities
                }
            }
        }

        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: parent.height * 0.35
            visible: rootRange.activeTab === "notifications"

            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainerLow
            clip: true

            CopilotChat {
                anchors.fill: parent
            }
        }
    }
}

