import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import qs.modules.nexus
import qs.modules.nexus.common
import qs.modules.nexus.pages
import qs.modules.nexus.pages.apps
import qs.modules.nexus.pages.audio
import qs.modules.nexus.pages.bluetooth
import qs.modules.nexus.pages.network
import qs.modules.nexus.pages.panels
import qs.modules.nexus.pages.services
import qs.modules.nexus.pages.wallandstyle
import qs.modules.nexus.pages.panels.taskbar

QtObject {
    id: root

    readonly property list<Component> pageComps: [
        // Appearance
        Component {
            StackPage {
                pageUrls: [
                    "pages/WallpaperAndStyle.qml",
                    "pages/wallandstyle/WallpaperSelect.qml",
                    "pages/wallandstyle/WallpaperCategory.qml",
                    "pages/wallandstyle/ColourSelect.qml"
                ]
            }
        },

        // Connectivity
        Component {
            StackPage {
                pageUrls: [
                    "pages/DisplayPage.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/NetworkPage.qml",
                    "pages/network/EthernetDetailPage.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/BluetoothPage.qml",
                    "pages/bluetooth/BtDeviceInfo.qml",
                    "pages/bluetooth/BluetoothPairing.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/AudioPage.qml",
                    "pages/audio/AppVolumes.qml"
                ]
            }
        },

        // System
        Component {
            StackPage {
                pageUrls: [
                    "pages/UpdatesPage.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/PluginsPage.qml"
                ]
            }
        },

        // Shell
        Component {
            StackPage {
                pageUrls: [
                    "pages/PanelsPage.qml",
                    "pages/panels/DashboardPanel.qml",
                    "pages/panels/TaskbarPanel.qml",
                    "pages/panels/LauncherPanel.qml",
                    "pages/panels/SidebarPanel.qml",
                    "pages/panels/taskbar/BarWorkspaces.qml",
                    "pages/panels/taskbar/BarActiveWindow.qml",
                    "pages/panels/taskbar/BarTray.qml",
                    "pages/panels/taskbar/BarStatusIcons.qml",
                    "pages/panels/taskbar/BarClock.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/AppsPage.qml",
                    "pages/apps/AllApps.qml",
                    "pages/apps/AppInfo.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/ServicesPage.qml",
                    "pages/services/NotificationsPage.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/LanguageAndRegion.qml"
                ]
            }
        },
        Component {
            StackPage {
                pageUrls: [
                    "pages/PathsPage.qml"
                ]
            }
        },

        // About
        Component {
            StackPage {
                pageUrls: [
                    "pages/AboutPage.qml"
                ]
            }
        }
    ]

    readonly property Component placeholderComp: Component {
        PlaceholderComp {}
    }

    component PlaceholderComp: Item {
        property NexusState nState // To avoid the warning from non-existent property

        ColumnLayout {
            anchors.centerIn: parent
            spacing: Tokens.padding.extraSmall

            MaterialIcon {
                Layout.alignment: Qt.AlignHCenter
                text: "handyman"
                color: Colours.palette.m3outlineVariant
                fontStyle: Tokens.font.icon.extraLarge
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Page under construction")
                color: Colours.palette.m3outlineVariant
                font: Tokens.font.title.large
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("This page will be available in a future update.")
                color: Colours.palette.m3outlineVariant
                font: Tokens.font.body.large
            }
        }
    }
}
