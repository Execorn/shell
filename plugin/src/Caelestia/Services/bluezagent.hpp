#pragma once

#include <QtDBus/qdbusabstractadaptor.h>
#include <QtDBus/qdbuscontext.h>
#include <QtDBus/qdbusextratypes.h>
#include <QtDBus/qdbusmessage.h>
#include <qobject.h>
#include <qqmlintegration.h>
#include <qstring.h>
#include <qtimer.h>

class QDBusServiceWatcher;

namespace caelestia::services {

class BluezAgent;

namespace detail {

/// D-Bus host object implementing QDBusContext for org.bluez.Agent1 delayed replies.
class BluezAgentEndpoint final : public QObject, protected QDBusContext {
    Q_OBJECT

public:
    explicit BluezAgentEndpoint(BluezAgent* agent);

    [[nodiscard]] bool isCalledFromDBus() const { return calledFromDBus(); }

    [[nodiscard]] QDBusMessage currentMessage() const { return message(); }

    void markDelayedReply() const { setDelayedReply(true); }

private:
    BluezAgent* m_agent;
    friend class BluezAgentAdaptor;
};

/// QDBusAbstractAdaptor exposing exact org.bluez.Agent1 method signatures.
class BluezAgentAdaptor final : public QDBusAbstractAdaptor {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.bluez.Agent1")

public:
    explicit BluezAgentAdaptor(BluezAgentEndpoint* endpoint);

public slots:
    void Release();
    QString RequestPinCode(const QDBusObjectPath& device);
    void DisplayPinCode(const QDBusObjectPath& device, const QString& pincode);
    quint32 RequestPasskey(const QDBusObjectPath& device);
    void DisplayPasskey(const QDBusObjectPath& device, quint32 passkey, quint16 entered);
    void RequestConfirmation(const QDBusObjectPath& device, quint32 passkey);
    void RequestAuthorization(const QDBusObjectPath& device);
    void AuthorizeService(const QDBusObjectPath& device, const QString& uuid);
    void Cancel();

private:
    BluezAgentEndpoint* m_endpoint;
};

} // namespace detail

/// QML singleton registering a BlueZ org.bluez.Agent1 pairing agent on the system D-Bus.
class BluezAgent final : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(bool registered READ registered NOTIFY registeredChanged FINAL)
    Q_PROPERTY(bool hasPendingRequest READ hasPendingRequest NOTIFY pendingChanged FINAL)
    Q_PROPERTY(bool needsReply READ needsReply NOTIFY pendingChanged FINAL)
    Q_PROPERTY(QString requestType READ requestType NOTIFY pendingChanged FINAL)
    Q_PROPERTY(QString devicePath READ devicePath NOTIFY pendingChanged FINAL)
    Q_PROPERTY(QString deviceAddress READ deviceAddress NOTIFY pendingChanged FINAL)
    Q_PROPERTY(QString deviceName READ deviceName NOTIFY pendingChanged FINAL)
    Q_PROPERTY(QString passkey READ passkey NOTIFY pendingChanged FINAL)
    Q_PROPERTY(int entered READ entered NOTIFY pendingChanged FINAL)
    Q_PROPERTY(QString serviceUuid READ serviceUuid NOTIFY pendingChanged FINAL)

public:
    explicit BluezAgent(QObject* parent = nullptr);
    ~BluezAgent() override;

    [[nodiscard]] bool registered() const { return m_registered; }

    [[nodiscard]] bool hasPendingRequest() const { return m_hasPendingReply || m_displayActive; }

    [[nodiscard]] bool needsReply() const { return m_hasPendingReply; }

    [[nodiscard]] QString requestType() const { return m_requestType; }

    [[nodiscard]] QString devicePath() const { return m_devicePath; }

    [[nodiscard]] QString deviceAddress() const { return m_deviceAddress; }

    [[nodiscard]] QString deviceName() const { return m_deviceName; }

    [[nodiscard]] QString passkey() const { return m_passkey; }

    [[nodiscard]] int entered() const { return m_entered; }

    [[nodiscard]] QString serviceUuid() const { return m_serviceUuid; }

    Q_INVOKABLE void registerAgent();
    Q_INVOKABLE void respondConfirmation(bool accept);
    Q_INVOKABLE void respondPin(const QString& pin);
    Q_INVOKABLE void respondPasskey(int passkeyValue);
    Q_INVOKABLE void cancelPending();

signals:
    void registeredChanged();
    void pendingChanged();
    void requestReceived(const QString& type, const QString& address, const QString& passkey);
    void requestCancelled();
    void registrationFailed(const QString& reason);

private:
    friend class detail::BluezAgentAdaptor;

    void handleRelease();
    void handleCancel();
    void handleDisplayPinCode(const QDBusObjectPath& device, const QString& pincode);
    void handleDisplayPasskey(const QDBusObjectPath& device, quint32 passkeyValue, quint16 enteredCount);
    void beginDelayedRequest(detail::BluezAgentEndpoint* endpoint, const QString& type, const QDBusObjectPath& device,
        const QString& passkeyStr, const QString& uuid);

    void finishWithReply(const QDBusMessage& reply);
    void abortPendingReply(const QString& dbusErrorName, const QString& errorMessage);
    void clearRequestState();
    void requestDefaultAgent();
    void resolveDeviceAlias(const QString& path);
    void setRegistered(bool value);

    [[nodiscard]] static QString addressFromObjectPath(const QString& objectPath);
    [[nodiscard]] static QString formatSixDigitPasskey(quint32 value);

    detail::BluezAgentEndpoint* m_endpoint = nullptr;
    detail::BluezAgentAdaptor* m_adaptor = nullptr;
    QDBusServiceWatcher* m_serviceWatcher = nullptr;
    QTimer m_timeoutTimer;

    bool m_objectExported = false;
    bool m_registered = false;
    bool m_hasPendingReply = false;
    bool m_displayActive = false;

    QDBusMessage m_pendingReply;
    QString m_requestType;
    QString m_devicePath;
    QString m_deviceAddress;
    QString m_deviceName;
    QString m_passkey;
    int m_entered = 0;
    QString m_serviceUuid;
};

} // namespace caelestia::services
