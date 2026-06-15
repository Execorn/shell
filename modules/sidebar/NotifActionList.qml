pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import Caelestia.Config
import qs.components
import qs.components.containers
import qs.components.effects
import qs.services

Item {
    id: root

    required property NotifData notif
    property bool showMuteOptions: false

    Layout.fillWidth: true
    implicitHeight: flickable.contentHeight

    layer.enabled: true
    layer.smooth: true
    layer.effect: Mask {
        maskSource: gradientMask
    }

    Item {
        id: gradientMask

        anchors.fill: parent
        layer.enabled: true
        visible: false

        Rectangle {
            anchors.fill: parent

            gradient: Gradient {
                orientation: Gradient.Horizontal

                GradientStop {
                    position: 0
                    color: Qt.rgba(0, 0, 0, 0)
                }
                GradientStop {
                    position: 0.1
                    color: Qt.rgba(0, 0, 0, 1)
                }
                GradientStop {
                    position: 0.9
                    color: Qt.rgba(0, 0, 0, 1)
                }
                GradientStop {
                    position: 1
                    color: Qt.rgba(0, 0, 0, 0)
                }
            }
        }

        Rectangle {
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.left: parent.left

            implicitWidth: parent.width / 2
            opacity: flickable.contentX > 0 ? 0 : 1

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }
        }

        Rectangle {
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.right: parent.right

            implicitWidth: parent.width / 2
            opacity: flickable.contentX < flickable.contentWidth - parent.width ? 0 : 1

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }
        }
    }

    StyledFlickable {
        id: flickable

        anchors.fill: parent
        contentWidth: Math.max(width, actionList.implicitWidth)
        contentHeight: actionList.implicitHeight

        RowLayout {
            id: actionList

            anchors.fill: parent
            spacing: Tokens.spacing.small

            Repeater {
                model: {
                    const _dummy = Notifs.mutedAppsJson;

                    if (showMuteOptions) {
                        return [
                            { isBack: true },
                            { isMuteOption: true, hours: 1, text: qsTr("Mute 1h") },
                            { isMuteOption: true, hours: 24, text: qsTr("Mute 24h") },
                            { isMuteOption: true, hours: 0, text: qsTr("Mute Forever") }
                        ];
                    }

                    const isMuted = Notifs.isAppMuted(root.notif.appName);
                    const baseModel = [
                        { isClose: true },
                        ...(root.notif?.actions ?? []),
                        { isCopy: true }
                    ];

                    if (root.notif.appName) {
                        if (isMuted) {
                            baseModel.push({ isUnmute: true });
                        } else {
                            baseModel.push({ isMuteToggle: true });
                        }
                    }

                    return baseModel;
                }

                StyledRect {
                    id: action

                    required property var modelData

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    implicitWidth: actionInner.implicitWidth + Tokens.padding.medium * 2
                    implicitHeight: actionInner.implicitHeight + Tokens.padding.small

                    Layout.preferredWidth: implicitWidth + (actionStateLayer.pressed ? Tokens.padding.large : 0)
                    radius: actionStateLayer.pressed ? Tokens.rounding.medium / 2 : Tokens.rounding.medium
                    color: Colours.layer(Colours.palette.m3surfaceContainerHighest, 4)

                    Timer {
                        id: copyTimer

                        interval: 3000
                        onTriggered: actionInner.item.text = "content_copy"
                    }

                    StateLayer {
                        id: actionStateLayer

                        onClicked: {
                            if (action.modelData.isClose) {
                                root.notif.close();
                            } else if (action.modelData.isCopy) {
                                Quickshell.clipboardText = root.notif.body;
                                actionInner.item.text = "inventory";
                                copyTimer.start();
                            } else if (action.modelData.isMuteToggle) {
                                root.showMuteOptions = true;
                            } else if (action.modelData.isUnmute) {
                                Notifs.unmuteApp(root.notif.appName);
                            } else if (action.modelData.isBack) {
                                root.showMuteOptions = false;
                            } else if (action.modelData.isMuteOption) {
                                Notifs.muteApp(root.notif.appName, action.modelData.hours);
                                root.showMuteOptions = false;
                            } else if (action.modelData.invoke) {
                                action.modelData.invoke();
                            } else if (!root.notif.resident) {
                                root.notif.close();
                            }
                        }
                    }

                    Loader {
                        id: actionInner

                        anchors.centerIn: parent
                        sourceComponent: {
                            if (action.modelData.isClose || action.modelData.isCopy || action.modelData.isMuteToggle || action.modelData.isUnmute || action.modelData.isBack)
                                return iconBtn;
                            if (action.modelData.isMuteOption)
                                return textComp;
                            return root.notif?.hasActionIcons ? iconComp : textComp;
                        }
                    }

                    Component {
                        id: iconBtn

                        MaterialIcon {
                            animate: action.modelData.isCopy ?? false
                            text: {
                                if (action.modelData.isCopy) return "content_copy";
                                if (action.modelData.isClose) return "close";
                                if (action.modelData.isMuteToggle) return "notifications_paused";
                                if (action.modelData.isUnmute) return "notifications_active";
                                if (action.modelData.isBack) return "arrow_back";
                                return "";
                            }
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }

                    Component {
                        id: iconComp

                        IconImage {
                            asynchronous: true
                            source: Quickshell.iconPath(action.modelData.identifier)
                        }
                    }

                    Component {
                        id: textComp

                        StyledText {
                            text: action.modelData.text
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }

                    Behavior on Layout.preferredWidth {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }

                    Behavior on radius {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }
                }
            }
        }
    }
}
