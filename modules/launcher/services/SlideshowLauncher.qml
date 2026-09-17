pragma Singleton

import ".."
import QtQuick
import Quickshell
import Caelestia
import Caelestia.Config
import qs.utils
import qs.services

Singleton {
    id: root

    function parseInputToSeconds(input: string): var {
        const str = input.trim().toLowerCase();
        if (!str) return null;
        if (/^\d+(\.\d+)?m$/.test(str)) return Math.max(5, Math.round(parseFloat(str) * 60));
        if (/^\d+(\.\d+)?s$/.test(str)) return Math.max(5, Math.round(parseFloat(str)));
        if (/^\d+(\.\d+)?h$/.test(str)) return Math.max(5, Math.round(parseFloat(str) * 3600));
        if (/^\d+$/.test(str)) {
            const val = parseInt(str, 10);
            return Math.max(5, val < 60 ? val * 60 : val);
        }
        return null;
    }

    function formatSeconds(sec: int): string {
        if (sec < 60) return `${sec}s`;
        const mins = sec / 60;
        if (mins < 60) return `${mins}m`;
        const hrs = mins / 60;
        return `${hrs}h`;
    }

    function query(search: string): var {
        const prefix = `${GlobalConfig.launcher.actionPrefix}slideshow`;
        const cleanSearch = search.trim().replace(/\s+/g, " ");
        const subQuery = cleanSearch.slice(prefix.length).trim();

        const items = [];

        // If user typed a custom interval like "2m", "30s", "10"
        const customSec = parseInputToSeconds(subQuery);
        if (customSec !== null) {
            items.push({
                "id": "custom",
                "name": qsTr("Set slideshow interval to %1").arg(subQuery),
                "desc": qsTr("Change wallpaper automatically every %1 (%2 seconds)").arg(formatSeconds(customSec)).arg(customSec),
                "icon": "schedule",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    Wallpapers.setSlideshowInterval(customSec);
                }
            });
        }

        // Toggle action
        items.push({
            "id": "toggle",
            "name": Wallpapers.slideshowEnabled ? qsTr("Pause Slideshow") : qsTr("Start Slideshow"),
            "desc": Wallpapers.slideshowEnabled
                ? qsTr("Currently running: auto-changing every %1m").arg(Math.max(1, Math.round(Wallpapers.slideshowIntervalSec / 60)))
                : qsTr("Currently stopped: click to start slideshow"),
            "icon": Wallpapers.slideshowEnabled ? "pause_circle" : "play_circle",
            "onClicked": function(list) {
                list.visibilities.launcher = false;
                Wallpapers.toggleSlideshow();
            }
        });

        // Next random wallpaper immediately
        items.push({
            "id": "next",
            "name": qsTr("Next Random Wallpaper"),
            "desc": qsTr("Immediately switch to another random wallpaper"),
            "icon": "skip_next",
            "onClicked": function(list) {
                list.visibilities.launcher = false;
                Wallpapers.setRandom();
            }
        });

        // Preset intervals
        const presets = [
            { sec: 60, label: qsTr("Every 1 Minute") },
            { sec: 300, label: qsTr("Every 5 Minutes") },
            { sec: 600, label: qsTr("Every 10 Minutes") },
            { sec: 900, label: qsTr("Every 15 Minutes") },
            { sec: 1800, label: qsTr("Every 30 Minutes") },
            { sec: 3600, label: qsTr("Every 1 Hour") },
            { sec: 7200, label: qsTr("Every 2 Hours") }
        ];

        for (const p of presets) {
            const isCurrent = Wallpapers.slideshowEnabled && Wallpapers.slideshowIntervalSec === p.sec;
            items.push({
                "id": `interval_${p.sec}`,
                "name": p.label,
                "desc": isCurrent
                    ? qsTr("Currently active")
                    : qsTr("Automatically change wallpaper every %1").arg(formatSeconds(p.sec)),
                "icon": isCurrent ? "check_circle" : "timer",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    Wallpapers.setSlideshowInterval(p.sec);
                }
            });
        }

        if (!subQuery || customSec !== null) {
            return items;
        }

        const qLower = subQuery.toLowerCase();
        return items.filter(item => item.name.toLowerCase().includes(qLower) || item.desc.toLowerCase().includes(qLower));
    }
}
