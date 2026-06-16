import QtQuick
import QtQuick.Layouts
import Caelestia
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
    property string value
    property alias placeholderText: input.placeholderText
    property bool showBrowse: false
    property bool selectFolder: false
    signal accepted(string text)

    readonly property bool isValid: {
        const text = input.text.trim();
        if (!text) return true;
        if (typeof CUtils === "undefined" || CUtils === null) return true;
        const absPath = Paths.absolutePath(text);
        if (selectFolder) {
            return CUtils.dirExists(absPath);
        } else {
            return CUtils.fileExists(absPath);
        }
    }

    readonly property bool showError: !isValid && !input.activeFocus

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

    FileDialog {
        id: fileDialog
        title: selectFolder ? qsTr("Select Directory") : qsTr("Select File")
        selectFolder: root.selectFolder
        onAccepted: path => {
            const localPath = Paths.shortenHome(path);
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

        Item {
            id: labelWrapper

            Layout.fillWidth: true
            implicitHeight: colLayout.implicitHeight
            Layout.alignment: Qt.AlignVCenter

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.IBeamCursor
                onClicked: input.forceActiveFocus()
            }

            ColumnLayout {
                id: colLayout

                anchors.fill: parent
                spacing: 0

                StyledText {
                    id: label

                    Layout.fillWidth: true
                    font: Tokens.font.body.small
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    visible: root.subtext || root.showError
                    text: root.showError ? (root.selectFolder ? qsTr("Directory does not exist or is invalid") : qsTr("File does not exist or is invalid")) : root.subtext
                    color: root.showError ? Colours.palette.m3error : Colours.palette.m3outline
                    font: Tokens.font.label.small
                    elide: Text.ElideRight
                }
            }
        }

        StyledTextField {
            id: input

            Layout.preferredWidth: 320
            font: Tokens.font.body.small
            color: root.showError ? Colours.palette.m3error : Colours.palette.m3onSurface
            onEditingFinished: root.accepted(text)

            Binding {
                target: input
                property: "text"
                value: root.value
                when: !input.activeFocus
            }
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
