pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia
import Caelestia.Config
import qs.services
import QtCore

Singleton {
    id: root

    property alias enabled: settings.enabled
    property bool isReady: false

    property var originalOptions: null

    Settings {
        id: settings
        location: "file:///home/execorn/.config/caelestia/gamemode.conf"
        property bool enabled: false
    }

    readonly property var defaultOptions: ({
        "animations:enabled": 1,
        "decoration:shadow:enabled": 1,
        "decoration:blur:enabled": 1,
        "general:gaps_in": 5,
        "general:gaps_out": 10,
        "general:border_size": 1,
        "decoration:rounding": 15,
        "general:allow_tearing": 0
    })

    function setDynamicConfs(): void {
        const currentAnimations = Hypr.options["animations:enabled"];
        if (currentAnimations === undefined) {
            console.log("[GameMode] Hypr.options are not yet loaded. Skipping saving originalOptions.");
        } else if (currentAnimations === false || currentAnimations === 0) {
            console.log("[GameMode] Animations are already disabled. Skipping saving originalOptions.");
        } else {
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
            console.log("[GameMode] Saved original options: " + JSON.stringify(originalOptions));
        }

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
            console.log("[GameMode] No originalOptions saved. Restoring default configuration options.");
            Hypr.extras.applyOptions(defaultOptions);
        }
    }

    onEnabledChanged: {
        if (enabled) {
            setDynamicConfs();
            if (isReady) {
                Quickshell.execDetached(["/home/execorn/scripts/disable_monitors.sh"]);
            }
            if (GlobalConfig.utilities.toasts.gameModeChanged)
                Toaster.toast(qsTr("Game mode enabled"), qsTr("Disabled Hyprland animations, blur, gaps and shadows"), "gamepad");
        } else {
            restoreConfs();
            if (isReady) {
                Quickshell.execDetached(["/home/execorn/scripts/enable_monitors.sh"]);
            }
            if (GlobalConfig.utilities.toasts.gameModeChanged)
                Toaster.toast(qsTr("Game mode disabled"), qsTr("Hyprland settings restored"), "gamepad");
        }
    }

    Component.onCompleted: {
        if (!enabled) {
            restoreConfs();
        }
        Qt.callLater(function() {
            isReady = true;
        });
    }

    Connections {
        function onConfigReloaded(): void {
            if (root.enabled)
                root.setDynamicConfs();
        }

        target: Hypr
    }

    IpcHandler {
        function isEnabled(): bool {
            return root.enabled;
        }

        function toggle(): void {
            root.enabled = !root.enabled;
        }

        function enable(): void {
            root.enabled = true;
        }

        function disable(): void {
            root.enabled = false;
        }

        target: "gameMode"
    }
}
