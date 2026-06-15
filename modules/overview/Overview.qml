pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import qs.components.containers
import qs.components.misc
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
                                    color: Hypr.activeWsId === wsId ? "#223b82f6" : "#1a212124"
                                    border.color: dropArea.containsDrag ? "#3b82f6" : (Hypr.activeWsId === wsId ? "#3b82f6" : "#44ffffff")
                                    border.width: dropArea.containsDrag ? 2 : 1
                                    radius: 12

                                    // Display Workspace Number
                                    Text {
                                        anchors.top: parent.top
                                        anchors.left: parent.left
                                        anchors.margins: 10
                                        text: card.wsId.toString()
                                        color: Hypr.activeWsId === card.wsId ? "#3b82f6" : "#88ffffff"
                                        font.bold: true
                                        font.pixelSize: 16
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
                                                color: dragArea.drag.active ? "#dd3b82f6" : "#66ffffff"
                                                border.color: dragArea.drag.active ? "#3b82f6" : "#88ffffff"
                                                border.width: 1.5
                                                radius: 6

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: thumbnail.title
                                                    color: "white"
                                                    font.pixelSize: 9
                                                    elide: Text.ElideRight
                                                    width: parent.width - 6
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
