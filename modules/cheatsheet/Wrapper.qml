pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.components

Item {
    id: root

    required property DrawerVisibilities visibilities

    readonly property bool shouldBeActive: visibilities.cheatsheet
    property real offsetScale: shouldBeActive ? 0 : 1

    visible: offsetScale < 1
    opacity: 1 - offsetScale
    scale: 1 - (offsetScale * 0.1)

    implicitWidth: Math.min(1000, (parent ? parent.width : 1000) - Tokens.padding.extraLarge * 2)
    implicitHeight: Math.min(650, (parent ? parent.height : 650) - Tokens.padding.extraLarge * 2)
    width: implicitWidth
    height: implicitHeight

    Behavior on offsetScale {
        Anim {
            type: Anim.Emphasized
        }
    }

    // Intercept clicks on the widget wrapper to prevent click-through dismissal
    MouseArea {
        anchors.fill: parent
    }

    Loader {
        id: content

        anchors.fill: parent
        active: root.shouldBeActive || root.visible

        sourceComponent: Content {
            visibilities: root.visibilities
        }
    }
}
