pragma Singleton

import ".."
import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia
import Caelestia.Config
import qs.utils
import qs.services

Singleton {
    id: root

    function transformSearch(search: string): string {
        return search;
    }

    property var presetsList: []

    function reload(): void {
        getPresets.running = false;
        getPresets.running = true;
    }

    Process {
        id: getPresets

        running: true
        command: ["/usr/bin/python3", "-u", "/home/execorn/scripts/eq-control.py", "list-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (!text.trim()) return;
                try {
                    const presetList = JSON.parse(text);
                    console.log("[EQs.qml debug] Parsed presets count:", presetList.length);
                    
                    const mapped = presetList.map(item => {
                        return {
                            "id": item.id ?? "",
                            "name": item.name ?? "",
                            "desc": item.desc ?? "",
                            "icon": item.icon ?? "music_note",
                            "onClicked": function(list) {
                                list.visibilities.launcher = false;
                                
                                let cmd = [];
                                let toastTitle = qsTr("Equalizer");
                                let toastMsg = "";
                                let toastIcon = "music_note";
                                
                                if (item.id === "on") {
                                    cmd = ["/home/execorn/scripts/eq-control.py", "on"];
                                    toastMsg = qsTr("Equalizer Enabled");
                                    toastIcon = "volume_up";
                                } else if (item.id === "off") {
                                    cmd = ["/home/execorn/scripts/eq-control.py", "off"];
                                    toastMsg = qsTr("Equalizer Bypassed");
                                    toastIcon = "volume_off";
                                } else {
                                    cmd = ["/home/execorn/scripts/eq-control.py", "apply", item.id];
                                    toastMsg = qsTr("Preset Applied: %1").arg((item.name ?? "").replace("Preset: ", ""));
                                    toastIcon = "music_note";
                                }
                                
                                Quickshell.execDetached(cmd);
                                Toaster.toast(toastTitle, toastMsg, toastIcon);
                                
                                root.reload();
                            }
                        };
                    });
                    
                    root.presetsList = mapped;
                } catch (e) {
                    console.log("[EQs.qml error] Failed to parse presets:", e, "Raw text:", text);
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim().length > 0) {
                    console.log("[EQs.qml stderr]:", text);
                }
            }
        }
    }

    Process {
        id: downloadProc

        property string queryName: ""

        command: ["/usr/bin/python3", "-u", "/home/execorn/scripts/eq-control.py", "download", queryName]

        onExited: (exitCode, exitStatus) => {
            if (exitCode === 0) {
                Toaster.toast(qsTr("Equalizer"), qsTr("Preset downloaded and installed successfully!"), "download_done");
            } else {
                Toaster.toast(qsTr("Equalizer"), qsTr("Failed to find or download preset for \"%1\"").arg(queryName), "error");
            }
            root.reload();
        }
    }

    function query(search: string): var {
        const prefix = `${GlobalConfig.launcher.actionPrefix}eq`; // e.g. ">eq"
        const cleanSearch = search.trim().replace(/\s+/g, " ");
        const presetsPrefix = `${prefix} preset`; // e.g. ">eq preset"
        
        console.log("[EQs.qml debug] query called with search:", search, "cleanSearch:", cleanSearch, "presetsList length:", presetsList.length);
        
        const presets = root.presetsList;
        
        if (cleanSearch.startsWith(presetsPrefix)) {
            // ----------------------------------------------------
            // Sub-Group: Choose Presets
            // ----------------------------------------------------
            const subQuery = cleanSearch.slice(presetsPrefix.length).trim().toLowerCase();
            
            // Filter all presets (excluding on/off toggle items)
            const filteredPresets = presets.filter(p => {
                if (p.id === "on" || p.id === "off") return false;
                if (!subQuery) return true;
                return p.name.toLowerCase().includes(subQuery) || p.desc.toLowerCase().includes(subQuery);
            });
            
            // If the query isn't empty, provide an option to download/install it
            if (subQuery.length > 0) {
                const exactMatch = filteredPresets.some(p => p.name.toLowerCase() === subQuery || p.id === subQuery);
                if (!exactMatch) {
                    const installItem = {
                        "id": "install",
                        "name": qsTr("Install: \"%1\"").arg(subQuery),
                        "desc": qsTr("Search and download from AutoEQ database"),
                        "icon": "download",
                        "installQuery": subQuery,
                        "onClicked": function(list) {
                            list.visibilities.launcher = false;
                            Toaster.toast(qsTr("Equalizer"), qsTr("Searching and downloading preset for \"%1\"...").arg(subQuery), "download");
                            downloadProc.queryName = subQuery;
                            downloadProc.running = true;
                        }
                    };
                    return [installItem, ...filteredPresets];
                }
            }
            return filteredPresets;
        } else {
            // ----------------------------------------------------
            // Main Group: Equalizer Options
            // ----------------------------------------------------
            const mainItems = [];
            
            const eqOn = presets.find(p => p.id === "on");
            const eqOff = presets.find(p => p.id === "off");
            if (eqOn) mainItems.push(eqOn);
            if (eqOff) mainItems.push(eqOff);
            
            mainItems.push({
                "id": "choose_presets",
                "name": qsTr("Choose Presets"),
                "desc": qsTr("Select or install parametric EQ presets"),
                "icon": "settings",
                "onClicked": function(list) {
                    list.search.text = `${GlobalConfig.launcher.actionPrefix}eq preset `;
                }
            });
            
            const subQuery = cleanSearch.slice(prefix.length).trim().toLowerCase();
            if (!subQuery) {
                return mainItems;
            }
            return mainItems.filter(item => item.name.toLowerCase().includes(subQuery) || item.desc.toLowerCase().includes(subQuery));
        }
    }
}
