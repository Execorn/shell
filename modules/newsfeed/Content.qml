pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Caelestia
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

StyledRect {
    id: root

    required property DrawerVisibilities visibilities
    required property var panels
    required property real maxHeight

    color: Colours.tPalette.m3surface
    radius: Tokens.rounding.extraLarge
    border.color: Colours.tPalette.m3outlineVariant
    border.width: 1

    implicitWidth: 800
    implicitHeight: Math.min(600, maxHeight)

    property var newsData: ({})
    property var topics: Object.keys(newsData)
    property string currentTopic: topics.length > 0 ? topics[0] : ""
    property bool isRefreshing: false

    ListModel {
        id: newsModel
    }

    function loadNews() {
        try {
            var xhr = new XMLHttpRequest();
            xhr.onreadystatechange = function() {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    if (xhr.status === 200 || xhr.status === 0) {
                        try {
                            var data = JSON.parse(xhr.responseText);
                            root.newsData = data;
                            root.updateModel();
                        } catch (e) {
                            console.error("Failed to parse newsfeed JSON:", e);
                        }
                    }
                }
            };
            xhr.open("GET", "file:///home/execorn/.cache/caelestia/newsfeed.json", true);
            xhr.send();
        } catch (err) {
            console.error("Failed to read newsfeed cache:", err);
        }
    }

    function updateModel() {
        newsModel.clear();
        var items = root.newsData[root.currentTopic];
        if (items) {
            for (var i = 0; i < items.length; i++) {
                newsModel.append(items[i]);
            }
        }
    }

    onCurrentTopicChanged: root.updateModel()

    Connections {
        function onNewsfeedChanged(): void {
            if (root.visibilities.newsfeed) {
                root.loadNews();
                root.forceActiveFocus();
            }
        }
        target: root.visibilities
    }

    Component.onCompleted: {
        root.loadNews();
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        // Header Title Bar
        RowLayout {
            Layout.fillWidth: true

            StyledText {
                text: qsTr("NEWS RADAR")
                font: Tokens.font.title.builders.medium.weight(Font.Bold).build()
                color: Colours.palette.m3primary
            }

            Item { Layout.fillWidth: true }

            IconButton {
                id: refreshButton
                icon: "refresh"
                onClicked: {
                    root.isRefreshing = true;
                    Quickshell.execDetached(["/home/execorn/scripts/caelestia-news-fetcher.py"]);
                    var timer = Qt.createQmlObject("import QtQuick; Timer { interval: 1500; repeat: false; }", root);
                    timer.triggered.connect(() => {
                        root.loadNews();
                        root.isRefreshing = false;
                    });
                    timer.start();
                }

                RotationAnimator {
                    target: refreshButton
                    from: 0
                    to: 360
                    duration: 1000
                    running: root.isRefreshing
                    loops: Animation.Infinite
                }
            }

            IconButton {
                icon: "close"
                onClicked: root.visibilities.newsfeed = false
            }
        }

        // Horizontal Category Tabs
        Row {
            id: tabRow
            spacing: Tokens.spacing.small
            Layout.fillWidth: true

            Repeater {
                model: root.topics

                delegate: StyledRect {
                    required property string modelData

                    width: tabText.implicitWidth + Tokens.padding.large * 2
                    height: tabText.implicitHeight + Tokens.padding.medium * 2
                    color: root.currentTopic === modelData 
                        ? Colours.palette.m3primaryContainer 
                        : (tabMouse.containsMouse ? Colours.layer(Colours.palette.m3surfaceContainer, 3) : Colours.layer(Colours.palette.m3surfaceContainer, 1))
                    radius: Tokens.rounding.medium
                    border.color: root.currentTopic === modelData ? Colours.palette.m3primary : "transparent"
                    border.width: 1

                    StyledText {
                        id: tabText
                        anchors.centerIn: parent
                        text: modelData.toUpperCase()
                        font: Tokens.font.body.builders.small.weight(Font.Bold).build()
                        color: root.currentTopic === modelData ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface
                    }

                    MouseArea {
                        id: tabMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.currentTopic = modelData
                    }

                    Behavior on color { CAnim {} }
                }
            }
        }

        // Scrollable List of News Cards
        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: Tokens.spacing.small
            model: newsModel
            visible: newsModel.count > 0

            delegate: StyledRect {
                required property string title
                required property string source
                required property string age
                required property string url
                required property string description

                width: listView.width
                height: cardCol.implicitHeight + Tokens.padding.medium * 2
                color: cardMouse.containsMouse ? Colours.layer(Colours.palette.m3surfaceContainer, 3) : Colours.layer(Colours.palette.m3surfaceContainer, 1)
                radius: Tokens.rounding.medium
                border.color: cardMouse.containsMouse ? Colours.palette.m3outline : "transparent"
                border.width: 1

                Column {
                    id: cardCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: Tokens.padding.medium
                    spacing: Tokens.spacing.extraSmall

                    StyledText {
                        width: parent.width
                        text: title
                        font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
                        color: Colours.palette.m3onSurface
                        wrapMode: Text.WordWrap
                    }

                    StyledText {
                        width: parent.width
                        text: description
                        font: Tokens.font.body.small
                        color: Colours.palette.m3onSurfaceVariant
                        wrapMode: Text.WordWrap
                        visible: description !== ""
                    }

                    Row {
                        spacing: Tokens.spacing.small
                        
                        StyledText {
                            text: source
                            font: Tokens.font.body.small
                            color: Colours.palette.m3primary
                        }

                        StyledText {
                            text: "•"
                            font: Tokens.font.body.small
                            color: Colours.palette.m3onSurfaceVariant
                        }

                        StyledText {
                            text: age
                            font: Tokens.font.body.small
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }
                }

                MouseArea {
                    id: cardMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        Quickshell.execDetached(["xdg-open", url]);
                        root.visibilities.newsfeed = false;
                    }
                }

                Behavior on color { CAnim {} }
            }

            ScrollBar.vertical: ScrollBar {
                active: true
            }
        }

        // Empty/Loading State Placeholder
        StyledRect {
            id: emptyState
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Colours.layer(Colours.palette.m3surfaceContainer, 1)
            radius: Tokens.rounding.medium
            border.color: Colours.palette.m3outlineVariant
            border.width: 1
            visible: newsModel.count === 0

            ColumnLayout {
                anchors.centerIn: parent
                spacing: Tokens.spacing.medium

                MaterialIcon {
                    text: "rss_feed"
                    fontStyle: Tokens.font.icon.builders.extraLarge.scale(2).build()
                    color: Colours.palette.m3primary
                    Layout.alignment: Qt.AlignHCenter
                }

                StyledText {
                    text: qsTr("No articles cached for this topic.")
                    font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
                    color: Colours.palette.m3onSurface
                    Layout.alignment: Qt.AlignHCenter
                }

                StyledText {
                    text: qsTr("Click refresh at the top to download the latest news.")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }
}
