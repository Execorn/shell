pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Caelestia.Config
import qs.components
import qs.services
import qs.utils
import Quickshell.Widgets

ColumnLayout {
    id: root

    required property int index
    required property int activeWsId
    required property var occupied
    required property int groupOffset

    visible: root.isOccupied || root.activeWsId === root.ws

    readonly property bool isWorkspace: true // Flag for finding workspace children
    // Unanimated prop for others to use as reference
    readonly property int size: implicitHeight + (hasWindows ? Tokens.padding.extraSmall : 0)

    readonly property int ws: groupOffset + index + 1
    readonly property bool isOccupied: occupied[ws] ?? false
    readonly property bool hasWindows: isOccupied && Config.bar.workspaces.showWindows

    Layout.alignment: Qt.AlignHCenter
    Layout.preferredHeight: size

    spacing: 4

    StyledText {
        id: wsNum
        Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
        Layout.preferredHeight: Tokens.sizes.bar.innerWidth / 2

        text: root.ws.toString()
        color: root.activeWsId === root.ws && Config.bar.workspaces.activeIndicator ? Colours.palette.m3onPrimary : (Config.bar.workspaces.occupiedBg || root.isOccupied ? Colours.palette.m3onSurface : Colours.layer(Colours.palette.m3outlineVariant, 2))
        font.family: Tokens.font.workspaces
        verticalAlignment: Qt.AlignVCenter
    }

    IconImage {
        id: wsIcon
        asynchronous: true
        Layout.alignment: Qt.AlignHCenter
        visible: root.isOccupied
        width: 22
        height: 22
        source: {
            if (root.isOccupied) {
                const windows = Hypr.toplevels.values.filter(c => c.workspace?.id === root.ws);
                if (windows.length > 0) {
                    return Icons.getAppIcon(windows[0].lastIpcObject.class, "image-missing");
                }
            }
            return "";
        }
    }

    Loader {
        id: windows

        asynchronous: true

        Layout.alignment: Qt.AlignHCenter
        Layout.fillHeight: true
        Layout.topMargin: -Tokens.sizes.bar.innerWidth / 10

        visible: active
        active: false

        sourceComponent: Column {
            spacing: 0

            add: Transition {
                Anim {
                    properties: "scale"
                    from: 0
                    to: 1
                    easing: Tokens.anim.standardDecel
                }
            }

            move: Transition {
                Anim {
                    properties: "scale"
                    to: 1
                    easing: Tokens.anim.standardDecel
                }
                Anim {
                    properties: "x,y"
                }
            }

            Repeater {
                model: ScriptModel {
                    values: {
                        const ws = root.ws;
                        const windows = Hypr.toplevels.values.filter(c => c.workspace?.id === ws);
                        const maxIcons = root.Config.bar.workspaces.maxWindowIcons;
                        return maxIcons > 0 ? windows.slice(0, maxIcons) : windows;
                    }
                }

                MaterialIcon {
                    required property var modelData

                    grade: 0
                    text: Icons.getAppCategoryIcon(modelData.lastIpcObject.class, "terminal")
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }

    Behavior on Layout.preferredHeight {
        Anim {}
    }
}
