pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Pipewire
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

Item {
    id: root

    required property PopoutState popouts

    implicitWidth: layout.implicitWidth + Tokens.padding.medium * 2
    implicitHeight: layout.implicitHeight + Tokens.padding.medium * 2

    ButtonGroup {
        id: sinks
    }

    ButtonGroup {
        id: sources
    }

    ColumnLayout {
        id: layout

        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: Tokens.spacing.medium

        StyledText {
            text: qsTr("Output device")
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
        }

        Repeater {
            model: Audio.physicalSinks

            StyledRadioButton {
                id: control

                required property PwNode modelData

                ButtonGroup.group: sinks
                checked: Audio.activePhysicalSinkId === modelData.id
                onClicked: if (modelData) Audio.setAudioSink(modelData)
                text: modelData ? modelData.description : ""
            }
        }

        StyledText {
            Layout.topMargin: Tokens.spacing.medium
            text: qsTr("Input device")
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
        }

        Repeater {
            model: Audio.physicalSources

            StyledRadioButton {
                required property PwNode modelData

                ButtonGroup.group: sources
                checked: modelData ? Audio.activePhysicalSourceId === modelData.id : false
                onClicked: if (modelData) Audio.setAudioSource(modelData)
                text: modelData ? modelData.description : ""
            }
        }

        StyledText {
            Layout.topMargin: Tokens.spacing.medium
            text: qsTr("Volume (%1)").arg(Audio.muted ? qsTr("Muted") : `${Math.round(Audio.volume * 100)}%`)
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
        }

        CustomMouseArea {
            Layout.fillWidth: true
            implicitHeight: Tokens.padding.medium * 3

            onWheel: event => {
                if (event.angleDelta.y > 0)
                    Audio.incrementVolume();
                else if (event.angleDelta.y < 0)
                    Audio.decrementVolume();
            }

            StyledSlider {
                anchors.left: parent.left
                anchors.right: parent.right
                implicitHeight: parent.implicitHeight

                value: Audio.volume
                onInteraction: value => Audio.setVolume(value)
            }
        }

        StyledText {
            Layout.topMargin: Tokens.spacing.medium
            text: qsTr("Applications")
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
            visible: Audio.streams.length > 0
        }

        Repeater {
            model: Audio.streams
            visible: Audio.streams.length > 0

            ColumnLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: Tokens.spacing.small

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.medium

                    StyledText {
                        Layout.fillWidth: true
                        text: Audio.getStreamName(modelData)
                        font: Tokens.font.body.builders.small.build()
                        elide: Text.ElideRight
                    }

                    IconButton {
                        icon: Audio.getStreamMuted(modelData) ? "volume_off" : "volume_up"
                        onClicked: Audio.setStreamMuted(modelData, !Audio.getStreamMuted(modelData))
                    }
                }

                CustomMouseArea {
                    Layout.fillWidth: true
                    implicitHeight: Tokens.padding.medium * 3

                    StyledSlider {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        implicitHeight: parent.implicitHeight

                        value: Audio.getStreamVolume(modelData)
                        onInteraction: value => Audio.setStreamVolume(modelData, value)
                    }
                }
            }
        }

        IconTextButton {
            Layout.fillWidth: true
            Layout.topMargin: Tokens.spacing.medium
            inactiveColour: Colours.palette.m3primaryContainer
            inactiveOnColour: Colours.palette.m3onPrimaryContainer
            verticalPadding: Tokens.padding.extraSmall
            text: qsTr("Open settings")
            icon: "settings"

            onClicked: root.popouts.detachRequested("audio")
        }
    }
}
