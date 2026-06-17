pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia
import Caelestia.Config
import qs.services

Singleton {
    id: root

    property alias enabled: props.enabled

    property var originalOptions: null

    function setDynamicConfs(): void {
        const optionsToSave = [
            "animations:enabled",
            "decoration:shadow:enabled",
            "decoration:blur:enabled",
            "general:gaps_in",
            "general:gaps_out",
            "general:border_size",
            "decoration:rounding",
            "general:allow_tearing"
        ];
        const saved = {};
        for (let i = 0; i < optionsToSave.length; i++) {
            const opt = optionsToSave[i];
            const val = Hypr.options[opt];
            if (val !== undefined) {
                saved[opt] = val;
            }
        }
        originalOptions = saved;

        Hypr.extras.applyOptions({
            "animations:enabled": 0,
            "decoration:shadow:enabled": 0,
            "decoration:blur:enabled": 0,
            "general:gaps_in": 0,
            "general:gaps_out": 0,
            "general:border_size": 1,
            "decoration:rounding": 0,
            "general:allow_tearing": 1
        });
    }

    function restoreConfs(): void {
        if (originalOptions && Object.keys(originalOptions).length > 0) {
            Hypr.extras.applyOptions(originalOptions);
        } else {
            Hypr.extras.message("reload");
        }
    }

    onEnabledChanged: {
        if (enabled) {
            setDynamicConfs();
            Quickshell.execDetached(["/home/execorn/scripts/disable_monitors.sh"]);
            if (GlobalConfig.utilities.toasts.gameModeChanged)
                Toaster.toast(qsTr("Game mode enabled"), qsTr("Disabled Hyprland animations, blur, gaps and shadows"), "gamepad");
        } else {
            restoreConfs();
            if (GlobalConfig.utilities.toasts.gameModeChanged)
                Toaster.toast(qsTr("Game mode disabled"), qsTr("Hyprland settings restored"), "gamepad");
        }
    }

    PersistentProperties {
        id: props

        property bool enabled: Hypr.options["animations:enabled"] === 0 // qmllint disable missing-property

        reloadableId: "gameMode"
    }

    Connections {
        function onConfigReloaded(): void {
            if (props.enabled)
                root.setDynamicConfs();
        }

        target: Hypr
    }

    IpcHandler {
        function isEnabled(): bool {
            return props.enabled;
        }

        function toggle(): void {
            props.enabled = !props.enabled;
        }

        function enable(): void {
            props.enabled = true;
        }

        function disable(): void {
            props.enabled = false;
        }

        target: "gameMode"
    }
}
