pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

Singleton {
    id: root

    property var pluginsList: []
    property var pluginsMap: ({})
    property var resolutionOrder: []
    property string resolutionError: ""
    property var loadedPluginsMap: ({})
    property bool scanning: false

    readonly property int loadedPluginsCount: {
        let count = 0;
        for (let key in loadedPluginsMap) {
            if (loadedPluginsMap[key]) count++;
        }
        return count;
    }

    readonly property string pythonScanScript: `
import sys, os, json

plugins_dir = sys.argv[1]
result = {}

if os.path.exists(plugins_dir):
    for item in os.listdir(plugins_dir):
        item_path = os.path.join(plugins_dir, item)
        if os.path.isdir(item_path):
            meta_path = os.path.join(item_path, 'metadata.json')
            if not os.path.exists(meta_path):
                result[item] = {
                    "id": item,
                    "name": item,
                    "status": "invalid",
                    "error": "Missing metadata.json",
                    "author": "Unknown",
                    "version": "0.0.0",
                    "dependencies": []
                }
                continue
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                status = meta.get("status", "disabled")
                error_msg = None
                
                if status in ("enabled", "crashed"):
                    main_path = os.path.join(item_path, 'main.qml')
                    if not os.path.exists(main_path):
                        status = "crashed"
                        error_msg = "Entry point main.qml missing"
                        with open(os.path.join(item_path, 'error.log'), 'w') as ef:
                            ef.write(error_msg)
                        meta['status'] = 'crashed'
                        with open(meta_path, 'w') as mf:
                            json.dump(meta, mf, indent=2)
                    else:
                        try:
                            with open(main_path, 'r') as mf_content:
                                content = mf_content.read()
                            if "import" not in content or "{" not in content:
                                status = "crashed"
                                error_msg = "QML syntax error in main.qml"
                                with open(os.path.join(item_path, 'error.log'), 'w') as ef:
                                    ef.write(error_msg)
                                meta['status'] = 'crashed'
                                with open(meta_path, 'w') as mf:
                                    json.dump(meta, mf, indent=2)
                        except Exception as qmle:
                            status = "crashed"
                            error_msg = str(qmle)
                            with open(os.path.join(item_path, 'error.log'), 'w') as ef:
                                ef.write(error_msg)
                            meta['status'] = 'crashed'
                            with open(meta_path, 'w') as mf:
                                json.dump(meta, mf, indent=2)
                                
                if status == "crashed" and not error_msg:
                    log_path = os.path.join(item_path, 'error.log')
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, 'r') as log_f:
                                error_msg = log_f.read()
                        except Exception as le:
                            error_msg = str(le)
                    else:
                        error_msg = "Unknown crash"

                result[item] = {
                    "id": item,
                    "name": meta.get("name", item),
                    "author": meta.get("author", "Unknown"),
                    "version": meta.get("version", "0.0.0"),
                    "dependencies": meta.get("dependencies", []),
                    "status": status,
                    "error": error_msg
                }
            except json.JSONDecodeError:
                result[item] = {
                    "id": item,
                    "name": item,
                    "status": "corrupt",
                    "error": "Corrupt metadata.json",
                    "author": "Unknown",
                    "version": "0.0.0",
                    "dependencies": []
                }
            except Exception as e:
                result[item] = {
                    "id": item,
                    "name": item,
                    "status": "error",
                    "error": str(e),
                    "author": "Unknown",
                    "version": "0.0.0",
                    "dependencies": []
                }
print(json.dumps(result))
`

    Process {
        id: pluginScanProcess
        running: false
        command: ["python3", "-c", root.pythonScanScript, Paths.config + "/plugins"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    let parsed = JSON.parse(text);
                    root.pluginsMap = parsed;
                    root.resolveAndLoad();
                } catch (e) {
                    console.log("Failed to parse plugin scanner output:", e);
                    root.resolutionError = "Failed to scan plugins: " + e.message;
                }
                root.scanning = false;
            }
        }
    }

    function scan() {
        if (scanning) return;
        scanning = true;
        pluginScanProcess.running = false;
        pluginScanProcess.running = true;
    }

    Component.onCompleted: {
        scan();
    }

    function updateLoadedMap(pluginId, loaded) {
        let newMap = {};
        for (let key in loadedPluginsMap) {
            newMap[key] = loadedPluginsMap[key];
        }
        if (loaded) {
            newMap[pluginId] = true;
        } else {
            delete newMap[pluginId];
        }
        loadedPluginsMap = newMap;
    }

    function resolveAndLoad() {
        let visited = {};
        let path = {};
        let order = [];
        let circularError = "";

        function visit(name) {
            if (circularError) return;
            if (path[name]) {
                circularError = "Circular dependency detected: " + name;
                return;
            }
            if (!visited[name]) {
                path[name] = true;
                let plugin = root.pluginsMap[name];
                if (plugin && plugin.status !== "corrupt" && plugin.status !== "invalid" && plugin.status !== "error") {
                    let deps = plugin.dependencies || [];
                    for (let i = 0; i < deps.length; i++) {
                        visit(deps[i]);
                    }
                }
                delete path[name];
                visited[name] = true;
                order.push(name);
            }
        }

        let keys = Object.keys(root.pluginsMap);
        for (let i = 0; i < keys.length; i++) {
            visit(keys[i]);
            if (circularError) break;
        }

        if (circularError) {
            root.resolutionOrder = [];
            root.resolutionError = circularError;
            root.loadedPluginsMap = {};
        } else {
            root.resolutionOrder = order;
            root.resolutionError = "";
        }

        // Check for missing/disabled/crashed dependencies and propagate failure
        let changedAny = false;
        if (!circularError) {
            for (let i = 0; i < order.length; i++) {
                let pluginId = order[i];
                let plugin = root.pluginsMap[pluginId];
                if (plugin && plugin.status === "enabled") {
                    let deps = plugin.dependencies || [];
                    for (let j = 0; j < deps.length; j++) {
                        let depId = deps[j];
                        let depPlugin = root.pluginsMap[depId];
                        if (!depPlugin || depPlugin.status === "crashed" || depPlugin.status === "error" || depPlugin.status === "invalid" || depPlugin.status === "corrupt") {
                            root.writePluginStatus(pluginId, "crashed", "Dependency '" + depId + "' failed to load or is invalid.");
                            changedAny = true;
                            break;
                        } else if (depPlugin.status === "disabled") {
                            root.writePluginStatus(pluginId, "crashed", "Dependency '" + depId + "' is disabled.");
                            changedAny = true;
                            break;
                        }
                    }
                }
            }
        }

        if (changedAny) {
            scan();
            return;
        }

        let newList = [];
        for (let i = 0; i < order.length; i++) {
            newList.push(root.pluginsMap[order[i]]);
        }
        for (let key in root.pluginsMap) {
            if (order.indexOf(key) === -1) {
                newList.push(root.pluginsMap[key]);
            }
        }
        root.pluginsList = newList;
    }

    function writePluginStatus(pluginId, status, errorMsg) {
        let plugin = root.pluginsMap[pluginId];
        if (!plugin) return;

        plugin.status = status;
        plugin.error = errorMsg;

        let newMeta = {
            "name": plugin.name,
            "author": plugin.author,
            "version": plugin.version,
            "dependencies": plugin.dependencies,
            "status": status
        };

        let targetPath = Paths.config + "/plugins/" + pluginId + "/metadata.json";
        let pyWriteScript = "import json; f = open('" + targetPath + "', 'w'); json.dump(" + JSON.stringify(newMeta) + ", f, indent=2); f.close()";
        Quickshell.execDetached(["python3", "-c", pyWriteScript]);

        let logPath = Paths.config + "/plugins/" + pluginId + "/error.log";
        if (status === "crashed" || status === "error") {
            let pyWriteLog = "f = open('" + logPath + "', 'w'); f.write(" + JSON.stringify(errorMsg || "Unknown error") + "); f.close()";
            Quickshell.execDetached(["python3", "-c", pyWriteLog]);
        } else {
            Quickshell.execDetached(["rm", "-f", logPath]);
        }
    }

    function enablePlugin(pluginId) {
        writePluginStatus(pluginId, "enabled", null);
        scan();
    }

    function disablePlugin(pluginId) {
        updateLoadedMap(pluginId, false);
        writePluginStatus(pluginId, "disabled", null);
        scan();
    }

    // Dynamic Background Loaders
    Item {
        id: loadersContainer

        Repeater {
            model: root.resolutionOrder
            delegate: Loader {
                required property var modelData // pluginId string

                asynchronous: true
                source: {
                    let plugin = root.pluginsMap[modelData];
                    if (!plugin || plugin.status !== "enabled") return "";

                    // Wait until all dependencies are loaded
                    let deps = plugin.dependencies || [];
                    for (let i = 0; i < deps.length; i++) {
                        if (!root.loadedPluginsMap[deps[i]]) return "";
                    }
                    return "file://" + Paths.config + "/plugins/" + modelData + "/main.qml";
                }

                onStatusChanged: {
                    if (status === Loader.Ready) {
                        root.updateLoadedMap(modelData, true);
                    } else {
                        root.updateLoadedMap(modelData, false);
                        if (status === Loader.Error) {
                            console.log("QML plugin loader failed: " + modelData);
                            root.writePluginStatus(modelData, "crashed", "QML Loader Error: failed to load or parse component main.qml");
                            root.scan();
                        }
                    }
                }
            }
        }
    }
}
