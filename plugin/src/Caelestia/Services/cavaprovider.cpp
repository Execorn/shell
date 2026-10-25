#include "cavaprovider.hpp"

#include "audiocollector.hpp"
#include "audioprovider.hpp"
#include <QLibrary>
#include <cava/cavacore.h>
#include <cstddef>
#include <qloggingcategory.h>

Q_LOGGING_CATEGORY(lcCava, "caelestia.services.cava", QtInfoMsg)
Q_LOGGING_CATEGORY(lcCavaProcessor, "caelestia.services.cava.processor", QtInfoMsg)

namespace caelestia::services {

namespace {

struct CavaApi {
    using CavaInitFn = struct cava_plan* (*)(int, unsigned int, int, int, double, int, int);
    using CavaExecuteFn = void (*)(double*, int, double*, struct cava_plan*);
    using CavaDestroyFn = void (*)(struct cava_plan*);

    QLibrary lib{ QStringLiteral("cava"), 1 };
    CavaInitFn cavaInit = nullptr;
    CavaExecuteFn cavaExecute = nullptr;
    CavaDestroyFn cavaDestroy = nullptr;
    bool valid = false;

    CavaApi() {
        if (!lib.load()) {
            lib.setFileName(QStringLiteral("libcava.so.1"));
            if (!lib.load()) {
                return;
            }
        }
        cavaInit = reinterpret_cast<CavaInitFn>(lib.resolve("cava_init"));
        cavaExecute = reinterpret_cast<CavaExecuteFn>(lib.resolve("cava_execute"));
        cavaDestroy = reinterpret_cast<CavaDestroyFn>(lib.resolve("cava_destroy"));
        valid = cavaInit && cavaExecute && cavaDestroy;
    }

    static const CavaApi& instance() {
        static const CavaApi api;
        return api;
    }
};

} // namespace

CavaProcessor::CavaProcessor(QObject* parent)
    : AudioProcessor(parent)
    , m_plan(nullptr)
    , m_in(nullptr)
    , m_out(nullptr)
    , m_bars(0) {}

CavaProcessor::~CavaProcessor() {
    cleanup();
    delete[] m_in;
}

void CavaProcessor::init() {
    AudioProcessor::init();
    if (!m_in) {
        m_in = new double[ac::CHUNK_SIZE];
    }
    initCava();
}

void CavaProcessor::process() {
    if (!m_plan || m_bars == 0 || !m_in || !m_out) {
        return;
    }

    const int count = static_cast<int>(AudioCollector::instance().readChunk(m_in));

    // Process in data via cava
    CavaApi::instance().cavaExecute(m_in, count, m_out, m_plan);

    // Apply monstercat filter
    QVector<double> values(m_bars);

    // Left to right pass
    const double inv = 1.0 / 1.5;
    double carry = 0.0;
    for (int i = 0; i < m_bars; ++i) {
        carry = std::max(m_out[i], carry * inv);
        values[i] = carry;
    }

    // Right to left pass and combine
    carry = 0.0;
    for (int i = m_bars - 1; i >= 0; --i) {
        carry = std::max(m_out[i], carry * inv);
        values[i] = std::max(values[i], carry);
    }

    // Update values
    if (values != m_values) {
        m_values = std::move(values);
        emit valuesChanged(m_values);
    }
}

void CavaProcessor::setBars(int bars) {
    if (bars < 0) {
        qCWarning(lcCavaProcessor) << "setBars: bars must be greater than 0. Setting to 0.";
        bars = 0;
    }

    if (m_bars != bars) {
        m_bars = bars;
        reload();
    }
}

void CavaProcessor::reload() {
    cleanup();
    initCava();
}

void CavaProcessor::cleanup() {
    if (m_plan) {
        if (CavaApi::instance().valid) {
            CavaApi::instance().cavaDestroy(m_plan);
        }
        m_plan = nullptr;
    }

    if (m_out) {
        delete[] m_out;
        m_out = nullptr;
    }
}

void CavaProcessor::initCava() {
    if (m_plan || m_bars == 0 || !m_in) {
        return;
    }

    const auto& api = CavaApi::instance();
    if (!api.valid) {
        return;
    }

    m_plan = api.cavaInit(m_bars, ac::SAMPLE_RATE, 1, 1, 0.85, 50, 10000);
    m_out = new double[static_cast<size_t>(m_bars)];
}

CavaProvider::CavaProvider(QObject* parent)
    : AudioProvider(parent)
    , m_bars(0)
    , m_values(m_bars, 0.0) {
    m_processor = new CavaProcessor();
    init();

    connect(static_cast<CavaProcessor*>(m_processor), &CavaProcessor::valuesChanged, this, &CavaProvider::updateValues);
}

int CavaProvider::bars() const {
    return m_bars;
}

void CavaProvider::setBars(int bars) {
    if (bars < 0) {
        qCWarning(lcCava) << "setBars: bars must be greater than 0. Setting to 0.";
        bars = 0;
    }

    if (m_bars == bars) {
        return;
    }

    m_values.resize(bars, 0.0);
    m_bars = bars;
    emit barsChanged();
    emit valuesChanged();

    QMetaObject::invokeMethod(
        static_cast<CavaProcessor*>(m_processor), &CavaProcessor::setBars, Qt::QueuedConnection, bars);
}

QVector<double> CavaProvider::values() const {
    return m_values;
}

void CavaProvider::updateValues(QVector<double> values) {
    if (values != m_values) {
        m_values = values;
        emit valuesChanged();
    }
}

} // namespace caelestia::services
