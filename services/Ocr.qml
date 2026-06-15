pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

Singleton {
    id: root

    property string ocrText: ""
    property string translatedText: ""
    property bool running: false
    property string lastError: ""

    readonly property Process ocrProcess: Process {
        command: ["sh", "-c", "geom=$(slurp) && grim -g \"$geom\" /tmp/ocr_capture.png && tesseract /tmp/ocr_capture.png stdout -l eng 2>/dev/null | wl-copy && wl-paste"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.running = false;
                const result = text.trim();
                if (result.length > 0) {
                    root.ocrText = result;
                    Toaster.toast(qsTr("OCR Completed"), qsTr("Text copied to clipboard (%1 chars)").arg(result.length), "content_copy");
                } else {
                    root.lastError = "No text detected, or operation cancelled.";
                }
            }
        }
    }

    function startOcr(): void {
        ocrText = "";
        translatedText = "";
        lastError = "";
        running = true;

        ocrProcess.running = false;
        ocrProcess.running = true;
    }

    function translateText(targetLang: string): void {
        if (!ocrText.trim()) return;

        translatedText = "... translating ...";
        lastError = "";

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:11434/api/chat", true);
        xhr.setRequestHeader("Content-Type", "application/json");

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
                    root.translatedText = "";
                    root.lastError = "Ollama connection error.";
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
                    root.translatedText = "";
                    root.lastError = "Ollama connection error.";
                }
            }
        };

        xhr.send(JSON.stringify(payload));
    }
}
