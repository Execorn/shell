#include "bluezagent.hpp"

#include <QtDBus/qdbusconnection.h>
#include <QtDBus/qdbuserror.h>
#include <QtDBus/qdbuspendingcall.h>
#include <QtDBus/qdbuspendingreply.h>
#include <QtDBus/qdbusservicewatcher.h>
#include <qloggingcategory.h>

Q_LOGGING_CATEGORY(lcBluezAgent, "caelestia.services.bluezagent", QtInfoMsg)

namespace caelestia::services {

namespace {

using Qt::StringLiterals::operator""_s;

constexpr const char* BLUEZ_SERVICE = "org.bluez";
constexpr const char* AGENT_MANAGER_PATH = "/org/bluez";
constexpr const char* AGENT_MANAGER_IFACE = "org.bluez.AgentManager1";
constexpr const char* DEVICE_IFACE = "org.bluez.Device1";
constexpr const char* DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties";
constexpr const char* AGENT_OBJECT_PATH = "/org/caelestia/BluezAgent";
constexpr const char* AGENT_CAPABILITY = "KeyboardDisplay";
constexpr int REQUEST_TIMEOUT_MS = 60'000;

} // namespace

namespace detail {

BluezAgentEndpoint::BluezAgentEndpoint(BluezAgent* agent)
    : QObject(agent)
    , m_agent(agent) {}

BluezAgentAdaptor::BluezAgentAdaptor(BluezAgentEndpoint* endpoint)
    : QDBusAbstractAdaptor(endpoint)
    , m_endpoint(endpoint) {}

void BluezAgentAdaptor::Release() {
    m_endpoint->m_agent->handleRelease();
}

QString BluezAgentAdaptor::RequestPinCode(const QDBusObjectPath& device) {
    m_endpoint->m_agent->beginDelayedRequest(m_endpoint, u"pin"_s, device, {}, {});
    return {};
}

void BluezAgentAdaptor::DisplayPinCode(const QDBusObjectPath& device, const QString& pincode) {
    m_endpoint->m_agent->handleDisplayPinCode(device, pincode);
}

quint32 BluezAgentAdaptor::RequestPasskey(const QDBusObjectPath& device) {
    m_endpoint->m_agent->beginDelayedRequest(m_endpoint, u"passkey"_s, device, {}, {});
    return 0;
}

void BluezAgentAdaptor::DisplayPasskey(const QDBusObjectPath& device, quint32 passkey, quint16 entered) {
    m_endpoint->m_agent->handleDisplayPasskey(device, passkey, entered);
}

void BluezAgentAdaptor::RequestConfirmation(const QDBusObjectPath& device, quint32 passkey) {
    m_endpoint->m_agent->beginDelayedRequest(
        m_endpoint, u"confirm"_s, device, BluezAgent::formatSixDigitPasskey(passkey), {});
}

void BluezAgentAdaptor::RequestAuthorization(const QDBusObjectPath& device) {
    m_endpoint->m_agent->beginDelayedRequest(m_endpoint, u"authorize"_s, device, {}, {});
}

void BluezAgentAdaptor::AuthorizeService(const QDBusObjectPath& device, const QString& uuid) {
    m_endpoint->m_agent->beginDelayedRequest(m_endpoint, u"authorizeService"_s, device, {}, uuid);
}

void BluezAgentAdaptor::Cancel() {
    m_endpoint->m_agent->handleCancel();
}

} // namespace detail

BluezAgent::BluezAgent(QObject* parent)
    : QObject(parent)
    , m_endpoint(new detail::BluezAgentEndpoint(this))
    , m_adaptor(new detail::BluezAgentAdaptor(m_endpoint)) {
    m_timeoutTimer.setSingleShot(true);
    m_timeoutTimer.setInterval(REQUEST_TIMEOUT_MS);
    connect(&m_timeoutTimer, &QTimer::timeout, this, [this]() {
        if (!m_hasPendingReply)
            return;
        qCWarning(lcBluezAgent) << "Bluetooth agent request timed out for" << m_deviceAddress;
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Pairing prompt timed out"_s);
        emit requestCancelled();
    });

    auto bus = QDBusConnection::systemBus();
    if (!bus.isConnected()) {
        qCWarning(lcBluezAgent) << "System D-Bus unavailable; BlueZ pairing agent disabled:"
                                << bus.lastError().message();
        return;
    }

    m_objectExported =
        bus.registerObject(QLatin1StringView(AGENT_OBJECT_PATH), m_endpoint, QDBusConnection::ExportAdaptors);
    if (!m_objectExported) {
        qCWarning(lcBluezAgent) << "Failed to export org.bluez.Agent1 object:" << bus.lastError().message();
        return;
    }

    m_serviceWatcher =
        new QDBusServiceWatcher(QLatin1StringView(BLUEZ_SERVICE), bus, QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceOwnerChanged, this,
        [this](const QString&, const QString&, const QString& newOwner) {
            if (newOwner.isEmpty()) {
                handleRelease();
            } else {
                registerAgent();
            }
        });

    registerAgent();
}

BluezAgent::~BluezAgent() {
    m_timeoutTimer.stop();
    if (m_hasPendingReply) {
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Pairing agent shutting down"_s);
    }

    auto bus = QDBusConnection::systemBus();
    if (!bus.isConnected())
        return;

    if (m_registered) {
        auto msg = QDBusMessage::createMethodCall(QLatin1StringView(BLUEZ_SERVICE),
            QLatin1StringView(AGENT_MANAGER_PATH), QLatin1StringView(AGENT_MANAGER_IFACE), u"UnregisterAgent"_s);
        msg << QVariant::fromValue(QDBusObjectPath(QLatin1StringView(AGENT_OBJECT_PATH)));
        bus.call(msg, QDBus::NoBlock);
    }

    if (m_objectExported) {
        bus.unregisterObject(QLatin1StringView(AGENT_OBJECT_PATH));
    }
}

void BluezAgent::registerAgent() {
    if (!m_objectExported)
        return;

    auto bus = QDBusConnection::systemBus();
    if (!bus.isConnected())
        return;

    auto msg = QDBusMessage::createMethodCall(QLatin1StringView(BLUEZ_SERVICE), QLatin1StringView(AGENT_MANAGER_PATH),
        QLatin1StringView(AGENT_MANAGER_IFACE), u"RegisterAgent"_s);
    msg << QVariant::fromValue(QDBusObjectPath(QLatin1StringView(AGENT_OBJECT_PATH)))
        << QLatin1StringView(AGENT_CAPABILITY);

    auto* watcher = new QDBusPendingCallWatcher(bus.asyncCall(msg), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self;
        self->deleteLater();

        if (reply.isError()) {
            const auto err = reply.error();
            if (err.name() == u"org.bluez.Error.AlreadyExists"_s) {
                setRegistered(true);
                requestDefaultAgent();
                return;
            }
            if (err.name() != u"org.freedesktop.DBus.Error.ServiceUnknown"_s) {
                qCWarning(lcBluezAgent) << "RegisterAgent failed:" << err.name() << err.message();
                emit registrationFailed(err.message());
            }
            setRegistered(false);
            return;
        }

        setRegistered(true);
        requestDefaultAgent();
    });
}

