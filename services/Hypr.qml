pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Caelestia
import Caelestia.Config
import Caelestia.Internal
import qs.components.misc

Singleton {
    id: root

    readonly property var toplevels: Hyprland.toplevels
    readonly property var workspaces: Hyprland.workspaces
    readonly property var monitors: Hyprland.monitors

    readonly property HyprlandToplevel activeToplevel: {
        const t = Hyprland.activeToplevel;
        return t?.workspace?.name.startsWith("special:") || Hyprland.focusedWorkspace?.toplevels.values.length > 0 ? t : null;
    }
    readonly property HyprlandWorkspace focusedWorkspace: Hyprland.focusedWorkspace
    readonly property HyprlandMonitor focusedMonitor: Hyprland.focusedMonitor
    readonly property int activeWsId: focusedWorkspace?.id ?? 1

    readonly property HyprKeyboard keyboard: extras.devices.keyboards.find(kb => kb.main) ?? null
    readonly property bool capsLock: keyboard?.capsLock ?? false
    readonly property bool numLock: keyboard?.numLock ?? false
    readonly property string defaultKbLayout: keyboard?.layout.split(",")[0] ?? "??"
    readonly property string kbLayoutFull: keyboard?.activeKeymap ?? "Unknown"
    readonly property string kbLayout: kbMap.get(kbLayoutFull) ?? "??"
    readonly property var kbMap: new Map()

    readonly property alias extras: extras
    readonly property alias options: extras.options
    readonly property alias devices: extras.devices

    property bool hadKeyboard
    property string lastSpecialWorkspace: ""

    signal configReloaded

    function dispatch(request: string): void {
        Hyprland.dispatch(request);
    }

    function cycleSpecialWorkspace(direction: string): void {
        const openSpecials = workspaces.values.filter(w => w.name.startsWith("special:") && w.lastIpcObject.windows > 0);

        if (openSpecials.length === 0)
            return;

        const activeSpecial = focusedMonitor.lastIpcObject.specialWorkspace.name ?? "";

        if (!activeSpecial) {
            if (lastSpecialWorkspace) {
                const workspace = workspaces.values.find(w => w.name === lastSpecialWorkspace);
                if (workspace && workspace.lastIpcObject.windows > 0) {
                    dispatch(`workspace ${lastSpecialWorkspace}`);
                    return;
                }
            }
            dispatch(`workspace ${openSpecials[0].name}`);
            return;
        }

        const currentIndex = openSpecials.findIndex(w => w.name === activeSpecial);
        let nextIndex = 0;

        if (currentIndex !== -1) {
            if (direction === "next")
                nextIndex = (currentIndex + 1) % openSpecials.length;
            else
                nextIndex = (currentIndex - 1 + openSpecials.length) % openSpecials.length;
        }

        dispatch(`workspace ${openSpecials[nextIndex].name}`);
    }

    function monitorNames(): list<string> {
        return monitors.values.map(e => e.name);
    }

    function monitorFor(screen: ShellScreen): HyprlandMonitor {
        return Hyprland.monitorFor(screen);
    }

    function reloadDynamicConfs(): void {
        extras.batchMessage(["keyword bindlni ,Caps_Lock,global,caelestia:refreshDevices", "keyword bindlni ,Num_Lock,global,caelestia:refreshDevices"]);
    }

    Component.onCompleted: reloadDynamicConfs()

    onCapsLockChanged: {
        if (!GlobalConfig.utilities.toasts.capsLockChanged)
            return;

        if (capsLock)
            Toaster.toast(qsTr("Caps lock enabled"), qsTr("Caps lock is currently enabled"), "keyboard_capslock_badge");
        else
            Toaster.toast(qsTr("Caps lock disabled"), qsTr("Caps lock is currently disabled"), "keyboard_capslock");
    }

    onNumLockChanged: {
        if (!GlobalConfig.utilities.toasts.numLockChanged)
            return;

        if (numLock)
            Toaster.toast(qsTr("Num lock enabled"), qsTr("Num lock is currently enabled"), "looks_one");
        else
            Toaster.toast(qsTr("Num lock disabled"), qsTr("Num lock is currently disabled"), "timer_1");
    }

    onKbLayoutFullChanged: {
        if (hadKeyboard && GlobalConfig.utilities.toasts.kbLayoutChanged)
            Toaster.toast(qsTr("Keyboard layout changed"), qsTr("Layout changed to: %1").arg(kbLayoutFull), "keyboard");

        hadKeyboard = !!keyboard;
    }

    Connections {
        function onRawEvent(event: HyprlandEvent): void {
            const n = event.name;
            if (n.endsWith("v2"))
                return;

            if (n === "configreloaded") {
                root.configReloaded();
                root.reloadDynamicConfs();
                autotileTimer.restart();
            } else if (["workspace", "moveworkspace", "activespecial", "focusedmon"].includes(n)) {
                Hyprland.refreshWorkspaces();
                Hyprland.refreshMonitors();
                autotileTimer.restart();
            } else if (["openwindow", "closewindow", "movewindow"].includes(n)) {
                Hyprland.refreshToplevels();
                Hyprland.refreshWorkspaces();
                autotileTimer.restart();
            } else if (n.includes("mon")) {
                Hyprland.refreshMonitors();
            } else if (n.includes("workspace")) {
                Hyprland.refreshWorkspaces();
                autotileTimer.restart();
            } else if (n.includes("window") || n.includes("group") || ["pin", "fullscreen", "changefloatingmode", "minimize"].includes(n)) {
                Hyprland.refreshToplevels();
                autotileTimer.restart();
            }
        }

        target: Hyprland
    }

    Connections {
        function onLastIpcObjectChanged(): void {
            const specialName = root.focusedMonitor.lastIpcObject.specialWorkspace.name;

            if (specialName && specialName.startsWith("special:")) {
                root.lastSpecialWorkspace = specialName;
            }
        }

        target: root.focusedMonitor
    }

    FileView {
        id: kbLayoutFile

        path: Quickshell.env("CAELESTIA_XKB_RULES_PATH") || "/usr/share/X11/xkb/rules/base.lst"
        onLoaded: {
            const layoutMatch = text().match(/! layout\n([\s\S]*?)\n\n/);
            if (layoutMatch) {
                const lines = layoutMatch[1].split("\n");
                for (const line of lines) {
                    if (!line.trim() || line.trim().startsWith("!"))
                        continue;

                    const match = line.match(/^\s*([a-z]{2,})\s+([a-zA-Z() ]+)$/);
                    if (match)
                        root.kbMap.set(match[2], match[1]);
                }
            }

            const variantMatch = text().match(/! variant\n([\s\S]*?)\n\n/);
            if (variantMatch) {
                const lines = variantMatch[1].split("\n");
                for (const line of lines) {
                    if (!line.trim() || line.trim().startsWith("!"))
                        continue;

                    const match = line.match(/^\s*([a-zA-Z0-9_-]+)\s+([a-z]{2,}): (.+)$/);
                    if (match)
                        root.kbMap.set(match[3], match[2]);
                }
            }
        }
    }

    IpcHandler {
        function refreshDevices(): void {
            extras.refreshDevices();
        }

        function cycleSpecialWorkspace(direction: string): void {
            root.cycleSpecialWorkspace(direction);
        }

        function listSpecialWorkspaces(): string {
            return root.workspaces.values.filter(w => w.name.startsWith("special:") && w.lastIpcObject.windows > 0).map(w => w.name).join("\n");
        }

        target: "hypr"
    }

    // qmllint disable unresolved-type
    CustomShortcut {
        // qmllint enable unresolved-type
        name: "refreshDevices"
        description: "Reload devices"
        onPressed: extras.refreshDevices()
        onReleased: extras.refreshDevices()
    }

    HyprExtras {
        id: extras
    }

    Timer {
        id: autotileTimer
        interval: 100
        repeat: false
        onTriggered: root.checkAndFixLayout()
    }

    function checkAndFixLayout() {
        const activeWs = root.focusedWorkspace;
        if (!activeWs) return;
        const activeWsId = activeWs.id;

        // Get all tiled (non-floating) mapped windows on the active workspace
        const tiled = [];
        const allToplevels = root.toplevels.values;
        for (let i = 0; i < allToplevels.length; i++) {
            const t = allToplevels[i];
            const obj = t.lastIpcObject;
            if (!obj) continue;
            
            const wsId = obj.workspace ? obj.workspace.id : -1;
            if (wsId === activeWsId && !obj.floating && obj.mapped) {
                tiled.push(obj);
            }
        }

        if (tiled.length < 2) return;

        // Group into vertical columns based on X and width
        const columns = [];
        for (let i = 0; i < tiled.length; i++) {
            const c = tiled[i];
            const x = c.at[0];
            const w = c.size[0];
            
            let matched = false;
            for (let j = 0; j < columns.length; j++) {
                const col = columns[j];
                const ref = col[0];
                const ref_x = ref.at[0];
                const ref_w = ref.size[0];
                
                if (Math.abs(x - ref_x) < 15 && Math.abs(w - ref_w) < 15) {
                    col.push(c);
                    matched = true;
                    break;
                }
            }
            if (!matched) {
                columns.push([c]);
            }
        }

        // Check deepest adjacent pair for each column
        for (let i = 0; i < columns.length; i++) {
            const col = columns[i];
            if (col.length < 2) continue;

            // Sort by Y coordinate
            col.sort((a, b) => a.at[1] - b.at[1]);

            // Get deepest pair
            const c1 = col[col.length - 2];
            const c2 = col[col.length - 1];

            const x1 = c1.at[0];
            const y1 = c1.at[1];
            const w1 = c1.size[0];
            const h1 = c1.size[1];

            const x2 = c2.at[0];
            const y2 = c2.at[1];
            const w2 = c2.size[0];
            const h2 = c2.size[1];

            if (Math.abs(x1 - x2) < 15) {
                const H = (y2 + h2) - y1;
                const W = (w1 + w2) / 2;

                if (W > H * 1.1) {
                    console.log("[Autotile] Suboptimal stack detected: " + c1.class + " and " + c2.class + ". W=" + W + ", H=" + H + ". Forcing side-by-side.");
                    
                    // Focus c1 if the active window is not one of them
                    const activeT = root.activeToplevel;
                    const activeAddr = activeT ? activeT.lastIpcObject.address : "";
                    if (activeAddr !== c1.address && activeAddr !== c2.address) {
                        root.dispatch("focuswindow address:" + c1.address);
                    }
                    root.dispatch("layoutmsg togglesplit");
                    return; // Exit after one correction
                }
            }
        }
    }
}

