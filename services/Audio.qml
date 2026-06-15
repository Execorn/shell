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

    function isNodeValid(node: var): bool {
        return !!node && !!Pipewire && !!Pipewire.nodes && Pipewire.nodes.indexOf(node) !== -1 && node.ready;
    }

    function setVolume(newVolume: real): void {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        const isVirtual = isNodeValid(dSink) && dSink.properties && (dSink.properties["node.virtual"] === "true" || dSink.name === "easyeffects_sink");
        if (isVirtual && root.physicalDriverId !== -1) {
            const driverId = root.physicalDriverId;
            const volClamped = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
            volumeSetProc.running = false;
            volumeSetProc.command = ["wpctl", "set-volume", driverId.toString(), volClamped.toFixed(2)];
            volumeSetProc.running = true;
            root.customVolume = volClamped;
            root.customMuted = 0;
        } else if (isNodeValid(sink) && sink.audio) {
            sink.audio.muted = false;
            sink.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
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

    function setAudioSink(newSink: var): void {
        if (Pipewire) {
            Pipewire.preferredDefaultAudioSink = newSink;
        }
    }

    function setAudioSource(newSource: var): void {
        if (Pipewire) {
            Pipewire.preferredDefaultAudioSource = newSource;
        }
    }

    property int physicalDriverId: -1

    readonly property Process volumeSetProc: Process {}
    readonly property Process muteSetProc: Process {}

    function getBestOutputSinkName(): string {
        if (physicalSinks.length === 0) return "";
        
        // 1. Look for Bluetooth headphones/speakers
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && s.name.indexOf("bluez_output") === 0) {
                return s.name;
            }
        }
        
        // 2. Look for USB audio cards / speakers (excluding microphones/inputs)
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("alsa_output.usb") === 0 || s.name.indexOf("usb-") !== -1)) {
                const nameLower = s.name.toLowerCase();
                const isMic = nameLower.indexOf("micro") !== -1 || nameLower.indexOf("mic") !== -1 || nameLower.indexOf("input") !== -1;
                if (!isMic) {
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
        const bestSinkName = getBestOutputSinkName();
        const bestSinkNode = physicalSinks.find(s => isNodeValid(s) && s.name === bestSinkName);
        root.physicalDriverId = bestSinkNode ? bestSinkNode.id : -1;

        const sinkMapStr = sinks.filter(isNodeValid).map(n => n.id + ":" + (n.name || "")).join(", ");
        console.log("[Audio.qml debug] updateActiveSink called. physicalDriverId:", root.physicalDriverId, "sinks:", sinkMapStr);
        let resolvedSink = null;
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        if (isNodeValid(dSink)) {
            if (dSink.properties && (dSink.properties["node.virtual"] === "true" || dSink.name === "easyeffects_sink")) {
                const driverId = root.physicalDriverId;
                if (driverId !== -1) {
                    const physicalSink = sinks.find(n => isNodeValid(n) && n.id === driverId);
                    if (physicalSink && physicalSink.properties && physicalSink.properties["node.virtual"] !== "true" && physicalSink.name !== "easyeffects_sink") {
                        resolvedSink = physicalSink;
                    }
                }
                if (!resolvedSink) {
                    root.customVolume = -1;
                    root.customMuted = -1;
                    const prefSink = Pipewire ? Pipewire.preferredDefaultAudioSink : null;
                    if (isNodeValid(prefSink) && prefSink.properties && prefSink.properties["node.virtual"] !== "true" && prefSink.name !== "easyeffects_sink") {
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
            console.log("[Audio.qml debug] Updating root.sink from", isNodeValid(root.sink) ? root.sink.name : "none", "to", isNodeValid(resolvedSink) ? resolvedSink.name : "none");
            root.sink = resolvedSink;
        }
    }

    function cycleNextAudioOutput(): void {
        if (physicalSinks.length === 0)
            return;

        const currentIndex = physicalSinks.findIndex(s => s === sink);
        const nextIndex = (currentIndex + 1) % physicalSinks.length;
        setAudioSink(physicalSinks[nextIndex]);
    }

    function setStreamVolume(stream: var, newVolume: real): void {
        if (isNodeValid(stream) && stream.audio) {
            stream.audio.muted = false;
            stream.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function setStreamMuted(stream: var, muted: bool): void {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        const isVirtual = isNodeValid(dSink) && dSink.properties && (dSink.properties["node.virtual"] === "true" || dSink.name === "easyeffects_sink");
        if (stream === root.sink && isVirtual && root.physicalDriverId !== -1) {
            const driverId = root.physicalDriverId;
            muteSetProc.running = false;
            muteSetProc.command = ["wpctl", "set-mute", driverId.toString(), muted ? "1" : "0"];
            muteSetProc.running = true;
            root.customMuted = muted ? 1 : 0;
        } else if (isNodeValid(stream) && stream.audio) {
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

    onVolumeChanged: {
        console.log("[Audio.qml debug] Volume changed:", volume, "Muted:", muted, "Sink:", isNodeValid(sink) ? sink.name : "none", "Sink.audio:", isNodeValid(sink) ? sink.audio : "none", "Sink.audio.volume:", isNodeValid(sink) ? sink.audio?.volume : "none");
    }

    onSinkChanged: {
        root.customVolume = -1;
        root.customMuted = -1;
        console.log("[Audio.qml debug] Sink changed:", isNodeValid(sink) ? sink.name : "none", "description:", isNodeValid(sink) ? sink.description : "none", "audio:", isNodeValid(sink) ? sink.audio : "none", "properties:", isNodeValid(sink) ? JSON.stringify(sink.properties) : "none");
        if (!isNodeValid(sink))
            return;

        const newSinkName = sink.description || sink.name || qsTr("Unknown Device");

        if (previousSinkName && previousSinkName !== newSinkName && GlobalConfig.utilities.toasts.audioOutputChanged)
            Toaster.toast(qsTr("Audio output changed"), qsTr("Now using: %1").arg(newSinkName), "volume_up");

        previousSinkName = newSinkName;
    }

    onSourceChanged: {
        console.log("[Audio.qml debug] Source changed:", isNodeValid(source) ? source.name : "none", "description:", isNodeValid(source) ? source.description : "none");
        if (!isNodeValid(source))
            return;

        const newSourceName = source.description || source.name || qsTr("Unknown Device");

        if (previousSourceName && previousSourceName !== newSourceName && GlobalConfig.utilities.toasts.audioInputChanged)
            Toaster.toast(qsTr("Audio input changed"), qsTr("Now using: %1").arg(newSourceName), "mic");

        previousSourceName = newSourceName;
    }

    function syncNodes(): void {
        if (!Pipewire || !Pipewire.nodes) return;
        console.log("[JS LOG] syncNodes called. Pipewire.nodes.values length:", Pipewire.nodes.values.length, "values:", Pipewire.nodes.values);

        const newSinks = [];
        const newSources = [];
        const newStreams = [];
        const newPhysicalSinks = [];
        const newPhysicalSources = [];

        for (const node of Pipewire.nodes.values) {
            if (!node) continue;

            // Dynamically listen to readyChanged to trigger sync when it changes
            try {
                node.readyChanged.disconnect(root.syncNodes);
            } catch (e) {}
            try {
                node.readyChanged.connect(root.syncNodes);
            } catch (e) {}

            if (!node.ready) continue;
            if (!node.isStream) {
                const isVirtual = (node.properties && node.properties["node.virtual"] === "true") || node.name === "easyeffects_sink" || node.name === "easyeffects_source";

                if (node.isSink) {
                    newSinks.push(node);
                    if (!isVirtual) {
                        newPhysicalSinks.push(node);
                    }
                } else if (node.audio) {
                    newSources.push(node);
                    if (!isVirtual) {
                        newPhysicalSources.push(node);
                    }
                }
            } else if (node.audio) {
                newStreams.push(node);
            }
        }

        root.sinks = newSinks;
        root.sources = newSources;
        root.streams = newStreams;
        root.physicalSinks = newPhysicalSinks;
        root.physicalSources = newPhysicalSources;

        tracker.objects = [...newSinks, ...newSources, ...newStreams];

        Qt.callLater(root.updateActiveSink);
    }

    Component.onCompleted: {
        previousSinkName = isNodeValid(sink) ? (sink.description || sink.name) : qsTr("Unknown Device");
        previousSourceName = isNodeValid(source) ? (source.description || source.name) : qsTr("Unknown Device");
        root.syncNodes();
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

        function updateVolume(volStr: string, mutStr: string): void {
            console.log("[Audio.qml debug] IPC updateVolume called. volStr:", volStr, "mutStr:", mutStr);
            const vol = parseFloat(volStr);
            const mut = (mutStr === "true" || mutStr === "1");
            if (!isNaN(vol)) {
                root.customVolume = vol;
                root.customMuted = mut ? 1 : 0;
            }
        }

        target: "audio"
    }
}