void BluezAgent::requestDefaultAgent() {
    auto bus = QDBusConnection::systemBus();
    if (!bus.isConnected())
        return;

    auto msg = QDBusMessage::createMethodCall(QLatin1StringView(BLUEZ_SERVICE), QLatin1StringView(AGENT_MANAGER_PATH),
        QLatin1StringView(AGENT_MANAGER_IFACE), u"RequestDefaultAgent"_s);
    msg << QVariant::fromValue(QDBusObjectPath(QLatin1StringView(AGENT_OBJECT_PATH)));

    auto* watcher = new QDBusPendingCallWatcher(bus.asyncCall(msg), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self;
        self->deleteLater();

        if (reply.isError()) {
            const auto err = reply.error();
            qCWarning(lcBluezAgent) << "RequestDefaultAgent failed:" << err.name() << err.message();
        } else {
            qCInfo(lcBluezAgent) << "Registered default BlueZ pairing agent at" << AGENT_OBJECT_PATH;
        }
    });
}

void BluezAgent::respondConfirmation(bool accept) {
    if (!m_hasPendingReply)
        return;

    if (m_requestType != u"confirm"_s && m_requestType != u"authorize"_s && m_requestType != u"authorizeService"_s)
        return;

    if (accept) {
        finishWithReply(m_pendingReply.createReply());
    } else {
        abortPendingReply(u"org.bluez.Error.Rejected"_s, u"Pairing rejected by user"_s);
    }
}

