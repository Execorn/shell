#pragma once

#include <qobject.h>
#include <qset.h>

namespace caelestia::services {

class Service : public QObject {
    Q_OBJECT

public:
    explicit Service(QObject* parent = nullptr);
    virtual ~Service();

    void ref(QObject* sender);
    void unref(QObject* sender);

private:
    QSet<QObject*> m_refs;
    bool m_destroying = false;

    virtual void start() {}
    virtual void stop() {}
};

} // namespace caelestia::services
