pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Caelestia.Config
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.modules.launcher.items
import qs.modules.launcher.services

StyledListView {
    id: root

    required property StyledTextField search
    required property DrawerVisibilities visibilities

    property var activeGroup: null
    property int savedGroupIndex: 0

    function isAppX11Only(app): bool {
        if (!app) return false;
        const id = (app.id || "").toLowerCase();
        const name = (app.name || "").toLowerCase();
        const exec = (app.execString || "").toLowerCase();
        
        const x11Ids = [
            "arandr", "lxappearance", "gpick", "picom", "compton", "feh", 
            "redshift", "rofi", "wpgtk", "xterm", "uxterm", "simplescreenrecorder",
            "nvidia-settings"
        ];
        
        for (var i = 0; i < x11Ids.length; i++) {
            if (id.indexOf(x11Ids[i]) !== -1 || name.indexOf(x11Ids[i]) !== -1 || exec.indexOf(x11Ids[i]) !== -1) {
                return true;
            }
        }
        
        if (id.startsWith("xfce") && (id.indexOf("settings") !== -1 || id.indexOf("display") !== -1 || id.indexOf("keyboard") !== -1 || id.indexOf("mouse") !== -1 || id.indexOf("color") !== -1 || id.indexOf("mime") !== -1)) {
            return true;
        }
        
        return false;
    }

    function getAppBrand(app): string {
        if (!app) return "";

        // 1. Check X11-only status first
        if (root.isAppX11Only(app)) {
            return "X11 Apps";
        }

        const name = (app.name || "").trim();
        const id = (app.id || "").trim();
        const idLower = id.toLowerCase();
        const nameLower = name.toLowerCase();

        // 2. Map known brands/keywords
        if (idLower.startsWith("libreoffice-") || nameLower.startsWith("libreoffice")) {
            return "LibreOffice";
        }
        if (idLower.startsWith("antigravity")) {
            return "Antigravity";
        }
        if (idLower.startsWith("xfce") || idLower.startsWith("org.xfce") || idLower.includes("catfish")) {
            return "Xfce Suite";
        }
        if (idLower.includes("bluetooth") || idLower.includes("blueman") || idLower.includes("bluez") || nameLower.includes("bluetooth")) {
            return "Bluetooth";
        }
        if (idLower.includes("avahi")) {
            return "Avahi";
        }
        if (idLower.includes("qt") || idLower.includes("assistant") || idLower.includes("designer") || idLower.includes("linguist") || idLower.includes("qdbus") || nameLower.startsWith("qt")) {
            return "Qt Tools";
        }
        if (idLower.startsWith("nvidia") || nameLower.includes("nvidia")) {
            return "NVIDIA";
        }

        // 3. Dynamic brand extraction using first word of the name
        const nameWords = name.split(/[\s-]+/);
        if (nameWords.length > 0) {
            const firstWord = nameWords[0];
            if (firstWord.length >= 3 && !/^(the|and|for|app|run|new|get|sys)$/i.test(firstWord)) {
                return firstWord.charAt(0).toUpperCase() + firstWord.slice(1);
            }
        }

        return "";
    }

    Connections {
        target: root.visibilities
        function onLauncherChanged(): void {
            if (!root.visibilities.launcher)
                root.activeGroup = null;
        }
    }

    Connections {
        target: search
        function onTextChanged(): void {
            root.activeGroup = null;
        }
    }

    readonly property var appsList: {
        const rawApps = Apps.search(search.text);
        if (search.text !== "") {
            return rawApps;
        }

        if (root.activeGroup !== null) {
            const backItem = {
                isBack: true,
                id: "back",
                name: qsTr("Go Back"),
                icon: "go-previous",
                comment: qsTr("Return to applications list"),
                genericName: "",
                apps: []
            };
            return [backItem].concat(root.activeGroup.apps);
        }

        const groupIcons = {
            "X11 Apps": "dialog-warning",
            "LibreOffice": "libreoffice-startcenter",
            "Antigravity": "antigravity",
            "Xfce Suite": "preferences-system",
            "Bluetooth": "preferences-system-bluetooth",
            "Avahi": "network-workgroup",
            "Qt Tools": "preferences-desktop-display"
        };

        const groupComments = {
            "X11 Apps": qsTr("Applications only supported on X11"),
            "LibreOffice": qsTr("Office suite applications"),
            "Antigravity": qsTr("Antigravity development environment"),
            "Xfce Suite": qsTr("Xfce settings and desktop utilities"),
            "Bluetooth": qsTr("Bluetooth settings and file sharing"),
            "Avahi": qsTr("Avahi zeroconf network services"),
            "Qt Tools": qsTr("Qt design and development utilities")
        };

        const groups = {};
        rawApps.forEach(function(app) {
            const brand = root.getAppBrand(app);
            if (brand) {
                if (!groups[brand]) {
                    groups[brand] = {
                        isGroup: true,
                        isX11: brand === "X11 Apps",
                        id: "group:" + brand.toLowerCase().replace(/\s+/g, "-"),
                        name: brand,
                        icon: groupIcons[brand] || "",
                        comment: groupComments[brand] || "",
                        genericName: "",
                        apps: []
                    };
                }
                groups[brand].apps.push(app);
            }
        });

        for (const brand in groups) {
            const g = groups[brand];
            if (g.apps.length > 1) {
                if (!g.icon && g.apps[0]) {
                    g.icon = g.apps[0].icon;
                }
                if (!g.comment) {
                    g.comment = qsTr("Group of %1 applications").arg(g.apps.length);
                }
            }
        }

        const result = [];
        const addedGroups = {};

        rawApps.forEach(function(app) {
            const brand = root.getAppBrand(app);
            if (brand && groups[brand].apps.length > 1) {
                if (!addedGroups[brand]) {
                    result.push(groups[brand]);
                    addedGroups[brand] = true;
                }
            } else {
                result.push(app);
            }
        });

        return result;
    }

    model: ScriptModel {
        id: model

        onValuesChanged: {
            if (root.activeGroup !== null) {
                root.currentIndex = 0;
            } else {
                root.currentIndex = root.savedGroupIndex;
                Qt.callLater(function() {
                    root.positionViewAtIndex(root.savedGroupIndex, ListView.Contain);
                });
            }
        }
    }

    spacing: Tokens.spacing.small
    orientation: Qt.Vertical
    implicitHeight: (Tokens.sizes.launcher.itemHeight + spacing) * Math.min(Config.launcher.maxShown, count) - spacing

    preferredHighlightBegin: 0
    preferredHighlightEnd: height
    highlightRangeMode: ListView.ApplyRange

    highlightFollowsCurrentItem: false
    highlight: StyledRect {
        radius: Tokens.rounding.large
        color: Colours.palette.m3onSurface
        opacity: 0.08

        y: root.currentItem?.y ?? 0
        implicitWidth: root.width
        implicitHeight: root.currentItem?.implicitHeight ?? 0

        Behavior on y {
            Anim {}
        }
    }

    state: {
        const text = search.text;
        const prefix = GlobalConfig.launcher.actionPrefix;
        if (text.startsWith(prefix)) {
            for (const action of ["calc", "scheme", "variant", "eq", "monitors", "gamemode"])
                if (text.startsWith(`${prefix}${action} `) || text === `${prefix}${action}`)
                    return action;

            return "actions";
        }

        return "apps";
    }

    onStateChanged: {
        if (state === "scheme" || state === "variant")
            Schemes.reload();
        else if (state === "eq")
            EQs.reload();
    }

    states: [
        State {
            name: "apps"

            PropertyChanges {
                model.values: root.appsList
                root.delegate: appItem
            }
        },
        State {
            name: "actions"

            PropertyChanges {
                model.values: Actions.query(search.text)
                root.delegate: actionItem
            }
        },
        State {
            name: "calc"

            PropertyChanges {
                model.values: [0]
                root.delegate: calcItem
            }
        },
        State {
            name: "scheme"

            PropertyChanges {
                model.values: Schemes.query(search.text)
                root.delegate: schemeItem
            }
        },
        State {
            name: "variant"

            PropertyChanges {
                model.values: M3Variants.query(search.text)
                root.delegate: variantItem
            }
        },
        State {
            name: "eq"

            PropertyChanges {
                model.values: (EQs.presetsList, EQs.query(search.text))
                root.delegate: actionItem
            }
        },
        State {
            name: "monitors"

            PropertyChanges {
                model.values: Monitors.query(search.text)
                root.delegate: actionItem
            }
        },
        State {
            name: "gamemode"

            PropertyChanges {
                model.values: GameModeLauncher.query(search.text)
                root.delegate: actionItem
            }
        }
    ]

    transitions: Transition {
        SequentialAnimation {
            ParallelAnimation {
                Anim {
                    target: root
                    property: "opacity"
                    from: 1
                    to: 0
                    duration: Tokens.anim.durations.small
                    easing: Tokens.anim.standardAccel
                }
                Anim {
                    target: root
                    property: "scale"
                    from: 1
                    to: 0.9
                    duration: Tokens.anim.durations.small
                    easing: Tokens.anim.standardAccel
                }
            }
            PropertyAction {
                targets: [model, root]
                properties: "values,delegate"
            }
            ParallelAnimation {
                Anim {
                    target: root
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: Tokens.anim.durations.small
                    easing: Tokens.anim.standardDecel
                }
                Anim {
                    target: root
                    property: "scale"
                    from: 0.9
                    to: 1
                    duration: Tokens.anim.durations.small
                    easing: Tokens.anim.standardDecel
                }
            }
            PropertyAction {
                targets: [root.add, root.remove]
                property: "enabled"
                value: true
            }
        }
    }

    StyledScrollBar.vertical: StyledScrollBar {
        flickable: root
    }

    add: Transition {
        enabled: !root.state

        Anim {
            type: Anim.DefaultEffects
            property: "opacity"
            from: 0
            to: 1
        }
    }

    remove: Transition {
        enabled: !root.state

        Anim {
            type: Anim.DefaultEffects
            property: "opacity"
            from: 1
            to: 0
        }
    }

    move: Transition {
        Anim {
            property: "y"
        }
        Anim {
            type: Anim.DefaultEffects
            property: "opacity"
            to: 1
        }
    }

    addDisplaced: Transition {
        Anim {
            property: "y"
            type: Anim.StandardSmall
        }
        Anim {
            type: Anim.DefaultEffects
            property: "opacity"
            to: 1
        }
    }

    displaced: Transition {
        Anim {
            property: "y"
        }
        Anim {
            type: Anim.DefaultEffects
            property: "opacity"
            to: 1
        }
    }

    Component {
        id: appItem

        AppItem {
            visibilities: root.visibilities
            list: root
        }
    }

    Component {
        id: actionItem

        ActionItem {
            list: root
        }
    }

    Component {
        id: calcItem

        CalcItem {
            list: root
        }
    }

    Component {
        id: schemeItem

        SchemeItem {
            list: root
        }
    }

    Component {
        id: variantItem

        VariantItem {
            list: root
        }
    }
}