void BluezAgent::respondPin(const QString& pin) {
    if (!m_hasPendingReply || m_requestType != u"pin"_s)
        return;

    const QString cleaned = pin.trimmed();
    if (cleaned.isEmpty() || cleaned.length() > 16) {
        abortPendingReply(u"org.bluez.Error.Rejected"_s, u"Invalid PIN length"_s);
        return;
    }

    finishWithReply(m_pendingReply.createReply(QVariant::fromValue(cleaned)));
}

void BluezAgent::respondPasskey(int passkeyValue) {
    if (!m_hasPendingReply || m_requestType != u"passkey"_s)
        return;

    if (passkeyValue < 0 || passkeyValue > 999999) {
        abortPendingReply(u"org.bluez.Error.Rejected"_s, u"Passkey out of range (000000-999999)"_s);
        return;
    }

    finishWithReply(m_pendingReply.createReply(QVariant::fromValue(static_cast<quint32>(passkeyValue))));
}

void BluezAgent::cancelPending() {
    if (m_hasPendingReply) {
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Pairing cancelled by user"_s);
        emit requestCancelled();
        return;
    }

    if (m_displayActive) {
        clearRequestState();
        emit requestCancelled();
    }
}

void BluezAgent::handleRelease() {
    m_timeoutTimer.stop();
    if (m_hasPendingReply) {
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Agent released"_s);
    } else if (m_displayActive) {
        clearRequestState();
    }
    setRegistered(false);
}

void BluezAgent::handleCancel() {
    m_timeoutTimer.stop();
    if (m_hasPendingReply || m_displayActive) {
        clearRequestState();
        emit requestCancelled();
    }
}

void BluezAgent::handleDisplayPinCode(const QDBusObjectPath& device, const QString& pincode) {
    if (m_hasPendingReply) {
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Superseded by display PIN request"_s);
    }

    const QString path = device.path();
    const QString addr = addressFromObjectPath(path);
    m_requestType = u"displayPin"_s;
    m_devicePath = path;
    m_deviceAddress = addr;
    m_deviceName = addr;
    m_passkey = pincode;
    m_entered = 0;
    m_serviceUuid.clear();
    m_displayActive = true;

    emit pendingChanged();
    emit requestReceived(m_requestType, m_deviceAddress, m_passkey);
    resolveDeviceAlias(path);
}

void BluezAgent::handleDisplayPasskey(const QDBusObjectPath& device, quint32 passkeyValue, quint16 enteredCount) {
    if (m_hasPendingReply) {
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Superseded by display passkey request"_s);
    }

    const QString path = device.path();
    const QString addr = addressFromObjectPath(path);
    const QString formatted = formatSixDigitPasskey(passkeyValue);
    const bool sameDisplay = m_displayActive && m_requestType == u"displayPasskey"_s && m_devicePath == path;

    m_requestType = u"displayPasskey"_s;
    m_devicePath = path;
    m_deviceAddress = addr;
    if (!sameDisplay || m_deviceName.isEmpty())
        m_deviceName = addr;
    m_passkey = formatted;
    m_entered = static_cast<int>(enteredCount);
    m_serviceUuid.clear();
    m_displayActive = true;

    emit pendingChanged();
    if (!sameDisplay) {
        emit requestReceived(m_requestType, m_deviceAddress, m_passkey);
        resolveDeviceAlias(path);
    }
}

