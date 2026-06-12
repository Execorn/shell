pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: qsTr("Colours")
    isSubPage: true

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            text: qsTr("General Settings")
            first: true
        }

        // 1. Dark Mode Toggle
        ToggleRow {
            Layout.fillWidth: true
            text: qsTr("Dark Mode")
            subtext: qsTr("Toggle light or dark theme mode")
            checked: GlobalConfig.theme.darkMode
            first: true
            last: true
            onToggled: {
                GlobalConfig.theme.darkMode = checked;
                GlobalConfig.theme.mode = checked ? "dark" : "light";
                Colours.setMode(checked ? "dark" : "light");
            }
        }

        SectionHeader {
            text: qsTr("Color Source")
        }

        // 2. Color Source Dropdown
        SelectRow {
            Layout.fillWidth: true
            label: qsTr("Source Type")
            subtext: qsTr("Select how the primary accent color is derived")
            first: true
            last: true
            fallbackText: GlobalConfig.theme.colorSource === "dynamic" ? qsTr("Wallpaper Extracted") : qsTr("Static Accent")
            
            menuItems: [
                MenuItem {
                    text: qsTr("Wallpaper Extracted")
                    onClicked: {
                        GlobalConfig.theme.colorSource = "dynamic";
                        GlobalConfig.theme.source = "wallpaper";
                        GlobalConfig.theme.accentColor = "wallpaper";
                        triggerSchemeUpdate();
                    }
                },
                MenuItem {
                    text: qsTr("Static Accent")
                    onClicked: {
                        GlobalConfig.theme.colorSource = "static";
                        GlobalConfig.theme.source = "custom";
                        applyCustomAccent();
                    }
                }
            ]
        }

        SectionHeader {
            text: qsTr("Theme Customizer")
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            // 3. Flavor Selection
            SelectRow {
                Layout.fillWidth: true
                label: qsTr("Material 3 Flavor")
                subtext: qsTr("The variant algorithm used to compute secondary and tertiary tones")
                fallbackText: getFlavorDisplayName(GlobalConfig.theme.flavor)
                first: true
                last: GlobalConfig.theme.colorSource === "dynamic"
                
                menuItems: [
                    MenuItem { text: qsTr("Tonal Spot"); onClicked: updateFlavor("tonal-spot") },
                    MenuItem { text: qsTr("Vibrant"); onClicked: updateFlavor("vibrant") },
                    MenuItem { text: qsTr("Expressive"); onClicked: updateFlavor("expressive") },
                    MenuItem { text: qsTr("Monochrome"); onClicked: updateFlavor("monochrome") }
                ]
            }

            // 4. Custom Accent HSL Sliders (Visible only when static mode is active)
            ColumnLayout {
                Layout.fillWidth: true
                visible: GlobalConfig.theme.colorSource === "static"
                spacing: 0

                SliderRow {
                    Layout.fillWidth: true
                    label: qsTr("Hue")
                    valueLabel: Math.round(hueSlider.value * 360) + "°"
                    value: getHslPart(0) / 360
                    id: hueSlider
                    onMoved: val => updateHslValue(Math.round(val * 360), null, null)
                }

                SliderRow {
                    Layout.fillWidth: true
                    label: qsTr("Saturation")
                    valueLabel: Math.round(satSlider.value * 100) + "%"
                    value: getHslPart(1) / 100
                    id: satSlider
                    onMoved: val => updateHslValue(null, Math.round(val * 100), null)
                }

                SliderRow {
                    Layout.fillWidth: true
                    label: qsTr("Lightness")
                    valueLabel: Math.round(lightSlider.value * 100) + "%"
                    value: getHslPart(2) / 100
                    id: lightSlider
                    last: true
                    onMoved: val => updateHslValue(null, null, Math.round(val * 100))
                }
            }
        }
    }

    // Process to run caelestia scheme set
    Process {
        id: schemeProcess

        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0) {
                console.warn("caelestia scheme set command failed with exit code: " + exitCode);
            }
        }
    }

    // FileView to check if the wallpaper exists on the filesystem
    FileView {
        id: wallpaperChecker
        path: Wallpapers.current || ""
        watchChanges: true
        printErrors: false
        
        onLoadFailed: {
            handleWallpaperMissing();
        }
    }

    Connections {
        target: Colours.palette
        ignoreUnknownSignals: true
        function onM3primaryChanged() {
            if (GlobalConfig.theme.colorSource === "dynamic") {
                GlobalConfig.theme.extractedColors.primary = Colours.palette.m3primary;
            }
        }
        function onM3secondaryChanged() {
            if (GlobalConfig.theme.colorSource === "dynamic") {
                GlobalConfig.theme.extractedColors.secondary = Colours.palette.m3secondary;
            }
        }
        function onM3tertiaryChanged() {
            if (GlobalConfig.theme.colorSource === "dynamic") {
                GlobalConfig.theme.extractedColors.tertiary = Colours.palette.m3tertiary;
            }
        }
    }

    Connections {
        target: GlobalConfig.theme
        ignoreUnknownSignals: true
        function onCustomAccentHSLChanged() {
            if (!validateHslString(GlobalConfig.theme.customAccentHSL)) {
                GlobalConfig.theme.customAccentHSL = "220,100,50";
            }
        }
        function onFlavorChanged() {
            let flavor = GlobalConfig.theme.flavor;
            const validFlavors = ["tonal-spot", "vibrant", "expressive", "monochrome"];
            if (!validFlavors.includes(flavor)) {
                GlobalConfig.theme.flavor = "tonal-spot";
            }
        }
    }

    Component.onCompleted: {
        // Run initial sanity check on load
        if (!validateHslString(GlobalConfig.theme.customAccentHSL)) {
            GlobalConfig.theme.customAccentHSL = "220,100,50";
        }
        let flavor = GlobalConfig.theme.flavor;
        const validFlavors = ["tonal-spot", "vibrant", "expressive", "monochrome"];
        if (!validFlavors.includes(flavor)) {
            GlobalConfig.theme.flavor = "tonal-spot";
        }
    }

    function handleWallpaperMissing() {
        if (GlobalConfig.theme.colorSource === "dynamic") {
            GlobalConfig.theme.colorSource = "static";
            GlobalConfig.theme.source = "custom";
            GlobalConfig.theme.accentColor = "#6750A4";
            applyCustomAccent();
        }
    }

    // Helper functions for HSL parsing and conversion
    function getHslPart(index) {
        let hslStr = GlobalConfig.theme.customAccentHSL || "220,100,50";
        let parts = hslStr.split(",");
        if (parts.length !== 3) {
            parts = ["220", "100", "50"];
        }
        let val = parseFloat(parts[index]);
        if (isNaN(val)) {
            return index === 0 ? 220 : (index === 1 ? 100 : 50);
        }
        if (index === 0) {
            return Math.max(0, Math.min(360, val));
        } else {
            return Math.max(0, Math.min(100, val));
        }
    }

    function validateHslString(hslStr) {
        if (!hslStr) return false;
        let parts = hslStr.split(",");
        if (parts.length !== 3) return false;
        let h = parseFloat(parts[0]);
        let s = parseFloat(parts[1]);
        let l = parseFloat(parts[2]);
        if (isNaN(h) || isNaN(s) || isNaN(l)) return false;
        if (h < 0 || h > 360) return false;
        if (s < 0 || s > 100) return false;
        if (l < 0 || l > 100) return false;
        return true;
    }

    function updateHslValue(h, s, l) {
        let parts = (GlobalConfig.theme.customAccentHSL || "220,100,50").split(",");
        if (parts.length !== 3) {
            parts = ["220", "100", "50"];
        }
        let currentH = h !== null ? h : parseFloat(parts[0]);
        let currentS = s !== null ? s : parseFloat(parts[1]);
        let currentL = l !== null ? l : parseFloat(parts[2]);
        
        let newHslStr = currentH + "," + currentS + "," + currentL;
        GlobalConfig.theme.customAccentHSL = newHslStr;
        applyCustomAccent();
    }

    function updateFlavor(flavorName) {
        const validFlavors = ["tonal-spot", "vibrant", "expressive", "monochrome"];
        let validated = validFlavors.includes(flavorName) ? flavorName : "tonal-spot";
        GlobalConfig.theme.flavor = validated;
        triggerSchemeUpdate();
    }

    function applyCustomAccent() {
        let hslStr = GlobalConfig.theme.customAccentHSL || "220,100,50";
        let parts = hslStr.split(",");
        if (parts.length !== 3) {
            parts = ["220", "100", "50"];
        }
        
        let h = parseFloat(parts[0]);
        let s = parseFloat(parts[1]);
        let l = parseFloat(parts[2]);
        let validatedColor;
        if (isNaN(h) || isNaN(s) || isNaN(l) || h < 0 || h > 360 || s < 0 || s > 100 || l < 0 || l > 100) {
            validatedColor = "#6750A4"; // Fallback for malformed values
        } else {
            validatedColor = hslToHex(h, s, l);
        }
        
        GlobalConfig.theme.accentColor = validatedColor;
        triggerSchemeUpdate();
    }

    function triggerSchemeUpdate() {
        let flavor = GlobalConfig.theme.flavor || "tonal-spot";
        const validFlavors = ["tonal-spot", "vibrant", "expressive", "monochrome"];
        if (!validFlavors.includes(flavor)) {
            flavor = "tonal-spot";
        }

        let cmd = [];
        if (GlobalConfig.theme.colorSource === "static") {
            let hslParts = (GlobalConfig.theme.customAccentHSL || "220,100,50").split(",");
            if (hslParts.length !== 3) {
                hslParts = ["220", "100", "50"];
            }
            let colorArg = "hsl(" + hslParts[0] + "," + hslParts[1] + "%," + hslParts[2] + "%)";
            cmd = ["caelestia", "scheme", "set", flavor, colorArg];
        } else {
            // Dynamic mode
            let wallPath = Wallpapers.current || "";
            if (wallPath === "") {
                handleWallpaperMissing();
                return;
            }
            cmd = ["caelestia", "scheme", "set", flavor, wallPath];
        }

        if (schemeProcess.running) {
            schemeProcess.running = false;
        }
        schemeProcess.command = cmd;
        schemeProcess.running = true;
    }

    function getFlavorDisplayName(f) {
        if (f === "tonal-spot") return qsTr("Tonal Spot");
        if (f === "vibrant") return qsTr("Vibrant");
        if (f === "expressive") return qsTr("Expressive");
        if (f === "monochrome") return qsTr("Monochrome");
        return qsTr("Tonal Spot");
    }

    // JS helper to convert HSL to Hex
    function hslToHex(h, s, l) {
        h = parseFloat(h) / 360.0;
        s = parseFloat(s) / 100.0;
        l = parseFloat(l) / 100.0;
        
        let r, g, b;
        if (s === 0) {
            r = g = b = l;
        } else {
            function hue2rgb(p, q, t) {
                if (t < 0) t += 1;
                if (t > 1) t -= 1;
                if (t < 1/6) return p + (q - p) * 6 * t;
                if (t < 1/2) return q;
                if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                return p;
            }
            let q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            let p = 2 * l - q;
            r = hue2rgb(p, q, h + 1/3);
            g = hue2rgb(p, q, h);
            b = hue2rgb(p, q, h - 1/3);
        }
        
        r = Math.max(0, Math.min(255, Math.round(r * 255)));
        g = Math.max(0, Math.min(255, Math.round(g * 255)));
        b = Math.max(0, Math.min(255, Math.round(b * 255)));
        
        let rHex = r.toString(16).padStart(2, '0');
        let gHex = g.toString(16).padStart(2, '0');
        let bHex = b.toString(16).padStart(2, '0');
        
        return "#" + rHex + gHex + bHex;
    }
}
