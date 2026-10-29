#include "sessionmanager.hpp"

#include <QtDBus/qdbusargument.h>
#include <QtDBus/qdbusconnection.h>
#include <QtDBus/qdbuserror.h>
#include <QtDBus/qdbusextratypes.h>
#include <QtDBus/qdbusmessage.h>
#include <QtDBus/qdbuspendingcall.h>
#include <QtDBus/qdbuspendingreply.h>
#include <QtDBus/qdbusreply.h>
#include <qloggingcategory.h>
#include <qprocess.h>

#include "../toaster.hpp"

Q_LOGGING_CATEGORY(lcSessionManager, "caelestia.services.sessionmanager", QtInfoMsg)

namespace caelestia::services {

namespace {

using Qt::StringLiterals::operator""_s;

constexpr const char* LOGIN_SERVICE = "org.freedesktop.login1";
constexpr const char* LOGIN_PATH = "/org/freedesktop/login1";
constexpr const char* LOGIN_IFACE = "org.freedesktop.login1.Manager";
constexpr const char* SESSION_IFACE = "org.freedesktop.login1.Session";

} // namespace

SessionManager::SessionManager(QObject* parent)
    : QObject(parent) {
    auto bus = getSystemBus();
    if (!bus)
        return;

    bool ok = bus->connect(
        LOGIN_SERVICE, LOGIN_PATH, LOGIN_IFACE, "PrepareForSleep", this, SLOT(handlePrepareForSleep(bool)));
    if (!ok)
        qCWarning(lcSessionManager) << "Failed to connect to PrepareForSleep signal:" << bus->lastError().message();

    if (!resolveSessionPath(*bus))
        return;

    ok = bus->connect(LOGIN_SERVICE, m_sessionPath, SESSION_IFACE, "Lock", this, SLOT(handleLockRequested()));
    if (!ok)
        qCWarning(lcSessionManager) << "Failed to connect to Lock signal:" << bus->lastError().message();

    ok = bus->connect(LOGIN_SERVICE, m_sessionPath, SESSION_IFACE, "Unlock", this, SLOT(handleUnlockRequested()));
    if (!ok)
        qCWarning(lcSessionManager) << "Failed to connect to Unlock signal:" << bus->lastError().message();

    auto hibernateMsg = QDBusMessage::createMethodCall(LOGIN_SERVICE, LOGIN_PATH, LOGIN_IFACE, "CanHibernate");
    auto* watcher = new QDBusPendingCallWatcher(bus->asyncCall(hibernateMsg), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<QString> reply = *self;
        if (reply.isValid()) {
            const QString state = reply.value();
            m_hibernateAvailable = (state == u"yes"_s || state == u"challenge"_s);
        }
        self->deleteLater();
    });
}

