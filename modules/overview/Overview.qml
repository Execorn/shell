pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import Quickshell.Wayland
import Quickshell.Io
import qs.components
import qs.components.containers
import qs.components.misc
import qs.components.effects
import qs.services

Scope {
    id: root
    objectName: "overviewRoot"

    property alias active: loader.active

    // Helper functions for programmatic triggers and testing
    function dragAndDropWindow(addr, wsId) {
        let target = addr;
        // Check if it looks like a hex address
        if (typeof addr === "string") {
            if (/^[0-9a-fA-F]+$/.test(addr)) {
                target = "address:0x" + addr;
            } else if (addr.indexOf("0x") === 0) {
                target = "address:" + addr;
            }
        }
        Hypr.dispatch("movetoworkspace " + wsId + "," + target);
    }

    function clickCard(wsId) {
        Hypr.dispatch("workspace " + wsId);
        root.active = false;
    }

    LazyLoader {
        id: loader
        objectName: "loader"
        active: false

        Variants {
            model: Screens.screens

            StyledWindow {
                id: win
                objectName: "window"

                required property var modelData
                screen: modelData

                name: "overview"
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                // Fullscreen Overlay Background
                Rectangle {
                    anchors.fill: parent
                    color: "#e60c0c0e" // Elegant dark translucent overlay

                    // Tap/Click background to close the overview
                    TapHandler {
                        onTapped: root.active = false
                    }

                    // Main centering container for cards
                    Rectangle {
                        anchors.centerIn: parent
                        width: grid.width + 40
                        height: grid.height + 40
                        color: "#1a212124"
                        border.color: "#33ffffff"
                        border.width: 1
                        radius: 16

                        Grid {
                            id: grid
                            anchors.centerIn: parent
                            columns: 5
                            spacing: 20

                            readonly property real cardWidth: win.screen ? win.screen.width * 0.15 : 288
                            readonly property real cardHeight: win.screen ? win.screen.height * 0.15 : 162

                            Repeater {
                                model: 10 // Workspaces 1-10
                                Component.onCompleted: console.log("REPEATER completed, count:", count)

                                delegate: Rectangle {
                                    id: card
                                    objectName: "workspaceCard"
                                    required property int index
                                    readonly property int wsId: index + 1
                                    Component.onCompleted: console.log("CARD delegate completed, wsId:", wsId)
                                    width: grid.cardWidth
                                    height: grid.cardHeight
                                    color: Hypr.activeWsId === wsId ? Colours.layer(Colours.palette.m3primaryContainer, 1) : Colours.layer(Colours.palette.m3surfaceContainerLow, 1)
                                    border.color: dropArea.containsDrag ? Colours.palette.m3primary : (Hypr.activeWsId === wsId ? Colours.palette.m3primary : Colours.palette.m3outlineVariant)
                                    border.width: (dropArea.containsDrag || Hypr.activeWsId === wsId) ? 2 : 1
                                    radius: 12

                                    readonly property int windowCount: Hypr.toplevels.values.filter(c => c && c.workspace && c.workspace.id === card.wsId).length

                                    // Display Workspace Number
                                    Text {
                                        anchors.top: parent.top
                                        anchors.left: parent.left
                                        anchors.margins: 10
                                        text: card.wsId.toString()
                                        color: Hypr.activeWsId === card.wsId ? Colours.palette.m3primary : Colours.palette.m3outline
                                        font.bold: true
                                        font.pixelSize: 16
                                    }

                                    // Display Window Count
                                    RowLayout {
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 10
                                        spacing: 4
                                        visible: card.windowCount > 0

                                        MaterialIcon {
                                            text: "content_copy"
                                            color: Colours.palette.m3outline
                                            fontStyle: Tokens.font.icon.small
                                        }

                                        StyledText {
                                            text: card.windowCount.toString()
                                            color: Colours.palette.m3outline
                                            font: Tokens.font.body.small
                                        }
                                    }

                                    // Empty Placeholder
                                    Text {
                                        anchors.centerIn: parent
                                        text: qsTr("Empty Workspace")
                                        color: Colours.palette.m3outline
                                        font.pixelSize: 11
                                        font.italic: true
                                        visible: card.windowCount === 0
                                    }

                                    // Drop Area for workspace window drag-n-drop
                                    DropArea {
                                        id: dropArea
                                        objectName: "dropArea"
                                        anchors.fill: parent
                                        keys: ["window"]

                                        onDropped: (drop) => {
                                            if (drop.source && drop.source.address) {
                                                root.dragAndDropWindow(drop.source.address, card.wsId);
                                            }
                                        }
                                    }

                                    // Clicking a workspace card switches to it and closes the overview overlay
                                    MouseArea {
                                        objectName: "cardMouseArea"
                                        anchors.fill: parent
                                        onClicked: {
                                            root.clickCard(card.wsId);
                                        }
                                    }

                                    // Render Window Thumbnails
                                    Repeater {
                                        model: Hypr.toplevels.values.filter(c => c && c.workspace && c.workspace.id === card.wsId)

                                        delegate: Item {
                                            id: thumbnail
                                            objectName: "windowThumbnail"
                                            required property var modelData

                                            readonly property real scaleX: win.screen ? (modelData.lastIpcObject?.at?.[0] - win.screen.x) * (grid.cardWidth / win.screen.width) : 0
                                            readonly property real scaleY: win.screen ? (modelData.lastIpcObject?.at?.[1] - win.screen.y) * (grid.cardHeight / win.screen.height) : 0
                                            readonly property real scaleW: win.screen ? (modelData.lastIpcObject?.size?.[0]) * (grid.cardWidth / win.screen.width) : 0
                                            readonly property real scaleH: win.screen ? (modelData.lastIpcObject?.size?.[1]) * (grid.cardHeight / win.screen.height) : 0

                                            x: scaleX
                                            y: scaleY
                                            width: Math.max(scaleW, 16)
                                            height: Math.max(scaleH, 16)
                                            z: dragArea.drag.active ? 100 : 1

                                            readonly property string address: modelData.address || (modelData.lastIpcObject?.address ?? "")
                                            readonly property string title: modelData.title || (modelData.lastIpcObject?.title ?? "")

                                            Rectangle {
                                                id: visualRect
                                                width: parent.width
                                                height: parent.height
                                                color: dragArea.drag.active 
                                                    ? Colours.layer(Colours.palette.m3primaryContainer, 3)
                                                    : (dragArea.containsMouse ? Colours.layer(Colours.palette.m3surfaceVariant, 4) : Colours.layer(Colours.palette.m3surfaceVariant, 1))
                                                opacity: dragArea.drag.active ? 0.95 : 0.8
                                                border.color: dragArea.drag.active 
                                                    ? Colours.palette.m3primary 
                                                    : (dragArea.containsMouse ? Colours.palette.m3primary : Colours.palette.m3outline)
                                                border.width: (dragArea.drag.active || dragArea.containsMouse) ? 2 : 1
                                                radius: 8

                                                // Scaling on Hover
                                                scale: dragArea.containsMouse ? 1.05 : 1.0
                                                Behavior on scale {
                                                    NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
                                                }
                                                Behavior on border.color {
                                                    ColorAnimation { duration: 150 }
                                                }
                                                Behavior on color {
                                                    ColorAnimation { duration: 150 }
                                                }

                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    anchors.margins: 4
                                                    spacing: 2

                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 4
                                                        Layout.alignment: Qt.AlignTop

                                                        IconImage {
                                                            asynchronous: true
                                                            source: Quickshell.iconPath(modelData.lastIpcObject?.class?.toLowerCase() ?? "", "application-x-executable")
                                                            Layout.preferredWidth: Math.min(parent.height * 0.8, 14)
                                                            Layout.preferredHeight: Layout.preferredWidth
                                                            Layout.alignment: Qt.AlignVCenter
                                                        }

                                                        Text {
                                                            Layout.fillWidth: true
                                                            text: modelData.lastIpcObject?.class ?? "App"
                                                            color: Colours.palette.m3onSurfaceVariant
                                                            font.pixelSize: 8
                                                            font.bold: true
                                                            elide: Text.ElideRight
                                                            visible: parent.width > 35 && parent.height > 12
                                                        }
                                                    }

                                                    Text {
                                                        Layout.fillWidth: true
                                                        Layout.fillHeight: true
                                                        text: thumbnail.title
                                                        color: Colours.palette.m3onSurface
                                                        font.pixelSize: 8
                                                        wrapMode: Text.WordWrap
                                                        elide: Text.ElideRight
                                                        visible: parent.width > 50 && parent.height > 25
                                                    }
                                                }
                                            }

                                            // Hover title bubble
                                            Rectangle {
                                                id: hoverBubble
                                                visible: dragArea.containsMouse && thumbnail.title !== ""
                                                anchors.bottom: visualRect.top
                                                anchors.horizontalCenter: visualRect.horizontalCenter
                                                anchors.bottomMargin: 6
                                                width: hoverText.implicitWidth + 12
                                                height: hoverText.implicitHeight + 6
                                                color: Colours.palette.m3surfaceContainerHighest
                                                border.color: Colours.palette.m3primary
                                                border.width: 1
                                                radius: 6
                                                z: 99

                                                Text {
                                                    id: hoverText
                                                    anchors.centerIn: parent
                                                    text: thumbnail.title
                                                    color: Colours.palette.m3onSurface
                                                    font.pixelSize: 9
                                                    font.bold: true
                                                    elide: Text.ElideRight
                                                    horizontalAlignment: Text.AlignHCenter
                                                }
                                            }

                                            Drag.active: dragArea.drag.active
                                            Drag.keys: ["window"]
                                            Drag.hotSpot.x: width / 2
                                            Drag.hotSpot.y: height / 2

                                            MouseArea {
                                                id: dragArea
                                                objectName: "dragMouseArea"
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                drag.target: visualRect

                                                onPressed: {
                                                    visualRect.anchors.fill = undefined;
                                                }

                                                onReleased: {
                                                     visualRect.x = 0;
                                                     visualRect.y = 0;
                                                     visualRect.anchors.fill = parent;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Keyboard trigger shortcut targeting "overview"
    // qmllint disable unresolved-type
    CustomShortcut {
        id: shortcut
        objectName: "shortcut"
        // qmllint enable unresolved-type
        name: "overview"
        description: "Toggle workspace overview"
        onPressed: {
            root.active = !root.active;
        }
    }

    // IPC Command Handler targeting "overview"
    IpcHandler {
        id: ipcHandler
        objectName: "ipcHandler"
        target: "overview"

        function toggle(): void {
            root.active = !root.active;
        }

        function open(): void {
            root.active = true;
        }

        function close(): void {
            root.active = false;
        }
    }
}
