pragma Singleton

import QtQuick
import Quickshell
import qs.utils

Singleton {
    id: root

    property string geminiEndpoint: "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    property string ollamaEndpoint: "http://localhost:11434/api/chat"

    property int activeRequestsCount: 0
    readonly property bool loading: activeRequestsCount > 0
    property var requestQueue: []
    property string lastError: ""

    readonly property ListModel chatHistory: ListModel {}

    function clearChat(): void {
        chatHistory.clear();
        chatHistory.append({
            "role": "assistant",
            "message": "Hello! I am your Caelestia AI Copilot. How can I help you customize or control your desktop today?"
        });
    }

    function sendToOllama(): void {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", root.ollamaEndpoint, true);
        xhr.setRequestHeader("Content-Type", "application/json");

        const systemPrompt = "You are Caelestia AI Copilot, a helpful Linux/Arch desktop assistant. You can control the user's desktop shell by outputting raw JSON command blocks anywhere in your response (e.g. at the end). Make sure to wrap it in markdown json block:\n```json\n{\n  \"action\": \"<action_name>\",\n  ...\n}\n```\nAvailable Actions:\n1. Switch active workspace: {\"action\": \"workspace\", \"id\": 1-10}\n2. Set volume percentage: {\"action\": \"volume\", \"value\": 0-100}\n3. Toggle mute (audio or mic): {\"action\": \"mute\", \"type\": \"audio\"|\"mic\", \"state\": true|false}\n4. Launch application: {\"action\": \"exec\", \"command\": \"<command_name>\"} (e.g. alacritty, librewolf, nemo)\n5. Cycle wallpaper: {\"action\": \"wallpaper\", \"direction\": \"next\"|\"prev\"|\"random\"}\n6. Toggle shell panel drawer: {\"action\": \"drawer\", \"name\": \"launcher\"|\"dashboard\"|\"cheatsheet\"|\"sidebar\", \"state\": true|false}\n7. Toggle Do Not Disturb (DND) state: {\"action\": \"dnd\", \"state\": true|false}\n\nRules:\n- Be concise, helpful, and friendly.\n- Respond in standard markdown.\n- Under no circumstances run dangerous or destructive terminal commands.\n- You can combine multiple actions by outputting multiple JSON blocks or a list of actions.";

        const messages = [
            {
                "role": "system",
                "content": systemPrompt
            }
        ];

        for (let i = 0; i < chatHistory.count; i++) {
            const item = chatHistory.get(i);
            messages.push({
                "role": item.role,
                "content": item.message
            });
        }

        const payload = {
            "model": "llama3:latest",
            "messages": messages,
            "stream": false
        };

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                activeRequestsCount--;
                processNextRequest();
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        const assistantMsg = response.message.content;
                        if (typeof assistantMsg !== "string") throw new Error("Assistant response is not a string");
                        chatHistory.append({
                            "role": "assistant",
                            "message": assistantMsg
                        });

                        // Parse actions from assistant response
                        executeActionsFromText(assistantMsg);
                    } catch (e) {
                        lastError = "Failed to parse model response.";
                        console.error("[Copilot.qml error]", e);
                    }
                } else {
                    lastError = "Cannot connect to local Ollama server...";
                }
            }
        };

        xhr.send(JSON.stringify(payload));
    }

    function sendToGemini(apiKey: string): void {
        const xhr = new XMLHttpRequest();
        const url = root.geminiEndpoint + "?key=" + apiKey;
        xhr.open("POST", url, true);
        xhr.setRequestHeader("Content-Type", "application/json");

        const systemPrompt = "You are Caelestia AI Copilot, a helpful Linux/Arch desktop assistant. You can control the user's desktop shell by outputting raw JSON command blocks anywhere in your response (e.g. at the end). Make sure to wrap it in markdown json block:\n```json\n{\n  \"action\": \"<action_name>\",\n  ...\n}\n```\nAvailable Actions:\n1. Switch active workspace: {\"action\": \"workspace\", \"id\": 1-10}\n2. Set volume percentage: {\"action\": \"volume\", \"value\": 0-100}\n3. Toggle mute (audio or mic): {\"action\": \"mute\", \"type\": \"audio\"|\"mic\", \"state\": true|false}\n4. Launch application: {\"action\": \"exec\", \"command\": \"<command_name>\"} (e.g. alacritty, librewolf, nemo)\n5. Cycle wallpaper: {\"action\": \"wallpaper\", \"direction\": \"next\"|\"prev\"|\"random\"}\n6. Toggle shell panel drawer: {\"action\": \"drawer\", \"name\": \"launcher\"|\"dashboard\"|\"cheatsheet\"|\"sidebar\", \"state\": true|false}\n7. Toggle Do Not Disturb (DND) state: {\"action\": \"dnd\", \"state\": true|false}\n\nRules:\n- Be concise, helpful, and friendly.\n- Respond in standard markdown.\n- Under no circumstances run dangerous or destructive terminal commands.\n- You can combine multiple actions by outputting multiple JSON blocks or a list of actions.";

        const contents = [];
        for (let i = 1; i < chatHistory.count; i++) {
            const item = chatHistory.get(i);
            const mappedRole = item.role === "assistant" ? "model" : "user";
            contents.push({
                "role": mappedRole,
                "parts": [{"text": item.message}]
            });
        }

        const payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": systemPrompt}]
            }
        };

        let fallbackTriggered = false;
        const triggerFallback = () => {
            if (fallbackTriggered) return;
            fallbackTriggered = true;
            console.log("[Copilot.qml] Falling back to Ollama...");
            sendToOllama();
        };

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        const assistantMsg = response.candidates[0].content.parts[0].text;
                        if (typeof assistantMsg !== "string") throw new Error("Assistant response is not a string");
                        chatHistory.append({
                            "role": "assistant",
                            "message": assistantMsg
                        });

                        // Parse actions from assistant response
                        executeActionsFromText(assistantMsg);
                        activeRequestsCount--;
                        processNextRequest();
                    } catch (e) {
                        lastError = "Failed to parse Gemini response. Falling back to Ollama.";
                        console.error("[Copilot.qml Gemini error]", e);
                        triggerFallback();
                    }
                } else {
                    console.warn("[Copilot.qml] Gemini API request failed (status " + xhr.status + "). Falling back to Ollama.");
                    triggerFallback();
                }
            }
        };

        xhr.onerror = function() {
            console.warn("[Copilot.qml] Gemini API request network/CORS error. Falling back to Ollama.");
            triggerFallback();
        };

        xhr.send(JSON.stringify(payload));
    }

    function processNextRequest(): void {
        if (activeRequestsCount >= 4 || requestQueue.length === 0) return;
        const nextRequest = requestQueue.shift();
        activeRequestsCount++;
        lastError = "";
        const apiKey = Quickshell.env("GEMINI_API_KEY");
        if (apiKey) {
            sendToGemini(apiKey);
        } else {
            sendToOllama();
        }
    }

    function sendMessage(text: string): void {
        if (!text.trim()) return;

        chatHistory.append({
            "role": "user",
            "message": text
        });

        requestQueue.push(text);
        processNextRequest();
    }

    function executeActionsFromText(text: string): void {
        // Find markdown JSON blocks
        const regex = /```json\s*([\s\S]*?)\s*```/g;
        let match;
        while ((match = regex.exec(text)) !== null) {
            const jsonStr = match[1].trim();
            try {
                const actionObj = JSON.parse(jsonStr);
                if (Array.isArray(actionObj)) {
                    for (let i = 0; i < actionObj.length; i++) {
                        executeSingleAction(actionObj[i]);
                    }
                } else {
                    executeSingleAction(actionObj);
                }
            } catch (e) {
                console.warn("[Copilot.qml] Failed to parse action block:", jsonStr, e);
            }
        }
    }

    function executeSingleAction(act: var): void {
        if (!act || !act.action) return;

        console.log("[Copilot.qml] Executing AI action:", JSON.stringify(act));

        switch (act.action) {
            case "workspace":
                if (act.id !== undefined) {
                    Hypr.dispatch("workspace " + act.id);
                    Toaster.toast(qsTr("Workspace changed"), qsTr("Switched to workspace %1").arg(act.id), "grid_view");
                }
                break;
            case "volume":
                if (act.value !== undefined) {
                    const volReal = act.value / 100.0;
                    Audio.setVolume(volReal);
                    Toaster.toast(qsTr("Volume adjusted"), qsTr("Volume set to %1%").arg(act.value), "volume_up");
                }
                break;
            case "mute":
                if (act.state !== undefined) {
                    if (act.type === "mic") {
                        if (Audio.source && Audio.source.audio) {
                            Audio.source.audio.muted = act.state;
                        }
                    } else {
                        Audio.setStreamMuted(Audio.sink, act.state);
                    }
                    Toaster.toast(qsTr("Mute toggled"), qsTr("%1 muted: %2").arg(act.type === "mic" ? "Microphone" : "Audio").arg(act.state), act.state ? "volume_off" : "volume_up");
                }
                break;
            case "exec":
                if (act.command) {
                    Quickshell.execDetached([act.command]);
                    Toaster.toast(qsTr("App Launched"), qsTr("Started %1").arg(act.command), "rocket_launch");
                }
                break;
            case "wallpaper":
                if (act.direction === "random") {
                    Wallpapers.setRandom();
                } else if (act.direction === "next" || act.direction === "prev") {
                    // Let's cycle wallpaper
                    const allWalls = Wallpapers.list;
                    if (allWalls.length > 0) {
                        const currentIdx = allWalls.findIndex(w => w.path === Wallpapers.actualCurrent);
                        let nextIdx = 0;
                        if (currentIdx !== -1) {
                            if (act.direction === "next") {
                                nextIdx = (currentIdx + 1) % allWalls.length;
                            } else {
                                nextIdx = (currentIdx - 1 + allWalls.length) % allWalls.length;
                            }
                        }
                        Wallpapers.setWallpaper(allWalls[nextIdx].path);
                    }
                }
                break;
            case "drawer":
                if (act.name && act.state !== undefined) {
                    const vis = Visibilities.getForActive();
                    if (vis && vis[act.name] !== undefined) {
                        vis[act.name] = act.state;
                    }
                }
                break;
            case "dnd":
                if (act.state !== undefined) {
                    Notifs.dnd = act.state;
                    Toaster.toast(
                        act.state ? qsTr("Do not disturb enabled") : qsTr("Do not disturb disabled"),
                        act.state ? qsTr("Popup notifications are now disabled") : qsTr("Popup notifications are now enabled"),
                        act.state ? "do_not_disturb_on" : "do_not_disturb_off"
                    );
                }
                break;
            default:
                console.warn("[Copilot.qml] Unknown action:", act.action);
        }
    }

    function getChatHistoryCount(): int {
        return chatHistory.count;
    }

    function getChatHistoryItemJson(index: int): string {
        if (index < 0 || index >= chatHistory.count) return "";
        const item = chatHistory.get(index);
        return JSON.stringify({
            "role": item.role,
            "message": item.message
        });
    }

    Component.onCompleted: {
        clearChat();
    }
}
