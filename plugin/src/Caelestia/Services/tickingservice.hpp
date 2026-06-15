#pragma once

#include "service.hpp"

namespace caelestia::services {

class TickingService : public Service {
    Q_OBJECT

    Q_PROPERTY(int updateInterval READ updateInterval NOTIFY updateIntervalChanged)

public:
    explicit TickingService(QObject* parent = nullptr);
    ~TickingService() override;

    [[nodiscard]] int updateInterval() const;

signals:
    void updateIntervalChanged();

protected:
    void start() final;
    void stop() final;

    virtual void tick() {}

private:
    void applyInterval(int ms);

    QTimer* m_timer;
    int m_interval = 1000;
    bool m_running = false;
};

} // namespace caelestia::services
