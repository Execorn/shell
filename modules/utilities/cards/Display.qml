pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

StyledRect {
    id: root

    readonly property real nonAnimHeight: layout.implicitHeight + (ScreenTemp.active ? sliderLoader.implicitHeight + sliderLoader.anchors.topMargin : 0) + Tokens.padding.extraLargeIncreased

    Layout.fillWidth: true
    implicitHeight: nonAnimHeight

    radius: Tokens.rounding.large
    color: Colours.tPalette.m3surfaceContainer
    clip: true

    RowLayout {
        id: layout

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        StyledRect {
            implicitWidth: implicitHeight
            implicitHeight: icon.implicitHeight + Tokens.padding.large

            radius: Tokens.rounding.full
            color: ScreenTemp.active ? Colours.palette.m3secondary : Colours.palette.m3secondaryContainer

            MaterialIcon {
                id: icon

                anchors.centerIn: parent
                text: "wb_sunny"
                color: ScreenTemp.active ? Colours.palette.m3onSecondary : Colours.palette.m3onSecondaryContainer
                fontStyle: Tokens.font.icon.large
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            StyledText {
                Layout.fillWidth: true
                text: qsTr("Night Light")
                font: Tokens.font.body.medium
                elide: Text.ElideRight
            }

            StyledText {
                Layout.fillWidth: true
                text: ScreenTemp.active ? qsTr("Screen temp: %1K").arg(ScreenTemp.temperature) : qsTr("Normal screen temperature")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
                elide: Text.ElideRight
            }
        }

        StyledSwitch {
            checked: ScreenTemp.active
            onToggled: ScreenTemp.active = checked
        }
    }

    Loader {
        id: sliderLoader

        asynchronous: true
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: Tokens.spacing.large
        anchors.bottomMargin: ScreenTemp.active ? Tokens.padding.large : -implicitHeight
        anchors.leftMargin: Tokens.padding.large
        anchors.rightMargin: Tokens.padding.large

        opacity: ScreenTemp.active ? 1 : 0
        scale: ScreenTemp.active ? 1 : 0.5

        Component.onCompleted: active = Qt.binding(() => opacity > 0)

        sourceComponent: StyledSlider {
            value: ScreenTemp.temperature
            from: 2500
            to: 6500
            onInteraction: v => ScreenTemp.temperature = Math.round(from + v * (to - from))
        }

        Behavior on anchors.bottomMargin {
            Anim {}
        }

        Behavior on opacity {
            Anim {
                type: Anim.StandardSmall
            }
        }

        Behavior on scale {
            Anim {}
        }
    }

    Behavior on implicitHeight {
        Anim {}
    }
}
