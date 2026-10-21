pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.modules.bar as Bar
import qs.services

Scope {
    id: root

    required property ShellScreen screen
    required property Bar.BarWrapper bar

    readonly property int borderThickness: GlobalConfig.forScreen(root.screen.name).border.thickness
    readonly property int leftReserved: root.bar.exclusiveZone
    readonly property string monitorName: root.screen?.name ?? ""

    function applyReserved(): void {
        if (!root.monitorName)
            return;

        const top = root.borderThickness;
        const bottom = root.borderThickness;
        const left = root.leftReserved;
        const right = root.borderThickness;

        if (Hypr.usingLua) {
            Hypr.extras.message(`eval local m = hl.get_monitor("${root.monitorName}"); if m then hl.monitor({ output = m.name, mode = string.format("%dx%d@%.2f", m.width, m.height, m.refresh_rate), position = string.format("%dx%d", m.x, m.y), scale = m.scale, reserved = { top = ${top}, bottom = ${bottom}, left = ${left}, right = ${right} } }) end`);
        } else {
            Hypr.extras.message(`keyword monitor ${root.monitorName},addreserved,${top},${bottom},${left},${right}`);
        }
    }

    onMonitorNameChanged: applyReserved()
    onBorderThicknessChanged: applyReserved()
    onLeftReservedChanged: applyReserved()

    Component.onCompleted: applyReserved()

    Connections {
        target: Hypr

        function onConfigReloaded(): void {
            root.applyReserved();
        }
    }
}
