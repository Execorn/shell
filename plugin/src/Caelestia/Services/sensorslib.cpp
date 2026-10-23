#include "sensorslib.hpp"

#include <atomic>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <qloggingcategory.h>
#include <sensors/sensors.h>
#include <vector>

Q_LOGGING_CATEGORY(lcSensorsLib, "caelestia.services.sensorslib", QtInfoMsg)

namespace caelestia::services::sensorslib {

namespace {

struct SensorInput {
    const sensors_chip_name* chip = nullptr;
    int subfeatureNr = -1;
};

std::atomic<bool> g_initOk{ false };
std::once_flag g_initFlag;
std::vector<SensorInput> g_cpuPrimary;
std::vector<SensorInput> g_cpuFallback;
std::vector<SensorInput> g_gpuPrimary;
std::vector<SensorInput> g_gpuFallback;

[[nodiscard]] std::optional<double> readSensorInput(const SensorInput& input) {
    double value = 0.0;
    if (sensors_get_value(input.chip, input.subfeatureNr, &value) != 0) {
        return std::nullopt;
    }
    return value;
}

[[nodiscard]] QByteArray featureLabel(const sensors_chip_name* chip, const sensors_feature* feat) {
    char* raw = sensors_get_label(chip, feat);
    if (!raw) {
        return {};
    }
    QByteArray out(raw);
    std::free(raw);
    return out;
}

bool labelEquals(const QByteArray& label, const char* literal) {
    return label == QByteArrayView(literal);
}

bool labelStartsWith(const QByteArray& label, const char* prefix) {
    const auto n = std::strlen(prefix);
    return static_cast<size_t>(label.size()) >= n && std::memcmp(label.constData(), prefix, n) == 0;
}

void doInit() {
    if (sensors_init(nullptr) != 0) {
        qCWarning(lcSensorsLib, "sensors_init failed");
        g_initOk.store(false, std::memory_order_release);
        return;
    }

    int chipNr = 0;
    while (const sensors_chip_name* chip = sensors_get_detected_chips(nullptr, &chipNr)) {
        const bool isPci = (chip->bus.type == SENSORS_BUS_TYPE_PCI);

        int featNr = 0;
        while (const sensors_feature* feat = sensors_get_features(chip, &featNr)) {
            if (feat->type != SENSORS_FEATURE_TEMP) {
                continue;
            }
            const sensors_subfeature* sf = sensors_get_subfeature(chip, feat, SENSORS_SUBFEATURE_TEMP_INPUT);
            if (!sf) {
                continue;
            }
            const QByteArray label = featureLabel(chip, feat);
            if (label.isEmpty()) {
                continue;
            }

            const SensorInput input{ chip, sf->number };

            if (labelStartsWith(label, "Package id ") || labelEquals(label, "Tdie")) {
                g_cpuPrimary.push_back(input);
            } else if (labelEquals(label, "Tctl")) {
                g_cpuFallback.push_back(input);
            }

            if (isPci) {
                const bool tempIndexed = labelStartsWith(label, "temp") && label.size() > 4 &&
                                         std::isdigit(static_cast<unsigned char>(label[4]));
                const bool isPrimary = tempIndexed || labelEquals(label, "GPU core") || labelEquals(label, "edge");
                const bool isFallback = labelEquals(label, "junction") || labelEquals(label, "mem");

                if (isPrimary) {
                    g_gpuPrimary.push_back(input);
                } else if (isFallback) {
                    g_gpuFallback.push_back(input);
                }
            }
        }
    }

    g_initOk.store(true, std::memory_order_release);
    std::atexit([] {
        if (g_initOk.load(std::memory_order_acquire)) {
            sensors_cleanup();
        }
    });
}

} // namespace

void ensureInit() {
    std::call_once(g_initFlag, doInit);
}

std::optional<double> cpuPackageTemp() {
    ensureInit();
    if (!g_initOk.load(std::memory_order_acquire)) {
        return std::nullopt;
    }

    std::optional<double> primary;
    for (const SensorInput& input : g_cpuPrimary) {
        if (auto v = readSensorInput(input)) {
            primary = v;
        }
    }
    if (primary.has_value()) {
        return primary;
    }

    std::optional<double> fallback;
    for (const SensorInput& input : g_cpuFallback) {
        if (auto v = readSensorInput(input)) {
            fallback = v;
        }
    }
    return fallback;
}

std::optional<double> gpuPciAverageTemp() {
    ensureInit();
    if (!g_initOk.load(std::memory_order_acquire)) {
        return std::nullopt;
    }

    double sumPrimary = 0.0;
    int countPrimary = 0;
    for (const SensorInput& input : g_gpuPrimary) {
        if (const auto v = readSensorInput(input)) {
            sumPrimary += *v;
            ++countPrimary;
        }
    }
    if (countPrimary > 0) {
        return sumPrimary / countPrimary;
    }

    double sumFallback = 0.0;
    int countFallback = 0;
    for (const SensorInput& input : g_gpuFallback) {
        if (const auto v = readSensorInput(input)) {
            sumFallback += *v;
            ++countFallback;
        }
    }
    if (countFallback > 0) {
        return sumFallback / countFallback;
    }
    return std::nullopt;
}

} // namespace caelestia::services::sensorslib
