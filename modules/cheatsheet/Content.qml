pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Caelestia
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.utils

StyledRect {
    id: root

    required property DrawerVisibilities visibilities

    color: Colours.tPalette.m3surface
    radius: Tokens.rounding.extraLarge
    border.color: Colours.tPalette.m3outlineVariant
    border.width: 1

    focus: true
    activeFocusOnTab: true

    property var sectionsModel: []
    property int currentSectionIndex: 0
    property string searchText: ""

    onSectionsModelChanged: {
        if (Array.isArray(sectionsModel) && sectionsModel.length > 0) {
            if (currentSectionIndex >= sectionsModel.length) {
                currentSectionIndex = Math.max(0, sectionsModel.length - 1);
            }
        } else {
            currentSectionIndex = 0;
        }
    }

    Component.onCompleted: {
        root.forceActiveFocus();
        if (root.visibilities && root.visibilities.cheatsheet) {
            parseProcess.running = true;
        }
    }

    function getSectionIcon(section) {
        const sec = (section || "").toLowerCase();
        if (sec.includes("system")) return "settings";
        if (sec.includes("window")) return "grid_view";
        if (sec.includes("app")) return "apps";
        if (sec.includes("util")) return "build";
        if (sec.includes("shell")) return "terminal";
        return "keyboard";
    }

    function getCategoryIcon(category) {
        const cat = (category || "").toLowerCase();
        if (cat.includes("window")) return "grid_view";
        if (cat.includes("launcher")) return "search";
        if (cat.includes("session") || cat.includes("lock") || cat.includes("sleep")) return "power_settings_new";
        if (cat.includes("brightness")) return "brightness_6";
        if (cat.includes("media")) return "play_circle_filled";
        if (cat.includes("volume")) return "volume_up";
        if (cat.includes("workspace")) return "tab";
        if (cat.includes("group")) return "group_work";
        if (cat.includes("action")) return "touch_app";
        if (cat.includes("resize")) return "photo_size_select_small";
        if (cat.includes("app")) return "open_in_new";
        if (cat.includes("util")) return "construction";
        if (cat.includes("clipboard")) return "assignment";
        if (cat.includes("testing")) return "bug_report";
        if (cat.includes("cheatsheet")) return "help_outline";
        return "label";
    }

    readonly property bool isSearching: root.searchText.length > 0

    readonly property var searchResults: {
        if (!isSearching) return [];
        let results = [];
        const query = root.searchText;
        for (const sec of root.sectionsModel) {
            if (!sec.categories) continue;
            for (const cat of sec.categories) {
                if (!cat.keybinds) continue;
                for (const kb of cat.keybinds) {
                    const descMatch = (kb.desc || "").toLowerCase().includes(query);
                    const actionMatch = (kb.action || "").toLowerCase().includes(query);
                    const keyMatch = (kb.key || "").toLowerCase().includes(query);
                    const modsMatch = kb.mods && Array.isArray(kb.mods) && kb.mods.some(m => m.toLowerCase().includes(query));
                    
                    if (descMatch || actionMatch || keyMatch || modsMatch) {
                        results.push({
                            section: sec.section,
                            category: cat.category,
                            desc: kb.desc,
                            action: kb.action,
                            mods: kb.mods || [],
                            key: kb.key || "",
                            notInstalled: kb.notInstalled || false,
                            appName: kb.appName || ""
                        });
                    }
                }
            }
        }
        return results;
    }

    function executeAction(action, notInstalled, appName) {
        if (notInstalled) {
            Toaster.toast(qsTr("Package Not Installed"), qsTr("Package \"%1\" is not installed.").arg(appName || "unknown"), "error", Toast.Error);
            return;
        }
        
        const act = action.trim();
        if (act.startsWith("exec ")) {
            const cmd = act.substring(5).trim();
            Quickshell.execDetached(["sh", "-c", cmd]);
        } else {
            const dispatcher = act.replace(/,\s*/, " ");
            Hypr.dispatch(dispatcher);
        }
        root.visibilities.cheatsheet = false;
    }

    FileView {
        id: keybindsFile
        path: `${Paths.state}/keybinds.json`
        watchChanges: true
        
        onFileChanged: reload()
        onLoaded: {
            try {
                let parsed = JSON.parse(text());
                if (Array.isArray(parsed)) {
                    root.sectionsModel = parsed;
                } else {
                    root.sectionsModel = [];
                }
            } catch (e) {
                console.error("Error parsing keybinds.json: ", e);
                root.sectionsModel = [];
            }
        }
        onLoadFailed: {
            root.sectionsModel = [];
        }
    }

    Process {
        id: parseProcess
        command: ["python3", Paths.cheatsheetParser]
        running: false
        stdout: StdioCollector {
            onStreamFinished: console.log("parser stdout:", text)
        }
        stderr: StdioCollector {
            onStreamFinished: console.log("parser stderr:", text)
        }
        onExited: (code) => {
            console.log("parser exited with code:", code)
        }
    }

    Connections {
        function onCheatsheetChanged(): void {
            if (root.visibilities.cheatsheet) {
                searchInput.text = "";
                searchInput.forceActiveFocus();
                parseProcess.running = true;
            }
        }
        target: root.visibilities
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            MaterialIcon {
                text: "keyboard"
                fontStyle: Tokens.font.icon.large
                color: Colours.palette.m3primary
            }

            StyledText {
                text: qsTr("Keybindings Cheatsheet")
                font: Tokens.font.title.large
                color: Colours.palette.m3onSurface
                Layout.fillWidth: true
            }

            StyledTextField {
                id: searchInput
                placeholderText: qsTr("Search shortcuts...")
                Layout.preferredWidth: 260
                
                onTextChanged: {
                    root.searchText = text.trim().toLowerCase();
                }

                Keys.onEscapePressed: {
                    if (text !== "") {
                        text = "";
                    } else {
                        root.visibilities.cheatsheet = false;
                    }
                }

                Component.onCompleted: forceActiveFocus()
            }

            IconButton {
                icon: "close"
                onClicked: root.visibilities.cheatsheet = false
            }
        }

        StyledRect {
            Layout.fillWidth: true
            height: 1
            color: Colours.tPalette.m3outlineVariant
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Tokens.spacing.large

            ListView {
                id: sectionsList
                Layout.preferredWidth: 200
                Layout.fillHeight: true
                clip: true
                visible: !root.isSearching
                model: root.sectionsModel
                spacing: Tokens.spacing.extraSmall
                
                delegate: Item {
                    required property var modelData
                    required property int index

                    width: sectionsList.width - Tokens.padding.small
                    height: 40
                    
                    StyledRect {
                        anchors.fill: parent
                        radius: Tokens.rounding.medium
                        color: index === root.currentSectionIndex ? Colours.tPalette.m3primaryContainer : "transparent"
                        
                        StateLayer {
                            radius: Tokens.rounding.medium
                            onClicked: {
                                root.currentSectionIndex = index;
                            }
                        }
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Tokens.padding.medium
                            anchors.rightMargin: Tokens.padding.medium
                            spacing: Tokens.spacing.small
                            
                            MaterialIcon {
                                text: root.getSectionIcon(modelData.section)
                                fontStyle: Tokens.font.icon.medium
                                color: index === root.currentSectionIndex ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
                            }

                            StyledText {
                                text: modelData.section
                                font: index === root.currentSectionIndex ? Tokens.font.title.builders.small.weight(Font.Bold).build() : Tokens.font.body.medium
                                color: index === root.currentSectionIndex ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
                
                StyledScrollBar.vertical: StyledScrollBar {
                    flickable: sectionsList
                }
            }

            StyledRect {
                Layout.fillHeight: true
                width: 1
                color: Colours.tPalette.m3outlineVariant
                visible: !root.isSearching
            }

            ListView {
                id: rightPaneList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: Tokens.spacing.medium
                
                model: root.isSearching ? root.searchResults : (root.sectionsModel[root.currentSectionIndex] ? root.sectionsModel[root.currentSectionIndex].categories : [])
                
                delegate: Loader {
                    id: delegateLoader
                    width: rightPaneList.width - Tokens.padding.medium
                    height: item ? item.height : 0
                    
                    required property var modelData
                    required property int index
                    
                    sourceComponent: root.isSearching ? searchItemDelegate : categoryDelegate
                }
                
                StyledScrollBar.vertical: StyledScrollBar {
                    flickable: rightPaneList
                }
            }
        }
    }

    Component {
        id: categoryDelegate

        ColumnLayout {
            id: categoryLayout
            property var modelData: parent ? parent.modelData : null
            property int index: parent ? parent.index : -1

            width: parent ? parent.width : 0
            height: implicitHeight
            spacing: Tokens.spacing.small

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.small

                MaterialIcon {
                    text: root.getCategoryIcon(categoryLayout.modelData.category)
                    fontStyle: Tokens.font.icon.small
                    color: Colours.palette.m3primary
                }

                StyledText {
                    text: categoryLayout.modelData.category || ""
                    font: Tokens.font.title.builders.small.weight(Font.Bold).build()
                    color: Colours.palette.m3primary
                    Layout.fillWidth: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                Repeater {
                    model: categoryLayout.modelData.keybinds || []

                    delegate: StyledRect {
                        id: keybindRow
                        required property var modelData
                        required property int index

                        Layout.fillWidth: true
                        height: implicitHeight
                        implicitHeight: Math.max(40, rowLayout.implicitHeight + Tokens.padding.small * 2)

                        color: Colours.tPalette.m3surfaceContainer
                        radius: Tokens.rounding.medium
                        border.color: Colours.tPalette.m3outlineVariant
                        border.width: 1

                        StateLayer {
                            radius: Tokens.rounding.medium
                            onClicked: {
                                root.executeAction(keybindRow.modelData.action, keybindRow.modelData.notInstalled, keybindRow.modelData.appName);
                            }
                        }

                        RowLayout {
                            id: rowLayout
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: Tokens.padding.medium
                            anchors.rightMargin: Tokens.padding.medium
                            spacing: Tokens.spacing.medium

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Tokens.spacing.small

                                StyledText {
                                    text: keybindRow.modelData.desc || keybindRow.modelData.action || ""
                                    font: Tokens.font.body.medium
                                    color: (keybindRow.modelData && keybindRow.modelData.notInstalled) ? Colours.palette.m3error : Colours.palette.m3onSurface
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                StyledText {
                                    visible: (keybindRow.modelData && keybindRow.modelData.notInstalled) || false
                                    text: qsTr("not installed")
                                    font: Tokens.font.body.builders.small.weight(Font.Bold).build()
                                    color: Colours.palette.m3error
                                    Layout.alignment: Qt.AlignVCenter
                                }
                            }

                            RowLayout {
                                spacing: Tokens.spacing.extraSmall

                                Repeater {
                                    model: keybindRow.modelData.mods || []
                                    delegate: KeyBadge {
                                        required property string modelData
                                        text: modelData
                                        highlighted: true
                                    }
                                }

                                KeyBadge {
                                    text: keybindRow.modelData.key || ""
                                    highlighted: false
                                    visible: text !== ""
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: searchItemDelegate

        StyledRect {
            id: searchRow
            property var modelData: parent ? parent.modelData : null
            property int index: parent ? parent.index : -1

            width: parent ? parent.width : 0
            height: implicitHeight
            implicitHeight: Math.max(54, searchRowLayout.implicitHeight + Tokens.padding.small * 2)

            color: Colours.tPalette.m3surfaceContainer
            radius: Tokens.rounding.medium
            border.color: Colours.tPalette.m3outlineVariant
            border.width: 1

            StateLayer {
                radius: Tokens.rounding.medium
                onClicked: {
                    root.executeAction(searchRow.modelData.action, searchRow.modelData.notInstalled, searchRow.modelData.appName);
                }
            }

            RowLayout {
                id: searchRowLayout
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Tokens.padding.medium
                anchors.rightMargin: Tokens.padding.medium
                spacing: Tokens.spacing.medium

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    StyledText {
                        text: `${searchRow.modelData.section} > ${searchRow.modelData.category}`
                        font: Tokens.font.label.small
                        color: Colours.palette.m3primary
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Tokens.spacing.small

                        StyledText {
                            text: searchRow.modelData.desc || searchRow.modelData.action || ""
                            font: Tokens.font.body.medium
                            color: (searchRow.modelData && searchRow.modelData.notInstalled) ? Colours.palette.m3error : Colours.palette.m3onSurface
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        StyledText {
                            visible: (searchRow.modelData && searchRow.modelData.notInstalled) || false
                            text: qsTr("not installed")
                            font: Tokens.font.body.builders.small.weight(Font.Bold).build()
                            color: Colours.palette.m3error
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }
                }

                RowLayout {
                    spacing: Tokens.spacing.extraSmall

                    Repeater {
                        model: searchRow.modelData.mods || []
                        delegate: KeyBadge {
                            required property string modelData
                            text: modelData
                            highlighted: true
                        }
                    }

                    KeyBadge {
                        text: searchRow.modelData.key || ""
                        highlighted: false
                        visible: text !== ""
                    }
                }
            }
        }
    }

    Keys.onEscapePressed: {
        root.visibilities.cheatsheet = false;
    }
}
