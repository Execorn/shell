pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import Caelestia.Config
import qs.components
import qs.services
import qs.modules.nexus
import qs.modules.windowinfo

Item {
    id: root

    required property ShellScreen screen
    required property real offsetScale

    readonly property alias content: content
    readonly property alias winfo: winfo
    readonly property alias nexus: nexus

    readonly property real nonAnimWidth: children.find(c => c.shouldBeActive)?.implicitWidth ?? content.implicitWidth
    readonly property real nonAnimHeight: children.find(c => c.shouldBeActive)?.implicitHeight ?? content.implicitHeight
    readonly property Item current: content.item?.current ?? null // qmllint disable missing-property
    readonly property bool isDetached: detachedMode.length > 0

    property alias currentName: popoutState.currentName
    property alias hasCurrent: popoutState.hasCurrent
    property real currentCenter

    property string detachedMode
    property string queuedMode

    // Dummy object so Tokens attached prop resolves to global config
    // Anim configs are not per-monitor
    readonly property QtObject dummy: QtObject {}
    property int animLength: dummy.Tokens.anim.durations.expressiveDefaultSpatial
    property var animCurve: dummy.Tokens.anim.expressiveDefaultSpatial // The easingCurve type is Qt 6.11+ so we gotta use var for now

    function setAnims(detach: bool): void {
        const type = `expressive${detach ? "Slow" : "Default"}Spatial`;
        animLength = dummy.Tokens.anim.durations[type];
        animCurve = dummy.Tokens.anim[type];
    }

    function detach(mode: string): void {
        setAnims(true);
        if (mode === "winfo") {
            detachedMode = mode;
        } else {
            queuedMode = mode;
            detachedMode = "any";
        }
        setAnims(false);
        focus = true;
    }

    function close(): void {
        hasCurrent = false;
        detachedMode = "";
    }

    implicitWidth: nonAnimWidth
    implicitHeight: nonAnimHeight

    focus: hasCurrent
    Keys.onEscapePressed: {
        // Forward escape to password popout if active, otherwise close
        if (currentName === "wirelesspassword" && content.item) {
            const passwordPopout = (content.item as Item)?.children.find(c => c.name === "wirelesspassword"); // qmllint disable missing-property
            if (passwordPopout && passwordPopout.item) {
                passwordPopout.item.closeDialog();
                return;
            }
        }
        close();
    }

    Keys.onPressed: event => {
        // Don't intercept keys when password popout is active - let it handle them
        if (currentName === "wirelesspassword") {
            event.accepted = false;
        }
    }

    PopoutState {
        id: popoutState

        onDetachRequested: mode => root.detach(mode)
    }

    HyprlandFocusGrab {
        active: root.isDetached
        windows: [QsWindow.window]
        onCleared: root.close()
    }

    Binding {
        when: root.isDetached || (root.hasCurrent && root.currentName === "wirelesspassword")

        target: QsWindow.window
        property: "WlrLayershell.keyboardFocus"
        value: WlrKeyboardFocus.OnDemand
    }

    Comp {
        id: content

        shouldBeActive: root.hasCurrent && !root.detachedMode
        anchors.fill: parent

        onActiveChanged: {
            if (active)
                setSource("Content.qml", { popouts: popoutState });
            else
                source = "";
        }
    }

    Comp {
        id: winfo

        shouldBeActive: root.detachedMode === "winfo"
        anchors.centerIn: parent

        onActiveChanged: {
            if (active)
                setSource("../../windowinfo/WindowInfo.qml", { screen: root.screen, client: Hypr.activeToplevel });
            else
                source = "";
        }

        Binding {
            when: winfo.item !== null
            target: winfo.item
            property: "client"
            value: Hypr.activeToplevel
        }
    }

    Comp {
        id: nexus

        shouldBeActive: root.detachedMode === "any"
        anchors.centerIn: parent

        onActiveChanged: {
            if (active) {
                setSource("../../nexus/DetachedNexus.qml", {
                    screen: root.screen,
                    animatingContainer: nexus.opacity < 1,
                    initPageIdx: ["appearance", "network", "bluetooth", "audio"].indexOf(root.queuedMode)
                });
            } else {
                source = "";
            }
        }

        Binding {
            when: nexus.item !== null
            target: nexus.item
            property: "animatingContainer"
            value: nexus.opacity < 1
        }

        Connections {
            function onClose(): void {
                root.close();
            }

            target: nexus.item
        }
    }

    Behavior on implicitWidth {
        Anim {
            duration: root.animLength
            easing: root.animCurve
        }
    }

    Behavior on implicitHeight {
        enabled: root.offsetScale < 1

        Anim {
            duration: root.animLength
            easing: root.animCurve
        }
    }

    component Comp: Loader {
        id: comp

        property bool shouldBeActive

        active: false
        opacity: 0

        // Makes the loader load on the same frame shouldBeActive becomes true, which ensures size is set
        states: State {
            name: "active"
            when: comp.shouldBeActive

            PropertyChanges {
                comp.opacity: 1
                comp.active: true
            }
        }

        transitions: [
            Transition {
                from: ""
                to: "active"

                SequentialAnimation {
                    PropertyAction {
                        property: "active"
                    }
                    Anim {
                        type: Anim.DefaultEffects
                        property: "opacity"
                    }
                }
            },
            Transition {
                from: "active"
                to: ""

                SequentialAnimation {
                    Anim {
                        type: Anim.DefaultEffects
                        property: "opacity"
                    }
                    PropertyAction {
                        property: "active"
                    }
                }
            }
        ]
    }
}
