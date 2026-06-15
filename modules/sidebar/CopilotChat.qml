pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.utils

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.medium

        // Header: Title and History Sweep Button
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            StyledText {
                text: qsTr("AI Copilot")
                color: Colours.palette.m3onSurface
                font: Tokens.font.title.builders.medium.weight(Font.Bold).build()
            }

            Item {
                Layout.fillWidth: true
            }

            IconButton {
                icon: "delete_sweep"
                onClicked: Copilot.clearChat()
            }
        }

        // Message List & Status
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: chatListView
                anchors.fill: parent
                model: Copilot.chatHistory
                spacing: Tokens.spacing.medium
                clip: true

                onCountChanged: Qt.callLater(() => { chatListView.positionViewAtEnd(); })

                StyledScrollBar.vertical: StyledScrollBar {
                    flickable: chatListView
                }

                delegate: Item {
                    id: delegateItem
                    width: chatListView.width
                    height: bubbleRect.height + Tokens.spacing.medium

                    readonly property bool isUser: model.role === "user"

                    StyledRect {
                        id: bubbleRect

                        readonly property real maxTextWidth: delegateItem.width * 0.75

                        width: {
                            const contentW = textItem.implicitWidth + Tokens.padding.medium * 2;
                            return contentW > maxTextWidth ? maxTextWidth : contentW;
                        }
                        height: textItem.implicitHeight + Tokens.padding.medium * 2

                        anchors.right: isUser ? delegateItem.right : undefined
                        anchors.left: isUser ? undefined : delegateItem.left

                        radius: Tokens.rounding.medium
                        color: isUser ? Colours.tPalette.m3primaryContainer : Colours.tPalette.m3surfaceContainerHigh

                        StyledText {
                            id: textItem
                            x: Tokens.padding.medium
                            y: Tokens.padding.medium
                            width: bubbleRect.width - Tokens.padding.medium * 2
                            wrapMode: Text.WordWrap
                            textFormat: Text.AutoText
                            color: isUser ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface
                            text: model.message
                        }
                    }
                }
            }
        }

        // Loading and Error Status Section
        RowLayout {
            id: statusArea
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium
            visible: Copilot.loading || Copilot.lastError !== ""

            LoadingIndicator {
                id: spinner
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                visible: Copilot.loading
                animated: Copilot.loading
            }

            StyledText {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Copilot.lastError !== "" ? Colours.palette.m3error : Colours.palette.m3outline
                font: Tokens.font.body.small
                text: {
                    if (Copilot.loading) {
                        return qsTr("Copilot is thinking...");
                    } else if (Copilot.lastError !== "") {
                        return Copilot.lastError;
                    }
                    return "";
                }
            }
        }

        // Input Area Row
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            StyledInputField {
                id: messageInput
                Layout.fillWidth: true
                placeholderText: qsTr("Type a message...")
                
                onEditingFinished: {
                    if (messageInput.text.trim()) {
                        Copilot.sendMessage(messageInput.text);
                        messageInput.clear();
                    }
                }
            }

            IconButton {
                icon: "send"
                onClicked: {
                    if (messageInput.text.trim()) {
                        Copilot.sendMessage(messageInput.text);
                        messageInput.clear();
                    }
                }
            }
        }
    }
}
