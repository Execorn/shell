pragma Singleton

import QtQuick
import Quickshell
import Caelestia
import Caelestia.Config

Singleton {
    id: root

    readonly property string home: Quickshell.env("HOME")
    readonly property string pictures: Quickshell.env("XDG_PICTURES_DIR") || `${home}/Pictures`
    readonly property string videos: Quickshell.env("XDG_VIDEOS_DIR") || `${home}/Videos`

    readonly property string data: `${Quickshell.env("XDG_DATA_HOME") || `${home}/.local/share`}/caelestia`
    readonly property string state: `${Quickshell.env("XDG_STATE_HOME") || `${home}/.local/state`}/caelestia`
    readonly property string cache: `${Quickshell.env("XDG_CACHE_HOME") || `${home}/.cache`}/caelestia`
    readonly property string config: `${Quickshell.env("XDG_CONFIG_HOME") || `${home}/.config`}/caelestia`

    readonly property string imagecache: `${cache}/imagecache`
    readonly property string notifimagecache: `${imagecache}/notifs`
    readonly property string wallsdir: {
        const envVal = Quickshell.env("CAELESTIA_WALLPAPERS_DIR");
        if (envVal && envVal.trim() !== "") return envVal;
        const configVal = GlobalConfig.paths && GlobalConfig.paths.wallpaperDir;
        return (configVal && configVal.trim() !== "") ? absolutePath(configVal) : pictures + "/Wallpapers";
    }
    readonly property string recsdir: {
        const envVal = Quickshell.env("CAELESTIA_RECORDINGS_DIR");
        if (envVal && envVal.trim() !== "") return envVal;
        const configVal = GlobalConfig.paths && GlobalConfig.paths.recordingDir;
        return (configVal && configVal.trim() !== "") ? absolutePath(configVal) : videos + "/Recordings";
    }
    readonly property string libdir: Quickshell.env("CAELESTIA_LIB_DIR") || "/usr/lib/caelestia"

    readonly property string screenshotHelper: {
        const configVal = GlobalConfig.paths && GlobalConfig.paths.screenshotHelper;
        return (configVal && configVal.trim() !== "") ? absolutePath(configVal) : "/home/execorn/scripts/screenshot_helper.sh";
    }
    readonly property string screenshotDir: {
        const configVal = GlobalConfig.paths && GlobalConfig.paths.screenshotDir;
        return (configVal && configVal.trim() !== "") ? absolutePath(configVal) : pictures + "/Screenshots";
    }
    readonly property string cheatsheetParser: {
        const configVal = GlobalConfig.paths && GlobalConfig.paths.cheatsheetParser;
        return (configVal && configVal.trim() !== "") ? absolutePath(configVal) : "/home/execorn/programming/projects/hyprland_cheat_sheet/parser/parse_keybinds.py";
    }
    readonly property string eqControlScript: {
        const configVal = GlobalConfig.paths && GlobalConfig.paths.eqControlScript;
        return (configVal && configVal.trim() !== "") ? absolutePath(configVal) : "/home/execorn/scripts/eq-control.py";
    }

    function toLocalFile(path: url): string {
        path = Qt.resolvedUrl(path);
        if (!path.toString()) return "";
        
        var s = path.toString();
        if (s.startsWith("qs:")) {
            s = "file:" + s.substring(3);
            path = Qt.resolvedUrl(s);
        }
        
        if (typeof CUtils !== "undefined" && CUtils !== null) {
            return CUtils.toLocalFile(path);
        }
        if (s.startsWith("file://")) {
            return s.substring(7);
        }
        return s;
    }

    function absolutePath(path: string): string {
        if (!path || path.trim() === "") return "";
        return toLocalFile(path.replace(/~|(\$({?)HOME(}?))+/, home));
    }

    function shortenHome(path: string): string {
        return path.replace(home, "~");
    }
}
