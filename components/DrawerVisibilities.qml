import Quickshell

PersistentProperties {
    property bool bar
    property bool osd
    property bool session
    property bool launcher
    property bool dashboard
    property bool utilities
    property bool sidebar
    property bool cheatsheet
    property bool dashboardFocused: false

    onDashboardChanged: {
        if (!dashboard)
            dashboardFocused = false;
    }

    onLauncherChanged: {
        if (launcher)
            Quickshell.execDetached(["hyprctl", "switchxkblayout", "all", "0"]);
    }
}
