pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia.Config
import Caelestia.Models
import qs.services
import qs.utils

Searcher {
    id: root

    readonly property string currentNamePath: `${Paths.state}/wallpaper/path.txt`
    readonly property list<string> smartArg: GlobalConfig.services.smartScheme ? [] : ["--no-smart"]
    readonly property string fallback: Quickshell.shellPath("assets/wallpaper.webp")

    property bool showPreview: false
    readonly property string current: showPreview ? previewPath : actualCurrent
    property string previewPath
    property string actualCurrent
    property bool previewColourLock
    property bool pendingPreviewClear

    readonly property string wwalConfigPath: `${Paths.config}/wwal.json`
    property bool randomOnBoot: false
    property bool slideshowEnabled: false
    property int slideshowIntervalSec: 300
    property string slideshowEffect: "random"
    property bool initialBootHandled: false
    property bool configLoaded: false
    property bool pathLoaded: false
    property bool randomPending: false

    function getCategoryFor(w: FileSystemEntry): string {
        let category = w.parentDir.slice(Paths.wallsdir.length + 1);
        if (category.includes("/"))
            category = category.slice(0, category.indexOf("/"));
        return category;
    }

    function setRandom(): void {
        const entries = root.list;
        const effect = root.slideshowEffect || "random";
        if (entries && entries.length > 0) {
            let available = entries;
            if (entries.length > 1 && root.actualCurrent) {
                available = entries.filter(e => e.path !== root.actualCurrent);
                if (available.length === 0)
                    available = entries;
            }
            const idx = Math.floor(Math.random() * available.length);
            const path = available[idx].path;
            setWallpaper(path, effect);
        } else {
            root.randomPending = true;
            Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "random", effect]);
        }
    }

    function toggleRandomOnBoot(): void {
        root.randomOnBoot = !root.randomOnBoot;
        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "toggle-random-boot"]);
        Toaster.toast(
            qsTr("Wallpaper on Boot"),
            root.randomOnBoot ? qsTr("Random wallpaper on boot: Enabled") : qsTr("Random wallpaper on boot: Disabled (last saved)"),
            "restart_alt"
        );
    }

    function toggleSlideshow(): void {
        root.slideshowEnabled = !root.slideshowEnabled;
        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "toggle-slideshow"]);
        Toaster.toast(
            qsTr("Wallpaper Slideshow"),
            root.slideshowEnabled
                ? qsTr("Slideshow started (changing every %1m)").arg(Math.max(1, Math.round(root.slideshowIntervalSec / 60)))
                : qsTr("Slideshow stopped"),
            "wallpaper_slideshow"
        );
    }

    function setSlideshowInterval(seconds: int): void {
        root.slideshowIntervalSec = seconds;
        root.slideshowEnabled = true;
        slideshowTimer.restart();
        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "set-slideshow-interval", `${seconds}s`]);
        Toaster.toast(
            qsTr("Slideshow Interval"),
            seconds >= 60
                ? qsTr("Interval set to %1 minutes").arg(Math.round(seconds / 60))
                : qsTr("Interval set to %1 seconds").arg(seconds),
            "timer"
        );
    }

    function handleInitialBoot(): void {
        if (root.initialBootHandled)
            return;
        root.initialBootHandled = true;
        if (root.randomOnBoot) {
            root.setRandom();
        } else if (root.actualCurrent) {
            Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "restore", root.actualCurrent]);
        }
    }

    Timer {
        id: bootFallbackTimer
        interval: 600
        running: !root.initialBootHandled
        repeat: false
        onTriggered: root.handleInitialBoot()
    }

    Timer {
        id: slideshowTimer
        interval: Math.max(5000, root.slideshowIntervalSec * 1000)
        running: root.slideshowEnabled
        repeat: true
        onTriggered: {
            if (!root.showPreview) {
                root.setRandom();
            }
        }
    }

    function setWallpaper(path: string, effect: string): void {
        previewPath = path;
        actualCurrent = path;
        const helperArgs = ["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "set", path];
        if (effect)
            helperArgs.push(effect);
        Quickshell.execDetached(helperArgs);
        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/apply-theme.py"), "--wallpaper", path, "--no-wwal"]);
    }

    function preview(path: string): void {
        if (!path || (showPreview && path === previewPath))
            return;
        previewPath = path;
        showPreview = true;
        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "scroll", path]);

        if (Colours.scheme === "dynamic")
            getPreviewColoursProc.running = true;
    }

    function stopPreview(): void {
        if (!showPreview)
            return;
        showPreview = false;
        if (previewPath !== actualCurrent && actualCurrent) {
            Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "restore", actualCurrent]);
        }
        if (previewColourLock)
            pendingPreviewClear = true;
        else
            Colours.showPreview = false;
    }

    onPreviewColourLockChanged: {
        if (!previewColourLock && pendingPreviewClear)
            Colours.showPreview = false;
    }

    list: wallpapers ? wallpapers.entries : []
    key: "relativePath"
    useFuzzy: GlobalConfig.launcher.useFuzzy.wallpapers
    extraOpts: useFuzzy ? ({}) : ({
            forward: false
        })

    IpcHandler {
        function get(): string {
            return root.actualCurrent;
        }

        function set(path: string): void {
            root.setWallpaper(path);
        }

        function random(): void {
            root.setRandom();
        }

        function toggleSlideshow(): void {
            root.toggleSlideshow();
        }

        function toggleRandomOnBoot(): void {
            root.toggleRandomOnBoot();
        }

        function setInterval(sec: int): void {
            root.setSlideshowInterval(sec);
        }

        function list(): string {
            return root.list.map(w => w.path).join("\n");
        }

        target: "wallpaper"
    }

    FileView {
        path: root.wwalConfigPath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                const cfg = JSON.parse(text());
                root.randomOnBoot = Boolean(cfg.randomOnBoot);
                if (cfg.slideshow && typeof cfg.slideshow === "object") {
                    root.slideshowEnabled = Boolean(cfg.slideshow.enabled);
                    if (cfg.slideshow.interval)
                        root.slideshowIntervalSec = Number(cfg.slideshow.interval);
                    if (cfg.slideshow.effect)
                        root.slideshowEffect = cfg.slideshow.effect;
                } else if (cfg.slideshow !== undefined) {
                    root.slideshowEnabled = Boolean(cfg.slideshow);
                    if (cfg.slideshowInterval)
                        root.slideshowIntervalSec = Number(cfg.slideshowInterval);
                }
            } catch (e) {
                console.warn("Failed to parse wwal.json:", e);
            }
            root.configLoaded = true;
            if (root.pathLoaded)
                root.handleInitialBoot();
        }
        onLoadFailed: {
            root.configLoaded = true;
            if (root.pathLoaded)
                root.handleInitialBoot();
        }
    }

    FileView {
        path: root.currentNamePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            let wall = text().trim();
            if (!wall) {
                wall = root.fallback;
                Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/apply-theme.py"), "--wallpaper", root.fallback]);
            }
            root.previewColourLock = false;

            if (root.initialBootHandled) {
                if (wall !== root.actualCurrent) {
                    root.actualCurrent = wall;
                    if (root.randomPending) {
                        root.randomPending = false;
                    } else {
                        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/wwal-helper.py"), "restore", wall]);
                    }
                }
            } else {
                root.actualCurrent = wall;
                root.pathLoaded = true;
                if (root.configLoaded)
                    root.handleInitialBoot();
            }
        }
        onLoadFailed: {
            root.actualCurrent = root.fallback;
            root.previewColourLock = false;
            Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/apply-theme.py"), "--wallpaper", root.fallback]);
            if (!root.initialBootHandled) {
                root.pathLoaded = true;
                if (root.configLoaded)
                    root.handleInitialBoot();
            }
        }
    }

    FileSystemModel {
        id: wallpapers

        recursive: true
        path: Paths.wallsdir
        filter: FileSystemModel.Images
    }

    Process {
        id: getPreviewColoursProc

        command: ["caelestia", "wallpaper", "-p", root.previewPath, ...root.smartArg]
        stdout: StdioCollector {
            onStreamFinished: {
                Colours.load(text, true);
                Colours.showPreview = true;
            }
        }
    }
}
