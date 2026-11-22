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
    property var startupPendingNodes: []
    property var readyOnceNodes: []
    property string lastToastedSinkName: ""
    property double lastToastedSinkTime: 0
    property double lastPrioritySinkConnectTime: 0
    property string lastToastedSourceName: ""
    property double lastToastedSourceTime: 0
    property double lastPrioritySourceConnectTime: 0
    property var btSinkOrder: []
    property bool hasRunCardProfileFix: false
    property double lastManualSinkSetTime: 0
    property double lastManualSourceSetTime: 0

    readonly property Timer startupEnumTimer: Timer {
        interval: 800
        repeat: false
        onTriggered: {
            root.startupPendingNodes = [];
            root.startupEnumerating = false;
            if (!root.hasRunCardProfileFix) {
                root.hasRunCardProfileFix = true;
                if (!Quickshell.env("PYTEST_CURRENT_TEST"))
                    cardProfileFixProc.running = true;
            }
            root.updateActiveSink();
            root.updateActiveSource();
            root.previousSinkName = root.activePhysicalSinkDesc || root.previousSinkName || qsTr("Unknown Device");
            root.previousSourceName = root.activePhysicalSourceDesc || root.previousSourceName || qsTr("Unknown Device");
            root.previousPhysicalSinkDesc = root.previousSinkName;
            root.previousPhysicalSourceDesc = root.previousSourceName;
        }
    }

    readonly property Timer customStateTimer: Timer {
        interval: 350
        repeat: false
        onTriggered: {
            root.customVolume = -1;
            root.customMuted = -1;
        }
    }

    property int eqRouteRetries: 0
    readonly property Timer eqRouteRetryTimer: Timer {
        interval: 250
        repeat: false
        onTriggered: {
            const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
            if (root.isNodeValid(dSink) && dSink.name === "riced_equalizer_sink" && root.preferredPhysicalSink !== "" && root.lastRoutedPhysicalSink !== root.preferredPhysicalSink) {
                root.routeEqualizerTo(root.preferredPhysicalSink);
            }
        }
    }

    property int micRouteRetries: 0
    readonly property Timer micRouteRetryTimer: Timer {
        interval: 250
        repeat: false
        onTriggered: {
            if (root.preferredPhysicalSource !== "" && root.lastRoutedPhysicalSource !== root.preferredPhysicalSource) {
                root.routeMicrophoneFrom(root.preferredPhysicalSource);
            }
        }
    }

    readonly property Timer filterSyncTimer: Timer {
        interval: 150
        repeat: false
        onTriggered: {
            if (Quickshell.env("PYTEST_CURRENT_TEST"))
                return;
            if (root.eqRouteProc.running || root.micRouteProc.running || root.filterTargetSyncProc.running)
                return;
            const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
            const eqActive = root.isNodeValid(dSink) && dSink.name === "riced_equalizer_sink";
            const micEqPresent = root.sources.some(s => s && s.name === "riced_microphone_source");
            if (eqActive || micEqPresent) {
                root.filterTargetSyncProc.running = true;
            }
        }
    }

    property var sinks: []
    property var sources: []
    property var streams: []
    property var physicalSinks: []
    property var physicalSources: []

    property var sink: null
    property var source: null

    property real customVolume: -1
    property int customMuted: -1 // -1 = unset, 0 = false, 1 = true

    readonly property bool muted: customMuted !== -1 ? (customMuted === 1) : (isNodeValid(sink) && sink.audio ? !!sink.audio.muted : false)
    readonly property real volume: customVolume !== -1 ? customVolume : (isNodeValid(sink) && sink.audio ? sink.audio.volume : 0)

    readonly property bool sourceMuted: isNodeValid(source) && source.audio ? !!source.audio.muted : false
    readonly property real sourceVolume: isNodeValid(source) && source.audio ? source.audio.volume : 0

    readonly property alias cava: cava
    readonly property alias beatTracker: beatTracker

    signal osdTriggered
    signal sourceOsdTriggered

    function isNodeValid(node: var): bool {
        return !!node && !!Pipewire && !!Pipewire.nodes && Pipewire.nodes.values.indexOf(node) !== -1 && (node.ready || root.readyOnceNodes.indexOf(node) !== -1);
    }

    function isVirtualNode(node: var): bool {
        return !!node && ((node.properties && node.properties["node.virtual"] === "true") || node.name === "easyeffects_sink" || node.name === "easyeffects_source" || node.name === "riced_equalizer_sink" || node.name === "riced_microphone_source");
    }

    function isBluetoothSinkName(name: string): bool {
        return !!name && (name.indexOf("bluez_output") !== -1 || name.indexOf("bluez_sink") !== -1);
    }

    function isBluetoothSourceName(name: string): bool {
        return !!name && (name.indexOf("bluez_input") !== -1 || name.indexOf("bluez_source") !== -1);
    }

    function btMacOf(name: string): string {
        if (!name) return "";
        const m = name.match(/^bluez_(?:output|sink|input|source)\.([0-9A-Fa-f_:]+)/);
        return m ? m[1].replace(/:/g, "_") : "";
    }

    function isMicOrLoopbackSink(node: var): bool {
        if (!node || !node.name) return true;
        const nameLower = node.name.toLowerCase();
        const descLower = (node.description || "").toLowerCase();
        const isLoopback = nameLower.indexOf("loopback") !== -1 || descLower.indexOf("loopback") !== -1 || nameLower.indexOf("hifi__line2") !== -1;
        if (isLoopback) return true;
        const hasDualKeyword = nameLower.indexOf("headphone") !== -1 || descLower.indexOf("headphone") !== -1
            || nameLower.indexOf("headset") !== -1 || descLower.indexOf("headset") !== -1
            || nameLower.indexOf("speaker") !== -1 || descLower.indexOf("speaker") !== -1
            || nameLower.indexOf("dac") !== -1 || descLower.indexOf("dac") !== -1
            || nameLower.indexOf("line1") !== -1 || descLower.indexOf("main out") !== -1
            || descLower.indexOf("interface") !== -1;
        const hasMicKeyword = nameLower.indexOf("micro") !== -1 || nameLower.indexOf("mic") !== -1 || nameLower.indexOf("input") !== -1
            || descLower.indexOf("microphone") !== -1 || descLower.indexOf("mic") !== -1;
        return hasMicKeyword && !hasDualKeyword;
    }

    function isIgnoredUsbSource(node: var): bool {
        if (!node || !node.name) return true;
        const nameLower = node.name.toLowerCase();
        const descLower = (node.description || "").toLowerCase();
        const isLoopback = nameLower.indexOf("loopback") !== -1 || descLower.indexOf("loopback") !== -1 || nameLower.indexOf("hifi__line2") !== -1;
        const isInstrument = nameLower.indexOf("minifuse") !== -1 || descLower.indexOf("minifuse") !== -1 || descLower.indexOf("inst ") !== -1;
        return isLoopback || isInstrument;
    }

    function isAppPlaybackStream(node: var): bool {
        if (!node) return false;
        const props = node.properties;
        if (props) {
            if (props["node.virtual"] === "true" || props["node.passive"] === "true" || props["stream.capture.sink"] === "true")
                return false;
            const mediaClass = props["media.class"];
            if (mediaClass && String(mediaClass).indexOf("Stream/Output/") !== 0)
                return false;
        }
        const name = node.name || "";
        if (name.indexOf("output.filter-chain") === 0 || name.indexOf("input.filter-chain") === 0 || name.indexOf("bluez_capture_internal") === 0 || name === "caelestia-shell")
            return false;
        return true;
    }

    function enforceEqSinkUnattenuated(): void {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        if (isNodeValid(dSink) && dSink.name === "riced_equalizer_sink" && dSink.audio) {
            if (Math.abs(dSink.audio.volume - 1.0) > 0.01 || dSink.audio.muted) {
                dSink.audio.muted = false;
                dSink.audio.volume = 1.0;
            }
        }
    }

    property var pendingVolumeCmd: null
    function enqueueVolumeCmd(cmd: var): void {
        if (volumeSetProc.running) {
            root.pendingVolumeCmd = cmd;
        } else {
            root.pendingVolumeCmd = null;
            volumeSetProc.command = cmd;
            volumeSetProc.running = true;
        }
    }

    property var pendingMuteCmd: null
    function enqueueMuteCmd(cmd: var): void {
        if (muteSetProc.running) {
            root.pendingMuteCmd = cmd;
        } else {
            root.pendingMuteCmd = null;
            muteSetProc.command = cmd;
            muteSetProc.running = true;
        }
    }

    function setVolume(newVolume: real): void {
        if (typeof newVolume !== "number" || !isFinite(newVolume))
            return;

        const volClamped = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        const isVirtual = isNodeValid(dSink) && isVirtualNode(dSink);

        if (!isVirtual && isNodeValid(sink) && sink.audio) {
            sink.audio.muted = false;
            sink.audio.volume = volClamped;
        } else if (isVirtual) {
            const targetId = root.physicalDriverId !== -1 ? root.physicalDriverId : (isNodeValid(sink) ? sink.id : -1);
            if (targetId !== -1) {
                enqueueVolumeCmd(["wpctl", "set-volume", targetId.toString(), volClamped.toFixed(2)]);
                root.customVolume = volClamped;
                root.customMuted = 0;
                customStateTimer.restart();
            }
        }

        root.osdTriggered();
    }

    function incrementVolume(amount: var): void {
        setVolume(volume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementVolume(amount: var): void {
        setVolume(volume - (amount || GlobalConfig.services.audioIncrement));
    }

    function toggleMute(): void {
        if (isNodeValid(sink)) {
            setStreamMuted(sink, !muted);
            root.osdTriggered();
        }
    }

    function setSourceVolume(newVolume: real): void {
        if (typeof newVolume !== "number" || !isFinite(newVolume))
            return;
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

    function setSourceMuted(mutedState: bool): void {
        if (isNodeValid(source) && source.audio) {
            source.audio.muted = mutedState;
        }
        const dSource = Pipewire ? Pipewire.defaultAudioSource : null;
        if (isNodeValid(dSource) && isVirtualNode(dSource) && dSource.audio && (dSource.audio.muted || dSource.audio.volume < 0.99)) {
            dSource.audio.muted = false;
            dSource.audio.volume = 1.0;
        }
        root.sourceOsdTriggered();
    }

    function toggleSourceMute(): void {
        if (isNodeValid(source) && source.audio) {
            setSourceMuted(!sourceMuted);
        }
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
        }
        if (isNodeValid(sink) && !isVirtualNode(sink)) {
            return sink.description || sink.name || "";
        }
        return "";
    }

    property string pendingEqTarget: ""
    property string inFlightEqTarget: ""
    readonly property Process eqRouteProc: Process {
        stdout: StdioCollector {
            onStreamFinished: {
                const out = text.trim();
                if (out === ("ROUTED:" + root.inFlightEqTarget)) {
                    root.lastRoutedPhysicalSink = root.inFlightEqTarget;
                    root.eqRouteRetries = 0;
                    eqRouteRetryTimer.stop();
                } else {
                    root.lastRoutedPhysicalSink = "";
                    if (!Quickshell.env("PYTEST_CURRENT_TEST") && root.eqRouteRetries < 5 && root.preferredPhysicalSink !== "") {
                        root.eqRouteRetries += 1;
                        eqRouteRetryTimer.restart();
                    }
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim().length > 0)
                    console.warn("[Audio.qml] eqRouteProc stderr:", text.trim());
            }
        }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                root.lastRoutedPhysicalSink = "";
            if (root.pendingEqTarget !== "") {
                const nextTarget = root.pendingEqTarget;
                root.pendingEqTarget = "";
                if (nextTarget !== root.lastRoutedPhysicalSink)
                    root.routeEqualizerTo(nextTarget);
            }
        }
    }

    readonly property int activePhysicalSinkId: {
        if (isNodeValid(sink) && !isVirtualNode(sink))
            return sink.id;
        const node = physicalSinks.find(s => isNodeValid(s) && s.name === preferredPhysicalSink);
        return node ? node.id : -1;
    }

    function routeEqualizerTo(sinkName: string): void {
        if (!sinkName) return;
        if (eqRouteProc.running) {
            root.pendingEqTarget = sinkName;
            return;
        }
        root.inFlightEqTarget = sinkName;
        root.pendingEqTarget = "";
        eqRouteProc.command = [
            "python3", "-c",
            `import json, subprocess, sys
target = sys.argv[1]
try:
    sinks_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "sinks"], text=True))
    sinks = {s.get("index"): s.get("name") for s in (sinks_raw if isinstance(sinks_raw, list) else [sinks_raw])}
    if target not in sinks.values():
        print("MISSING_TARGET", flush=True)
        sys.exit(0)
    inputs_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "sink-inputs"], text=True))
    inputs = inputs_raw if isinstance(inputs_raw, list) else [inputs_raw]
    found = False
    for inp in inputs:
        props = inp.get("properties", {})
        node_name = props.get("node.name", "")
        media_name = props.get("media.name", "")
        dev_desc = props.get("device.description", "")
        if node_name.startswith("output.filter-chain") or media_name == "Riced Equalizer Sink" or dev_desc == "Riced Equalizer Sink":
            found = True
            sid = str(inp.get("index"))
            if sinks.get(inp.get("sink")) != target:
                subprocess.run(["pactl", "move-sink-input", sid, target], check=True)
    print(f"ROUTED:{target}" if found else "MISSING_STREAM", flush=True)
except Exception as e:
    print(f"eqRoute error: {e}", file=sys.stderr)
    sys.exit(1)
`,
            sinkName
        ];
        eqRouteProc.running = true;
    }

    function setAudioSink(newSink: var): void {
        if (!newSink || !newSink.name) return;
        root.lastManualSinkSetTime = Date.now();
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
        if (isNodeValid(source) && !isVirtualNode(source))
            return source.description || source.name || "";
        return "";
    }

    property string pendingMicTarget: ""
    property string inFlightMicTarget: ""
    readonly property Process micRouteProc: Process {
        stdout: StdioCollector {
            onStreamFinished: {
                const out = text.trim();
                if (out === ("ROUTED:" + root.inFlightMicTarget)) {
                    root.lastRoutedPhysicalSource = root.inFlightMicTarget;
                    root.micRouteRetries = 0;
                    micRouteRetryTimer.stop();
                } else {
                    root.lastRoutedPhysicalSource = "";
                    if (!Quickshell.env("PYTEST_CURRENT_TEST") && root.micRouteRetries < 5 && root.preferredPhysicalSource !== "") {
                        root.micRouteRetries += 1;
                        micRouteRetryTimer.restart();
                    }
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim().length > 0)
                    console.warn("[Audio.qml] micRouteProc stderr:", text.trim());
            }
        }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                root.lastRoutedPhysicalSource = "";
            if (root.pendingMicTarget !== "") {
                const nextTarget = root.pendingMicTarget;
                root.pendingMicTarget = "";
                if (nextTarget !== root.lastRoutedPhysicalSource)
                    root.routeMicrophoneFrom(nextTarget);
            }
        }
    }

    readonly property Process filterTargetSyncProc: Process {
        command: [
            "python3", "-c",
            `import json, subprocess
res = {"eqSink": "", "micSource": ""}
try:
    sinks_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "sinks"], text=True))
    sinks = {s.get("index"): s.get("name", "") for s in (sinks_raw if isinstance(sinks_raw, list) else [sinks_raw])}
    inputs_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "sink-inputs"], text=True))
    for inp in (inputs_raw if isinstance(inputs_raw, list) else [inputs_raw]):
        props = inp.get("properties", {})
        if props.get("node.name", "").startswith("output.filter-chain") or props.get("media.name") == "Riced Equalizer Sink":
            res["eqSink"] = sinks.get(inp.get("sink"), "")
            break
except Exception:
    pass
try:
    srcs_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "sources"], text=True))
    srcs = {s.get("index"): s.get("name", "") for s in (srcs_raw if isinstance(srcs_raw, list) else [srcs_raw])}
    outputs_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "source-outputs"], text=True))
    for outp in (outputs_raw if isinstance(outputs_raw, list) else [outputs_raw]):
        props = outp.get("properties", {})
        if props.get("node.name", "").startswith("input.filter-chain") or props.get("media.name") == "Riced Microphone Source":
            res["micSource"] = srcs.get(outp.get("source"), "")
            break
except Exception:
    pass
print(json.dumps(res), flush=True)
`
        ]
        stdout: StdioCollector {
            onStreamFinished: {
                const raw = text.trim();
                if (!raw) return;
                try {
                    const data = JSON.parse(raw);
                    const now = Date.now();
                    if (data.eqSink && !root.eqRouteProc.running && (now - root.lastManualSinkSetTime) > 500) {
                        const eqNode = root.physicalSinks.find(s => root.isNodeValid(s) && s.name === data.eqSink);
                        if (eqNode && data.eqSink !== root.preferredPhysicalSink) {
                            root.manualSinkOverride = true;
                            root.preferredPhysicalSink = data.eqSink;
                            root.lastRoutedPhysicalSink = data.eqSink;
                            root.updateActiveSink();
                        }
                    }
                    if (data.micSource && !root.micRouteProc.running && (now - root.lastManualSourceSetTime) > 500) {
                        const micNode = root.physicalSources.find(s => root.isNodeValid(s) && s.name === data.micSource);
                        if (micNode && data.micSource !== root.preferredPhysicalSource && !root.isBluetoothSourceName(data.micSource)) {
                            root.manualSourceOverride = true;
                            root.preferredPhysicalSource = data.micSource;
                            root.lastRoutedPhysicalSource = data.micSource;
                            root.updateActiveSource();
                        }
                    }
                } catch (e) {}
            }
        }
    }

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
        if (micRouteProc.running) {
            root.pendingMicTarget = sourceName;
            return;
        }
        root.inFlightMicTarget = sourceName;
        root.pendingMicTarget = "";
        micRouteProc.command = [
            "python3", "-c",
            `import json, subprocess, sys
target = sys.argv[1]
try:
    srcs_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "sources"], text=True))
    srcs = {s.get("index"): s.get("name", "") for s in (srcs_raw if isinstance(srcs_raw, list) else [srcs_raw])}
    if target not in srcs.values():
        print("MISSING_TARGET", flush=True)
        sys.exit(0)
    outputs_raw = json.loads(subprocess.check_output(["pactl", "-f", "json", "list", "source-outputs"], text=True))
    for outp in (outputs_raw if isinstance(outputs_raw, list) else [outputs_raw]):
        props = outp.get("properties", {})
        node_name = props.get("node.name", "")
        media_name = props.get("media.name", "")
        dev_desc = props.get("device.description", "")
        if node_name.startswith("input.filter-chain") or media_name == "Riced Microphone Source" or dev_desc == "Riced Microphone Source":
            sid = str(outp.get("index"))
            if srcs.get(outp.get("source")) != target:
                subprocess.run(["pactl", "move-source-output", sid, target], check=True)
    cur_def = subprocess.check_output(["pactl", "get-default-source"], text=True).strip()
    if cur_def != target:
        subprocess.run(["pactl", "set-default-source", target], check=True)
    print(f"ROUTED:{target}", flush=True)
except Exception as e:
    print(f"micRoute error: {e}", file=sys.stderr)
    sys.exit(1)
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
        root.lastManualSourceSetTime = Date.now();
        manualSourceOverride = true;
        preferredPhysicalSource = newSource.name;
        if (Pipewire) {
            Pipewire.preferredDefaultAudioSource = newSource;
        }
        Qt.callLater(root.updateActiveSource);
    }

    property int physicalDriverId: -1

    readonly property Process volumeSetProc: Process {
        onExited: (exitCode, exitStatus) => {
            if (root.pendingVolumeCmd !== null) {
                const nextCmd = root.pendingVolumeCmd;
                root.pendingVolumeCmd = null;
                volumeSetProc.command = nextCmd;
                volumeSetProc.running = true;
            }
        }
    }
    readonly property Process muteSetProc: Process {
        onExited: (exitCode, exitStatus) => {
            if (root.pendingMuteCmd !== null) {
                const nextCmd = root.pendingMuteCmd;
                root.pendingMuteCmd = null;
                muteSetProc.command = nextCmd;
                muteSetProc.running = true;
            }
        }
    }

    function getBestOutputSinkName(): string {
        if (physicalSinks.length === 0) return "";

        // 1. Most-recently-connected Bluetooth headphones/speakers
        for (let i = 0; i < btSinkOrder.length; i++) {
            const btName = btSinkOrder[i];
            const btNode = physicalSinks.find(s => isNodeValid(s) && s.name === btName);
            if (btNode) return btNode.name;
        }
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && isBluetoothSinkName(s.name)) {
                return s.name;
            }
        }

        // 2. USB audio cards / speakers / DACs (excluding USB mic-only pseudo-sinks & loopbacks)
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("alsa_output.usb") === 0 || s.name.indexOf("usb-") !== -1)) {
                if (!isMicOrLoopbackSink(s)) {
                    return s.name;
                }
            }
        }

        // 3. Other non-PCI physical sinks (excluding mics & loopbacks)
        for (let i = 0; i < physicalSinks.length; i++) {
            const s = physicalSinks[i];
            if (isNodeValid(s) && s.name && s.name.indexOf("pci-") === -1 && !isMicOrLoopbackSink(s)) {
                return s.name;
            }
        }

        // 4. Built-in analog PCI speakers (before HDMI/DP PCI sinks)
        const internalAnalog = physicalSinks.find(s => isNodeValid(s) && s.name && s.name.indexOf("pci-") !== -1 && s.name.indexOf("analog-stereo") !== -1);
        if (internalAnalog && internalAnalog.name) {
            return internalAnalog.name;
        }
        const anyAnalog = physicalSinks.find(s => isNodeValid(s) && s.name && s.name.indexOf("analog-stereo") !== -1 && !isMicOrLoopbackSink(s));
        if (anyAnalog && anyAnalog.name) {
            return anyAnalog.name;
        }

        // 5. HDMI / DisplayPort PCI sinks fallback
        const hdmiSink = physicalSinks.find(s => isNodeValid(s) && s.name && s.name.indexOf("pci-") !== -1 && (s.name.indexOf("hdmi") !== -1 || s.name.indexOf("displayport") !== -1));
        if (hdmiSink && hdmiSink.name) {
            return hdmiSink.name;
        }

        const nonMicSink = physicalSinks.find(s => isNodeValid(s) && s.name && !isMicOrLoopbackSink(s));
        if (nonMicSink && nonMicSink.name) {
            return nonMicSink.name;
        }

        const firstSink = physicalSinks.find(s => isNodeValid(s) && s.name);
        return firstSink ? firstSink.name : "";
    }

    function updateActiveSink(): void {
        const prefExists = physicalSinks.some(s => isNodeValid(s) && s.name === preferredPhysicalSink);
        if (!prefExists && !root.startupEnumerating) {
            root.manualSinkOverride = false;
            preferredPhysicalSink = "";
        }

        let effectiveSinkName = prefExists ? preferredPhysicalSink : "";
        if (!root.manualSinkOverride || effectiveSinkName === "") {
            const bestName = getBestOutputSinkName();
            if (bestName !== "") {
                effectiveSinkName = bestName;
                if (prefExists || !root.startupEnumerating) {
                    preferredPhysicalSink = bestName;
                }
            }
        }

        const activeNode = physicalSinks.find(s => isNodeValid(s) && s.name === effectiveSinkName) || null;
        const bestSinkName = getBestOutputSinkName();
        const bestSinkNode = physicalSinks.find(s => isNodeValid(s) && s.name === bestSinkName) || null;

        let resolvedSink = null;
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        if (isNodeValid(dSink)) {
            const isEQ = dSink.name === "riced_equalizer_sink";
            const isVirt = isVirtualNode(dSink);
            if (isEQ) {
                const routeTarget = activeNode ? activeNode.name : bestSinkName;
                if (routeTarget !== "" && routeTarget !== lastRoutedPhysicalSink) {
                    routeEqualizerTo(routeTarget);
                }
                enforceEqSinkUnattenuated();
            } else {
                lastRoutedPhysicalSink = "";
                eqRouteRetryTimer.stop();
                root.eqRouteRetries = 0;
                if (!isVirt && !root.manualSinkOverride && effectiveSinkName !== "" && effectiveSinkName !== root.lastConfiguredPhysicalSink) {
                    const targetNode = physicalSinks.find(s => isNodeValid(s) && s.name === effectiveSinkName);
                    if (targetNode && Pipewire.preferredDefaultAudioSink !== targetNode) {
                        Pipewire.preferredDefaultAudioSink = targetNode;
                    }
                    root.lastConfiguredPhysicalSink = effectiveSinkName;
                }
            }

            if (isVirt) {
                root.physicalDriverId = activeNode ? activeNode.id : (bestSinkNode ? bestSinkNode.id : -1);
                const driverId = root.physicalDriverId;
                if (driverId !== -1) {
                    const physicalSink = sinks.find(n => isNodeValid(n) && n.id === driverId);
                    if (physicalSink && !isVirtualNode(physicalSink)) {
                        resolvedSink = physicalSink;
                    }
                }
                if (!resolvedSink) {
                    root.customVolume = -1;
                    root.customMuted = -1;
                    const prefSink = Pipewire ? Pipewire.preferredDefaultAudioSink : null;
                    if (isNodeValid(prefSink) && !isVirtualNode(prefSink)) {
                        resolvedSink = prefSink;
                    } else {
                        resolvedSink = physicalSinks.find(isNodeValid) || null;
                    }
                }
            } else {
                resolvedSink = dSink;
                root.physicalDriverId = dSink.id !== undefined ? dSink.id : -1;
                root.customVolume = -1;
                root.customMuted = -1;
            }
        } else {
            root.physicalDriverId = activeNode ? activeNode.id : (bestSinkNode ? bestSinkNode.id : -1);
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

        // 1. Dedicated USB microphone (excluding loopbacks & audio interface instrument inputs)
        for (let i = 0; i < physicalSources.length; i++) {
            const s = physicalSources[i];
            if (isNodeValid(s) && s.name && (s.name.indexOf("alsa_input.usb") === 0 || s.name.indexOf("usb-") !== -1)) {
                if (!isIgnoredUsbSource(s)) {
                    return s.name;
                }
            }
        }

        // 2. Internal PCI microphone (explicitly prefer pci- before generic analog-stereo)
        const pciAnalogSource = physicalSources.find(s => isNodeValid(s) && s.name && s.name.indexOf("pci-") !== -1 && s.name.indexOf("analog-stereo") !== -1 && !isBluetoothSourceName(s.name));
        if (pciAnalogSource && pciAnalogSource.name) {
            return pciAnalogSource.name;
        }
        const pciSource = physicalSources.find(s => isNodeValid(s) && s.name && s.name.indexOf("pci-") !== -1 && !isBluetoothSourceName(s.name));
        if (pciSource && pciSource.name) {
            return pciSource.name;
        }

        // 3. Any other non-Bluetooth, non-loopback, non-instrument microphone
        const otherWiredSource = physicalSources.find(s => {
            if (!isNodeValid(s) || !s.name) return false;
            if (isBluetoothSourceName(s.name)) return false;
            return !isIgnoredUsbSource(s);
        });
        if (otherWiredSource && otherWiredSource.name) {
            return otherWiredSource.name;
        }

        // 4. Bluetooth microphone ONLY as last resort when no wired/internal mic exists
        for (let i = 0; i < physicalSources.length; i++) {
            const s = physicalSources[i];
            if (isNodeValid(s) && isBluetoothSourceName(s.name)) {
                return s.name;
            }
        }

        const firstSource = physicalSources.find(s => isNodeValid(s) && s.name);
        return firstSource ? firstSource.name : "";
    }

    function updateActiveSource(): void {
        const prefExists = physicalSources.some(s => isNodeValid(s) && s.name === preferredPhysicalSource);
        if (!prefExists && !root.startupEnumerating) {
            root.manualSourceOverride = false;
            preferredPhysicalSource = "";
        }

        let effectiveSourceName = prefExists ? preferredPhysicalSource : "";
        if (!root.manualSourceOverride || effectiveSourceName === "") {
            const bestName = getBestInputSourceName();
            if (bestName !== "") {
                effectiveSourceName = bestName;
                if (prefExists || !root.startupEnumerating) {
                    preferredPhysicalSource = bestName;
                }
            }
        }

        const activeNode = physicalSources.find(s => isNodeValid(s) && s.name === effectiveSourceName) || null;

        if (activeNode && effectiveSourceName !== "") {
            // Do not auto-route riced_microphone_source or default source onto bluez_input unless explicitly chosen or no other physical mic exists
            const isManualOrOnly = root.manualSourceOverride || !isBluetoothSourceName(effectiveSourceName) || getBestInputSourceName() === effectiveSourceName;
            if (isManualOrOnly) {
                if (effectiveSourceName !== lastRoutedPhysicalSource) {
                    routeMicrophoneFrom(effectiveSourceName);
                }
                if (Pipewire && Pipewire.preferredDefaultAudioSource !== activeNode) {
                    Pipewire.preferredDefaultAudioSource = activeNode;
                }
            }
        }

        let resolvedSource = activeNode;
        if (!resolvedSource) {
            const dSource = Pipewire ? Pipewire.defaultAudioSource : null;
            if (isNodeValid(dSource) && !isVirtualNode(dSource)) {
                resolvedSource = dSource;
            } else {
                resolvedSource = physicalSources.find(isNodeValid) || null;
            }
        }
        if (root.source !== resolvedSource) {
            root.source = resolvedSource;
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
        if (typeof newVolume !== "number" || !isFinite(newVolume))
            return;
        if (isNodeValid(stream) && stream.audio) {
            stream.audio.muted = false;
            stream.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function setStreamMuted(stream: var, mutedState: bool): void {
        const dSink = Pipewire ? Pipewire.defaultAudioSink : null;
        const isVirtual = isNodeValid(dSink) && isVirtualNode(dSink);
        const isDefaultSink = (stream !== null && stream === root.sink);

        if (isDefaultSink && isVirtual) {
            const targetId = root.physicalDriverId !== -1 ? root.physicalDriverId : (isNodeValid(root.sink) ? root.sink.id : -1);
            if (targetId !== -1) {
                enqueueMuteCmd(["wpctl", "set-mute", targetId.toString(), mutedState ? "1" : "0"]);
                root.customMuted = mutedState ? 1 : 0;
                customStateTimer.restart();
            }
            return;
        }

        if (isNodeValid(stream) && stream.audio) {
            stream.audio.muted = mutedState;
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
            const hasPriority = physicalSinks.some(s => isNodeValid(s) && s.name && (s.name.indexOf("bluez_") !== -1 || (s.name.indexOf("usb") !== -1 && !isMicOrLoopbackSink(s))));
            if (!hasPriority)
                return;
        }

        if (!root.startupEnumerating && previousSinkName && previousSinkName !== qsTr("Unknown Device") && previousSinkName !== newSinkName && GlobalConfig.utilities.toasts.audioOutputChanged) {
            if (newSinkName !== root.lastToastedSinkName || (now - root.lastToastedSinkTime) >= 1500) {
                Toaster.toast(qsTr("Audio output changed"), qsTr("Now using: %1").arg(newSinkName), "volume_up");
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
            const hasPriority = physicalSources.some(s => isNodeValid(s) && s.name && (s.name.indexOf("usb") !== -1 && !isIgnoredUsbSource(s)));
            if (!hasPriority)
                return;
        }

        if (!root.startupEnumerating && previousSourceName && previousSourceName !== qsTr("Unknown Device") && previousSourceName !== newSourceName && GlobalConfig.utilities.toasts.audioInputChanged) {
            if (newSourceName !== root.lastToastedSourceName || (now - root.lastToastedSourceTime) >= 1500) {
                Toaster.toast(qsTr("Audio input changed"), qsTr("Now using: %1").arg(newSourceName), "mic");
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
        customStateTimer.stop();
        if (root.syncingNodes || !isNodeValid(sink) || isVirtualNode(sink))
            return;

        const newSinkName = sink.description || sink.name || qsTr("Unknown Device");
        notifyOutputChanged(newSinkName);
    }

    onSourceChanged: {
        if (root.syncingNodes || !isNodeValid(source) || isVirtualNode(source))
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
        const nextReadyOnce = [];

        for (const node of Pipewire.nodes.values) {
            if (!node) continue;

            try {
                node.readyChanged.disconnect(root.syncNodes);
            } catch (e) {}
            try {
                node.readyChanged.connect(root.syncNodes);
            } catch (e) {}

            const isReady = node.ready || root.readyOnceNodes.indexOf(node) !== -1;
            if (isReady) {
                nextReadyOnce.push(node);
            }

            if (!node.isStream) {
                const isVirt = isVirtualNode(node);

                if (node.isSink) {
                    trackerObjects.push(node);
                    if (isReady) {
                        newSinks.push(node);
                        if (!isVirt) {
                            newPhysicalSinks.push(node);
                        }
                    }
                } else if (node.audio) {
                    trackerObjects.push(node);
                    if (isReady) {
                        newSources.push(node);
                        if (!isVirt) {
                            newPhysicalSources.push(node);
                        }
                    }
                }
            } else if (node.audio) {
                trackerObjects.push(node);
                if (isReady && isAppPlaybackStream(node)) {
                    newStreams.push(node);
                }
            }
        }

        root.readyOnceNodes = nextReadyOnce;
        root.syncingNodes = true;
        root.sinks = newSinks;
        root.sources = newSources;
        root.streams = newStreams;
        root.physicalSinks = newPhysicalSinks;
        root.physicalSources = newPhysicalSources;

        const currentPhysicalNames = newPhysicalSinks.map(s => s.name);

        // Maintain most-recently-connected BT sink order
        const nextBtOrder = root.btSinkOrder.filter(n => currentPhysicalNames.indexOf(n) !== -1);
        for (let i = 0; i < newPhysicalSinks.length; i++) {
            const s = newPhysicalSinks[i];
            if (s && isBluetoothSinkName(s.name) && root.knownPhysicalSinkNames.indexOf(s.name) === -1) {
                const idx = nextBtOrder.indexOf(s.name);
                if (idx !== -1) nextBtOrder.splice(idx, 1);
                nextBtOrder.unshift(s.name);
            }
        }
        for (let i = 0; i < newPhysicalSinks.length; i++) {
            const s = newPhysicalSinks[i];
            if (s && isBluetoothSinkName(s.name) && nextBtOrder.indexOf(s.name) === -1) {
                nextBtOrder.push(s.name);
            }
        }
        root.btSinkOrder = nextBtOrder;

        if (!root.startupEnumerating && root.knownPhysicalSinkNames.length > 0) {
            for (let i = 0; i < newPhysicalSinks.length; i++) {
                const sinkNode = newPhysicalSinks[i];
                const name = sinkNode ? sinkNode.name : "";
                if (name && root.knownPhysicalSinkNames.indexOf(name) === -1) {
                    console.log("[Audio.qml] Newly connected physical sink:", name);
                    if (isBluetoothSinkName(name)) {
                        const mac = btMacOf(name);
                        const sameBtProfileSwitch = root.manualSinkOverride && mac !== "" && root.knownPhysicalSinkNames.some(k => isBluetoothSinkName(k) && btMacOf(k) === mac);
                        if (!sameBtProfileSwitch) {
                            console.log("[Audio.qml] Auto-switching to newly connected priority BT device:", name);
                            root.manualSinkOverride = false;
                            root.preferredPhysicalSink = name;
                            root.lastPrioritySinkConnectTime = Date.now();
                        }
                    } else if (name.indexOf("usb") !== -1 && !isMicOrLoopbackSink(sinkNode)) {
                        console.log("[Audio.qml] Auto-switching to newly connected priority USB device:", name);
                        root.manualSinkOverride = false;
                        root.preferredPhysicalSink = name;
                        root.lastPrioritySinkConnectTime = Date.now();
                    }
                }
            }
        }
        root.knownPhysicalSinkNames = currentPhysicalNames;

        const currentPhysicalSourceNames = newPhysicalSources.map(s => s.name);
        if (!root.startupEnumerating && root.knownPhysicalSourceNames.length > 0) {
            for (let i = 0; i < newPhysicalSources.length; i++) {
                const srcNode = newPhysicalSources[i];
                const name = srcNode ? srcNode.name : "";
                if (name && root.knownPhysicalSourceNames.indexOf(name) === -1) {
                    console.log("[Audio.qml] Newly connected physical source:", name);
                    // Only auto-switch to newly connected dedicated USB mics; never auto-hijack onto bluez_input
                    if (name.indexOf("usb") !== -1 && !isIgnoredUsbSource(srcNode)) {
                        console.log("[Audio.qml] Auto-switching to newly connected priority USB input device:", name);
                        root.manualSourceOverride = false;
                        root.preferredPhysicalSource = name;
                        root.lastPrioritySourceConnectTime = Date.now();
                    }
                }
            }
        }
        root.knownPhysicalSourceNames = currentPhysicalSourceNames;

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
            root.lastRoutedPhysicalSink = "";
            root.lastConfiguredPhysicalSink = "";
            root.lastRoutedPhysicalSource = "";
            root.btSinkOrder = [];
            root.eqRouteRetries = 0;
            root.micRouteRetries = 0;
            eqRouteRetryTimer.stop();
            micRouteRetryTimer.stop();
            if (!Quickshell.env("PYTEST_CURRENT_TEST")) {
                root.startupEnumerating = true;
                startupEnumTimer.restart();
            }
        }

        root.updateActiveSink();
        root.updateActiveSource();
        root.syncingNodes = false;

        if (root.startupEnumerating && root.startupPendingNodes.length > 0) {
            const stillPending = root.startupPendingNodes.filter(node =>
                node && Pipewire.nodes.values.indexOf(node) !== -1 && !node.ready
            );
            root.startupPendingNodes = stillPending;
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
                if (node && !node.isStream && !node.ready) {
                    pending.push(node);
                }
            }
            if (pending.length > 0) {
                root.startupPendingNodes = pending;
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
            if (root.customVolume !== -1 && root.isNodeValid(root.sink) && root.sink.audio) {
                if (!root.volumeSetProc.running && root.pendingVolumeCmd === null) {
                    root.customVolume = -1;
                    if (root.customMuted === -1)
                        root.customStateTimer.stop();
                } else if (Math.abs(root.sink.audio.volume - root.customVolume) < 0.01) {
                    root.customVolume = -1;
                    if (root.customMuted === -1)
                        root.customStateTimer.stop();
                }
            }
        }

        function onMutedChanged(): void {
            if (root.customMuted !== -1 && root.isNodeValid(root.sink) && root.sink.audio) {
                const actualMuted = root.sink.audio.muted ? 1 : 0;
                if ((!root.muteSetProc.running && root.pendingMuteCmd === null) || actualMuted === root.customMuted) {
                    root.customMuted = -1;
                    if (root.customVolume === -1)
                        root.customStateTimer.stop();
                }
            }
        }
    }

    Connections {
        target: (Pipewire && Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.ready && Pipewire.defaultAudioSink.name === "riced_equalizer_sink") ? Pipewire.defaultAudioSink.audio : null
        ignoreUnknownSignals: true

        function onVolumeChanged(): void {
            root.enforceEqSinkUnattenuated();
        }

        function onMutedChanged(): void {
            root.enforceEqSinkUnattenuated();
        }
    }

    Connections {
        ignoreUnknownSignals: true

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
        function onLinkAdded(): void {
            root.filterSyncTimer.restart();
        }
        function onLinkGroupAdded(): void {
            root.filterSyncTimer.restart();
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

        function toggleMute(): void {
            root.toggleMute();
        }

        function toggleSourceMute(): void {
            root.toggleSourceMute();
        }

        function showOsd(): void {
            root.osdTriggered();
        }

        function getActivePhysicalSink(): string {
            return root.preferredPhysicalSink;
        }

        function updateVolume(volStr: string, mutStr: string): void {
            const vol = parseFloat(volStr);
            const mut = (mutStr === "true" || mutStr === "1");
            if (!isNaN(vol) && isFinite(vol)) {
                const clamped = Math.max(0, Math.min(GlobalConfig.services.maxVolume, vol));
                const sinkReady = root.isNodeValid(root.sink) && root.sink.audio;
                if (!sinkReady || Math.abs(root.sink.audio.volume - clamped) >= 0.005) {
                    root.customVolume = clamped;
                    root.customStateTimer.restart();
                }
                if (!sinkReady || (!!root.sink.audio.muted) !== mut) {
                    root.customMuted = mut ? 1 : 0;
                    root.customStateTimer.restart();
                }
                root.osdTriggered();
            }
        }

        target: "audio"
    }
}
