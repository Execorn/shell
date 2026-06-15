#include "service.hpp"

#include <qpointer.h>

namespace caelestia::services {

Service::Service(QObject* parent)
    : QObject(parent) {}

Service::~Service() {
    m_destroying = true;
    for (QObject* ref : m_refs) {
        QObject::disconnect(ref, &QObject::destroyed, this, &Service::unref);
    }
    m_refs.clear();
}

void Service::ref(QObject* sender) {
    if (m_destroying) {
        return;
    }
    if (m_refs.isEmpty()) {
        start();
    }

    QObject::connect(sender, &QObject::destroyed, this, &Service::unref);
    m_refs << sender;
}

void Service::unref(QObject* sender) {
    if (m_destroying) {
        return;
    }
    if (m_refs.remove(sender) && m_refs.isEmpty()) {
        stop();
    }
}

} // namespace caelestia::services
