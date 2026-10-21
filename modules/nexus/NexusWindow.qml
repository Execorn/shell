pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.components
import qs.services
import qs.modules.nexus

FloatingWindow {
    id: win

    color: Colours.tPalette.m3surface
    surfaceFormat.opaque: false

    onVisibleChanged: {
        if (!visible)
            destroy();
    }

    implicitWidth: nexus.implicitWidth
    implicitHeight: nexus.implicitHeight

    minimumSize.width: contentItem.Tokens.sizes.nexus.minWidth
    minimumSize.height: contentItem.Tokens.sizes.nexus.minHeight

    contentItem.Config.screen: screen.name
    contentItem.Tokens.screen: screen.name

    title: qsTr("Nexus — %1").arg(PageRegistry.pages[nexus.nState.currentPageIdx].label)

    Nexus {
        id: nexus

        anchors.fill: parent
        nState.screen: win.screen
        nState.isWindow: true
        onClose: win.destroy()
    }

    Behavior on color {
        CAnim {}
    }
}
