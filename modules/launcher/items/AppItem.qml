import QtQuick
import Quickshell
import Quickshell.Widgets
import Caelestia.Config
import qs.components
import qs.services
import qs.utils
import qs.modules.launcher.services

Item {
    id: root

    required property DesktopEntry modelData
    required property DrawerVisibilities visibilities

    readonly property bool isX11Only: {
        if (!modelData) return false;
        const id = (modelData.id || "").toLowerCase();
        const name = (modelData.name || "").toLowerCase();
        const exec = (modelData.execString || "").toLowerCase();
        
        const x11Ids = [
            "arandr", "lxappearance", "gpick", "picom", "compton", "feh", 
            "redshift", "rofi", "wpgtk", "xterm", "uxterm", "simplescreenrecorder",
            "nvidia-settings"
        ];
        
        for (var i = 0; i < x11Ids.length; i++) {
            if (id.indexOf(x11Ids[i]) !== -1 || name.indexOf(x11Ids[i]) !== -1 || exec.indexOf(x11Ids[i]) !== -1) {
                return true;
            }
        }
        
        if (id.startsWith("xfce") && (id.indexOf("settings") !== -1 || id.indexOf("display") !== -1 || id.indexOf("keyboard") !== -1 || id.indexOf("mouse") !== -1 || id.indexOf("color") !== -1 || id.indexOf("mime") !== -1)) {
            return true;
        }
        
        return false;
    }

    implicitHeight: Tokens.sizes.launcher.itemHeight

    anchors.left: parent?.left
    anchors.right: parent?.right

    StateLayer {
        radius: Tokens.rounding.large
        onClicked: {
            Apps.launch(root.modelData);
            root.visibilities.launcher = false;
        }
    }

    Item {
        anchors.fill: parent
        anchors.leftMargin: Tokens.padding.medium
        anchors.rightMargin: Tokens.padding.medium
        anchors.margins: Tokens.padding.small

        IconImage {
            id: icon

            asynchronous: true
            source: Quickshell.iconPath(root.modelData?.icon, "image-missing")
            implicitSize: parent.height * 0.8

            anchors.verticalCenter: parent.verticalCenter
        }

        Item {
            anchors.left: icon.right
            anchors.leftMargin: Tokens.spacing.medium
            anchors.verticalCenter: icon.verticalCenter

            implicitWidth: parent.width - icon.width - favouriteIcon.width
            implicitHeight: nameRow.implicitHeight + comment.implicitHeight

            Row {
                id: nameRow
                spacing: Tokens.spacing.small
                width: parent.width

                StyledText {
                    id: name
                    text: root.modelData?.name ?? ""
                    font: Tokens.font.body.medium
                }

                StyledText {
                    visible: root.isX11Only
                    text: qsTr("X11 only")
                    font: Tokens.font.body.builders.small.weight(Font.Bold).build()
                    color: Colours.palette.m3error
                    anchors.verticalCenter: name.verticalCenter
                }
            }

            StyledText {
                id: comment

                text: (root.modelData?.comment || root.modelData?.genericName || root.modelData?.name) ?? ""
                font: Tokens.font.body.small
                color: Colours.palette.m3outline

                elide: Text.ElideRight
                width: root.width - icon.width - favouriteIcon.width - Tokens.rounding.extraLargeIncreased

                anchors.top: nameRow.bottom
            }
        }

        Loader {
            id: favouriteIcon

            asynchronous: true
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            active: root.modelData && Strings.testRegexList(GlobalConfig.launcher.favouriteApps, root.modelData.id)

            sourceComponent: MaterialIcon {
                text: "favorite"
                fill: 1
                color: Colours.palette.m3primary
            }
        }
    }
}
