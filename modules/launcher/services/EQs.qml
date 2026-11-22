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
    property var queuedApply: null
    property string queuedDownloadQuery: ""

    Component.onCompleted: root.reload()

    function reload(): void {
        if (!getPresets.running) {
            getPresets.running = true;
        }
    }

    function firstErrorLine(stderrText: string): string {
        const lines = stderrText
            .split(/\r?\n/)
            .map(l => l.trim())
            .filter(l => l.length > 0);
        return lines.length > 0 ? lines[0] : "";
    }

    function runApplyAction(cmd: var, toastMsg: string, toastIcon: string): void {
        if (applyProc.running) {
            root.queuedApply = {
                command: cmd,
                toastMsg: toastMsg,
                toastIcon: toastIcon
            };
            return;
        }
        applyProc.errText = "";
        applyProc.command = cmd;
        applyProc.toastMsg = toastMsg;
        applyProc.toastIcon = toastIcon;
        applyProc.running = true;
    }

    function runDownload(queryName: string): void {
        const cleanQuery = queryName.trim();
        if (!cleanQuery)
            return;

        if (downloadProc.running) {
            root.queuedDownloadQuery = cleanQuery;
            Toaster.toast(
                qsTr("Equalizer"),
                qsTr("Queued AutoEQ download for \"%1\" after current search completes").arg(cleanQuery),
                "schedule"
            );
            return;
        }

        Toaster.toast(qsTr("Equalizer"), qsTr("Searching and downloading preset for \"%1\"...").arg(cleanQuery), "download");
        downloadProc.errText = "";
        downloadProc.activeQuery = cleanQuery;
        downloadProc.command = ["/usr/bin/python3", "-u", Paths.eqControlScript, "download", cleanQuery];
        downloadProc.running = true;
    }

    Process {
        id: applyProc

        property string toastMsg: ""
        property string toastIcon: "music_note"
        property string errText: ""

        stderr: StdioCollector {
            onStreamFinished: applyProc.errText = text
        }

        onExited: (exitCode, exitStatus) => {
            if (exitCode === 0) {
                if (toastMsg !== "") {
                    Toaster.toast(qsTr("Equalizer"), toastMsg, toastIcon);
                }
            } else {
                const detail = root.firstErrorLine(errText);
                const msg = detail
                    ? qsTr("Equalizer failed: %1").arg(detail)
                    : qsTr("Failed to apply equalizer setting (exit %1)").arg(exitCode);
                Toaster.toast(qsTr("Equalizer"), msg, "error");
            }
            root.reload();

            if (root.queuedApply) {
                const next = root.queuedApply;
                root.queuedApply = null;
                root.runApplyAction(next.command, next.toastMsg, next.toastIcon);
            }
        }
    }

    Process {
        id: getPresets

        running: false
        command: ["/usr/bin/python3", "-u", Paths.eqControlScript, "list-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (!text.trim()) return;
                try {
                    const presetList = JSON.parse(text);

                    const mapped = presetList.map(item => {
                        return {
                            "id": item.id ?? "",
                            "name": item.name ?? "",
                            "desc": item.desc ?? "",
                            "icon": item.icon ?? "music_note",
                            "onClicked": function(list) {
                                list.visibilities.launcher = false;

                                let cmd = [];
                                let toastMsg = "";
                                let toastIcon = "music_note";

                                if (item.id === "on") {
                                    cmd = ["/usr/bin/python3", "-u", Paths.eqControlScript, "on"];
                                    toastMsg = qsTr("Equalizer Enabled");
                                    toastIcon = "volume_up";
                                } else if (item.id === "off") {
                                    cmd = ["/usr/bin/python3", "-u", Paths.eqControlScript, "off"];
                                    toastMsg = qsTr("Equalizer Bypassed");
                                    toastIcon = "volume_off";
                                } else {
                                    cmd = ["/usr/bin/python3", "-u", Paths.eqControlScript, "apply", item.id];
                                    toastMsg = qsTr("Preset Applied: %1").arg((item.name ?? "").replace("Preset: ", ""));
                                    toastIcon = "music_note";
                                }

                                root.runApplyAction(cmd, toastMsg, toastIcon);
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

        property string activeQuery: ""
        property string errText: ""

        stderr: StdioCollector {
            onStreamFinished: downloadProc.errText = text
        }

        onExited: (exitCode, exitStatus) => {
            if (exitCode === 0) {
                Toaster.toast(
                    qsTr("Equalizer"),
                    qsTr("Preset \"%1\" downloaded and installed successfully!").arg(activeQuery),
                    "download_done"
                );
            } else {
                const detail = root.firstErrorLine(errText);
                const msg = detail
                    ? qsTr("Download failed for \"%1\": %2").arg(activeQuery).arg(detail)
                    : qsTr("Failed to find or download preset for \"%1\"").arg(activeQuery);
                Toaster.toast(qsTr("Equalizer"), msg, "error");
            }
            root.reload();

            if (root.queuedDownloadQuery !== "") {
                const nextQuery = root.queuedDownloadQuery;
                root.queuedDownloadQuery = "";
                root.runDownload(nextQuery);
            }
        }
    }

    function query(search: string): var {
        const actionPrefix = GlobalConfig.launcher.actionPrefix.toLowerCase(); // e.g. ">"
        const cleanSearch = search.trim().replace(/\s+/g, " ");
        const lowerSearch = cleanSearch.toLowerCase();

        const presets = root.presetsList;

        const eqPresetPfx = `${actionPrefix}eq preset`;
        const presetPfx = `${actionPrefix}preset`;

        let isPresets = false;
        let subQuery = "";

        if (lowerSearch.startsWith(eqPresetPfx)) {
            isPresets = true;
            let rest = lowerSearch.slice(eqPresetPfx.length);
            if (rest.startsWith("s")) rest = rest.slice(1);
            subQuery = rest.trim();
        } else if (lowerSearch.startsWith(presetPfx)) {
            isPresets = true;
            let rest = lowerSearch.slice(presetPfx.length);
            if (rest.startsWith("s")) rest = rest.slice(1);
            subQuery = rest.trim();
        }

        if (isPresets) {
            const filteredPresets = presets.filter(p => {
                if (p.id === "on" || p.id === "off") return false;
                if (!subQuery) return true;
                return p.name.toLowerCase().includes(subQuery)
                    || p.desc.toLowerCase().includes(subQuery)
                    || p.id.toLowerCase().includes(subQuery);
            });

            if (subQuery.length > 0) {
                const exactMatch = filteredPresets.some(p => p.name.toLowerCase() === subQuery || p.id.toLowerCase() === subQuery);
                if (!exactMatch) {
                    const installItem = {
                        "id": "install",
                        "name": qsTr("Install: \"%1\"").arg(subQuery),
                        "desc": qsTr("Search and download from AutoEQ database"),
                        "icon": "download",
                        "installQuery": subQuery,
                        "onClicked": function(list) {
                            list.visibilities.launcher = false;
                            root.runDownload(subQuery);
                        }
                    };
                    return [...filteredPresets, installItem];
                }
            }
            return filteredPresets;
        } else {
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

            const eqPrefix = `${actionPrefix}eq`;
            let mainSubQuery = "";
            if (lowerSearch.startsWith(eqPrefix)) {
                mainSubQuery = lowerSearch.slice(eqPrefix.length).trim();
            }
            if (!mainSubQuery) {
                return mainItems;
            }
            return mainItems.filter(
                item => item.name.toLowerCase().includes(mainSubQuery)
                    || item.desc.toLowerCase().includes(mainSubQuery)
            );
        }
    }
}