bool SessionManager::resolveSessionPath(QDBusConnection& bus) {
    const QString envSessionId = qEnvironmentVariable("XDG_SESSION_ID");
    if (!envSessionId.isEmpty()) {
        auto sessionMsg = QDBusMessage::createMethodCall(LOGIN_SERVICE, LOGIN_PATH, LOGIN_IFACE, "GetSession");
        sessionMsg.setArguments({ envSessionId });
        const QDBusReply<QDBusObjectPath> sessionReply = bus.call(sessionMsg);
        if (sessionReply.isValid() && !sessionReply.value().path().isEmpty()) {
            m_sessionId = envSessionId;
            m_sessionPath = sessionReply.value().path();
            return true;
        }
    }

    {
        auto sessionMsg = QDBusMessage::createMethodCall(LOGIN_SERVICE, LOGIN_PATH, LOGIN_IFACE, "GetSession");
        sessionMsg.setArguments({ u"auto"_s });
        const QDBusReply<QDBusObjectPath> sessionReply = bus.call(sessionMsg);
        if (sessionReply.isValid() && !sessionReply.value().path().isEmpty()) {
            m_sessionPath = sessionReply.value().path();
            auto idMsg = QDBusMessage::createMethodCall(
                LOGIN_SERVICE, m_sessionPath, u"org.freedesktop.DBus.Properties"_s, u"Get"_s);
            idMsg.setArguments({ QString::fromLatin1(SESSION_IFACE), u"Id"_s });
            const QDBusMessage idReply = bus.call(idMsg);
            if (idReply.type() == QDBusMessage::ReplyMessage && !idReply.arguments().isEmpty()) {
                m_sessionId = idReply.arguments().first().value<QDBusVariant>().variant().toString();
            }
            return true;
        }
    }

    // Fallback when caller has been moved out of its session scope (e.g. root cgroup by ananicy-cpp):
    // query the user's primary graphical Display session via /org/freedesktop/login1/user/self.
    auto propMsg = QDBusMessage::createMethodCall(
        LOGIN_SERVICE, u"/org/freedesktop/login1/user/self"_s, u"org.freedesktop.DBus.Properties"_s, u"Get"_s);
    propMsg.setArguments({ u"org.freedesktop.login1.User"_s, u"Display"_s });
    const QDBusMessage propReply = bus.call(propMsg);
    if (propReply.type() == QDBusMessage::ReplyMessage && !propReply.arguments().isEmpty()) {
        const QVariant outer = propReply.arguments().first().value<QDBusVariant>().variant();
        const auto arg = outer.value<QDBusArgument>();
        QString sessionId;
        QDBusObjectPath sessionObjPath;
        arg.beginStructure();
        arg >> sessionId >> sessionObjPath;
        arg.endStructure();
        if (!sessionObjPath.path().isEmpty() && sessionObjPath.path() != u"/"_s) {
            m_sessionId = sessionId;
            m_sessionPath = sessionObjPath.path();
            return true;
        }
    }

    qCWarning(lcSessionManager) << "Failed to resolve logind session path";
    return false;
}

bool SessionManager::exec(const QStringList& command) {
    if (command.isEmpty()) {
        return false;
    }

    static const QHash<QString, void (SessionManager::*)()> cmds = {
        { u"lock"_s, &SessionManager::lock },
        { u"locksession"_s, &SessionManager::lock },
        { u"logout"_s, &SessionManager::logout },
        { u"suspend"_s, &SessionManager::suspend },
        { u"suspendthenhibernate"_s, &SessionManager::suspendThenHibernate },
        { u"hibernate"_s, &SessionManager::hibernate },
        { u"poweroff"_s, &SessionManager::poweroff },
        { u"reboot"_s, &SessionManager::reboot },
    };

    auto cmd = command.first();
    // Alias systemctl and loginctl to raw dbus calls (only match exact command)
    if ((cmd == u"systemctl"_s || cmd == u"loginctl"_s) && command.size() == 2)
        cmd = command.at(1);
    if (cmd == u"loginctl"_s && command.size() == 3 && command.at(1) == u"terminate-user"_s && command.at(2).isEmpty())
        cmd = u"logout"_s; // Manual alias `loginctl terminate-user ''` -> logout

    // Normalise command
    cmd = cmd.remove("-").remove("_").toLower();

    const auto methodPtr = cmds.value(cmd, nullptr);
    if (methodPtr) {
        (this->*methodPtr)();
        return true;
    }

    return false;
}

void SessionManager::lock() {
    emit lockRequested();
    callSession("Lock");
}

void SessionManager::logout() {
    callSession("Terminate");
}

void SessionManager::suspend() {
    callManager("Suspend");
}

void SessionManager::suspendThenHibernate() {
    if (queryHibernateAvailable()) {
        callManager("SuspendThenHibernate");
    } else {
        // Fall back to suspend when no hibernate
        qCInfo(lcSessionManager) << "SuspendThenHibernate unavailable, falling back to suspend";
        callManager("Suspend");
    }
}

void SessionManager::hibernate() {
    if (queryHibernateAvailable()) {
        callManager("Hibernate");
    } else {
        qCWarning(lcSessionManager) << "Hibernate unavailable, ignoring hibernate request";

        auto* const engine = qmlEngine(this);
        if (!engine)
            return;
        auto* const toaster = engine->singletonInstance<Toaster*>("Caelestia", "Toaster");
        if (!toaster)
            return;
        toaster->toast(
            tr("Hibernate failed"), tr("Enable hibernation to use this feature."), "warning", Toast::Type::Warning);
    }
}

void SessionManager::poweroff() {
    callManager("PowerOff");
}

