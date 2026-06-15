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
    property string translatedText: ""
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
        translatedText = "";
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

    function translateText(targetLang: string): void {
        if (!ocrText.trim()) return;

        translatedText = "... translating ...";
        lastError = "";

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:11434/api/chat", true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.timeout = 10000;
        xhr.ontimeout = function() {
            root.translatedText = "";
            root.lastError = "Ollama connection error. (Request timed out)";
            console.error("[Ocr.qml translation timeout]");
        };
        xhr.onerror = function() {
            root.translatedText = "";
            root.lastError = "Ollama connection error. (Request failed)";
            console.error("[Ocr.qml translation error]");
        };

        const payload = {
            "model": "llama3:latest",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional desktop translator. Translate the text exactly into the requested language. Provide ONLY the direct translation. Do not include markdown blocks, greetings, explanations, or any extra text."
                },
                {
                    "role": "user",
                    "content": "Translate the following text into " + targetLang + ":\n\n" + ocrText
                }
            ],
            "stream": false
        };

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        root.translatedText = response.message.content.trim();
                    } catch (e) {
                        root.translatedText = "";
                        root.lastError = "Translation failed.";
                    }
                } else {
                    if (!root.lastError) {
                        root.translatedText = "";
                        root.lastError = "Ollama connection error.";
                    }
                }
            }
        };

        xhr.send(JSON.stringify(payload));
    }

    function explainText(): void {
        if (!ocrText.trim()) return;

        translatedText = "... explaining ...";
        lastError = "";

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:11434/api/chat", true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.timeout = 10000;
        xhr.ontimeout = function() {
            root.translatedText = "";
            root.lastError = "Ollama connection error. (Request timed out)";
            console.error("[Ocr.qml explanation timeout]");
        };
        xhr.onerror = function() {
            root.translatedText = "";
            root.lastError = "Ollama connection error. (Request failed)";
            console.error("[Ocr.qml explanation error]");
        };

        const payload = {
            "model": "llama3:latest",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful desktop assistant. Briefly explain the meaning or context of the provided screen-captured text in 1-2 concise sentences."
                },
                {
                    "role": "user",
                    "content": "Explain the following text:\n\n" + ocrText
                }
            ],
            "stream": false
        };

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        root.translatedText = response.message.content.trim();
                    } catch (e) {
                        root.translatedText = "";
                        root.lastError = "Explanation failed.";
                    }
                } else {
                    if (!root.lastError) {
                        root.translatedText = "";
                        root.lastError = "Ollama connection error.";
                    }
                }
            }
        };

        xhr.send(JSON.stringify(payload));
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
