pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Io

Singleton {
    id: root

    readonly property BluetoothAdapter adapter: Bluetooth.defaultAdapter // qmllint disable unresolved-type
    property bool enabling: false
    readonly property bool enabled: (adapter?.enabled ?? false) || enabling
    property bool pendingDiscovering: false
    readonly property bool discovering: (adapter?.discovering ?? false) || (enabling && pendingDiscovering)
    property BluetoothDevice pendingConnectDevice: null

    function setEnabled(on: bool): void {
        if (on) {
            if (adapter?.enabled) {
                enabling = false;
                flushPendingActions();
                return;
            }
            enabling = true;
            enableTimeout.restart();
            if (adapter && adapter.state !== BluetoothAdapterState.Blocked) // qmllint disable unresolved-type
                adapter.enabled = true;
            enableProc.running = false;
            enableProc.running = true;
        } else {
            enabling = false;
            pendingDiscovering = false;
            pendingConnectDevice = null;
            enableTimeout.stop();
            enableProc.running = false;
            if (adapter) {
                if (adapter.discovering)
                    adapter.discovering = false;
                adapter.enabled = false;
            }
        }
    }

    function toggleEnabled(): void {
        setEnabled(!enabled);
    }

    function setDiscovering(on: bool): void {
        if (on) {
            if (adapter?.enabled) {
                pendingDiscovering = false;
                adapter.discovering = true;
            } else {
                pendingDiscovering = true;
                setEnabled(true);
            }
        } else {
            pendingDiscovering = false;
            if (adapter?.discovering)
                adapter.discovering = false;
        }
    }

    function toggleDeviceConnection(dev: BluetoothDevice): void {
        if (!dev)
            return;

        const isConnectedOrConnecting = dev.connected || dev.state === BluetoothDeviceState.Connected || dev.state === BluetoothDeviceState.Connecting; // qmllint disable unresolved-type
        if (isConnectedOrConnecting || pendingConnectDevice === dev) {
            if (pendingConnectDevice === dev)
                pendingConnectDevice = null;
            if (isConnectedOrConnecting)
                dev.disconnect();
            return;
        }

        if (!dev.trusted)
            dev.trusted = true;

        if (adapter?.enabled) {
            dev.connect();
        } else {
            pendingConnectDevice = dev;
            setEnabled(true);
        }
    }

    function flushPendingActions(): void {
        if (!adapter?.enabled)
            return;

        if (pendingDiscovering) {
            pendingDiscovering = false;
            adapter.discovering = true;
        }

        if (pendingConnectDevice) {
            const dev = pendingConnectDevice;
            pendingConnectDevice = null;
            if (!dev.trusted)
                dev.trusted = true;
            dev.connect();
        }
    }

    Component.onCompleted: {
        if (adapter?.state === BluetoothAdapterState.Blocked) // qmllint disable unresolved-type
            unblockProc.running = true;
    }

    Connections {
        function onEnabledChanged(): void {
            if (root.adapter?.enabled) {
                root.enabling = false;
                enableTimeout.stop();
                root.flushPendingActions();
            }
        }

        function onStateChanged(): void {
            if (root.enabling && root.adapter && root.adapter.state !== BluetoothAdapterState.Blocked && !root.adapter.enabled) // qmllint disable unresolved-type
                root.adapter.enabled = true;
        }

        target: root.adapter
    }

    Process {
        id: unblockProc

        command: ["rfkill", "unblock", "bluetooth"]
    }

    Process {
        id: enableProc

        command: ["sh", "-c", "rfkill unblock bluetooth && for i in 1 2 3 4 5; do bluetoothctl power on && break; sleep 0.15; done"]
        onExited: {
            if (root.adapter && !root.adapter.enabled && root.adapter.state !== BluetoothAdapterState.Blocked) // qmllint disable unresolved-type
                root.adapter.enabled = true;
        }
    }

    Timer {
        id: enableTimeout

        interval: 4000
        onTriggered: {
            if (!root.adapter?.enabled) {
                root.enabling = false;
                root.pendingDiscovering = false;
                root.pendingConnectDevice = null;
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
            return `enabled=${root.enabled} adapterEnabled=${root.adapter?.enabled ?? false} discovering=${root.discovering}`;
        }

        function scan(onStr: string): void {
            root.setDiscovering(onStr === "true" || onStr === "1" || onStr === "on");
        }

        function connect(query: string): string {
            const q = query.trim().toLowerCase();
            const dev = Bluetooth.devices.values.find(d => d.address?.toLowerCase() === q || d.name?.toLowerCase() === q || d.deviceName?.toLowerCase() === q); // qmllint disable unresolved-type
            if (!dev)
                return `Device not found: ${query}`;
            root.toggleDeviceConnection(dev);
            return `Toggled connection for ${dev.name || dev.address}`;
        }

        target: "bluetooth"
    }
}
