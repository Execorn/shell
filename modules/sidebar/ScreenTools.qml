pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Caelestia.Config
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.utils
import "../utilities/cards"

Item {
    id: root

    required property var props
    required property DrawerVisibilities visibilities

    anchors.fill: parent
    anchors.margins: Tokens.padding.medium

    StyledFlickable {
        id: view

        anchors.fill: parent
        flickableDirection: Flickable.VerticalFlick
        contentWidth: width
        contentHeight: contentLayout.implicitHeight

        StyledScrollBar.vertical: StyledScrollBar {
            flickable: view
        }

        ColumnLayout {
            id: contentLayout

            width: parent.width
            spacing: Tokens.spacing.medium

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.medium

                StyledText {
                    text: qsTr("Screen Tools")
                    color: Colours.palette.m3onSurface
                    font: Tokens.font.title.builders.medium.weight(Font.Bold).build()
                }
            }

            SectionHeader {
                title: qsTr("Screen Recording")
            }

            Record {
                props: root.props
                visibilities: root.visibilities
            }

            SectionHeader {
                title: qsTr("Text Extraction")
            }

            IconTextButton {
                Layout.fillWidth: true
                icon: "crop_free"
                text: qsTr("Capture Screen (OCR)")
                onClicked: Ocr.startOcr()
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.medium
                visible: Ocr.running

                LoadingIndicator {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    visible: Ocr.running
                    animated: Ocr.running
                }

                StyledText {
                    Layout.fillWidth: true
                    font: Tokens.font.body.small
                    color: Colours.palette.m3outline
                    text: qsTr("OCR Capturing / Extracting...")
                }
            }

            StyledRect {
                Layout.fillWidth: true
                implicitHeight: ocrTextDisplay.implicitHeight + Tokens.padding.medium * 2
                radius: Tokens.rounding.medium
                color: Colours.layer(Colours.palette.m3surfaceContainer, 1)

                StyledText {
                    id: ocrTextDisplay
                    x: Tokens.padding.medium
                    y: Tokens.padding.medium
                    width: parent.width - Tokens.padding.medium * 2
                    wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                    color: Ocr.lastError ? Colours.palette.m3error : (Ocr.ocrText ? Colours.palette.m3onSurface : Colours.palette.m3outline)
                    text: Ocr.lastError ? Ocr.lastError : (Ocr.ocrText ? Ocr.ocrText : qsTr("No text captured. Click above to select screen area."))
                    font: Tokens.font.body.small
                }
            }
        }
    }
}
