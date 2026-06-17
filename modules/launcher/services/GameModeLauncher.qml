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
        const prefix = `${GlobalConfig.launcher.actionPrefix}gamemode`;
        const cleanSearch = search.trim().replace(/\s+/g, " ");

        const mainItems = [
            {
                "id": "enable",
                "name": qsTr("Enable Game Mode"),
                "desc": qsTr("Disable Hyprland animations, blur, gaps, and shadows for maximum gaming performance"),
                "icon": "gamepad",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    GameMode.enabled = true;
                }
            },
            {
                "id": "disable",
                "name": qsTr("Disable Game Mode"),
                "desc": qsTr("Restore default Hyprland animations and appearance"),
                "icon": "gamepad",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    GameMode.enabled = false;
                }
            },
            {
                "id": "toggle",
                "name": qsTr("Toggle Game Mode"),
                "desc": qsTr("Toggle maximum performance mode on or off"),
                "icon": "gamepad",
                "onClicked": function(list) {
                    list.visibilities.launcher = false;
                    GameMode.enabled = !GameMode.enabled;
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
