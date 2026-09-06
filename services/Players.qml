pragma Singleton

import QtQml
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import Caelestia
import Caelestia.Config
import qs.components.misc

Singleton {
    id: root

    readonly property list<MprisPlayer> list: Mpris.players.values
    property int _stateTrigger: 0

    function isDummyPlayer(player: MprisPlayer): bool {
        if (!player)
            return true;
        if (player.playbackState === MprisPlaybackState.Playing)
            return false;
        if (player.trackTitle && player.trackTitle.trim().length > 0)
            return false;
        return player.playbackState === MprisPlaybackState.Stopped;
    }

    readonly property MprisPlayer active: {
        root._stateTrigger;

        if (props.manualActive && list.includes(props.manualActive))
            return props.manualActive;

        // 1. Any player that is actively playing (prefer non-dummy)
        const playing = list.find(p => p.playbackState === MprisPlaybackState.Playing && !isDummyPlayer(p))
            ?? list.find(p => p.playbackState === MprisPlaybackState.Playing);
        if (playing)
            return playing;

        // 2. User's configured default player if running and not an empty dummy
        const defaultP = list.find(p => getIdentity(p) === GlobalConfig.services.defaultPlayer);
        if (defaultP && !isDummyPlayer(defaultP))
            return defaultP;

        // 3. Paused player with actual track info
        const pausedWithMedia = list.find(p => p.playbackState === MprisPlaybackState.Paused && (p.trackTitle || p.trackAlbum));
        if (pausedWithMedia)
            return pausedWithMedia;

        // 4. Any player with loaded track metadata
        const withMedia = list.find(p => (p.trackTitle && p.trackTitle.trim().length > 0) || (p.trackAlbum && p.trackAlbum.trim().length > 0));
        if (withMedia)
            return withMedia;

        // 5. Default player even if idle
        if (defaultP)
            return defaultP;

        // 6. Any player that isn't a dummy Bluetooth endpoint
        const nonDummy = list.find(p => !isDummyPlayer(p));
        if (nonDummy)
            return nonDummy;

        // 7. Absolute fallback
        return list[0] ?? null;
    }
    property alias manualActive: props.manualActive

    Variants {
        model: root.list

        Connections {
            required property MprisPlayer modelData

            target: modelData

            function onPlaybackStateChanged() {
                root._stateTrigger++;
            }

            function onTrackTitleChanged() {
                root._stateTrigger++;
            }

            function onTrackAlbumChanged() {
                root._stateTrigger++;
            }
        }
    }

    function getIdentity(player: MprisPlayer): string {
        if (!player)
            return "";
        const alias = GlobalConfig.services.playerAliases.find(a => a.from === player.identity);
        return alias?.to ?? player.identity;
    }

    function getArtUrl(player: MprisPlayer): string {
        if (!player)
            return "";
        if (player.trackArtUrl)
            return player.trackArtUrl;

        const url = player.metadata["xesam:url"] ?? "";
        if (typeof url === "string" && url.length > 0) {
            const ytMatch = url.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([\w-]{11})/);
            if (ytMatch && ytMatch[1])
                return `https://img.youtube.com/vi/${ytMatch[1]}/hqdefault.jpg`;
        }
        return "";
    }

    Connections {
        function onPostTrackChanged() {
            if (!GlobalConfig.utilities.toasts.nowPlaying) {
                return;
            }
            if (root.active.trackArtist != "" && root.active.trackTitle != "") {
                Toaster.toast(qsTr("Now Playing"), qsTr("%1 - %2").arg(root.active.trackArtist).arg(root.active.trackTitle), "music_note");
            }
        }

        target: root.active
    }

    PersistentProperties {
        id: props

        property MprisPlayer manualActive

        reloadableId: "players"
    }

    // qmllint disable unresolved-type
    CustomShortcut {
        // qmllint enable unresolved-type
        name: "mediaToggle"
        description: "Toggle media playback"
        onPressed: {
            const active = root.active;
            if (active && active.canTogglePlaying)
                active.togglePlaying();
        }
    }

    // qmllint disable unresolved-type
    CustomShortcut {
        // qmllint enable unresolved-type
        name: "mediaPrev"
        description: "Previous track"
        onPressed: {
            const active = root.active;
            if (active && active.canGoPrevious)
                active.previous();
        }
    }

    // qmllint disable unresolved-type
    CustomShortcut {
        // qmllint enable unresolved-type
        name: "mediaNext"
        description: "Next track"
        onPressed: {
            const active = root.active;
            if (active && active.canGoNext)
                active.next();
        }
    }

    // qmllint disable unresolved-type
    CustomShortcut {
        // qmllint enable unresolved-type
        name: "mediaStop"
        description: "Stop media playback"
        onPressed: root.active?.stop()
    }

    IpcHandler {
        function getActive(prop: string): string {
            const active = root.active;
            return active ? active[prop] ?? "Invalid property" : "No active player";
        }

        function setActive(name: string): string {
            if (name === "auto" || name === "clear" || name === "") {
                props.manualActive = null;
                return "Cleared manual player";
            }
            const found = root.list.find(p => root.getIdentity(p).toLowerCase() === name.toLowerCase() || p.identity.toLowerCase() === name.toLowerCase());
            if (found) {
                props.manualActive = found;
                return `Set active player to ${root.getIdentity(found)}`;
            }
            return `Player not found: ${name}`;
        }

        function list(): string {
            return root.list.map(p => root.getIdentity(p)).join("\n");
        }

        function play(): void {
            const active = root.active;
            if (active?.canPlay)
                active.play();
        }

        function pause(): void {
            const active = root.active;
            if (active?.canPause)
                active.pause();
        }

        function playPause(): void {
            const active = root.active;
            if (active?.canTogglePlaying)
                active.togglePlaying();
        }

        function previous(): void {
            const active = root.active;
            if (active?.canGoPrevious)
                active.previous();
        }

        function next(): void {
            const active = root.active;
            if (active?.canGoNext)
                active.next();
        }

        function stop(): void {
            root.active?.stop();
        }

        target: "mpris"
    }
}
