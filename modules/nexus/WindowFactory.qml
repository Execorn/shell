pragma Singleton

import QtQuick
import Quickshell

Singleton {
    id: root

    property Component nexusComp

    function create(parent: Item, props: var): void {
        if (!nexusComp)
            nexusComp = Qt.createComponent("NexusWindow.qml");
        if (nexusComp.status === Component.Ready)
            nexusComp.createObject(parent ?? dummy, props ?? {});
        else if (nexusComp.status === Component.Error)
            console.error(nexusComp.errorString());
    }

    QtObject {
        id: dummy
    }
}
