pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.components

Item {
    id: root

    required property ShellScreen screen
    required property DrawerVisibilities visibilities
    required property var panels

    readonly property bool shouldBeActive: visibilities.newsfeed

    readonly property real maxHeight: {
        return screen.height - Config.border.thickness * 2 - Tokens.padding.extraLarge * 2;
    }

    property real offsetScale: shouldBeActive ? 0 : 1

    onShouldBeActiveChanged: {
        if (shouldBeActive)
            implicitHeight = Qt.binding(() => content.implicitHeight);
        else
            implicitHeight = implicitHeight; // Break binding during close anim
    }

    visible: offsetScale < 1
    anchors.bottomMargin: (-implicitHeight - 5) * offsetScale
    implicitHeight: content.implicitHeight
    implicitWidth: content.implicitWidth || 800 // Fallback width
    opacity: 1 - offsetScale

    Behavior on offsetScale {
        Anim {}
    }

    Loader {
        id: content

        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter

        active: root.shouldBeActive || root.visible

        sourceComponent: Content {
            visibilities: root.visibilities
            panels: root.panels
            maxHeight: root.maxHeight
        }
    }
}
