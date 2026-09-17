pragma Singleton

import ".."
import QtQuick
import Quickshell
import Caelestia.Config
import Caelestia.Services
import qs.services
import qs.utils

Searcher {
    id: root

    function transformSearch(search: string): string {
        return search.slice(GlobalConfig.launcher.actionPrefix.length);
    }

    function selector(item: var): string {
        return `${item.name} ${item.desc}`;
    }

    keys: ["name", "desc"]
    list: variants.instances
    useFuzzy: GlobalConfig.launcher.useFuzzy.actions

    Variants {
        id: variants

        model: {
            const list = GlobalConfig.launcher.actions.filter(a => (a.enabled ?? true) && (GlobalConfig.launcher.enableDangerousActions || !(a.dangerous ?? false)) && a.name !== "Random");
            list.push({
                "name": qsTr("Random Wallpaper"),
                "description": qsTr("Switch to a random wallpaper immediately"),
                "icon": "casino",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    Wallpapers.setRandom();
                },
                "enabled": true
            });
            list.push({
                "name": qsTr("Wallpaper on Boot: %1").arg(Wallpapers.randomOnBoot ? qsTr("Random") : qsTr("Last Saved")),
                "description": qsTr("Toggle random wallpaper on startup (currently %1)").arg(Wallpapers.randomOnBoot ? qsTr("random") : qsTr("last saved")),
                "icon": Wallpapers.randomOnBoot ? "restart_alt" : "save",
                "onClicked": function(list) {
                    Wallpapers.toggleRandomOnBoot();
                },
                "enabled": true
            });
            list.push({
                "name": qsTr("Wallpaper Slideshow: %1").arg(Wallpapers.slideshowEnabled ? qsTr("Running") : qsTr("Stopped")),
                "description": qsTr("Toggle automatic wallpaper slideshow (every %1m)").arg(Math.max(1, Math.round(Wallpapers.slideshowIntervalSec / 60))),
                "icon": Wallpapers.slideshowEnabled ? "pause_circle" : "play_circle",
                "onClicked": function(list) {
                    Wallpapers.toggleSlideshow();
                },
                "enabled": true
            });
            list.push({
                "name": qsTr("Wallpaper Slideshow Interval"),
                "description": qsTr("Change slideshow duration (currently %1m)").arg(Math.max(1, Math.round(Wallpapers.slideshowIntervalSec / 60))),
                "icon": "timer",
                "command": ["autocomplete", "slideshow"],
                "enabled": true
            });
            list.push({
                "name": qsTr("Equalizer"),
                "description": qsTr("Change the current equalizer settings / preset"),
                "icon": "music_note",
                "command": ["autocomplete", "eq"],
                "enabled": true
            });
            list.push({
                "name": qsTr("Equalizer Presets"),
                "description": qsTr("Select or download equalizer presets"),
                "icon": "tune",
                "command": ["autocomplete", "eq preset"],
                "enabled": true
            });
            list.push({
                "name": qsTr("Monitors"),
                "description": qsTr("Enable or disable external monitors for gaming"),
                "icon": "desktop_windows",
                "command": ["autocomplete", "monitors"],
                "enabled": true
            });
            list.push({
                "name": qsTr("Game Mode"),
                "description": qsTr("Enable or disable maximum performance mode"),
                "icon": "gamepad",
                "command": ["autocomplete", "gamemode"],
                "enabled": true
            });
            return list;
        }

        Action {}
    }

    component Action: QtObject {
        required property var modelData
        readonly property string name: modelData.name ?? qsTr("Unnamed")
        readonly property string desc: modelData.description ?? qsTr("No description")
        readonly property string icon: modelData.icon ?? "help_outline"
        readonly property list<string> command: modelData.command ?? []
        readonly property bool enabled: modelData.enabled ?? true
        readonly property bool dangerous: modelData.dangerous ?? false

        function onClicked(list: AppList): void {
            if (typeof modelData.onClicked === "function") {
                modelData.onClicked(list);
                return;
            }
            if (command.length === 0)
                return;

            if (command[0] === "autocomplete" && command.length > 1) {
                list.search.text = `${GlobalConfig.launcher.actionPrefix}${command[1]} `;
            } else if (command[0] === "setMode" && command.length > 1) {
                list.visibilities.launcher = false;
                Colours.setMode(command[1]);
            } else {
                list.visibilities.launcher = false;
                if (!SessionManager.exec(command))
                    Quickshell.execDetached(command);
            }
        }
    }
}
