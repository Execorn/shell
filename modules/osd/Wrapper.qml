pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.components
import qs.services

Item {
    id: root

    required property ShellScreen screen
    required property DrawerVisibilities visibilities
    required property bool sidebarOrSessionVisible

    property bool hovered
    readonly property Brightness.Monitor monitor: Brightness.getMonitorForScreen(root.screen)
    readonly property bool shouldBeActive: visibilities.osd && Config.osd.enabled && !(visibilities.utilities && Config.utilities.enabled)
    property real offsetScale: shouldBeActive ? 0 : 1
    property real sidebarOffset: sidebarOrSessionVisible ? 12 : 0

    property real volume
    property bool muted
    property real sourceVolume
    property bool sourceMuted
    property real brightness

    property var lastSink: null
    property var lastSource: null
    property bool sinkSwitching: false
    property bool sourceSwitching: false

    function show(): void {
        visibilities.osd = true;
        timer.restart();
    }

    function syncSinkSnapshot(): void {
        root.sinkSwitching = true;
        root.lastSink = Audio.sink;
        root.volume = Audio.volume;
        root.muted = Audio.muted;
        Qt.callLater(() => {
            root.sinkSwitching = false;
        });
    }

    function syncSourceSnapshot(): void {
        root.sourceSwitching = true;
        root.lastSource = Audio.source;
        root.sourceVolume = Audio.sourceVolume;
        root.sourceMuted = Audio.sourceMuted;
        Qt.callLater(() => {
            root.sourceSwitching = false;
        });
    }

    onHoveredChanged: {
        if (!hovered && visibilities.osd)
            timer.restart();
    }

    Component.onCompleted: {
        lastSink = Audio.sink;
        lastSource = Audio.source;
        volume = Audio.volume;
        muted = Audio.muted;
        sourceVolume = Audio.sourceVolume;
        sourceMuted = Audio.sourceMuted;
        brightness = root.monitor?.brightness ?? 0;
    }

    visible: offsetScale < 1
    anchors.rightMargin: (-implicitWidth - 5 - sidebarOffset) * offsetScale
    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight
    opacity: 1 - offsetScale

    Behavior on offsetScale {
        Anim {}
    }

    Connections {
        function onOsdTriggered(): void {
            root.lastSink = Audio.sink;
            root.volume = Audio.volume;
            root.muted = Audio.muted;
            root.show();
        }

        function onSourceOsdTriggered(): void {
            root.lastSource = Audio.source;
            root.sourceVolume = Audio.sourceVolume;
            root.sourceMuted = Audio.sourceMuted;
            if (root.Config.osd.enableMicrophone)
                root.show();
        }

        function onSinkChanged(): void {
            root.syncSinkSnapshot();
        }

        function onSourceChanged(): void {
            root.syncSourceSnapshot();
        }

        function onMutedChanged(): void {
            if (Audio.startupEnumerating || root.sinkSwitching || root.lastSink !== Audio.sink) {
                root.syncSinkSnapshot();
                return;
            }
            root.muted = Audio.muted;
            root.show();
        }

        function onVolumeChanged(): void {
            if (Audio.startupEnumerating || root.sinkSwitching || root.lastSink !== Audio.sink) {
                root.syncSinkSnapshot();
                return;
            }
            root.volume = Audio.volume;
            root.show();
        }

        function onSourceMutedChanged(): void {
            if (Audio.startupEnumerating || root.sourceSwitching || root.lastSource !== Audio.source) {
                root.syncSourceSnapshot();
                return;
            }
            root.sourceMuted = Audio.sourceMuted;
            if (root.Config.osd.enableMicrophone)
                root.show();
        }

        function onSourceVolumeChanged(): void {
            if (Audio.startupEnumerating || root.sourceSwitching || root.lastSource !== Audio.source) {
                root.syncSourceSnapshot();
                return;
            }
            root.sourceVolume = Audio.sourceVolume;
            if (root.Config.osd.enableMicrophone)
                root.show();
        }

        target: Audio
    }

    Connections {
        function onBrightnessChanged(): void {
            root.show();
            root.brightness = root.monitor?.brightness ?? 0;
        }

        target: root.monitor
    }

    Connections {
        function onBrightnessUpdated(value: real): void {
            root.show();
            root.brightness = root.monitor?.brightness ?? value;
        }

        target: Brightness
    }

    Timer {
        id: timer

        interval: root.Config.osd.hideDelay
        onTriggered: {
            if (!root.hovered)
                root.visibilities.osd = false;
        }
    }

    Loader {
        id: content

        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left

        active: root.shouldBeActive || root.visible

        onActiveChanged: {
            if (active) {
                setSource("Content.qml", {
                    monitor: root.monitor,
                    visibilities: root.visibilities,
                    volume: root.volume,
                    muted: root.muted,
                    sourceVolume: root.sourceVolume,
                    sourceMuted: root.sourceMuted,
                    brightness: root.brightness
                });
            } else {
                source = "";
            }
        }

        Binding {
            when: content.item !== null
            target: content.item
            property: "monitor"
            value: root.monitor
        }

        Binding {
            when: content.item !== null
            target: content.item
            property: "volume"
            value: root.volume
        }

        Binding {
            when: content.item !== null
            target: content.item
            property: "muted"
            value: root.muted
        }

        Binding {
            when: content.item !== null
            target: content.item
            property: "sourceVolume"
            value: root.sourceVolume
        }

        Binding {
            when: content.item !== null
            target: content.item
            property: "sourceMuted"
            value: root.sourceMuted
        }

        Binding {
            when: content.item !== null
            target: content.item
            property: "brightness"
            value: root.brightness
        }
    }
}
