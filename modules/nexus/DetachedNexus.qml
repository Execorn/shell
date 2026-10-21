pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.components
import qs.modules.nexus

StyledClippingRect {
    id: root

    required property ShellScreen screen
    required property bool animatingContainer
    required property int initPageIdx

    signal close

    radius: Tokens.rounding.extraLarge
    implicitWidth: nexusInner.implicitWidth
    implicitHeight: nexusInner.implicitHeight

    Nexus {
        id: nexusInner

        anchors.fill: parent
        nState.screen: root.screen
        nState.animatingContainer: root.animatingContainer
        nState.currentPageIdx: root.initPageIdx
        onClose: root.close()
    }
}
