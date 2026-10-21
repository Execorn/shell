pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia
import qs.utils
import qs.components.misc
import qs.services

Singleton {
    id: root

    property string ocrText: ""
    property bool running: false
    property string lastError: ""
    property string activeDrawer: ""
    property bool startupGraceActive: true

    readonly property Timer startupGraceTimer: Timer {
        interval: 1500
        running: true
        repeat: false
        onTriggered: root.startupGraceActive = false
    }

    readonly property string user: Quickshell.env("USER") || "default"
    readonly property string tempPath: "/tmp/ocr_capture_" + (Quickshell.env("USER") || "user") + "_" + Math.floor(Math.random() * 10000) + ".png"

    readonly property Timer startTimer: Timer {
        interval: 250
        repeat: false
        onTriggered: root.startProcess()
    }

    readonly property Process screenshotProcess: Process {
        command: ["sh", "-c", "geom=$(slurp) && grim -g \"$geom\" " + tempPath]
        onRunningChanged: {
            if (!running) {
                if (exitCode === 0) {
                    ocrProcess.running = false;
                    ocrProcess.running = true;
                } else {
                    root.running = false;
                    root.lastError = "Screenshot selection cancelled or failed.";
                    root.restoreDrawer();
                }
            }
        }
    }

    readonly property Process ocrProcess: Process {
        command: ["sh", "-c", "tesseract " + tempPath + " stdout -l eng 2>/dev/null | wl-copy && wl-paste"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.running = false;
                const result = text.trim();
                if (result.length > 0) {
                    root.ocrText = result;
                    Toaster.toast(qsTr("OCR Completed"), qsTr("Text copied to clipboard (%1 chars)").arg(result.length), "content_copy");
                } else {
                    root.lastError = "No text detected.";
                }
                root.restoreDrawer();
            }
        }
    }

    function restoreDrawer(): void {
        if (root.activeDrawer !== "") {
            const vis = Visibilities.getForActive();
            if (vis) {
                vis[root.activeDrawer] = true;
            }
            root.activeDrawer = "";
        }
    }

    function startProcess(): void {
        screenshotProcess.running = false;
        screenshotProcess.running = true;
    }

    function startOcr(): void {
        ocrText = "";
        lastError = "";
        running = true;
        activeDrawer = "";

        const vis = Visibilities.getForActive();
        if (vis) {
            if (vis.sidebar) {
                activeDrawer = "sidebar";
                vis.sidebar = false;
            } else if (vis.launcher) {
                activeDrawer = "launcher";
                vis.launcher = false;
            } else if (vis.dashboard) {
                activeDrawer = "dashboard";
                vis.dashboard = false;
            } else if (vis.session) {
                activeDrawer = "session";
                vis.session = false;
            } else if (vis.cheatsheet) {
                activeDrawer = "cheatsheet";
                vis.cheatsheet = false;
            }
        }

        if (activeDrawer !== "") {
            startTimer.restart();
        } else {
            startProcess();
        }
    }

    IpcHandler {
        target: "ocr"
        function start(): void {
            root.startOcr();
        }
    }

    CustomShortcut {
        name: "ocr"
        description: "Trigger screen OCR"
        onPressed: {
            if (!root.startupGraceActive) {
                root.startOcr();
            } else {
                console.log("[Ocr.qml] Ignoring shortcut trigger during startup grace period");
            }
        }
    }
}
