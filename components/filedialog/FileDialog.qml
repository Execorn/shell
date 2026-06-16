pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.components
import qs.services
import qs.utils

LazyLoader {
    id: loader

    property list<string> cwd: ["Home"]
    property string filterLabel: "All files"
    property list<string> filters: ["*"]
    property string title: qsTr("Select a file")
    property bool selectFolder: false

    signal accepted(path: string)
    signal rejected

    function open(): void {
        activeAsync = true;
    }

    function close(): void {
        rejected();
    }

    onAccepted: activeAsync = false
    onRejected: activeAsync = false

    FloatingWindow {
        id: root

        property list<string> cwd: loader.cwd
        property string filterLabel: loader.filterLabel
        property list<string> filters: loader.filters
        property bool selectFolder: loader.selectFolder

        readonly property string currentFolder: {
            if (cwd[0] === "Home") {
                return Paths.home + (cwd.length > 1 ? `/${cwd.slice(1).join("/")}` : "");
            } else {
                return cwd.join("/");
            }
        }

        readonly property bool selectionValid: {
            if (selectFolder) {
                return true;
            }
            const file = folderContents.currentItem?.modelData;
            return (file && !file.isDir && (filters.includes("*") || filters.includes(file.suffix))) ?? false;
        }

        function acceptSelection(): void {
            if (selectFolder) {
                const file = folderContents.currentItem?.modelData;
                if (file && file.isDir) {
                    accepted(file.path);
                } else {
                    accepted(currentFolder);
                }
            } else {
                if (selectionValid) {
                    accepted(folderContents.currentItem.modelData.path);
                }
            }
        }

        function accepted(path: string): void {
            loader.accepted(path);
        }

        function rejected(): void {
            loader.rejected();
        }

        implicitWidth: 1000
        implicitHeight: 600
        minimumSize.width: 400
        minimumSize.height: 300
        color: Colours.tPalette.m3surface
        surfaceFormat.opaque: false
        title: loader.title

        onVisibleChanged: {
            if (!visible)
                rejected();
        }

        RowLayout {
            anchors.fill: parent

            spacing: 0

            Sidebar {
                Layout.fillHeight: true
                dialog: root
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true

                spacing: 0

                HeaderBar {
                    Layout.fillWidth: true
                    dialog: root
                }

                FolderContents {
                    id: folderContents

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    dialog: root
                }

                DialogButtons {
                    Layout.fillWidth: true
                    dialog: root
                    folder: folderContents
                }
            }
        }

        Behavior on color {
            CAnim {}
        }
    }
}
