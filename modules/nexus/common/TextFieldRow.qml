import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.components.filedialog
import qs.services
import qs.utils

ConnectedRect {
    id: root

    property alias label: label.text
    property string subtext
    property alias value: input.text
    property alias placeholderText: input.placeholderText
    property bool showBrowse: false
    property bool selectFolder: false
    signal accepted(string text)

    function parsePathToCwd(path, selectFolder) {
        if (!path) return ["Home"];
        
        let fullPath = path.trim();
        
        if (!selectFolder) {
            const lastSlash = fullPath.lastIndexOf("/");
            if (lastSlash !== -1) {
                fullPath = fullPath.substring(0, lastSlash);
            } else {
                return ["Home"];
            }
        }
        
        if (fullPath.startsWith("~/")) {
            const parts = fullPath.substring(2).split("/").filter(p => p.length > 0);
            return ["Home", ...parts];
        } else if (fullPath === "~") {
            return ["Home"];
        }
        
        const homePath = Paths.home;
        if (homePath && fullPath.startsWith(homePath)) {
            let relative = fullPath.substring(homePath.length);
            if (relative.startsWith("/")) {
                relative = relative.substring(1);
            }
            const parts = relative.split("/").filter(p => p.length > 0);
            return ["Home", ...parts];
        }
        
        if (fullPath.startsWith("/")) {
            const parts = fullPath.split("/").filter(p => p.length > 0);
            return ["", ...parts];
        }
        
        return ["Home"];
    }

    Layout.fillWidth: true
    implicitHeight: rowLayout.implicitHeight + rowLayout.anchors.margins * 2

    MouseArea {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: input.left
        anchors.rightMargin: Tokens.spacing.medium
        cursorShape: Qt.IBeamCursor
        onClicked: input.forceActiveFocus()
    }

    FileDialog {
        id: fileDialog
        title: selectFolder ? qsTr("Select Directory") : qsTr("Select File")
        selectFolder: root.selectFolder
        onAccepted: path => {
            const localPath = Paths.shortenHome(path);
            root.value = localPath;
            root.accepted(localPath);
        }
    }

    RowLayout {
        id: rowLayout

        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        anchors.leftMargin: Tokens.padding.largeIncreased
        anchors.rightMargin: Tokens.padding.largeIncreased
        spacing: Tokens.spacing.medium

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            StyledText {
                id: label

                Layout.fillWidth: true
                font: Tokens.font.body.small
                elide: Text.ElideRight
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.subtext
                text: root.subtext
                color: Colours.palette.m3outline
                font: Tokens.font.label.small
                elide: Text.ElideRight
            }
        }

        StyledTextField {
            id: input

            Layout.preferredWidth: 320
            font: Tokens.font.body.small
            onEditingFinished: root.accepted(text)
        }

        IconButton {
            visible: root.showBrowse
            icon: "folder_open"
            onClicked: {
                fileDialog.cwd = root.parsePathToCwd(root.value, root.selectFolder);
                fileDialog.open();
            }
        }
    }
}
