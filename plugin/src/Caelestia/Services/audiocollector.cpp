#include "audiocollector.hpp"

#include "service.hpp"
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <pipewire/pipewire.h>
#include <qloggingcategory.h>
#include <qmutex.h>
#include <spa/param/audio/format-utils.h>
#include <spa/param/latency-utils.h>
#include <span>
#include <stop_token>
#include <vector>

Q_LOGGING_CATEGORY(lcAc, "caelestia.services.ac", QtInfoMsg)
Q_LOGGING_CATEGORY(lcAcWorker, "caelestia.services.ac.worker", QtInfoMsg)

namespace caelestia::services {

PipeWireWorker::PipeWireWorker(std::stop_token token, AudioCollector* collector)
    : m_loop(nullptr)
    , m_stream(nullptr)
    , m_timer(nullptr)
    , m_wakeup(nullptr)
    , m_idle(true)
    , m_wasConnected(false)
    , m_token(std::move(token))
    , m_collector(collector) {
    pw_init(nullptr, nullptr);

    m_loop = pw_main_loop_new(nullptr);
    if (!m_loop) {
        qCWarning(lcAcWorker) << "init: failed to create PipeWire main loop";
        pw_deinit();
        return;
    }

    pw_loop* const loop = pw_main_loop_get_loop(m_loop);

    m_wakeup = pw_loop_add_event(
        loop,
        [](void* data, uint64_t) {
            auto* self = static_cast<PipeWireWorker*>(data);
            if (self->m_token.stop_requested()) {
                pw_main_loop_quit(self->m_loop);
            }
        },
        this);
    if (!m_wakeup) {
        qCWarning(lcAcWorker) << "init: failed to create wakeup event";
        cleanup();
        return;
    }

    timespec timeout = { 0, 10 * SPA_NSEC_PER_MSEC };
    m_timer = pw_loop_add_timer(loop, handleTimeout, this);
    if (!m_timer) {
        qCWarning(lcAcWorker) << "init: failed to create timer";
        cleanup();
        return;
    }
    pw_loop_update_timer(loop, m_timer, &timeout, &timeout, false);

    auto props = pw_properties_new(
        PW_KEY_MEDIA_TYPE, "Audio", PW_KEY_MEDIA_CATEGORY, "Capture", PW_KEY_MEDIA_ROLE, "Music", nullptr);
    pw_properties_set(props, PW_KEY_STREAM_CAPTURE_SINK, "true");
    pw_properties_set(props, PW_KEY_NODE_PASSIVE, "true");
    pw_properties_set(props, PW_KEY_NODE_VIRTUAL, "true");
    pw_properties_set(props, PW_KEY_STREAM_DONT_REMIX, "false");
    pw_properties_set(props, "channelmix.upmix", "true");

    std::vector<uint8_t> buffer(ac::CHUNK_SIZE);
    spa_pod_builder b;
    spa_pod_builder_init(&b, buffer.data(), static_cast<quint32>(buffer.size()));

    spa_audio_info_raw info{};
    info.format = SPA_AUDIO_FORMAT_S16;
    info.rate = ac::SAMPLE_RATE;
    info.channels = 1;

    const spa_pod* params[1];
    params[0] = spa_format_audio_raw_build(&b, SPA_PARAM_EnumFormat, &info);

    pw_stream_events events{};
    events.version = PW_VERSION_STREAM_EVENTS;
    events.state_changed = [](void* data, pw_stream_state, pw_stream_state state, const char*) {
        auto* self = static_cast<PipeWireWorker*>(data);
        self->streamStateChanged(state);
    };
    events.process = [](void* data) {
        auto* self = static_cast<PipeWireWorker*>(data);
        self->processStream();
    };

    m_stream = pw_stream_new_simple(loop, "caelestia-shell", props, &events, this);
    if (!m_stream) {
        qCWarning(lcAcWorker) << "init: failed to create stream";
        cleanup();
        return;
    }

    const int success = pw_stream_connect(m_stream, PW_DIRECTION_INPUT, PW_ID_ANY,
        static_cast<pw_stream_flags>(
            PW_STREAM_FLAG_AUTOCONNECT | PW_STREAM_FLAG_MAP_BUFFERS | PW_STREAM_FLAG_RT_PROCESS),
        params, 1);
    if (success < 0) {
        qCWarning(lcAcWorker) << "init: failed to connect stream";
        cleanup();
        return;
    }

    {
        std::stop_callback stopCb(m_token, [this, loop]() {
            pw_loop_signal_event(loop, m_wakeup);
        });
        if (!m_token.stop_requested()) {
            pw_main_loop_run(m_loop);
        }
    }

    cleanup();
}

void PipeWireWorker::cleanup() {
    if (m_stream) {
        pw_stream_destroy(m_stream);
        m_stream = nullptr;
    }
    if (m_loop) {
        pw_loop* const loop = pw_main_loop_get_loop(m_loop);
        if (m_timer) {
            pw_loop_destroy_source(loop, m_timer);
            m_timer = nullptr;
        }
        if (m_wakeup) {
            pw_loop_destroy_source(loop, m_wakeup);
            m_wakeup = nullptr;
        }
        pw_main_loop_destroy(m_loop);
        m_loop = nullptr;
    }
    pw_deinit();
}

void PipeWireWorker::handleTimeout(void* data, uint64_t expirations) {
    auto* self = static_cast<PipeWireWorker*>(data);

    if (self->m_token.stop_requested()) {
        pw_main_loop_quit(self->m_loop);
        return;
    }

    if (!self->m_idle) {
        if (expirations < 10) {
            self->m_collector->clearBuffer();
        } else {
            self->m_idle = true;
            timespec timeout = { 0, 500 * SPA_NSEC_PER_MSEC };
            pw_loop_update_timer(pw_main_loop_get_loop(self->m_loop), self->m_timer, &timeout, &timeout, false);
        }
    }
}

void PipeWireWorker::streamStateChanged(pw_stream_state state) {
    m_idle = false;
    switch (state) {
    case PW_STREAM_STATE_CONNECTING:
        m_wasConnected = true;
        break;
    case PW_STREAM_STATE_PAUSED: {
        m_wasConnected = true;
        timespec timeout = { 0, 10 * SPA_NSEC_PER_MSEC };
        pw_loop_update_timer(pw_main_loop_get_loop(m_loop), m_timer, &timeout, &timeout, false);
        break;
    }
    case PW_STREAM_STATE_STREAMING:
        m_wasConnected = true;
        pw_loop_update_timer(pw_main_loop_get_loop(m_loop), m_timer, nullptr, nullptr, false);
        break;
    case PW_STREAM_STATE_UNCONNECTED:
        if (m_wasConnected) {
            pw_main_loop_quit(m_loop);
        }
        break;
    case PW_STREAM_STATE_ERROR:
        pw_main_loop_quit(m_loop);
        break;
    }
}

void PipeWireWorker::processStream() {
    if (m_token.stop_requested()) {
        pw_main_loop_quit(m_loop);
        return;
    }

    pw_buffer* const buffer = pw_stream_dequeue_buffer(m_stream);
    if (buffer == nullptr) {
        return;
    }

    const spa_buffer* buf = buffer->buffer;
    if (buf != nullptr && buf->n_datas > 0 && buf->datas != nullptr && buf->datas[0].data != nullptr &&
        buf->datas[0].chunk != nullptr) {
        const spa_data& d = buf->datas[0];
        const spa_chunk& c = *d.chunk;
        if ((static_cast<uint32_t>(c.flags) & SPA_CHUNK_FLAG_CORRUPTED) == 0 && c.size > 0 && c.offset < d.maxsize) {
            const quint32 availableBytes = std::min(c.size, d.maxsize - c.offset);
            const quint32 count = availableBytes / static_cast<quint32>(sizeof(qint16));
            if (count > 0) {
                const auto* base = static_cast<const std::byte*>(d.data) + c.offset;
                const auto* samples = reinterpret_cast<const qint16*>(base);
                m_collector->loadChunk(samples, count);
            }
        }
    }

    pw_stream_queue_buffer(m_stream, buffer);
}

AudioCollector& AudioCollector::instance() {
    static AudioCollector instance;
    return instance;
}

AudioCollector* AudioCollector::existingInstance() {
    if (s_destroyed.load(std::memory_order_acquire)) {
        return nullptr;
    }
    return s_instance.load(std::memory_order_acquire);
}

void AudioCollector::clearBuffer() {
    const std::scoped_lock lock(m_samplesLock);
    m_samples.clear();
    m_discardPending.store(true, std::memory_order_release);
}

void AudioCollector::loadChunk(const qint16* samples, quint32 count) {
    if (m_discardPending.exchange(false, std::memory_order_acquire)) {
        m_pending.clear();
    }

    const auto toFloat = [](qint16 sample) {
        return static_cast<float>(sample) / 32768.0f;
    };

    // Called on the RT thread, so stash the chunk until the next callback rather than wait on a reader
    const std::unique_lock lock(m_samplesLock, std::try_to_lock);
    if (!lock.owns_lock()) {
        m_pending.push(std::span(samples, count), toFloat);
        return;
    }

    m_pending.pushTo(m_samples);
    m_pending.clear();
    m_samples.push(std::span(samples, count), toFloat);
}

template <typename T> quint32 AudioCollector::readLatest(T* out, quint32 count) {
    if (count == 0 || count > ac::CHUNK_SIZE) {
        count = ac::CHUNK_SIZE;
    }

    const std::span dest(out, count);
    const std::scoped_lock lock(m_samplesLock);

    // Pad the front with silence until the window has filled after a clear
    const auto available = static_cast<size_t>(std::min(m_samples.count(), static_cast<qsizetype>(count)));
    std::ranges::fill(dest.first(count - available), T(0));
    m_samples.copyLatest(dest.last(available), [](float sample) {
        return static_cast<T>(sample);
    });

    return count;
}

quint32 AudioCollector::readChunk(float* out, quint32 count) {
    return readLatest(out, count);
}

quint32 AudioCollector::readChunk(double* out, quint32 count) {
    return readLatest(out, count);
}

AudioCollector::AudioCollector(QObject* parent)
    : Service(parent)
    , m_samples(ac::CHUNK_SIZE)
    , m_pending(ac::CHUNK_SIZE)
    , m_discardPending(false) {
    s_instance.store(this, std::memory_order_release);
}

AudioCollector::~AudioCollector() {
    s_destroyed.store(true, std::memory_order_release);
    s_instance.store(nullptr, std::memory_order_release);
    AudioCollector::stop();
}

void AudioCollector::start() {
    if (m_thread.joinable()) {
        return;
    }

    clearBuffer();

    m_thread = std::jthread([this](std::stop_token token) {
        std::mutex waitMutex;
        std::condition_variable_any waitCv;
        while (!token.stop_requested()) {
            PipeWireWorker worker(token, this);
            if (!token.stop_requested()) {
                std::unique_lock lock(waitMutex);
                waitCv.wait_for(lock, token, std::chrono::milliseconds(500), [&token]() {
                    return token.stop_requested();
                });
            }
        }
    });
}

void AudioCollector::stop() {
    if (m_thread.joinable()) {
        m_thread.request_stop();
        m_thread.join();
    }
}

} // namespace caelestia::services
