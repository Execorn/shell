#include "beattracker.hpp"

#include "audiocollector.hpp"
#include "audioprovider.hpp"
#include <qlibrary.h>

namespace caelestia::services {

namespace {

class AubioApi {
public:
    using NewTempoFn = aubio_tempo_t* (*)(const char*, uint_t, uint_t, uint_t);
    using DelTempoFn = void (*)(aubio_tempo_t*);
    using TempoDoFn = void (*)(aubio_tempo_t*, const fvec_t*, fvec_t*);
    using TempoGetBpmFn = smpl_t (*)(aubio_tempo_t*);
    using NewFvecFn = fvec_t* (*)(uint_t);
    using DelFvecFn = void (*)(fvec_t*);

    static const AubioApi& instance() {
        static const AubioApi s_api;
        return s_api;
    }

    [[nodiscard]] bool available() const { return m_available; }

    NewTempoFn newTempo = nullptr;
    DelTempoFn delTempo = nullptr;
    TempoDoFn tempoDo = nullptr;
    TempoGetBpmFn tempoGetBpm = nullptr;
    NewFvecFn newFvec = nullptr;
    DelFvecFn delFvec = nullptr;

private:
    AubioApi()
        : m_lib(QStringLiteral("aubio"), 5) {
        if (!m_lib.load()) {
            return;
        }
        newTempo = reinterpret_cast<NewTempoFn>(m_lib.resolve("new_aubio_tempo"));
        delTempo = reinterpret_cast<DelTempoFn>(m_lib.resolve("del_aubio_tempo"));
        tempoDo = reinterpret_cast<TempoDoFn>(m_lib.resolve("aubio_tempo_do"));
        tempoGetBpm = reinterpret_cast<TempoGetBpmFn>(m_lib.resolve("aubio_tempo_get_bpm"));
        newFvec = reinterpret_cast<NewFvecFn>(m_lib.resolve("new_fvec"));
        delFvec = reinterpret_cast<DelFvecFn>(m_lib.resolve("del_fvec"));
        m_available = newTempo && delTempo && tempoDo && tempoGetBpm && newFvec && delFvec;
    }

    QLibrary m_lib;
    bool m_available = false;
};

} // namespace

BeatProcessor::BeatProcessor(QObject* parent)
    : AudioProcessor(parent)
    , m_tempo(nullptr)
    , m_in(nullptr)
    , m_out(nullptr) {}

BeatProcessor::~BeatProcessor() {
    if (!m_tempo && !m_in && !m_out) {
        return;
    }
    const auto& api = AubioApi::instance();
    if (!api.available()) {
        return;
    }
    if (m_tempo) {
        api.delTempo(m_tempo);
    }
    if (m_in) {
        api.delFvec(m_in);
    }
    if (m_out) {
        api.delFvec(m_out);
    }
}

void BeatProcessor::init() {
    AudioProcessor::init();
    const auto& api = AubioApi::instance();
    if (!api.available()) {
        return;
    }
    if (!m_tempo) {
        m_tempo = api.newTempo("default", 1024, ac::CHUNK_SIZE, ac::SAMPLE_RATE);
    }
    if (!m_in) {
        m_in = api.newFvec(ac::CHUNK_SIZE);
    }
    if (!m_out) {
        m_out = api.newFvec(2);
    }
}

void BeatProcessor::process() {
    if (!m_tempo || !m_in || !m_out) {
        return;
    }
    const auto& api = AubioApi::instance();
    if (!api.available()) {
        return;
    }

    AudioCollector::instance().readChunk(m_in->data);

    api.tempoDo(m_tempo, m_in, m_out);
    if (!qFuzzyIsNull(m_out->data[0])) {
        emit beat(api.tempoGetBpm(m_tempo));
    }
}

BeatTracker::BeatTracker(QObject* parent)
    : AudioProvider(parent)
    , m_bpm(120) {
    m_processor = new BeatProcessor();
    init();

    connect(static_cast<BeatProcessor*>(m_processor), &BeatProcessor::beat, this, &BeatTracker::updateBpm);
}

smpl_t BeatTracker::bpm() const {
    return m_bpm;
}

void BeatTracker::updateBpm(smpl_t bpm) {
    if (!qFuzzyCompare(bpm + 1.0f, m_bpm + 1.0f)) {
        m_bpm = bpm;
        emit bpmChanged();
    }
}

} // namespace caelestia::services
