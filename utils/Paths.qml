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
    readonly property string wallsdir: Quickshell.env("CAELESTIA_WALLPAPERS_DIR") || absolutePath(GlobalConfig.paths.wallpaperDir)
    readonly property string recsdir: Quickshell.env("CAELESTIA_RECORDINGS_DIR") || absolutePath(GlobalConfig.paths.recordingDir)
    readonly property string libdir: Quickshell.env("CAELESTIA_LIB_DIR") || "/usr/lib/caelestia"

    readonly property string screenshotHelper: absolutePath(GlobalConfig.paths.screenshotHelper)
    readonly property string screenshotDir: absolutePath(GlobalConfig.paths.screenshotDir)
    readonly property string cheatsheetParser: (GlobalConfig.paths && GlobalConfig.paths.cheatsheetParser) ? absolutePath(GlobalConfig.paths.cheatsheetParser) : "/home/execorn/teamwork_projects/hyprland_cheat_sheet/parser/parse_keybinds.py"
    readonly property string eqControlScript: absolutePath(GlobalConfig.paths.eqControlScript)

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
        return toLocalFile(path.replace(/~|(\$({?)HOME(}?))+/, home));
    }

    function shortenHome(path: string): string {
        return path.replace(home, "~");
    }
}
