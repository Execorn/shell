#include "config.hpp"
#include "appearanceconfig.hpp"
#include "backgroundconfig.hpp"
#include "barconfig.hpp"
#include "borderconfig.hpp"
#include "dashboardconfig.hpp"
#include "generalconfig.hpp"
#include "launcherconfig.hpp"
#include "lockconfig.hpp"
#include "monitorconfigmanager.hpp"
#include "nexusconfig.hpp"
#include "notifsconfig.hpp"
#include "osdconfig.hpp"
#include "serviceconfig.hpp"
#include "sessionconfig.hpp"
#include "sidebarconfig.hpp"
#include "tokens.hpp"
#include "userpaths.hpp"
#include "utilitiesconfig.hpp"
#include "winfoconfig.hpp"
#include "themeconfig.hpp"

#include <fcntl.h>
#include <qdir.h>
#include <qfileinfo.h>
#include <qicon.h>
#include <qqmlengine.h>
#include <qstandardpaths.h>
#include <unistd.h>

namespace caelestia::config {

namespace {

QString configDir() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/caelestia/");
}

void hardenStartupEnvironment() {
    // Initialize the platform theme icon loader (KIconLoader / libKF6I18n) on the main
    // GUI thread before QQuickPixmapReader spawns its worker thread.
    (void)QIcon::fromTheme(QStringLiteral("application-x-executable")).pixmap(16, 16);

    // libnvidia-egl-wayland opens /dev/dri/renderD128 with O_RDWR and without O_CLOEXEC
    // during Wayland EGL initialization. Mark any /dev/dri/* descriptors FD_CLOEXEC so
    // child processes (e.g. nmcli monitor) do not inherit DRM render node FDs.
    const QDir fdDir(QStringLiteral("/proc/self/fd"));
    const auto entries = fdDir.entryList(QDir::Files | QDir::System | QDir::NoDotAndDotDot);
    for (const QString& entry : entries) {
        bool ok = false;
        const int fd = entry.toInt(&ok);
        if (!ok || fd < 3)
            continue;
        const QString target = QFileInfo(fdDir.filePath(entry)).symLinkTarget();
        if (target.startsWith(QStringLiteral("/dev/dri/"))) {
            const int flags = fcntl(fd, F_GETFD);
            if (flags >= 0 && !(flags & FD_CLOEXEC)) {
                (void)fcntl(fd, F_SETFD, flags | FD_CLOEXEC);
            }
        }
    }
}

} // namespace

GlobalConfig::GlobalConfig(QObject* parent)
    : RootConfig(parent)
    , m_appearance(new AppearanceConfig(this))
    , m_general(new GeneralConfig(this))
    , m_background(new BackgroundConfig(this))
    , m_bar(new BarConfig(this))
    , m_border(new BorderConfig(this))
    , m_dashboard(new DashboardConfig(this))
    , m_launcher(new LauncherConfig(this))
    , m_lock(new LockConfig(this))
    , m_nexus(new NexusConfig(this))
    , m_notifs(new NotifsConfig(this))
    , m_osd(new OsdConfig(this))
    , m_services(new ServiceConfig(this))
    , m_session(new SessionConfig(this))
    , m_sidebar(new SidebarConfig(this))
    , m_utilities(new UtilitiesConfig(this))
    , m_winfo(new WInfoConfig(this))
    , m_paths(new UserPaths(this))
    , m_theme(new ThemeConfig(this)) {
    setupFileBackend(configDir() + QStringLiteral("shell.json"));
}

GlobalConfig::GlobalConfig(GlobalConfig* fallback, const QString& filePath, const QString& screen, QObject* parent)
    : RootConfig(parent)
    , m_appearance(new AppearanceConfig(this))
    , m_general(new GeneralConfig(this))
    , m_background(new BackgroundConfig(this))
    , m_bar(new BarConfig(this))
    , m_border(new BorderConfig(this))
    , m_dashboard(new DashboardConfig(this))
    , m_launcher(new LauncherConfig(this))
    , m_lock(new LockConfig(this))
    , m_nexus(new NexusConfig(this))
    , m_notifs(new NotifsConfig(this))
    , m_osd(new OsdConfig(this))
    , m_services(new ServiceConfig(this))
    , m_session(new SessionConfig(this))
    , m_sidebar(new SidebarConfig(this))
    , m_utilities(new UtilitiesConfig(this))
    , m_winfo(new WInfoConfig(this))
    , m_paths(new UserPaths(this))
    , m_theme(new ThemeConfig(this)) {
    if (!filePath.isEmpty())
        setupFileBackend(filePath, screen);
    if (fallback)
        syncFromGlobal(fallback);

    // Bind appearance computed properties to token base values
    bindAppearanceTokens();
}

GlobalConfig* GlobalConfig::instance() {
    static GlobalConfig instance;
    static const bool hardened = []() {
        hardenStartupEnvironment();
        return true;
    }();
    Q_UNUSED(hardened);
    instance.bindAppearanceTokens();
    return &instance;
}

GlobalConfig* GlobalConfig::defaults() {
    if (!m_defaults)
        m_defaults = new GlobalConfig(nullptr, QString(), QString(), this);
    return m_defaults;
}

void GlobalConfig::bindAppearanceTokens() {
    if (m_tokensBound)
        return;

    qCDebug(lcConfig) << "GlobalConfig::bindAppearanceTokens: binding appearance to token values";
    auto* const tokenAppearance = TokenConfig::instance()->appearance();
    m_appearance->rounding()->bindTokens(tokenAppearance->rounding());
    m_appearance->spacing()->bindTokens(tokenAppearance->spacing());
    m_appearance->padding()->bindTokens(tokenAppearance->padding());
    m_appearance->anim()->durations()->bindTokens(tokenAppearance->animDurations());
    m_tokensBound = true;
}

GlobalConfig* GlobalConfig::forScreen(const QString& screen) {
    return MonitorConfigManager::instance()->configForScreen(screen);
}

GlobalConfig* GlobalConfig::create(QQmlEngine*, QJSEngine*) {
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

} // namespace caelestia::config
