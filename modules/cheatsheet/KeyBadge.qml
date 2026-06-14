pragma ComponentBehavior: Bound

import QtQuick
import Caelestia.Config
import qs.components
import qs.services

StyledRect {
    id: root

    property string text: ""
    property bool highlighted: false

    color: highlighted ? Colours.tPalette.m3primaryContainer : Colours.tPalette.m3surfaceContainerHigh
    border.color: highlighted ? Colours.tPalette.m3primary : Colours.tPalette.m3outlineVariant
    border.width: 1
    radius: Tokens.rounding.small

    implicitWidth: Math.max(32, label.implicitWidth + Tokens.padding.small * 2)
    implicitHeight: label.implicitHeight + Tokens.padding.extraSmall * 2

    function prettifyKey(key) {
        if (!key) return "";
        switch (key.toUpperCase()) {
            case "SUPER": return "Super";
            case "CONTROL":
            case "CTRL": return "Ctrl";
            case "SHIFT": return "Shift";
            case "ALT": return "Alt";
            case "RETURN":
            case "ENTER": return "Enter";
            case "SPACE": return "Space";
            case "ESCAPE":
            case "ESC": return "Esc";
            default: return key;
        }
    }

    StyledText {
        id: label
        anchors.centerIn: parent
        text: root.prettifyKey(root.text)
        font: Tokens.font.label.small
        color: highlighted ? Colours.tPalette.m3onPrimaryContainer : Colours.tPalette.m3onSurface
    }
}
