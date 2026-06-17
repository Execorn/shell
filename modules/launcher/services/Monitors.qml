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

    function transformSearch(search: string): string {
        return search;
    }

    function query(search: string): var {
        const prefix = `${GlobalConfig.launcher.actionPrefix}monitors`;
        const cleanSearch = search.trim().replace(/\s+/g, " ");

        const mainItems = [
            {
                "id": "disable",
                "name": qsTr("Disable External Monitors"),
                "desc": qsTr("Power off and disable DP-3 and DP-4, leaving only eDP-1 active"),
                "icon": "desktop_access_disabled",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    Quickshell.execDetached(["/home/execorn/scripts/disable_monitors.sh"]);
                    Toaster.toast(qsTr("Monitors"), qsTr("External monitors disabled (gaming mode)"), "desktop_access_disabled");
                }
            },
            {
                "id": "enable",
                "name": qsTr("Enable External Monitors"),
                "desc": qsTr("Enable and power on DP-3 (100Hz) and DP-4 (144Hz) in triple screen layout"),
                "icon": "desktop_windows",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    Quickshell.execDetached(["/home/execorn/scripts/enable_monitors.sh"]);
                    Toaster.toast(qsTr("Monitors"), qsTr("External monitors enabled"), "desktop_windows");
                }
            }
        ];

        const subQuery = cleanSearch.slice(prefix.length).trim().toLowerCase();
        if (!subQuery) {
            return mainItems;
        }
        return mainItems.filter(item => item.name.toLowerCase().includes(subQuery) || item.desc.toLowerCase().includes(subQuery));
    }
}
