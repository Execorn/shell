import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

ShellRoot {
    Connections {
        target: Pipewire.nodes
        function onValuesChanged() {
            if (Pipewire.nodes.values.length > 0) {
                const node = Pipewire.nodes.values[0];
                console.log("--- NODE PROPERTIES ---");
                console.log("node object:", node);
                for (const prop in node) {
                    try {
                        console.log(`  ${prop}: ${node[prop]}`);
                    } catch (e) {
                        console.log(`  ${prop}: (error reading: ${e.message})`);
                    }
                }
                quitTimer.restart();
            }
        }
    }

    Timer {
        id: quitTimer
        interval: 1000
        onTriggered: Qt.quit()
    }
}