void BluezAgent::beginDelayedRequest(detail::BluezAgentEndpoint* endpoint, const QString& type,
    const QDBusObjectPath& device, const QString& passkeyStr, const QString& uuid) {
    if (m_hasPendingReply) {
        abortPendingReply(u"org.bluez.Error.Canceled"_s, u"Superseded by a newer request"_s);
    }

    if (endpoint && endpoint->isCalledFromDBus()) {
        endpoint->markDelayedReply();
        m_pendingReply = endpoint->currentMessage();
        m_hasPendingReply = true;
    } else {
        m_pendingReply = QDBusMessage{};
        m_hasPendingReply = false;
    }

    const QString path = device.path();
    const QString addr = addressFromObjectPath(path);

    m_displayActive = false;
    m_requestType = type;
    m_devicePath = path;
    m_deviceAddress = addr;
    m_deviceName = addr;
    m_passkey = passkeyStr;
    m_entered = 0;
    m_serviceUuid = uuid;

    if (m_hasPendingReply) {
        m_timeoutTimer.start();
    }

    emit pendingChanged();
    emit requestReceived(m_requestType, m_deviceAddress, m_passkey);
    resolveDeviceAlias(path);
}

void BluezAgent::finishWithReply(const QDBusMessage& reply) {
    m_timeoutTimer.stop();
    auto bus = QDBusConnection::systemBus();
    if (bus.isConnected() && m_pendingReply.type() == QDBusMessage::MethodCallMessage) {
        bus.send(reply);
    }
    clearRequestState();
}

void BluezAgent::abortPendingReply(const QString& dbusErrorName, const QString& errorMessage) {
    m_timeoutTimer.stop();
    auto bus = QDBusConnection::systemBus();
    if (bus.isConnected() && m_pendingReply.type() == QDBusMessage::MethodCallMessage) {
        bus.send(m_pendingReply.createErrorReply(dbusErrorName, errorMessage));
    }
    clearRequestState();
}

void BluezAgent::clearRequestState() {
    const bool hadState = m_hasPendingReply || m_displayActive || !m_requestType.isEmpty();
    m_hasPendingReply = false;
    m_displayActive = false;
    m_pendingReply = QDBusMessage{};
    m_requestType.clear();
    m_devicePath.clear();
    m_deviceAddress.clear();
    m_deviceName.clear();
    m_passkey.clear();
    m_entered = 0;
    m_serviceUuid.clear();
    if (hadState)
        emit pendingChanged();
}

void BluezAgent::resolveDeviceAlias(const QString& path) {
    if (path.isEmpty())
        return;

    auto bus = QDBusConnection::systemBus();
    if (!bus.isConnected())
        return;

    auto msg = QDBusMessage::createMethodCall(
        QLatin1StringView(BLUEZ_SERVICE), path, QLatin1StringView(DBUS_PROPS_IFACE), u"Get"_s);
    msg << QLatin1StringView(DEVICE_IFACE) << u"Alias"_s;

    auto* watcher = new QDBusPendingCallWatcher(bus.asyncCall(msg), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, path](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<QDBusVariant> reply = *self;
        self->deleteLater();

        if (!reply.isValid() || m_devicePath != path)
            return;

        const QString alias = reply.value().variant().toString().trimmed();
        if (!alias.isEmpty() && alias != m_deviceName) {
            m_deviceName = alias;
            emit pendingChanged();
        }
    });
}

void BluezAgent::setRegistered(bool value) {
    if (m_registered == value)
        return;
    m_registered = value;
    emit registeredChanged();
}

QString BluezAgent::addressFromObjectPath(const QString& objectPath) {
    const qsizetype idx = objectPath.lastIndexOf(u"/dev_"_s);
    if (idx < 0)
        return objectPath;
    QString mac = objectPath.mid(idx + 5);
    mac.replace(u'_', u':');
    return mac;
}

QString BluezAgent::formatSixDigitPasskey(quint32 value) {
    return QString::number(value).rightJustified(6, u'0');
}

} // namespace caelestia::services
