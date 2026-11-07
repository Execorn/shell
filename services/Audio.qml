pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import Caelestia
import Caelestia.Config
import Caelestia.Services

Singleton {
    id: root

    property string previousSinkName: ""
    property string previousSourceName: ""
    property bool syncingNodes: false
    property bool startupEnumerating: false
    property var startupPendingNodeIds: []
    property var readyOnceNodeIds: ({})
    property string lastToastedSinkName: ""
    property double lastToastedSinkTime: 0
    property double lastPrioritySinkConnectTime: 0
    property string lastToastedSourceName: ""
    property double lastToastedSourceTime: 0
    property double lastPrioritySourceConnectTime: 0

    readonly property Timer startupEnumTimer: Timer {
        interval: 800
        repeat: false
        onTriggered: {
            root.startupPendingNodeIds = [];
            root.startupEnumerating = false;
            root.previousSinkName = root.activePhysicalSinkDesc || root.previousSinkName || qsTr("Unknown Device");
            root.previousSourceName = root.activePhysicalSourceDesc || root.previousSourceName || qsTr("Unknown Device");
            root.previousPhysicalSinkDesc = root.previousSinkName;
            root.previousPhysicalSourceDesc = root.previousSourceName;
        }
    }

    property var sinks: []
    property var sources: []
    property var streams: []
    property var physicalSinks: []
    property var physicalSources: []

    property var sink: null
    readonly property var source: Pipewire ? Pipewire.defaultAudioSource : null

    property real customVolume: -1
    property int customMuted: -1 // -1 = unset, 0 = false, 1 = true

    readonly property bool muted: customMuted !== -1 ? (customMuted === 1) : (sink && sink.ready && sink.audio ? !!sink.audio.muted : false)
    readonly property real volume: customVolume !== -1 ? customVolume : (sink && sink.ready && sink.audio ? sink.audio.volume : 0)

    readonly property bool sourceMuted: source && source.ready && source.audio ? !!source.audio.muted : false
    readonly property real sourceVolume: source && source.ready && source.audio ? source.audio.volume : 0

    readonly property alias cava: cava
    readonly property alias beatTracker: beatTracker

    signal osdTriggered

    function isNodeValid(node: var): bool {
        return !!node && !!Pipewire && !!Pipewire.nodes && Pipewire.nodes.values.indexOf(node) !== -1 && (node.ready || !!(node.id !== undefined && root.readyOnceNodeIds[node.id]));
    }

    function setVolume(newVolume: real): void {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        const isVirtual = isNodeValid(dSink) && ((dSink.properties && dSink.properties["node.virtual"] === "true") || dSink.name === "easyeffects_sink" || dSink.name === "riced_equalizer_sink");
        const targetId = (isVirtual && root.physicalDriverId !== -1) ? root.physicalDriverId : (isNodeValid(sink) ? sink.id : -1);

        if (targetId !== -1) {
            const volClamped = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
            volumeSetProc.running = false;
            volumeSetProc.command = ["wpctl", "set-volume", targetId.toString(), volClamped.toFixed(2)];
            volumeSetProc.running = true;
            root.customVolume = volClamped;
            root.customMuted = 0;
        }

        if (!isVirtual && isNodeValid(sink) && sink.audio) {
            sink.audio.muted = false;
            sink.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }

        root.osdTriggered();
    }

    function incrementVolume(amount: var): void {
        setVolume(volume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementVolume(amount: var): void {
        setVolume(volume - (amount || GlobalConfig.services.audioIncrement));
    }

    function setSourceVolume(newVolume: real): void {
        if (isNodeValid(source) && source.audio) {
            source.audio.muted = false;
            source.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function incrementSourceVolume(amount: var): void {
        setSourceVolume(sourceVolume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementSourceVolume(amount: var): void {
        setSourceVolume(sourceVolume - (amount || GlobalConfig.services.audioIncrement));
    }

    property string preferredPhysicalSink: ""
    property string lastRoutedPhysicalSink: ""
    property bool manualSinkOverride: false
    property var knownPhysicalSinkNames: []
    property string previousPhysicalSinkDesc: ""

    readonly property string activePhysicalSinkDesc: {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        if (isNodeValid(dSink) && dSink.name === "riced_equalizer_sink") {
            const node = physicalSinks.find(s => isNodeValid(s) && s.name === preferredPhysicalSink);
            if (node) return node.description || node.name || "";
        } else if (isNodeValid(sink) && sink.name !== "riced_equalizer_sink" && sink.name !== "easyeffects_sink" && (!sink.properties || sink.properties["node.virtual"] !== "true")) {
            return sink.description || sink.name || "";
        }
        return "";
    }

    onActivePhysicalSinkDescChanged: {
        if (root.syncingNodes || !activePhysicalSinkDesc)
            return;
        notifyOutputChanged(activePhysicalSinkDesc);
    }

    readonly property Process eqRouteProc: Process {}

    readonly property int activePhysicalSinkId: {
        if (!isNodeValid(sink)) return -1;
        if (sink.name === "riced_equalizer_sink") {
            const node = physicalSinks.find(s => isNodeValid(s) && s.name === preferredPhysicalSink);
            return node ? node.id : -1;
        }
        return sink.id;
    }

    function routeEqualizerTo(sinkName: string): void {
        if (!sinkName) return;
        eqRouteProc.running = false;
        eqRouteProc.command = [
            "python3", "-c",
            `import subprocess, sys
target = sys.argv[1]
try:
    sinks = {}
    for line in subprocess.check_output(["pactl", "list", "sinks", "short"]).decode("utf-8", errors="replace").splitlines():
        parts = line.split("\\t")
        if len(parts) >= 2:
            sinks[parts[0].strip()] = parts[1].strip()
    out = subprocess.check_output(["pactl", "list", "sink-inputs"]).decode("utf-8", errors="replace")
    for block in out.split("Sink Input #"):
        if not block.strip(): continue
        lines = block.splitlines()
        sid = lines[0].strip()
        if "output.filter-chain" in block or "Riced Equalizer Sink" in block:
            cur_sink = next((l.split("Sink:")[1].strip() for l in lines if l.strip().startswith("Sink:")), "")
            if sinks.get(cur_sink) != target and cur_sink != target:
                subprocess.run(["pactl", "move-sink-input", sid, target], check=True)
except Exception:
    pass
`,
            sinkName
        ];
        eqRouteProc.running = true;
    }

    function setAudioSink(newSink: var): void {
        if (!newSink || !newSink.name) return;
        manualSinkOverride = true;
        preferredPhysicalSink = newSink.name;
        root.lastConfiguredPhysicalSink = newSink.name;
        if (Pipewire) {
            const dSink = Pipewire.defaultAudioSink;
            const isEQ = isNodeValid(dSink) && dSink.name === "riced_equalizer_sink";
            if (isEQ) {
                Qt.callLater(root.updateActiveSink);
            } else {
                Pipewire.preferredDefaultAudioSink = newSink;
            }
        }
    }

    property string lastConfiguredPhysicalSink: ""
    property string preferredPhysicalSource: ""
    property string lastRoutedPhysicalSource: ""
    property bool manualSourceOverride: false
    property var knownPhysicalSourceNames: []
    property string previousPhysicalSourceDesc: ""

    readonly property string activePhysicalSourceDesc: {
        const node = physicalSources.find(s => isNodeValid(s) && s.name === preferredPhysicalSource);
        if (node) return node.description || node.name || "";
        if (isNodeValid(source) && source.name !== "riced_microphone_source" && source.name !== "easyeffects_source" && (!source.properties || source.properties["node.virtual"] !== "true"))
            return source.description || source.name || "";
        return "";
    }

    onActivePhysicalSourceDescChanged: {
        if (root.syncingNodes || !activePhysicalSourceDesc)
            return;
        notifyInputChanged(activePhysicalSourceDesc);
    }

    readonly property Process micRouteProc: Process {}

    readonly property Process cardProfileFixProc: Process {
        command: [
            "python3", "-c",
            `import subprocess
try:
    cards = subprocess.check_output(["pactl", "list", "cards"]).decode("utf-8", errors="replace")
    for block in cards.split("Card #"):
        if "alsa_card.pci" in block and "Active Profile: output:analog-stereo\\n" in block:
            card_name = [l.split("Name: ")[1].strip() for l in block.splitlines() if "Name: " in l][0]
            subprocess.run(["pactl", "set-card-profile", card_name, "output:analog-stereo+input:analog-stereo"], check=True)
except Exception:
    pass
`
        ]
    }

    readonly property int activePhysicalSourceId: {
        const prefNode = physicalSources.find(s => isNodeValid(s) && s.name === preferredPhysicalSource);
        if (prefNode && prefNode.id !== undefined) return prefNode.id;
        if (isNodeValid(source) && physicalSources.indexOf(source) !== -1 && source.id !== undefined) return source.id;
        return (physicalSources.length > 0 && physicalSources[0]?.id !== undefined) ? physicalSources[0].id : -1;
    }

    function routeMicrophoneFrom(sourceName: string): void {
        if (!sourceName) return;
        micRouteProc.running = false;
        micRouteProc.command = [
            "python3", "-c",
            `import subprocess, sys
target = sys.argv[1]
try:
    sources = {}
    for line in subprocess.check_output(["pactl", "list", "sources", "short"]).decode("utf-8", errors="replace").splitlines():
        parts = line.split("\\t")
        if len(parts) >= 2:
            sources[parts[0].strip()] = parts[1].strip()
    out = subprocess.check_output(["pactl", "list", "source-outputs"]).decode("utf-8", errors="replace")
    for block in out.split("Source Output #"):
        if not block.strip(): continue
        lines = block.splitlines()
        sid = lines[0].strip()
        if "input.filter-chain" in block or "Riced Microphone Source" in block:
            cur_src = next((l.split("Source:")[1].strip() for l in lines if l.strip().startswith("Source:")), "")
            if sources.get(cur_src) != target and cur_src != target:
                subprocess.run(["pactl", "move-source-output", sid, target], check=True)
except Exception:
    pass

try:
    cur_def = subprocess.check_output(["pactl", "get-default-source"]).decode("utf-8", errors="replace").strip()
    if cur_def != target:
        subprocess.run(["pactl", "set-default-source", target], check=True)
except Exception:
    pass
`,
            sourceName
        ];
        micRouteProc.running = true;
    }

    function setAudioSource(newSource: var): void {
        if (!newSource) {
            if (Pipewire) Pipewire.preferredDefaultAudioSource = null;
            return;
        }
        if (!newSource.name) return;
        manualSourceOverride = true;
        preferredPhysicalSource = newSource.name;
        if (Pipewire) {
            Pipewire.preferredDefaultAudioSource = newSource;
        }
        Qt.callLater(root.updateActiveSource);
    }

    property int physicalDriverId: -1

    readonly property Process volumeSetProc: Process {}
    readonly property Process muteSetProc: Process {}

    function getBestOutputSinkName(): string {
        if (physicalSinks.length === 0) return "";
        
        // 1. Look for Bluetooth headphones/speakers
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("bluez_output") !== -1 || s.name.indexOf("bluez_sink") !== -1)) {
                return s.name;
            }
        }
        
        // 2. Look for USB audio cards / speakers (excluding microphones/inputs)
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("alsa_output.usb") === 0 || s.name.indexOf("usb-") !== -1)) {
                const nameLower = s.name.toLowerCase();
                const descLower = (s.description || "").toLowerCase();
                const isMic = nameLower.indexOf("micro") !== -1 || nameLower.indexOf("mic") !== -1 || nameLower.indexOf("input") !== -1;
                const isLoopback = nameLower.indexOf("loopback") !== -1 || descLower.indexOf("loopback") !== -1;
                if (!isMic && !isLoopback) {
                    return s.name;
                }
            }
        }
        
        // 3. Fallback to any physical sink that is not the built-in speaker and not a mic, just in case
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && s.name !== "alsa_output.pci-0000_05_00.6.analog-stereo" && s.name.indexOf("pci-") === -1) {
                const nameLower = s.name.toLowerCase();
                const isMic = nameLower.indexOf("micro") !== -1 || nameLower.indexOf("mic") !== -1 || nameLower.indexOf("input") !== -1;
                if (!isMic) {
                    return s.name;
                }
            }
        }
        
        // 4. Default fallback: computer speakers
        const internalSink = physicalSinks.find(s => isNodeValid(s) && s.name && (s.name.indexOf("pci-") !== -1 || s.name.indexOf("analog-stereo") !== -1));
        if (internalSink && internalSink.name) {
            return internalSink.name;
        }
        
        const firstSink = physicalSinks.find(s => isNodeValid(s) && s.name);
        return firstSink ? firstSink.name : "";
    }

    function updateActiveSink(): void {
        const prefExists = physicalSinks.some(s => isNodeValid(s) && s.name === preferredPhysicalSink);
        if (!prefExists) {
            root.manualSinkOverride = false;
            preferredPhysicalSink = "";
        }

        if (!root.manualSinkOverride || preferredPhysicalSink === "") {
            const bestName = getBestOutputSinkName();
            if (bestName !== "") {
                preferredPhysicalSink = bestName;
            }
        }

        const activeNode = physicalSinks.find(s => isNodeValid(s) && s.name === preferredPhysicalSink);
        const bestSinkName = getBestOutputSinkName();
        const bestSinkNode = physicalSinks.find(s => isNodeValid(s) && s.name === bestSinkName);
        root.physicalDriverId = activeNode ? activeNode.id : (bestSinkNode ? bestSinkNode.id : -1);

        let resolvedSink = null;
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        if (isNodeValid(dSink)) {
            const isEQ = dSink.name === "riced_equalizer_sink";
            if (isEQ) {
                if (preferredPhysicalSink !== "" && preferredPhysicalSink !== lastRoutedPhysicalSink) {
                    routeEqualizerTo(preferredPhysicalSink);
                    lastRoutedPhysicalSink = preferredPhysicalSink;
                }
                if (dSink.audio && (dSink.audio.volume < 0.99 || dSink.audio.muted)) {
                    dSink.audio.muted = false;
                    dSink.audio.volume = 1.0;
                }
            } else {
                lastRoutedPhysicalSink = "";
                if (!root.manualSinkOverride && preferredPhysicalSink !== "" && preferredPhysicalSink !== root.lastConfiguredPhysicalSink) {
                    const targetNode = physicalSinks.find(s => isNodeValid(s) && s.name === preferredPhysicalSink);
                    if (targetNode && Pipewire.preferredDefaultAudioSink !== targetNode) {
                        Pipewire.preferredDefaultAudioSink = targetNode;
                    }
                    root.lastConfiguredPhysicalSink = preferredPhysicalSink;
                }
            }

            const isVirtualSink = (dSink.properties && dSink.properties["node.virtual"] === "true") || dSink.name === "easyeffects_sink" || dSink.name === "riced_equalizer_sink";
            if (isVirtualSink) {
                const driverId = root.physicalDriverId;
                if (driverId !== -1) {
                    const physicalSink = sinks.find(n => isNodeValid(n) && n.id === driverId);
                    if (physicalSink && (!physicalSink.properties || physicalSink.properties["node.virtual"] !== "true") && physicalSink.name !== "easyeffects_sink" && physicalSink.name !== "riced_equalizer_sink") {
                        resolvedSink = physicalSink;
                    }
                }
                if (!resolvedSink) {
                    root.customVolume = -1;
                    root.customMuted = -1;
                    const prefSink = Pipewire ? Pipewire.preferredDefaultAudioSink : null;
                    if (isNodeValid(prefSink) && (!prefSink.properties || prefSink.properties["node.virtual"] !== "true") && prefSink.name !== "easyeffects_sink" && prefSink.name !== "riced_equalizer_sink") {
                        resolvedSink = prefSink;
                    } else {
                        resolvedSink = physicalSinks.find(isNodeValid) || null;
                    }
                }
            } else {
                resolvedSink = dSink;
                root.customVolume = -1;
                root.customMuted = -1;
            }
        }
        if (root.sink !== resolvedSink) {
            root.sink = resolvedSink;
        }
    }

    function cycleNextAudioOutput(): void {
        if (physicalSinks.length === 0)
            return;

        const currentIndex = physicalSinks.findIndex(s => s.id === root.activePhysicalSinkId);
        const nextIndex = currentIndex !== -1 ? (currentIndex + 1) % physicalSinks.length : 0;
        setAudioSink(physicalSinks[nextIndex]);
    }

    function getBestInputSourceName(): string {
        if (physicalSources.length === 0) return "";
        
        // 1. Look for Bluetooth microphone
        for (let i = 0; i < physicalSources.length; i++) {
            const s = physicalSources[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("bluez_input") !== -1 || s.name.indexOf("bluez_source") !== -1)) {
                return s.name;
            }
        }
        
        // 2. Look for dedicated USB microphone (excluding loopback & audio interface instrument inputs)
        for (let i = 0; i < physicalSources.length; i++) {
            const s = physicalSources[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("alsa_input.usb") === 0 || s.name.indexOf("usb-") !== -1)) {
                const nameLower = s.name.toLowerCase();
                const descLower = (s.description || "").toLowerCase();
                const isLoopback = nameLower.indexOf("loopback") !== -1 || descLower.indexOf("loopback") !== -1 || nameLower.indexOf("hifi__line2") !== -1;
                const isGuitarInterface = nameLower.indexOf("minifuse") !== -1 || descLower.indexOf("minifuse") !== -1 || descLower.indexOf("inst ") !== -1;
                if (!isLoopback && !isGuitarInterface) {
                    return s.name;
                }
            }
        }
        
        // 3. Fallback to laptop internal microphone
        const internalSource = physicalSources.find(s => isNodeValid(s) && s.name && (s.name.indexOf("pci-") !== -1 || s.name.indexOf("analog-stereo") !== -1));
        if (internalSource && internalSource.name) {
            return internalSource.name;
        }

        // 4. Fallback to any non-loopback source
        const nonLoopbackSource = physicalSources.find(s => {
            if (!isNodeValid(s) || !s.name) return false;
            const nameLower = s.name.toLowerCase();
            const descLower = (s.description || "").toLowerCase();
            return nameLower.indexOf("loopback") === -1 && descLower.indexOf("loopback") === -1 && nameLower.indexOf("hifi__line2") === -1;
        });
        if (nonLoopbackSource && nonLoopbackSource.name) {
            return nonLoopbackSource.name;
        }
        
        const firstSource = physicalSources.find(s => isNodeValid(s) && s.name);
        return firstSource ? firstSource.name : "";
    }

    function updateActiveSource(): void {
        const prefExists = physicalSources.some(s => isNodeValid(s) && s.name === preferredPhysicalSource);
        if (!prefExists) {
            root.manualSourceOverride = false;
            preferredPhysicalSource = "";
        }

        if (!root.manualSourceOverride || preferredPhysicalSource === "") {
            const bestName = getBestInputSourceName();
            if (bestName !== "") {
                preferredPhysicalSource = bestName;
            }
        }

        const activeNode = physicalSources.find(s => isNodeValid(s) && s.name === preferredPhysicalSource);

        if (activeNode && preferredPhysicalSource !== "") {
            if (preferredPhysicalSource !== lastRoutedPhysicalSource) {
                routeMicrophoneFrom(preferredPhysicalSource);
                lastRoutedPhysicalSource = preferredPhysicalSource;
            }
            if (Pipewire && Pipewire.preferredDefaultAudioSource !== activeNode) {
                Pipewire.preferredDefaultAudioSource = activeNode;
            }
        }
    }

    function cycleNextAudioInput(): void {
        if (physicalSources.length === 0)
            return;

        const currentIndex = physicalSources.findIndex(s => s.id === root.activePhysicalSourceId);
        const nextIndex = currentIndex !== -1 ? (currentIndex + 1) % physicalSources.length : 0;
        setAudioSource(physicalSources[nextIndex]);
    }

    function setStreamVolume(stream: var, newVolume: real): void {
        if (isNodeValid(stream) && stream.audio) {
            stream.audio.muted = false;
            stream.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function setStreamMuted(stream: var, muted: bool): void {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        const isVirtual = isNodeValid(dSink) && ((dSink.properties && dSink.properties["node.virtual"] === "true") || dSink.name === "easyeffects_sink" || dSink.name === "riced_equalizer_sink");
        const targetId = (stream === root.sink && isVirtual && root.physicalDriverId !== -1) ? root.physicalDriverId : (stream === root.sink && isNodeValid(root.sink) ? root.sink.id : -1);

        if (targetId !== -1) {
            muteSetProc.running = false;
            muteSetProc.command = ["wpctl", "set-mute", targetId.toString(), muted ? "1" : "0"];
            muteSetProc.running = true;
            root.customMuted = muted ? 1 : 0;
        }

        const isDefaultSink = stream === root.sink;
        if ((!isDefaultSink || !isVirtual) && isNodeValid(stream) && stream.audio) {
            stream.audio.muted = muted;
        }
    }

    function getStreamVolume(stream: var): real {
        return isNodeValid(stream) ? (stream.audio?.volume ?? 0) : 0;
    }

    function getStreamMuted(stream: var): bool {
        return isNodeValid(stream) ? !!stream.audio?.muted : false;
    }

    function getStreamName(stream: var): string {
        if (!isNodeValid(stream))
            return qsTr("Unknown");
        return (stream.properties && stream.properties["application.name"]) || stream.description || stream.name || qsTr("Unknown Application");
    }

    function notifyOutputChanged(newSinkName: string): void {
        if (!newSinkName || newSinkName === qsTr("Unknown Device") || newSinkName === "riced_equalizer_sink" || newSinkName === "easyeffects_sink" || newSinkName === "Riced Equalizer Sink" || newSinkName === "EasyEffects Sink")
            return;

        const now = Date.now();
        if (root.lastPrioritySinkConnectTime > 0 && (now - root.lastPrioritySinkConnectTime) < 1500 && newSinkName !== root.lastToastedSinkName && root.lastToastedSinkName !== "") {
            const hasPriority = physicalSinks.some(s => isNodeValid(s) && s.name && (s.name.indexOf("bluez_") !== -1 || s.name.indexOf("usb") !== -1));
            if (!hasPriority)
                return;
        }

        if (!root.startupEnumerating && previousSinkName && previousSinkName !== qsTr("Unknown Device") && previousSinkName !== newSinkName && GlobalConfig.utilities.toasts.audioOutputChanged) {
            if (newSinkName !== root.lastToastedSinkName || (now - root.lastToastedSinkTime) >= 1500) {
                const title = qsTr("Audio output changed");
                if (Toaster.toasts) {
                    for (let i = 0; i < Toaster.toasts.length; i++) {
                        const t = Toaster.toasts[i];
                        if (t && t.title === title && !t.closed && typeof t.close === "function")
                            t.close();
                    }
                }
                Toaster.toast(title, qsTr("Now using: %1").arg(newSinkName), "volume_up");
                root.lastToastedSinkName = newSinkName;
                root.lastToastedSinkTime = now;
            }
        }

        previousSinkName = newSinkName;
        previousPhysicalSinkDesc = newSinkName;
    }

    function notifyInputChanged(newSourceName: string): void {
        if (!newSourceName || newSourceName === qsTr("Unknown Device") || newSourceName === "riced_microphone_source" || newSourceName === "easyeffects_source" || newSourceName === "Riced Microphone Source" || newSourceName === "EasyEffects Source")
            return;

        const now = Date.now();
        if (root.lastPrioritySourceConnectTime > 0 && (now - root.lastPrioritySourceConnectTime) < 1500 && newSourceName !== root.lastToastedSourceName && root.lastToastedSourceName !== "") {
            const hasPriority = physicalSources.some(s => isNodeValid(s) && s.name && (s.name.indexOf("bluez_") !== -1 || s.name.indexOf("usb") !== -1));
            if (!hasPriority)
                return;
        }

        if (!root.startupEnumerating && previousSourceName && previousSourceName !== qsTr("Unknown Device") && previousSourceName !== newSourceName && GlobalConfig.utilities.toasts.audioInputChanged) {
            if (newSourceName !== root.lastToastedSourceName || (now - root.lastToastedSourceTime) >= 1500) {
                const title = qsTr("Audio input changed");
                if (Toaster.toasts) {
                    for (let i = 0; i < Toaster.toasts.length; i++) {
                        const t = Toaster.toasts[i];
                        if (t && t.title === title && !t.closed && typeof t.close === "function")
                            t.close();
                    }
                }
                Toaster.toast(title, qsTr("Now using: %1").arg(newSourceName), "mic");
                root.lastToastedSourceName = newSourceName;
                root.lastToastedSourceTime = now;
            }
        }

        previousSourceName = newSourceName;
        previousPhysicalSourceDesc = newSourceName;
    }

    onSinkChanged: {
        root.customVolume = -1;
        root.customMuted = -1;
        if (root.syncingNodes || !isNodeValid(sink))
            return;

        if (sink.name === "riced_equalizer_sink" || sink.name === "easyeffects_sink")
            return;

        const newSinkName = sink.description || sink.name || qsTr("Unknown Device");
        notifyOutputChanged(newSinkName);
    }

    onSourceChanged: {
        if (root.syncingNodes || !isNodeValid(source))
            return;

        if (source.name === "riced_microphone_source" || source.name === "easyeffects_source")
            return;

        if (preferredPhysicalSource !== "" && physicalSources.some(s => isNodeValid(s) && s.name === preferredPhysicalSource))
            return;

        const newSourceName = source.description || source.name || qsTr("Unknown Device");
        notifyInputChanged(newSourceName);
    }

    function syncNodes(): void {
        if (!Pipewire || !Pipewire.nodes) return;

        const newSinks = [];
        const newSources = [];
        const newStreams = [];
        const newPhysicalSinks = [];
        const newPhysicalSources = [];
        const trackerObjects = [];
        const nextReadyOnce = {};

        for (const node of Pipewire.nodes.values) {
            if (!node) continue;

            // Dynamically listen to readyChanged to trigger sync when it changes
            try {
                node.readyChanged.disconnect(root.syncNodes);
            } catch (e) {}
            try {
                node.readyChanged.connect(root.syncNodes);
            } catch (e) {}

            const isReady = node.ready || !!(node.id !== undefined && root.readyOnceNodeIds[node.id]);
            if (isReady && node.id !== undefined) {
                nextReadyOnce[node.id] = true;
            }

            if (!node.isStream) {
                const isVirtual = (node.properties && node.properties["node.virtual"] === "true") || node.name === "easyeffects_sink" || node.name === "easyeffects_source" || node.name === "riced_equalizer_sink" || node.name === "riced_microphone_source";

                if (node.isSink) {
                    trackerObjects.push(node);
                    if (isReady) {
                        newSinks.push(node);
                        if (!isVirtual) {
                            newPhysicalSinks.push(node);
                        }
                    }
                } else if (node.audio) {
                    trackerObjects.push(node);
                    if (isReady) {
                        newSources.push(node);
                        if (!isVirtual) {
                            newPhysicalSources.push(node);
                        }
                    }
                }
            } else if (node.audio) {
                trackerObjects.push(node);
                if (isReady) {
                    newStreams.push(node);
                }
            }
        }

        root.readyOnceNodeIds = nextReadyOnce;
        root.syncingNodes = true;
        root.sinks = newSinks;
        root.sources = newSources;
        root.streams = newStreams;
        root.physicalSinks = newPhysicalSinks;
        root.physicalSources = newPhysicalSources;

        const currentPhysicalNames = newPhysicalSinks.map(s => s.name);
        if (!root.startupEnumerating && root.knownPhysicalSinkNames.length > 0) {
            for (let i = 0; i < currentPhysicalNames.length; i++) {
                const name = currentPhysicalNames[i];
                if (root.knownPhysicalSinkNames.indexOf(name) === -1) {
                    console.log("[Audio.qml] Newly connected physical sink:", name);
                    if (name.indexOf("bluez_output") !== -1 || name.indexOf("bluez_sink") !== -1 || name.indexOf("usb") !== -1) {
                        console.log("[Audio.qml] Auto-switching to newly connected priority device:", name);
                        root.manualSinkOverride = false;
                        root.lastPrioritySinkConnectTime = Date.now();
                    }
                }
            }
        }
        root.knownPhysicalSinkNames = currentPhysicalNames;

        const currentPhysicalSourceNames = newPhysicalSources.map(s => s.name);
        if (!root.startupEnumerating && root.knownPhysicalSourceNames.length > 0) {
            for (let i = 0; i < currentPhysicalSourceNames.length; i++) {
                const name = currentPhysicalSourceNames[i];
                if (root.knownPhysicalSourceNames.indexOf(name) === -1) {
                    console.log("[Audio.qml] Newly connected physical source:", name);
                    const nameLower = name.toLowerCase();
                    const isIgnoredUsbSource = nameLower.indexOf("loopback") !== -1 || nameLower.indexOf("hifi__line2") !== -1 || nameLower.indexOf("minifuse") !== -1;
                    if (name.indexOf("bluez_input") !== -1 || name.indexOf("bluez_source") !== -1 || (name.indexOf("usb") !== -1 && !isIgnoredUsbSource)) {
                        console.log("[Audio.qml] Auto-switching to newly connected priority input device:", name);
                        root.manualSourceOverride = false;
                        root.lastPrioritySourceConnectTime = Date.now();
                    }
                }
            }
        }
        root.knownPhysicalSourceNames = currentPhysicalSourceNames;

        if (newPhysicalSources.length === 0 && !cardProfileFixProc.running) {
            cardProfileFixProc.running = true;
        }

        let objectsChanged = false;
        if (!tracker.objects || tracker.objects.length !== trackerObjects.length) {
            objectsChanged = true;
        } else {
            for (let i = 0; i < trackerObjects.length; i++) {
                if (tracker.objects[i] !== trackerObjects[i]) {
                    objectsChanged = true;
                    break;
                }
            }
        }
        if (objectsChanged) {
            tracker.objects = trackerObjects;
        }

        if (Pipewire.nodes.values.length === 0) {
            root.previousSinkName = "";
            root.previousPhysicalSinkDesc = "";
            root.previousSourceName = "";
            root.previousPhysicalSourceDesc = "";
            root.lastToastedSinkName = "";
            root.lastToastedSinkTime = 0;
            root.lastPrioritySinkConnectTime = 0;
            root.lastToastedSourceName = "";
            root.lastToastedSourceTime = 0;
            root.lastPrioritySourceConnectTime = 0;
        }

        root.updateActiveSink();
        root.updateActiveSource();
        root.syncingNodes = false;

        if (root.startupEnumerating && root.startupPendingNodeIds.length > 0) {
            const stillPending = root.startupPendingNodeIds.filter(id => {
                const n = Pipewire.nodes.values.find(node => node && node.id === id);
                return n && !n.ready;
            });
            root.startupPendingNodeIds = stillPending;
            if (stillPending.length === 0 && !startupEnumTimer.running) {
                root.startupEnumerating = false;
            }
        }

        if (root.activePhysicalSinkDesc)
            root.notifyOutputChanged(root.activePhysicalSinkDesc);
        if (root.activePhysicalSourceDesc)
            root.notifyInputChanged(root.activePhysicalSourceDesc);

        Qt.callLater(root.updateActiveSink);
        Qt.callLater(root.updateActiveSource);
    }

    Component.onCompleted: {
        if (!Quickshell.env("PYTEST_CURRENT_TEST")) {
            root.startupEnumerating = true;
            startupEnumTimer.restart();
        } else if (Pipewire && Pipewire.nodes && Pipewire.nodes.values) {
            const pending = [];
            for (const node of Pipewire.nodes.values) {
                if (node && !node.isStream && !node.ready && node.id !== undefined) {
                    pending.push(node.id);
                }
            }
            if (pending.length > 0) {
                root.startupPendingNodeIds = pending;
                root.startupEnumerating = true;
                startupEnumTimer.restart();
            }
        }
        root.syncNodes();
        previousSinkName = activePhysicalSinkDesc || qsTr("Unknown Device");
        previousSourceName = activePhysicalSourceDesc || qsTr("Unknown Device");
        previousPhysicalSinkDesc = previousSinkName;
        previousPhysicalSourceDesc = previousSourceName;
    }

    Connections {
        function onValuesChanged(): void {
            root.syncNodes();
        }

        target: Pipewire ? Pipewire.nodes : null
    }

    Connections {
        target: root.sink && root.sink.ready ? root.sink.audio : null
        ignoreUnknownSignals: true

        function onVolumeChanged(): void {
            if (root.customVolume !== -1 && isNodeValid(root.sink) && root.sink.audio) {
                if (Math.abs(root.sink.audio.volume - root.customVolume) < 0.01) {
                    root.customVolume = -1;
                }
            }
        }

        function onMutedChanged(): void {
            if (root.customMuted !== -1 && isNodeValid(root.sink) && root.sink.audio) {
                const actualMuted = root.sink.audio.muted ? 1 : 0;
                if (actualMuted === root.customMuted) {
                    root.customMuted = -1;
                }
            }
        }
    }

    Connections {
        function onDefaultAudioSinkChanged(): void {
            Qt.callLater(root.updateActiveSink);
        }
        function onPreferredDefaultAudioSinkChanged(): void {
            Qt.callLater(root.updateActiveSink);
        }
        function onDefaultAudioSourceChanged(): void {
            Qt.callLater(root.updateActiveSource);
        }
        function onPreferredDefaultAudioSourceChanged(): void {
            Qt.callLater(root.updateActiveSource);
        }
        target: Pipewire || null
    }

    PwObjectTracker {
        id: tracker
    }

    CavaProvider {
        id: cava

        bars: GlobalConfig.services.visualiserBars
    }

    BeatTracker {
        id: beatTracker
    }

    IpcHandler {
        function cycleOutput(): void {
            root.cycleNextAudioOutput();
        }

        function cycleInput(): void {
            root.cycleNextAudioInput();
        }

        function updateVolume(volStr: string, mutStr: string): void {
            const vol = parseFloat(volStr);
            const mut = (mutStr === "true" || mutStr === "1");
            if (!isNaN(vol)) {
                root.customVolume = vol;
                root.customMuted = mut ? 1 : 0;
                root.osdTriggered();
            }
        }

        target: "audio"
    }
}
