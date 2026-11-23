pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia.Config
import Caelestia.Internal

Singleton {
    id: root

    property int refCount: 0

    // Current speeds in bytes per second
    readonly property real downloadSpeed: _downloadSpeed
    readonly property real uploadSpeed: _uploadSpeed

    // Total bytes transferred since tracking started
    readonly property real downloadTotal: _downloadTotal
    readonly property real uploadTotal: _uploadTotal

    // History buffers for sparkline
    readonly property alias downloadBuffer: downloadHistory
    readonly property alias uploadBuffer: uploadHistory
    readonly property int historyLength: 30

    // Private properties
    property real _downloadSpeed: 0
    property real _uploadSpeed: 0
    property real _downloadTotal: 0
    property real _uploadTotal: 0

    // Per-interface previous counters and sampling state
    property var _prevByIface: ({})
    property real _prevTimestamp: 0
    property bool _initialized: false

    // Sysfs physical/virtual classification cache (iface -> true if physical hardware NIC)
    property var _sysfsPhysical: ({})
    property bool _probePending: false

    function reset(): void {
        root._downloadSpeed = 0;
        root._uploadSpeed = 0;
        root._downloadTotal = 0;
        root._uploadTotal = 0;
        root._prevByIface = {};
        root._prevTimestamp = 0;
        root._initialized = false;
        downloadHistory.clear();
        uploadHistory.clear();
    }

    function formatBytes(bytes: real): var {
        if (bytes < 0 || isNaN(bytes) || !isFinite(bytes)) {
            return {
                value: 0,
                unit: "B/s"
            };
        }

        const kib = 1024;
        const mib = kib * 1024;
        const gib = mib * 1024;
        const tib = gib * 1024;

        if (bytes < kib) {
            return {
                value: bytes,
                unit: "B/s"
            };
        } else if (bytes < mib) {
            return {
                value: bytes / kib,
                unit: "KB/s"
            };
        } else if (bytes < gib) {
            return {
                value: bytes / mib,
                unit: "MB/s"
            };
        } else if (bytes < tib) {
            return {
                value: bytes / gib,
                unit: "GB/s"
            };
        } else {
            return {
                value: bytes / tib,
                unit: "TB/s"
            };
        }
    }

    function formatBytesTotal(bytes: real): var {
        if (bytes < 0 || isNaN(bytes) || !isFinite(bytes)) {
            return {
                value: 0,
                unit: "B"
            };
        }

        const kib = 1024;
        const mib = kib * 1024;
        const gib = mib * 1024;
        const tib = gib * 1024;

        if (bytes < kib) {
            return {
                value: bytes,
                unit: "B"
            };
        } else if (bytes < mib) {
            return {
                value: bytes / kib,
                unit: "KB"
            };
        } else if (bytes < gib) {
            return {
                value: bytes / mib,
                unit: "MB"
            };
        } else if (bytes < tib) {
            return {
                value: bytes / gib,
                unit: "GB"
            };
        } else {
            return {
                value: bytes / tib,
                unit: "TB"
            };
        }
    }

    function isVirtualInterfaceName(iface: string): bool {
        if (!iface || iface === "lo")
            return true;
        return /^(tun\d*|tap\d*|wg\d*|utun\d*|tailscale\d*|zt[0-9a-z]+|docker\d*|veth.*|br-.*|virbr\d*|cni\d*|flannel\..*|podman\d*|cali.*|kube.*|dummy\d*|ifb\d*|sit\d*|gre\d*|ip6tnl\d*|mihomo.*|sing-?box.*|nekobox.*|warp.*|cloudflare.*|nordlynx.*|mullvad.*|proton\d*|amnezia.*|xray.*|.*[-_]xray.*)$/i.test(iface);
    }

    function parseNetDev(content: string): var {
        const result = {};
        if (!content)
            return result;

        const lines = content.split("\n");
        for (let i = 2; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line)
                continue;

            const colonIdx = line.indexOf(":");
            if (colonIdx <= 0)
                continue;

            const iface = line.slice(0, colonIdx).trim();
            if (!iface || iface === "lo")
                continue;

            const fields = line.slice(colonIdx + 1).trim().split(/\s+/);
            if (fields.length < 9)
                continue;

            const rxBytes = Number(fields[0]);
            const txBytes = Number(fields[8]);
            if (!isFinite(rxBytes) || !isFinite(txBytes) || rxBytes < 0 || txBytes < 0)
                continue;

            result[iface] = {
                rx: rxBytes,
                tx: txBytes
            };
        }

        return result;
    }

    function selectTrackedInterfaces(allIfaces: var): var {
        const physical = {};
        let physicalCount = 0;

        for (const iface in allIfaces) {
            if (!Object.prototype.hasOwnProperty.call(allIfaces, iface))
                continue;

            const hasSysfs = Object.prototype.hasOwnProperty.call(root._sysfsPhysical, iface);
            const isVirtual = hasSysfs ? !root._sysfsPhysical[iface] : root.isVirtualInterfaceName(iface);
            if (!isVirtual) {
                physical[iface] = allIfaces[iface];
                physicalCount++;
            }
        }

        if (physicalCount > 0)
            return physical;

        // Container/VM fallback when no hardware-backed NICs exist under /sys/class/net/*/device
        const fallback = {};
        let fallbackCount = 0;
        for (const iface in allIfaces) {
            if (!Object.prototype.hasOwnProperty.call(allIfaces, iface))
                continue;
            if (!root.isVirtualInterfaceName(iface)) {
                fallback[iface] = allIfaces[iface];
                fallbackCount++;
            }
        }

        return fallbackCount > 0 ? fallback : allIfaces;
    }

    function _maybeProbeInterfaces(allIfaces: var): void {
        let needsProbe = false;
        for (const iface in allIfaces) {
            if (Object.prototype.hasOwnProperty.call(allIfaces, iface) && !Object.prototype.hasOwnProperty.call(root._sysfsPhysical, iface)) {
                needsProbe = true;
                break;
            }
        }

        if (!needsProbe)
            return;

        if (ifaceProbeProc.running) {
            root._probePending = true;
        } else {
            ifaceProbeProc.running = true;
        }
    }

    function applySysfsClassification(output: string): void {
        if (!output)
            return;

        const nextMap = Object.assign({}, root._sysfsPhysical);
        const lines = output.split("\n");
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line)
                continue;
            const sep = line.lastIndexOf(" ");
            if (sep <= 0)
                continue;
            const iface = line.slice(0, sep).trim();
            const isPhys = line.slice(sep + 1).trim() === "1";
            if (iface)
                nextMap[iface] = isPhys;
        }

        root._sysfsPhysical = nextMap;

        // Drop any cached baselines for interfaces newly confirmed as virtual
        if (root._initialized) {
            let hasAnyPhysical = false;
            for (const iface in nextMap) {
                if (Object.prototype.hasOwnProperty.call(nextMap, iface) && nextMap[iface]) {
                    hasAnyPhysical = true;
                    break;
                }
            }
            if (hasAnyPhysical) {
                const cleaned = {};
                for (const iface in root._prevByIface) {
                    if (Object.prototype.hasOwnProperty.call(root._prevByIface, iface) && nextMap[iface] !== false)
                        cleaned[iface] = root._prevByIface[iface];
                }
                root._prevByIface = cleaned;
            }
        }
    }

    function processSample(content: string, nowMs: real): void {
        if (!content || !isFinite(nowMs))
            return;

        const allIfaces = root.parseNetDev(content);
        root._maybeProbeInterfaces(allIfaces);

        const tracked = root.selectTrackedInterfaces(allIfaces);

        if (!root._initialized) {
            const initialPrev = {};
            for (const iface in tracked) {
                if (!Object.prototype.hasOwnProperty.call(tracked, iface))
                    continue;
                initialPrev[iface] = {
                    rx: tracked[iface].rx,
                    tx: tracked[iface].tx
                };
            }
            root._prevByIface = initialPrev;
            root._prevTimestamp = nowMs;
            root._downloadSpeed = 0;
            root._uploadSpeed = 0;
            root._initialized = true;
            return;
        }

        let rxDelta = 0;
        let txDelta = 0;
        const nextPrev = {};

        for (const iface in tracked) {
            if (!Object.prototype.hasOwnProperty.call(tracked, iface))
                continue;

            const cur = tracked[iface];
            nextPrev[iface] = {
                rx: cur.rx,
                tx: cur.tx
            };

            // Only diff interfaces seen on the previous tick so hot-plugged NICs seed without spiking
            if (Object.prototype.hasOwnProperty.call(root._prevByIface, iface)) {
                const prev = root._prevByIface[iface];
                if (cur.rx >= prev.rx)
                    rxDelta += cur.rx - prev.rx;
                if (cur.tx >= prev.tx)
                    txDelta += cur.tx - prev.tx;
            }
        }

        root._prevByIface = nextPrev;

        const timeDelta = (nowMs - root._prevTimestamp) / 1000;
        root._prevTimestamp = nowMs;

        if (rxDelta > 0 && isFinite(rxDelta))
            root._downloadTotal += rxDelta;
        if (txDelta > 0 && isFinite(txDelta))
            root._uploadTotal += txDelta;

        const intervalMs = (GlobalConfig.dashboard && GlobalConfig.dashboard.resourceUpdateInterval > 0) ? GlobalConfig.dashboard.resourceUpdateInterval : 1000;
        const maxNormalGapSec = Math.max((intervalMs / 1000) * 5, 10);

        if (timeDelta <= 0 || timeDelta > maxNormalGapSec) {
            root._downloadSpeed = 0;
            root._uploadSpeed = 0;
            return;
        }

        const downSpeed = rxDelta / timeDelta;
        const upSpeed = txDelta / timeDelta;

        root._downloadSpeed = (downSpeed >= 0 && isFinite(downSpeed)) ? downSpeed : 0;
        root._uploadSpeed = (upSpeed >= 0 && isFinite(upSpeed)) ? upSpeed : 0;

        // Push upload first so downloadHistory.valuesChanged sees both updated maxima
        uploadHistory.push(root._uploadSpeed);
        downloadHistory.push(root._downloadSpeed);
    }

    CircularBuffer {
        id: downloadHistory

        capacity: root.historyLength + 1
    }

    CircularBuffer {
        id: uploadHistory

        capacity: root.historyLength + 1
    }

    FileView {
        id: netDevFile

        path: "/proc/net/dev"
    }

    Process {
        id: ifaceProbeProc

        command: ["sh", "-c", "for d in /sys/class/net/*; do [ -e \"$d\" ] || continue; n=\"${d##*/}\"; [ -e \"$d/device\" ] && printf '%s 1\\n' \"$n\" || printf '%s 0\\n' \"$n\"; done"]
        stdout: StdioCollector {
            onStreamFinished: root.applySysfsClassification(text)
        }
        onExited: {
            if (root._probePending) {
                root._probePending = false;
                ifaceProbeProc.running = true;
            }
        }
    }

    Timer {
        interval: GlobalConfig.dashboard.resourceUpdateInterval
        running: root.refCount > 0
        repeat: true
        triggeredOnStart: true

        onTriggered: {
            netDevFile.reload();
            const content = netDevFile.text();
            if (!content)
                return;

            root.processSample(content, Date.now());
        }
    }
}
