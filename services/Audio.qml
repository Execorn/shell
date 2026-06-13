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

    property list<PwNode> sinks: []
    property list<PwNode> sources: []
    property list<PwNode> streams: []
    property list<PwNode> physicalSinks: []
    property list<PwNode> physicalSources: []

    property PwNode sink: null
    readonly property PwNode source: Pipewire.defaultAudioSource

    property real customVolume: -1
    property int customMuted: -1 // -1 = unset, 0 = false, 1 = true

    readonly property bool muted: customMuted !== -1 ? (customMuted === 1) : (!!sink?.audio?.muted)
    readonly property real volume: customVolume !== -1 ? customVolume : (sink?.audio?.volume ?? 0)

    readonly property bool sourceMuted: !!source?.audio?.muted
    readonly property real sourceVolume: source?.audio?.volume ?? 0

    readonly property alias cava: cava
    readonly property alias beatTracker: beatTracker

    function setVolume(newVolume: real): void {
        const dSink = Pipewire.defaultAudioSink;
        const isVirtual = dSink && (dSink.properties["node.virtual"] === "true" || dSink.name === "easyeffects_sink");
        if (isVirtual && root.physicalDriverId !== -1) {
            const driverId = root.physicalDriverId;
            const volClamped = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
            volumeSetProc.running = false;
            volumeSetProc.command = ["wpctl", "set-volume", driverId.toString(), volClamped.toFixed(2)];
            volumeSetProc.running = true;
            root.customVolume = volClamped;
            root.customMuted = 0;
        } else if (sink?.ready && sink?.audio) {
            sink.audio.muted = false;
            sink.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function incrementVolume(amount: real): void {
        setVolume(volume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementVolume(amount: real): void {
        setVolume(volume - (amount || GlobalConfig.services.audioIncrement));
    }

    function setSourceVolume(newVolume: real): void {
        if (source?.ready && source?.audio) {
            source.audio.muted = false;
            source.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function incrementSourceVolume(amount: real): void {
        setSourceVolume(sourceVolume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementSourceVolume(amount: real): void {
        setSourceVolume(sourceVolume - (amount || GlobalConfig.services.audioIncrement));
    }

    function setAudioSink(newSink: PwNode): void {
        Pipewire.preferredDefaultAudioSink = newSink;
    }

    function setAudioSource(newSource: PwNode): void {
        Pipewire.preferredDefaultAudioSource = newSource;
    }

    property int physicalDriverId: -1

    readonly property Process volumeSetProc: Process {}

    function getBestOutputSinkName(): string {
        if (physicalSinks.length === 0) return "";
        
        // 1. Look for Bluetooth headphones/speakers
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (s.name.indexOf("bluez_output") === 0) {
                return s.name;
            }
        }
        
        // 2. Look for USB audio cards / speakers
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (s.name.indexOf("alsa_output.usb") === 0 || s.name.indexOf("usb-") !== -1) {
                return s.name;
            }
        }
        
        // 3. Fallback to any physical sink that is not the built-in speaker, just in case
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (s.name !== "alsa_output.pci-0000_05_00.6.analog-stereo" && s.name.indexOf("pci-") === -1) {
                return s.name;
            }
        }
        
        // 4. Default fallback: computer speakers
        const internalSink = physicalSinks.find(s => s.name.indexOf("pci-") !== -1 || s.name.indexOf("analog-stereo") !== -1);
        if (internalSink) {
            return internalSink.name;
        }
        
        return physicalSinks[0].name;
    }

    function updateActiveSink(): void {
        const bestSinkName = getBestOutputSinkName();
        const bestSinkNode = physicalSinks.find(s => s.name === bestSinkName);
        root.physicalDriverId = bestSinkNode ? bestSinkNode.id : -1;

        const sinkMapStr = sinks.map(n => n.id + ":" + n.name).join(", ");
        console.log("[Audio.qml debug] updateActiveSink called. physicalDriverId:", root.physicalDriverId, "sinks:", sinkMapStr);
        let resolvedSink = null;
        const dSink = Pipewire.defaultAudioSink;
        if (dSink) {
            if (dSink.properties["node.virtual"] === "true" || dSink.name === "easyeffects_sink") {
                const driverId = root.physicalDriverId;
                if (driverId !== -1) {
                    const physicalSink = sinks.find(n => n.id === driverId);
                    if (physicalSink && physicalSink.properties["node.virtual"] !== "true" && physicalSink.name !== "easyeffects_sink") {
                        resolvedSink = physicalSink;
                    }
                }
                if (!resolvedSink) {
                    root.customVolume = -1;
                    root.customMuted = -1;
                    if (Pipewire.preferredDefaultAudioSink && Pipewire.preferredDefaultAudioSink.properties["node.virtual"] !== "true" && Pipewire.preferredDefaultAudioSink.name !== "easyeffects_sink") {
                        resolvedSink = Pipewire.preferredDefaultAudioSink;
                    } else if (physicalSinks.length > 0) {
                        resolvedSink = physicalSinks[0];
                    }
                }
            } else {
                resolvedSink = dSink;
                root.customVolume = -1;
                root.customMuted = -1;
            }
        }
        if (root.sink !== resolvedSink) {
            console.log("[Audio.qml debug] Updating root.sink from", root.sink?.name, "to", resolvedSink?.name);
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

    function setStreamVolume(stream: PwNode, newVolume: real): void {
        if (stream?.ready && stream?.audio) {
            stream.audio.muted = false;
            stream.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function setStreamMuted(stream: PwNode, muted: bool): void {
        const dSink = Pipewire.defaultAudioSink;
        const isVirtual = dSink && (dSink.properties["node.virtual"] === "true" || dSink.name === "easyeffects_sink");
        if (stream === root.sink && isVirtual && root.physicalDriverId !== -1) {
            const driverId = root.physicalDriverId;
            volumeSetProc.running = false;
            volumeSetProc.command = ["wpctl", "set-mute", driverId.toString(), muted ? "1" : "0"];
            volumeSetProc.running = true;
            root.customMuted = muted ? 1 : 0;
        } else if (stream?.ready && stream?.audio) {
            stream.audio.muted = muted;
        }
    }

    function getStreamVolume(stream: PwNode): real {
        return stream?.audio?.volume ?? 0;
    }

    function getStreamMuted(stream: PwNode): bool {
        return !!stream?.audio?.muted;
    }

    function getStreamName(stream: PwNode): string {
        if (!stream)
            return qsTr("Unknown");
        return stream.properties["application.name"] || stream.description || stream.name || qsTr("Unknown Application");
    }

    onVolumeChanged: {
        console.log("[Audio.qml debug] Volume changed:", volume, "Muted:", muted, "Sink:", sink?.name, "Sink.audio:", sink?.audio, "Sink.audio.volume:", sink?.audio?.volume);
    }

    onSinkChanged: {
        console.log("[Audio.qml debug] Sink changed:", sink?.name, "description:", sink?.description, "audio:", sink?.audio, "properties:", JSON.stringify(sink?.properties));
        if (!sink?.ready)
            return;

        const newSinkName = sink.description || sink.name || qsTr("Unknown Device");

        if (previousSinkName && previousSinkName !== newSinkName && GlobalConfig.utilities.toasts.audioOutputChanged)
            Toaster.toast(qsTr("Audio output changed"), qsTr("Now using: %1").arg(newSinkName), "volume_up");

        previousSinkName = newSinkName;
    }

    onSourceChanged: {
        console.log("[Audio.qml debug] Source changed:", source?.name, "description:", source?.description);
        if (!source?.ready)
            return;

        const newSourceName = source.description || source.name || qsTr("Unknown Device");

        if (previousSourceName && previousSourceName !== newSourceName && GlobalConfig.utilities.toasts.audioInputChanged)
            Toaster.toast(qsTr("Audio input changed"), qsTr("Now using: %1").arg(newSourceName), "mic");

        previousSourceName = newSourceName;
    }

    Component.onCompleted: {
        previousSinkName = sink?.description || sink?.name || qsTr("Unknown Device");
        previousSourceName = source?.description || source?.name || qsTr("Unknown Device");
        root.updateActiveSink();
    }

    Connections {
        function onValuesChanged(): void {
            const newSinks = [];
            const newSources = [];
            const newStreams = [];
            const newPhysicalSinks = [];
            const newPhysicalSources = [];

            for (const node of Pipewire.nodes.values) {
                if (!node.isStream) {
                    const isVirtual = node.properties["node.virtual"] === "true" || node.name === "easyeffects_sink" || node.name === "easyeffects_source";

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

            root.updateActiveSink();
        }

        target: Pipewire.nodes
    }

    Connections {
        function onDefaultAudioSinkChanged(): void {
            root.updateActiveSink();
        }
        function onPreferredDefaultAudioSinkChanged(): void {
            root.updateActiveSink();
        }
        target: Pipewire
    }

    PwObjectTracker {
        objects: [...root.sinks, ...root.sources, ...root.streams]
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