void SessionManager::reboot() {
    callManager("Reboot");
}

std::optional<QDBusConnection> SessionManager::getSystemBus() const {
    auto bus = QDBusConnection::systemBus();
    if (!bus.isConnected()) {
        qCWarning(lcSessionManager) << "Failed to connect to system bus:" << bus.lastError().message();
        return std::nullopt;
    }
    return bus;
}

bool SessionManager::queryHibernateAvailable() const {
    if (m_hibernateAvailable.has_value()) {
        return *m_hibernateAvailable;
    }

    auto bus = getSystemBus();
    if (!bus)
        return false;

    auto hibernateMsg = QDBusMessage::createMethodCall(LOGIN_SERVICE, LOGIN_PATH, LOGIN_IFACE, "CanHibernate");
    const QDBusReply<QString> hibernateReply = bus->call(hibernateMsg);
    if (!hibernateReply.isValid()) {
        qCWarning(lcSessionManager) << "Failed to query hibernate support:" << hibernateReply.error().message();
    } else {
        const auto state = hibernateReply.value();
        m_hibernateAvailable = (state == "yes" || state == "challenge");
        return *m_hibernateAvailable;
    }

    return false;
}

void SessionManager::call(const QString& path, const QString& iface, const QString& method, const QVariantList& args) {
    auto bus = getSystemBus();
    if (!bus)
        return;

    auto msg = QDBusMessage::createMethodCall(LOGIN_SERVICE, path, iface, method);
    msg.setArguments(args);

    auto* watcher = new QDBusPendingCallWatcher(bus->asyncCall(msg), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, method](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self;
        if (reply.isError()) {
            qCWarning(lcSessionManager) << "Call to" << method << "failed:" << reply.error().message();
            fallbackCommand(method);
        }
        self->deleteLater();
    });
}

void SessionManager::callManager(const QString& method) {
    call(LOGIN_PATH, LOGIN_IFACE, method, { /* interactive = */ true });
}

void SessionManager::callSession(const QString& method) {
    if (m_sessionPath.isEmpty()) {
        if (auto bus = getSystemBus(); !bus || !resolveSessionPath(*bus)) {
            qCWarning(lcSessionManager) << "Cannot call" << method << "- no session path";
            fallbackCommand(method);
            return;
        }
    }

    call(m_sessionPath, SESSION_IFACE, method);
}

void SessionManager::fallbackCommand(const QString& method) const {
    if (method == u"PowerOff"_s) {
        QProcess::startDetached(u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"systemctl"_s, u"poweroff"_s });
    } else if (method == u"Reboot"_s) {
        QProcess::startDetached(u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"systemctl"_s, u"reboot"_s });
    } else if (method == u"Hibernate"_s) {
        QProcess::startDetached(u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"systemctl"_s, u"hibernate"_s });
    } else if (method == u"Suspend"_s) {
        QProcess::startDetached(u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"systemctl"_s, u"suspend"_s });
    } else if (method == u"SuspendThenHibernate"_s) {
        QProcess::startDetached(
            u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"systemctl"_s, u"suspend-then-hibernate"_s });
    } else if (method == u"Lock"_s) {
        if (!m_sessionId.isEmpty()) {
            QProcess::startDetached(
                u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"loginctl"_s, u"lock-session"_s, m_sessionId });
        } else {
            QProcess::startDetached(u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"loginctl"_s, u"lock-session"_s });
        }
    } else if (method == u"Terminate"_s) {
        if (!m_sessionId.isEmpty()) {
            QProcess::startDetached(
                u"systemd-run"_s, { u"--user"_s, u"--quiet"_s, u"--collect"_s, u"loginctl"_s, u"terminate-session"_s, m_sessionId });
        } else {
            QProcess::startDetached(u"hyprctl"_s, { u"dispatch"_s, u"hl.dsp.exit()"_s });
        }
    }
}

void SessionManager::handlePrepareForSleep(bool sleep) {
    if (sleep) {
        emit aboutToSleep();
    } else {
        emit resumed();
    }
}

void SessionManager::handleLockRequested() {
    emit lockRequested();
}

void SessionManager::handleUnlockRequested() {
    emit unlockRequested();
}

} // namespace caelestia::services
