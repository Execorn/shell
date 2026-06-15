import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

Item {
    id: root

    required property Props props
    required property DrawerVisibilities visibilities

    property string activeTab: "notifications" // "notifications", "control_center", or "screen_tools"

    ColumnLayout {
        id: layout

        anchors.fill: parent
        spacing: Tokens.spacing.medium

        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: root.activeTab === "control_center" ? parent.height : parent.height * 0.65

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
                        type: root.activeTab === "notifications" ? ButtonBase.Filled : ButtonBase.Tonal
                        onClicked: root.activeTab = "notifications"
                    }

                    TextButton {
                        Layout.fillWidth: true
                        text: qsTr("Control Center")
                        type: root.activeTab === "control_center" ? ButtonBase.Filled : ButtonBase.Tonal
                        onClicked: root.activeTab = "control_center"
                    }

                    TextButton {
                        Layout.fillWidth: true
                        text: qsTr("Screen Tools")
                        type: root.activeTab === "screen_tools" ? ButtonBase.Filled : ButtonBase.Tonal
                        onClicked: root.activeTab = "screen_tools"
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
                            if (root.activeTab === "notifications") return notifDockComponent;
                            if (root.activeTab === "control_center") return controlCenterComponent;
                            if (root.activeTab === "screen_tools") return screenToolsComponent;
                            return null;
                        }
                    }
                }
            }

            Component {
                id: notifDockComponent

                NotifDock {
                    props: root.props
                    visibilities: root.visibilities
                }
            }

            Component {
                id: controlCenterComponent

                ControlCenter {}
            }

            Component {
                id: screenToolsComponent

                ScreenTools {}
            }
        }

        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: parent.height * 0.35
            visible: root.activeTab !== "control_center"

            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainerLow
            clip: true

            CopilotChat {
                anchors.fill: parent
            }
        }
    }
}

