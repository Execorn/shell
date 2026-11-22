pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import QtQml
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Io
import Caelestia
import Caelestia.Services

Singleton {
    id: root

    readonly property var adapters: Bluetooth.adapters?.values ?? [] // qmllint disable unresolved-type
    readonly property BluetoothAdapter adapter: Bluetooth.defaultAdapter ?? adapters[0] ?? null // qmllint disable unresolved-type
    readonly property bool hasAdapter: adapter !== null
    property bool hardBlocked: false
    property bool softBlocked: false
    property bool enabling: false
    readonly property bool enabled: (adapter?.enabled ?? false) || enabling
    property bool pendingDiscovering: false
    property var pendingPairable: null
    readonly property bool discovering: (adapter?.discovering ?? false) || (enabling && pendingDiscovering)
    property BluetoothDevice pendingConnectDevice: null // qmllint disable unresolved-type
    property BluetoothDevice pendingPairDevice: null // qmllint disable unresolved-type
    property bool pairingUiActive: false

    // BlueZ Agent1 reactive state
    readonly property bool agentRegistered: BluezAgent.registered
    readonly property bool agentPending: BluezAgent.hasPendingRequest
    readonly property bool agentNeedsReply: BluezAgent.needsReply
    readonly property string agentRequestType: BluezAgent.requestType
    readonly property string agentDeviceAddress: BluezAgent.deviceAddress
    readonly property string agentDeviceName: {
        const addr = BluezAgent.deviceAddress.toLowerCase();
        if (addr) {
            const matched = (Bluetooth.devices?.values ?? []).find(d => (d.address ?? "").toLowerCase() === addr); // qmllint disable unresolved-type
            if (matched && (matched.name || matched.deviceName))
                return matched.name || matched.deviceName;
        }
        return BluezAgent.deviceName || BluezAgent.deviceAddress;
    }
    readonly property string agentPasskey: BluezAgent.passkey
    readonly property int agentEntered: BluezAgent.entered
    readonly property string agentServiceUuid: BluezAgent.serviceUuid

    // PipeWire card profile & codec cache keyed by uppercase MAC address
    property var cardProfilesByAddress: ({})
    property var _scanOwners: ({})
    property int _enableGeneration: 0
    property var _cardsSnapshot: []
    property var _sinksSnapshot: ({})
    property bool _cardsDone: false
    property bool _sinksDone: false
    property bool _refreshPending: false
    property int _profileRetryCount: 0

    readonly property int maxProfileRetries: 4
    readonly property int discoveryTimeoutMs: 45000

    function isSavedDevice(dev: BluetoothDevice): bool {
        return !!dev && (dev.bonded || dev.paired || dev.connected);
    }

    function setEnabled(on: bool): void {
        if (on) {
            if (adapter?.enabled) {
                enabling = false;
                hardBlocked = false;
                softBlocked = false;
                flushPendingActions();
                return;
            }
            if ((Bluetooth.adapters?.values?.length ?? 0) === 0 && !adapter) {
                _clearPendingOnDisable();
                Toaster.toast(qsTr("Bluetooth unavailable"), qsTr("No Bluetooth adapter found"), "bluetooth_disabled", Toast.Error);
                return;
            }

            _enableGeneration += 1;
            const gen = _enableGeneration;
            rfkillEnableProc.targetGeneration = gen;
            rfkillEnableProc.running = false;
            rfkillEnableProc.running = true;
        } else {
            _enableGeneration += 1;
            _clearPendingOnDisable();
            enableTimeout.stop();
            rfkillEnableProc.running = false;
            unblockProc.running = false;
            if (adapter) {
                if (adapter.discovering)
                    adapter.discovering = false;
                adapter.enabled = false;
            }
        }
    }

    function _clearPendingOnDisable(): void {
        enabling = false;
        pendingDiscovering = false;
        pendingPairable = null;
        pendingConnectDevice = null;
        pendingPairDevice = null;
        _scanOwners = {};
        discoveryTimeout.stop();
    }

    function toggleEnabled(): void {
        setEnabled(!enabled);
    }

    function setDiscovering(on: bool): void {
        if (on) {
            if (adapter?.enabled) {
                pendingDiscovering = false;
                if (!adapter.discovering)
                    adapter.discovering = true;
                discoveryTimeout.restart();
            } else {
                pendingDiscovering = true;
                discoveryTimeout.stop();
                setEnabled(true);
            }
        } else {
            pendingDiscovering = false;
            _scanOwners = {};
            discoveryTimeout.stop();
            if (adapter?.discovering)
                adapter.discovering = false;
        }
    }

    function acquireScan(owner: string, makePairable: bool): void {
        const nextOwners = Object.assign({}, _scanOwners);
        nextOwners[owner] = true;
        _scanOwners = nextOwners;

        if (makePairable) {
            if (adapter?.enabled)
                adapter.pairable = true;
            else
                pendingPairable = true;
        }

        if (adapter?.enabled) {
            pendingDiscovering = false;
            if (!adapter.discovering)
                adapter.discovering = true;
            discoveryTimeout.restart();
        } else {
            pendingDiscovering = true;
            setEnabled(true);
        }
    }

    function releaseScan(owner: string): void {
        if (!_scanOwners[owner])
            return;
        const nextOwners = Object.assign({}, _scanOwners);
        delete nextOwners[owner];
        _scanOwners = nextOwners;
        if (Object.keys(nextOwners).length === 0)
            setDiscovering(false);
    }

    function pairAndConnect(dev: BluetoothDevice): void {
        if (!dev)
            return;
        if (dev.blocked) {
            Toaster.toast(qsTr("Device blocked"), qsTr("Unblock %1 before pairing").arg(dev.name || dev.address), "block", Toast.Warning);
            return;
        }
        if (dev.pairing)
            return;

        pendingConnectDevice = dev;
        if (adapter?.enabled) {
            pendingPairDevice = null;
            dev.pair();
        } else {
            pendingPairDevice = dev;
            setEnabled(true);
        }
    }

    function toggleDeviceConnection(dev: BluetoothDevice): void {
        if (!dev)
            return;

        if (dev.blocked) {
            Toaster.toast(qsTr("Device blocked"), qsTr("Unblock %1 before connecting").arg(dev.name || dev.address), "block", Toast.Warning);
            return;
        }

        if (dev.state === BluetoothDeviceState.Disconnecting) // qmllint disable unresolved-type
            return;

        const isConnectedOrConnecting = dev.connected || dev.state === BluetoothDeviceState.Connected || dev.state === BluetoothDeviceState.Connecting; // qmllint disable unresolved-type
        if (isConnectedOrConnecting || pendingConnectDevice === dev || pendingPairDevice === dev) {
            if (pendingConnectDevice === dev)
                pendingConnectDevice = null;
            if (pendingPairDevice === dev)
                pendingPairDevice = null;
            if (isConnectedOrConnecting)
                dev.disconnect();
            return;
        }

        if (!dev.paired && !dev.bonded) {
            pairAndConnect(dev);
            return;
        }

        if (dev.bonded && !dev.trusted)
            dev.trusted = true;

        if (adapter?.enabled) {
            dev.connect();
        } else {
            pendingConnectDevice = dev;
            setEnabled(true);
        }
    }

    function forgetDevice(dev: BluetoothDevice): void {
        if (!dev)
            return;

        if (pendingConnectDevice === dev)
            pendingConnectDevice = null;
        if (pendingPairDevice === dev)
            pendingPairDevice = null;

        const key = (dev.address ?? "").toUpperCase();
        if (key && cardProfilesByAddress[key]) {
            const nextMap = Object.assign({}, cardProfilesByAddress);
            delete nextMap[key];
            cardProfilesByAddress = nextMap;
        }

        dev.forget();
    }

    function flushPendingActions(): void {
        if (!adapter?.enabled)
            return;

        if (pendingPairable !== null) {
            adapter.pairable = !!pendingPairable;
            pendingPairable = null;
        }

        if (pendingDiscovering) {
            pendingDiscovering = false;
            if (!adapter.discovering)
                adapter.discovering = true;
            discoveryTimeout.restart();
        }

        if (pendingPairDevice) {
            const pDev = pendingPairDevice;
            pendingPairDevice = null;
            pendingConnectDevice = pDev;
            pDev.pair();
            return;
        }

        if (pendingConnectDevice) {
            const cDev = pendingConnectDevice;
            pendingConnectDevice = null;
            if (!cDev.paired && !cDev.bonded) {
                pairAndConnect(cDev);
            } else {
                if (cDev.bonded && !cDev.trusted)
                    cDev.trusted = true;
                cDev.connect();
            }
        }
    }

    function respondAgentConfirmation(accept: bool): void {
        BluezAgent.respondConfirmation(accept);
    }

    function respondAgentPin(pin: string): void {
        BluezAgent.respondPin(pin);
    }

    function respondAgentPasskey(passkeyValue: int): void {
        BluezAgent.respondPasskey(passkeyValue);
    }

    function cancelAgentPending(): void {
        BluezAgent.cancelPending();
    }

    function refreshAudioProfiles(): void {
        _profileRetryCount = 0;
        cardsRetryTimer.stop();
        cardsRefreshDebounce.restart();
    }

    function cardInfoFor(address: string): var {
        if (!address)
            return null;
        return cardProfilesByAddress[address.toUpperCase()] ?? null;
    }

    function profilesFor(address: string): var {
        return cardInfoFor(address)?.profiles ?? [];
    }

    function activeProfileFor(address: string): string {
        return cardInfoFor(address)?.activeProfile ?? "";
    }

    function activeCodecFor(address: string): string {
        return cardInfoFor(address)?.codecLabel ?? "";
    }

    function setDeviceProfile(address: string, profileName: string): void {
        const info = cardInfoFor(address);
        if (!info || !info.cardName || !profileName)
            return;
        if (info.activeProfile === profileName)
            return;

        setProfileProc.targetAddress = address.toUpperCase();
        setProfileProc.targetProfile = profileName;
        setProfileProc.command = ["pactl", "set-card-profile", info.cardName, profileName];
        setProfileProc.running = false;
        setProfileProc.running = true;
    }

    function _formatCodecName(rawCodec: string): string {
        const key = (rawCodec ?? "").toLowerCase();
        const table = {
            ldac: "LDAC",
            aptx_hd: "aptX HD",
            aptx_ll: "aptX LL",
            aptx_ll_duplex: "aptX LL",
            aptx: "aptX",
            sbc_xq: "SBC-XQ",
            sbc: "SBC",
            aac: "AAC",
            aac_eld: "AAC-ELD",
            msbc: "mSBC",
            cvsd: "CVSD",
            lc3: "LC3"
        };
        return table[key] ?? (rawCodec ? rawCodec.toUpperCase() : "");
    }

    function _extractCodecFromDesc(desc: string): string {
        const match = /codec\s+([^)]+)\)/i.exec(desc ?? "");
        return match ? match[1].trim() : "";
    }

    function _formatProfileEntry(profileName: string, pObj: var, topCodecLabel: string): var {
        const desc = pObj.description ?? profileName;
        const parsedCodec = _extractCodecFromDesc(desc);
        let label = desc;
        let shortLabel = profileName;

        if (profileName === "off") {
            label = qsTr("Off");
            shortLabel = qsTr("Off");
        } else if (profileName.startsWith("a2dp-sink")) {
            const codec = parsedCodec || (profileName === "a2dp-sink" ? (topCodecLabel || "A2DP") : _formatCodecName(profileName.slice("a2dp-sink-".length)));
            label = codec ? qsTr("High Fidelity (A2DP • %1)").arg(codec) : desc;
            shortLabel = codec ? `A2DP • ${codec}` : "A2DP";
        } else if (profileName.startsWith("bap-")) {
            label = parsedCodec ? qsTr("LE Audio (BAP • %1)").arg(parsedCodec) : desc;
            shortLabel = parsedCodec ? `LE • ${parsedCodec}` : profileName;
        } else if (profileName.startsWith("headset-head-unit")) {
            const hfpCodec = parsedCodec || (profileName === "headset-head-unit" ? "mSBC" : "CVSD");
            label = qsTr("Headset Call + Mic (HFP • %1)").arg(hfpCodec);
            shortLabel = `HFP • ${hfpCodec}`;
        }

        return {
            name: profileName,
            description: desc,
            label: label,
            shortLabel: shortLabel,
            codec: parsedCodec,
            priority: pObj.priority ?? 0,
            available: pObj.available !== false,
            sinks: pObj.sinks ?? 0,
            sources: pObj.sources ?? 0,
            isHeadset: profileName.startsWith("headset-head-unit"),
            isA2dp: profileName.startsWith("a2dp-sink") || profileName.startsWith("bap-")
        };
    }

    function _rebuildCardProfiles(): void {
        if (!_cardsDone || !_sinksDone)
            return;

        const nextMap = {};
        for (const card of _cardsSnapshot) {
            const props = card.properties ?? {};
            if (props["device.api"] !== "bluez5" && !(card.name ?? "").startsWith("bluez_card."))
                continue;

            const addr = (props["api.bluez5.address"] ?? props["device.string"] ?? "").toUpperCase();
            if (!addr)
                continue;

            const activeProfile = card.active_profile ?? "";
            const sinkCodecRaw = _sinksSnapshot[addr] ?? "";
            const profilesObj = card.profiles ?? {};
            const activeProfileDesc = profilesObj[activeProfile]?.description ?? activeProfile;
            const parsedDescCodec = _extractCodecFromDesc(activeProfileDesc);
            const codecLabel = activeProfile === "off" ? "" : (_formatCodecName(sinkCodecRaw) || parsedDescCodec);

            const entries = [];
            for (const pName of Object.keys(profilesObj)) {
                const pObj = profilesObj[pName];
                if (!pObj || pObj.available === false)
                    continue;
                entries.push(_formatProfileEntry(pName, pObj, pName === activeProfile ? codecLabel : ""));
            }

            // Rank available profiles: active A2DP / higher-priority A2DP first, then HFP, then Off.
            entries.sort((a, b) => {
                const groupA = a.name === "off" ? 2 : (a.isHeadset ? 1 : 0);
                const groupB = b.name === "off" ? 2 : (b.isHeadset ? 1 : 0);
                if (groupA !== groupB)
                    return groupA - groupB;
                return (b.priority ?? 0) - (a.priority ?? 0);
            });

            nextMap[addr] = {
                cardName: card.name ?? "",
                activeProfile: activeProfile,
                activeProfileDesc: activeProfileDesc,
                codecRaw: sinkCodecRaw,
                codecLabel: codecLabel,
                profiles: entries
            };
        }

        cardProfilesByAddress = nextMap;

        if (_refreshPending) {
            _refreshPending = false;
            cardsRefreshDebounce.restart();
            return;
        }

        const needsCardOrCodec = (Bluetooth.devices?.values ?? []).some(d => { // qmllint disable unresolved-type
            if (!d.connected)
                return false;
            const icon = (d.icon ?? "").toLowerCase();
            if (icon.includes("keyboard") || icon.includes("mouse") || icon.includes("gamepad") || icon.includes("tablet"))
                return false;
            const info = nextMap[(d.address ?? "").toUpperCase()];
            return !info || (info.activeProfile !== "off" && !info.codecLabel);
        });
        if (needsCardOrCodec && _profileRetryCount < maxProfileRetries) {
            _profileRetryCount += 1;
            cardsRetryTimer.restart();
        }
    }

    function _findIpcDevice(query: string): BluetoothDevice {
        const q = query.trim().toLowerCase();
        const matches = (Bluetooth.devices?.values ?? []).filter(d => // qmllint disable unresolved-type
            (d.address ?? "").toLowerCase() === q
            || (d.name ?? "").toLowerCase() === q
            || (d.deviceName ?? "").toLowerCase() === q);
        if (matches.length === 0)
            return null;

        matches.sort((a, b) =>
            (b.connected - a.connected)
            || (b.bonded - a.bonded)
            || (b.paired - a.paired)
            || (a.blocked - b.blocked)
            || (a.name ?? "").localeCompare(b.name ?? ""));
        return matches[0];
    }

    Component.onCompleted: {
        rfkillProbeProc.running = true;
        refreshAudioProfiles();
    }

    Connections {
        target: root.adapter

        function onEnabledChanged(): void {
            if (root.adapter?.enabled) {
                root.enabling = false;
                root.softBlocked = false;
                enableTimeout.stop();
                root.flushPendingActions();
                root.refreshAudioProfiles();
            } else if (!root.enabling) {
                discoveryTimeout.stop();
                root._scanOwners = {};
                root.cardProfilesByAddress = {};
            }
        }

        function onStateChanged(): void {
            if (!root.adapter)
                return;
            if (root.adapter.state === BluetoothAdapterState.Blocked) { // qmllint disable unresolved-type
                rfkillProbeProc.running = true;
            } else if (root.enabling && !root.hardBlocked && !root.adapter.enabled) {
                root.adapter.enabled = true;
            }
        }

        function onDiscoveringChanged(): void {
            if (root.adapter?.discovering) {
                discoveryTimeout.restart();
            } else if (!root.enabling) {
                discoveryTimeout.stop();
                root._scanOwners = {};
            }
        }
    }

    Connections {
        target: root.pendingConnectDevice

        function onPairedChanged(): void {
            const dev = root.pendingConnectDevice;
            if (!dev || !dev.paired)
                return;
            root.pendingConnectDevice = null;
            dev.trusted = true;
            dev.connect();
        }

        function onPairingChanged(): void {
            const dev = root.pendingConnectDevice;
            if (!dev || dev.pairing || dev.paired)
                return;
            root.pendingConnectDevice = null;
            Toaster.toast(qsTr("Pairing failed"), qsTr("Could not pair with %1").arg(dev.name || dev.address), "bluetooth_disabled", Toast.Error);
        }
    }

    Instantiator {
        model: (Bluetooth.devices?.values ?? []).filter(d => d.bonded || d.paired || d.connected) // qmllint disable unresolved-type

        onObjectAdded: root.refreshAudioProfiles()
        onObjectRemoved: root.refreshAudioProfiles()

        delegate: Connections {
            required property BluetoothDevice modelData // qmllint disable unresolved-type

            target: modelData

            function onConnectedChanged(): void {
                root.refreshAudioProfiles();
            }
        }
    }

    Connections {
        target: Audio

        function onPhysicalSinksChanged(): void {
            root.refreshAudioProfiles();
        }

        function onPhysicalSourcesChanged(): void {
            root.refreshAudioProfiles();
        }

        function onSinksChanged(): void {
            root.refreshAudioProfiles();
        }
    }

    Connections {
        target: BluezAgent

        function onRequestReceived(type: string, address: string, passkey: string): void {
            if (root.pairingUiActive)
                return;
            const label = root.agentDeviceName || address;
            if (type === "confirm") {
                Toaster.toast(qsTr("Bluetooth pairing request"), qsTr("Confirm passkey %1 for %2 in Bluetooth Settings").arg(passkey, label), "bluetooth_searching", Toast.Info);
            } else if (type === "pin" || type === "passkey") {
                Toaster.toast(qsTr("Bluetooth PIN required"), qsTr("Enter pairing code for %1 in Bluetooth Settings").arg(label), "pin", Toast.Info);
            } else if (type === "displayPin" || type === "displayPasskey") {
                Toaster.toast(qsTr("Bluetooth passkey"), qsTr("Type %1 on %2 and press Enter").arg(passkey, label), "keyboard", Toast.Info);
            } else if (type === "authorize" || type === "authorizeService") {
                Toaster.toast(qsTr("Bluetooth authorization"), qsTr("Approve incoming connection from %1 in Bluetooth Settings").arg(label), "bluetooth_searching", Toast.Info);
            }
        }

        function onRegistrationFailed(reason: string): void {
            Toaster.toast(qsTr("Bluetooth agent error"), reason, "warning", Toast.Warning);
        }
    }

    Process {
        id: rfkillProbeProc

        command: ["rfkill", "-J"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const parsed = JSON.parse(text);
                    const btDevs = (parsed.rfkilldevices ?? []).filter(d => d.type === "bluetooth");
                    root.hardBlocked = btDevs.some(d => d.hard === "blocked");
                    root.softBlocked = btDevs.some(d => d.soft === "blocked");
                } catch (e) {
                    console.warn("Failed to parse rfkill probe output:", e);
                }
            }
        }
    }

    Process {
        id: rfkillEnableProc

        property int targetGeneration: 0

        command: ["rfkill", "-J"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (rfkillEnableProc.targetGeneration !== root._enableGeneration)
                    return;

                let isHard = false;
                let isSoft = false;
                try {
                    const parsed = JSON.parse(text);
                    const btDevs = (parsed.rfkilldevices ?? []).filter(d => d.type === "bluetooth");
                    isHard = btDevs.some(d => d.hard === "blocked");
                    isSoft = btDevs.some(d => d.soft === "blocked");
                } catch (e) {
                    console.warn("Failed to parse rfkill output during enable:", e);
                }

                root.hardBlocked = isHard;
                root.softBlocked = isSoft;

                if (isHard) {
                    root._clearPendingOnDisable();
                    Toaster.toast(qsTr("Bluetooth blocked"), qsTr("Bluetooth is disabled by hardware kill switch"), "bluetooth_disabled", Toast.Error);
                    return;
                }

                root.enabling = true;
                enableTimeout.restart();

                if (isSoft || root.adapter?.state === BluetoothAdapterState.Blocked) { // qmllint disable unresolved-type
                    unblockProc.targetGeneration = rfkillEnableProc.targetGeneration;
                    unblockProc.running = false;
                    unblockProc.running = true;
                } else if (root.adapter && !root.adapter.enabled) {
                    root.adapter.enabled = true;
                }
            }
        }
    }

    Process {
        id: unblockProc

        property int targetGeneration: 0

        command: ["rfkill", "unblock", "bluetooth"]
        onExited: exitCode => {
            if (targetGeneration !== root._enableGeneration)
                return;
            if (exitCode !== 0) {
                root._clearPendingOnDisable();
                enableTimeout.stop();
                Toaster.toast(qsTr("Bluetooth error"), qsTr("Failed to unblock Bluetooth radio"), "bluetooth_disabled", Toast.Error);
                return;
            }
            root.softBlocked = false;
            if (root.adapter && !root.adapter.enabled && root.adapter.state !== BluetoothAdapterState.Blocked) // qmllint disable unresolved-type
                root.adapter.enabled = true;
        }
    }

    Timer {
        id: enableTimeout

        interval: 5000
        onTriggered: {
            if (!root.adapter?.enabled && root.enabling) {
                root._enableGeneration += 1;
                root._clearPendingOnDisable();
                Toaster.toast(qsTr("Bluetooth timeout"), qsTr("Timed out enabling Bluetooth adapter"), "bluetooth_disabled", Toast.Error);
            }
        }
    }

    Timer {
        id: discoveryTimeout

        interval: root.discoveryTimeoutMs
        onTriggered: {
            if (root.discovering)
                root.setDiscovering(false);
        }
    }

    Timer {
        id: cardsRefreshDebounce

        interval: 250
        onTriggered: {
            if (cardsProc.running || sinksProc.running) {
                root._refreshPending = true;
                return;
            }
            root._cardsDone = false;
            root._sinksDone = false;
            cardsProc.running = true;
            sinksProc.running = true;
        }
    }

    Timer {
        id: cardsRetryTimer

        interval: 750
        onTriggered: cardsRefreshDebounce.restart()
    }

    Process {
        id: cardsProc

        command: ["pactl", "-f", "json", "list", "cards"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root._cardsSnapshot = JSON.parse(text);
                } catch (e) {
                    root._cardsSnapshot = [];
                }
                root._cardsDone = true;
                root._rebuildCardProfiles();
            }
        }
        onExited: exitCode => {
            if (exitCode !== 0) {
                root._cardsSnapshot = [];
                root._cardsDone = true;
                root._rebuildCardProfiles();
            }
        }
    }

    Process {
        id: sinksProc

        command: ["pactl", "-f", "json", "list", "sinks"]
        stdout: StdioCollector {
            onStreamFinished: {
                const map = {};
                try {
                    const sinks = JSON.parse(text);
                    for (const s of sinks) {
                        const props = s.properties ?? {};
                        const addr = (props["api.bluez5.address"] ?? "").toUpperCase();
                        const codec = props["api.bluez5.codec"] ?? "";
                        if (addr && codec)
                            map[addr] = codec;
                    }
                } catch (e) {
                    // Ignore transient pactl parse error
                }
                root._sinksSnapshot = map;
                root._sinksDone = true;
                root._rebuildCardProfiles();
            }
        }
        onExited: exitCode => {
            if (exitCode !== 0) {
                root._sinksSnapshot = {};
                root._sinksDone = true;
                root._rebuildCardProfiles();
            }
        }
    }

    Process {
        id: setProfileProc

        property string targetAddress: ""
        property string targetProfile: ""

        onExited: exitCode => {
            if (exitCode !== 0) {
                Toaster.toast(qsTr("Audio profile error"), qsTr("Failed to switch Bluetooth profile to %1").arg(targetProfile), "warning", Toast.Warning);
            } else {
                root.refreshAudioProfiles();
            }
        }
    }

    IpcHandler {
        function enable(): void {
            root.setEnabled(true);
        }

        function disable(): void {
            root.setEnabled(false);
        }

        function toggle(): void {
            root.toggleEnabled();
        }

        function status(): string {
            const connected = (Bluetooth.devices?.values ?? []) // qmllint disable unresolved-type
                .filter(d => d.connected)
                .map(d => {
                    const codec = root.activeCodecFor(d.address);
                    return codec ? `${d.name || d.address} [${codec}]` : (d.name || d.address);
                });
            return `hasAdapter=${root.hasAdapter} enabled=${root.enabled} adapterEnabled=${root.adapter?.enabled ?? false} hardBlocked=${root.hardBlocked} discovering=${root.discovering} agentRegistered=${root.agentRegistered} connected=[${connected.join(", ")}]`;
        }

        function scan(onStr: string): void {
            const on = onStr === "true" || onStr === "1" || onStr === "on";
            if (on)
                root.acquireScan("ipc", false);
            else
                root.setDiscovering(false);
        }

        function connect(query: string): string {
            const dev = root._findIpcDevice(query);
            if (!dev)
                return `Device not found: ${query}`;
            if (dev.blocked)
                return `Device is blocked: ${dev.name || dev.address}`;
            root.toggleDeviceConnection(dev);
            return `Toggled connection for ${dev.name || dev.address}`;
        }

        function pair(query: string): string {
            const dev = root._findIpcDevice(query);
            if (!dev)
                return `Device not found: ${query}`;
            root.pairAndConnect(dev);
            return `Pairing ${dev.name || dev.address}`;
        }

        function forget(query: string): string {
            const dev = root._findIpcDevice(query);
            if (!dev)
                return `Device not found: ${query}`;
            const label = dev.name || dev.address;
            root.forgetDevice(dev);
            return `Forgot ${label}`;
        }

        function profiles(query: string): string {
            const dev = root._findIpcDevice(query);
            if (!dev)
                return `Device not found: ${query}`;
            const list = root.profilesFor(dev.address).map(p => `${p.name === root.activeProfileFor(dev.address) ? "*" : ""}${p.name} (${p.shortLabel})`);
            return list.length > 0 ? list.join(", ") : `No audio profiles for ${dev.name || dev.address}`;
        }

        function setProfile(query: string, profileName: string): string {
            const dev = root._findIpcDevice(query);
            if (!dev)
                return `Device not found: ${query}`;
            const info = root.cardInfoFor(dev.address);
            if (!info)
                return `No PipeWire card found for ${dev.name || dev.address}`;
            root.setDeviceProfile(dev.address, profileName);
            return `Switching ${dev.name || dev.address} profile to ${profileName}`;
        }

        target: "bluetooth"
    }
}
