pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property bool active: false
    property int temperature: 4000

    readonly property var process: proc

    onActiveChanged: debounceTimer.restart()

    onTemperatureChanged: debounceTimer.restart()

    Component.onCompleted: {
        proc.command = ["wlsunset", "-t", root.temperature.toString()];
        proc.running = root.active;
    }

    Process {
        id: proc

        command: ["wlsunset", "-t", "4000"]
        running: false
    }

    Timer {
        id: debounceTimer

        interval: 300
        repeat: false

        onTriggered: {
            if (proc.running) {
                proc.running = false;
            }
            proc.command = ["wlsunset", "-t", root.temperature.toString()];
            proc.running = root.active;
        }
    }
}
