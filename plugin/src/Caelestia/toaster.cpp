#include "toaster.hpp"

#include <qcoreapplication.h>
#include <qlogging.h>
#include <qthread.h>
#include <qtimer.h>

namespace caelestia {

namespace {

bool matchesTranslatedTitle(const QString& title, const char* context, const char* sourceText) {
    return title == QLatin1String(sourceText) || title == QCoreApplication::translate(context, sourceText);
}

QString toastCategory(const QString& title) {
    if (matchesTranslatedTitle(title, "Hypr", "Caps lock enabled") ||
        matchesTranslatedTitle(title, "Hypr", "Caps lock disabled")) {
        return QStringLiteral("capslock");
    }
    if (matchesTranslatedTitle(title, "Hypr", "Num lock enabled") ||
        matchesTranslatedTitle(title, "Hypr", "Num lock disabled")) {
        return QStringLiteral("numlock");
    }
    if (matchesTranslatedTitle(title, "Notifs", "Do not disturb enabled") ||
        matchesTranslatedTitle(title, "Notifs", "Do not disturb disabled")) {
        return QStringLiteral("dnd");
    }
    if (matchesTranslatedTitle(title, "GameMode", "Game mode enabled") ||
        matchesTranslatedTitle(title, "GameMode", "Game mode disabled")) {
        return QStringLiteral("gamemode");
    }
    if (matchesTranslatedTitle(title, "BatteryMonitor", "Charger plugged in") ||
        matchesTranslatedTitle(title, "BatteryMonitor", "Charger unplugged")) {
        return QStringLiteral("charger");
    }
    if (title.startsWith(QLatin1String("VPN ")) || matchesTranslatedTitle(title, "VPN", "VPN connected") ||
        matchesTranslatedTitle(title, "VPN", "VPN disconnected") ||
        matchesTranslatedTitle(title, "VPN", "VPN authentication required") ||
        matchesTranslatedTitle(title, "VPN", "VPN error")) {
        return QStringLiteral("vpn");
    }
    if (matchesTranslatedTitle(title, "Audio", "Audio output changed")) {
        return QStringLiteral("audio-output");
    }
    if (matchesTranslatedTitle(title, "Audio", "Audio input changed")) {
        return QStringLiteral("audio-input");
    }
    if (matchesTranslatedTitle(title, "Hypr", "Keyboard layout changed")) {
        return QStringLiteral("kb-layout");
    }
    if (matchesTranslatedTitle(title, "KbLayoutModel", "Keyboard layout limit")) {
        return QStringLiteral("kb-limit");
    }
    if (matchesTranslatedTitle(title, "Players", "Now Playing")) {
        return QStringLiteral("now-playing");
    }
    if (matchesTranslatedTitle(title, "ConfigToasts", "Config loaded")) {
        return QStringLiteral("config-loaded");
    }
    if (matchesTranslatedTitle(title, "EQs", "Equalizer")) {
        return QStringLiteral("equalizer");
    }
    if (matchesTranslatedTitle(title, "Monitors", "Monitors")) {
        return QStringLiteral("monitors");
    }
    if (title == QLatin1String("Wallpaper on Boot") || title == QLatin1String("Wallpaper Slideshow") ||
        title == QLatin1String("Slideshow Interval")) {
        return title;
    }
    return QString();
}

} // namespace

Toast::Toast(const QString& title, const QString& message, const QString& icon, Type type, int timeout,
    const QString& category, QObject* parent)
    : QObject(parent)
    , m_closed(false)
    , m_title(title)
    , m_message(message)
    , m_icon(icon)
    , m_type(type)
    , m_timeout(timeout)
    , m_category(category) {
    if (m_icon.isEmpty()) {
        switch (m_type) {
        case Type::Success:
            m_icon = "check_circle_unread";
            break;
        case Type::Warning:
            m_icon = "warning";
            break;
        case Type::Error:
            m_icon = "error";
            break;
        default:
            m_icon = "info";
            break;
        }
    }

    if (timeout <= 0) {
        switch (m_type) {
        case Type::Warning:
            m_timeout = 7000;
            break;
        case Type::Error:
            m_timeout = 10000;
            break;
        default:
            m_timeout = 5000;
            break;
        }
    }

    QTimer::singleShot(m_timeout, this, &Toast::close);
}

bool Toast::closed() const {
    return m_closed;
}

QString Toast::title() const {
    return m_title;
}

QString Toast::message() const {
    return m_message;
}

QString Toast::icon() const {
    return m_icon;
}

int Toast::timeout() const {
    return m_timeout;
}

Toast::Type Toast::type() const {
    return m_type;
}

QString Toast::category() const {
    return m_category;
}

void Toast::close() {
    if (!m_closed) {
        m_closed = true;
        emit closedChanged();
    }

    if (m_locks.isEmpty()) {
        emit finishedClose();
    }
}

void Toast::lock(QObject* sender) {
    m_locks << sender;
    QObject::connect(sender, &QObject::destroyed, this, &Toast::unlock);
}

void Toast::unlock(QObject* sender) {
    if (m_locks.remove(sender) && m_closed) {
        close();
    }
}

Toaster::Toaster(QObject* parent)
    : QObject(parent) {}

QQmlListProperty<Toast> Toaster::toasts() {
    return QQmlListProperty<Toast>(this, &m_toasts);
}

void Toaster::toast(const QString& title, const QString& message, const QString& icon, Toast::Type type, int timeout,
    const QString& category) {
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(
            this,
            [this, title, message, icon, type, timeout, category]() {
                toast(title, message, icon, type, timeout, category);
            },
            Qt::QueuedConnection);
        return;
    }

    const QString resolvedCategory = !category.isEmpty() ? category : toastCategory(title);
    const auto currentToasts = m_toasts;
    for (auto* existing : currentToasts) {
        if (!existing || existing->closed()) {
            continue;
        }
        const bool exactMatch = existing->title() == title && existing->message() == message;
        const QString existingCategory =
            !existing->category().isEmpty() ? existing->category() : toastCategory(existing->title());
        const bool categoryMatch = !resolvedCategory.isEmpty() && existingCategory == resolvedCategory;
        if (exactMatch || categoryMatch) {
            existing->close();
        }
    }

    auto* toast = new Toast(title, message, icon, type, timeout, resolvedCategory, this);
    QObject::connect(toast, &Toast::finishedClose, this, [toast, this]() {
        if (m_toasts.removeOne(toast)) {
            emit toastsChanged();
            toast->deleteLater();
        }
    });
    m_toasts.push_front(toast);
    emit toastsChanged();
}

} // namespace caelestia
