import QtQuick
import QtQuick.Layouts
import Quickshell
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: qsTr("System Paths & Scripts")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        // Screenshot Utilities
        SectionHeader {
            first: true
            text: qsTr("Screenshot Utilities")
        }

        TextFieldRow {
            Layout.fillWidth: true
            first: true
            label: qsTr("Screenshot Helper Script")
            subtext: qsTr("Path to bash script handling screenshots")
            value: (GlobalConfig.paths && GlobalConfig.paths.screenshotHelper) || ""
            placeholderText: "/home/execorn/scripts/screenshot_helper.sh"
            showBrowse: true
            onAccepted: text => GlobalConfig.paths.screenshotHelper = text
        }

        TextFieldRow {
            Layout.fillWidth: true
            last: true
            label: qsTr("Screenshot Storage Directory")
            subtext: qsTr("Folder where captured images are saved")
            value: (GlobalConfig.paths && GlobalConfig.paths.screenshotDir) || ""
            placeholderText: "~/Pictures/Screenshots"
            showBrowse: true
            selectFolder: true
            onAccepted: text => GlobalConfig.paths.screenshotDir = text
        }

        // Audio & Screen Recording
        SectionHeader {
            text: qsTr("Media & Audio")
        }

        TextFieldRow {
            Layout.fillWidth: true
            first: true
            label: qsTr("Equalizer Script")
            subtext: qsTr("Path to python equalizer control script")
            value: (GlobalConfig.paths && GlobalConfig.paths.eqControlScript) || ""
            placeholderText: "/home/execorn/scripts/eq-control.py"
            showBrowse: true
            onAccepted: text => GlobalConfig.paths.eqControlScript = text
        }

        TextFieldRow {
            Layout.fillWidth: true
            label: qsTr("Equalizer Presets Directory")
            subtext: qsTr("Folder where parametric EQ presets are stored")
            value: (GlobalConfig.paths && GlobalConfig.paths.eqPresetsDir) || ""
            placeholderText: "~/.config/pipewire/eq-presets"
            showBrowse: true
            selectFolder: true
            onAccepted: text => GlobalConfig.paths.eqPresetsDir = text
        }

        TextFieldRow {
            Layout.fillWidth: true
            last: true
            label: qsTr("Screen Recordings Directory")
            subtext: qsTr("Folder where video recordings are stored")
            value: (GlobalConfig.paths && GlobalConfig.paths.recordingDir) || ""
            placeholderText: "~/Videos/Recordings"
            showBrowse: true
            selectFolder: true
            onAccepted: text => GlobalConfig.paths.recordingDir = text
        }

        // Cheatsheet & Keyboard
        SectionHeader {
            text: qsTr("Cheatsheet Utilities")
        }

        TextFieldRow {
            Layout.fillWidth: true
            first: true
            last: true
            label: qsTr("Keybinds Parser Script")
            subtext: qsTr("Python script parsing active window manager shortcuts")
            value: (GlobalConfig.paths && GlobalConfig.paths.cheatsheetParser) || ""
            placeholderText: "/home/execorn/teamwork_projects/hyprland_cheat_sheet/parser/parse_keybinds.py"
            showBrowse: true
            onAccepted: text => GlobalConfig.paths.cheatsheetParser = text
        }
    }
}
