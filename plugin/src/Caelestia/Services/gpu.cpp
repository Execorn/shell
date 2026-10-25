#include "gpu.hpp"

#include "../Config/config.hpp"
#include "../Config/serviceconfig.hpp"
#include "sensorslib.hpp"

#include <qdir.h>
#include <qdiriterator.h>
#include <qfile.h>
#include <qlibrary.h>
#include <qregularexpression.h>

namespace caelestia::services {

namespace {

QStringList gpuBusyFiles() {
    static const QRegularExpression cardRe(QStringLiteral("^card\\d+$"));

    QStringList files;
    QDirIterator it(QStringLiteral("/sys/class/drm"), QDir::Dirs | QDir::NoDotAndDotDot);
    while (it.hasNext()) {
        const QString path = it.next();
        if (!cardRe.match(it.fileName()).hasMatch()) {
            continue;
        }
        const QString busy = path + QStringLiteral("/device/gpu_busy_percent");
        if (QFile::exists(busy)) {
            files << busy;
        }
    }
    return files;
}

QString cleanName(QString s) {
    static const QRegularExpression noise(
        QStringLiteral("\\(R\\)|\\(TM\\)|Graphics"), QRegularExpression::CaseInsensitiveOption);
    static const QRegularExpression spaces(QStringLiteral("\\s+"));
    s.replace(noise, QString());
    s.replace(spaces, QStringLiteral(" "));
    return s.trimmed();
}

QString procNvidiaGpuName() {
    QDirIterator it(QStringLiteral("/proc/driver/nvidia/gpus"), QDir::Dirs | QDir::NoDotAndDotDot);
    while (it.hasNext()) {
        QFile infoFile(it.next() + QStringLiteral("/information"));
        if (!infoFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
            continue;
        }
        const QStringList lines = QString::fromUtf8(infoFile.readAll()).split('\n');
        for (const QString& line : lines) {
            if (line.startsWith(QStringLiteral("Model:"))) {
                const QString model = cleanName(line.mid(6));
                if (!model.isEmpty()) {
                    return model;
                }
            }
        }
    }
    return {};
}

struct NvmlUtilization {
    unsigned int gpu;
    unsigned int memory;
};

class NvmlClient {
public:
    static NvmlClient& instance() {
        static NvmlClient inst;
        return inst;
    }

    [[nodiscard]] QString deviceName() {
        if (!ensureInitialized() || !m_getName) {
            return {};
        }
        char buf[96] = {};
        if (m_getName(m_device, buf, sizeof(buf)) != 0) {
            return {};
        }
        return cleanName(QString::fromUtf8(buf));
    }

    [[nodiscard]] bool queryMetrics(qreal& outUsage, qreal& outTemp) {
        if (!ensureInitialized() || !m_getUtil || !m_getTemp) {
            return false;
        }
        NvmlUtilization util{};
        unsigned int temp = 0;
        if (m_getUtil(m_device, &util) != 0) {
            return false;
        }
        if (m_getTemp(m_device, 0, &temp) != 0) {
            return false;
        }
        outUsage = static_cast<qreal>(util.gpu) / 100.0;
        outTemp = static_cast<qreal>(temp);
        return true;
    }

    void release() {
        if (m_initialized && m_shutdown) {
            m_shutdown();
        }
        m_initialized = false;
        m_available = false;
        m_device = nullptr;
    }

private:
    using DeviceHandle = void*;
    using InitFn = int (*)();
    using ShutdownFn = int (*)();
    using GetHandleByIndexFn = int (*)(unsigned int, DeviceHandle*);
    using GetNameFn = int (*)(DeviceHandle, char*, unsigned int);
    using GetUtilFn = int (*)(DeviceHandle, NvmlUtilization*);
    using GetTempFn = int (*)(DeviceHandle, int, unsigned int*);

    NvmlClient()
        : m_lib(QStringLiteral("nvidia-ml"), 1) {}

    ~NvmlClient() {
        release();
    }

    bool ensureInitialized() {
        if (m_available) {
            return true;
        }
        if (m_loadFailed) {
            return false;
        }
        if (!m_lib.isLoaded() && !m_lib.load()) {
            m_loadFailed = true;
            return false;
        }
        if (!m_init) {
            m_init = reinterpret_cast<InitFn>(m_lib.resolve("nvmlInit_v2"));
            m_shutdown = reinterpret_cast<ShutdownFn>(m_lib.resolve("nvmlShutdown"));
            m_getHandle = reinterpret_cast<GetHandleByIndexFn>(m_lib.resolve("nvmlDeviceGetHandleByIndex_v2"));
            m_getName = reinterpret_cast<GetNameFn>(m_lib.resolve("nvmlDeviceGetName"));
            m_getUtil = reinterpret_cast<GetUtilFn>(m_lib.resolve("nvmlDeviceGetUtilizationRates"));
            m_getTemp = reinterpret_cast<GetTempFn>(m_lib.resolve("nvmlDeviceGetTemperature"));
        }
        if (!m_init || !m_getHandle || !m_getName || !m_getUtil || !m_getTemp) {
            m_loadFailed = true;
            return false;
        }
        if (!m_initialized) {
            if (m_init() != 0) {
                return false;
            }
            m_initialized = true;
        }
        if (m_getHandle(0, &m_device) != 0 || !m_device) {
            release();
            return false;
        }
        m_available = true;
        return true;
    }

    QLibrary m_lib;
    DeviceHandle m_device = nullptr;
    InitFn m_init = nullptr;
    ShutdownFn m_shutdown = nullptr;
    GetHandleByIndexFn m_getHandle = nullptr;
    GetNameFn m_getName = nullptr;
    GetUtilFn m_getUtil = nullptr;
    GetTempFn m_getTemp = nullptr;
    bool m_initialized = false;
    bool m_available = false;
    bool m_loadFailed = false;
};

QString parseNvidiaName(const QByteArray& out) {
    const QString first = QString::fromUtf8(out).split('\n').value(0).trimmed();
    return first.isEmpty() ? QString() : cleanName(first);
}

QString parseGlxinfoName(const QByteArray& out) {
    const QStringList lines = QString::fromUtf8(out).split('\n');
    for (const QString& line : lines) {
        const qsizetype idx = line.indexOf(QStringLiteral("Device:"));
        if (idx < 0) {
            continue;
        }

        QString rest = line.mid(idx + 7);
        const qsizetype paren = rest.indexOf('(');
        if (paren >= 0) {
            rest = rest.left(paren);
        }

        const QString cleaned = cleanName(rest);
        if (!cleaned.isEmpty()) {
            return cleaned;
        }
    }

    return QString();
}

QString parseLspciName(const QByteArray& out) {
    static const QRegularExpression lineRe(
        QStringLiteral("vga|3d controller|display"), QRegularExpression::CaseInsensitiveOption);

    const QStringList lines = QString::fromUtf8(out).split('\n');
    QString match;
    for (const QString& line : lines) {
        if (lineRe.match(line).hasMatch()) {
            match = line;
            break;
        }
    }

    if (match.isEmpty()) {
        return QString();
    }

    static const QRegularExpression bracketRe(QStringLiteral("\\[([^\\]]+)\\][^\\[]*$"));
    const auto bracket = bracketRe.match(match);
    if (bracket.hasMatch()) {
        return cleanName(bracket.captured(1));
    }

    // Split on a colon followed by whitespace so the PCI slot ("00:02.0") is not
    // mistaken for the class/name separator ("controller: Device").
    static const QRegularExpression colonRe(QStringLiteral(":\\s+(.+)"));
    const auto colon = colonRe.match(match);
    if (colon.hasMatch()) {
        return cleanName(colon.captured(1));
    }

    return QString();
}

struct NameSource {
    QString program;
    QStringList args;
    QString (*parse)(const QByteArray&);
};

// Name probes in priority order; the first non-empty result wins. The NVIDIA
// probe is first and doubles as the type probe (see finishNameSource).
const std::array<NameSource, 3>& nameSources() {
    static const std::array<NameSource, 3> sources = { {
        { QStringLiteral("nvidia-smi"), { QStringLiteral("--query-gpu=name"), QStringLiteral("--format=csv,noheader") },
            &parseNvidiaName },
        { QStringLiteral("glxinfo"), { QStringLiteral("-B") }, &parseGlxinfoName },
        { QStringLiteral("lspci"), {}, &parseLspciName },
    } };
    return sources;
}

// Index of the NVIDIA source within nameSources(); its result also drives type.
constexpr int kNvidiaSource = 0;

} // namespace

Gpu::Gpu(QObject* parent)
    : TickingService(parent) {
    m_busyFiles = gpuBusyFiles();

    auto* svc = caelestia::config::GlobalConfig::instance()->services();
    m_userType = parseType(svc->gpuType());
    QObject::connect(svc, &caelestia::config::ServiceConfig::gpuTypeChanged, this, [this, svc] {
        setUserType(parseType(svc->gpuType()));
    });

    detectGpu();
}

Gpu::Type Gpu::type() const {
    return m_userType == Auto ? m_autoType : m_userType;
}

Gpu::Type Gpu::userType() const {
    return m_userType;
}

Gpu::Type Gpu::autoType() const {
    return m_autoType;
}

QString Gpu::name() const {
    return m_name;
}

qreal Gpu::percentage() const {
    return m_percentage;
}

qreal Gpu::temperature() const {
    return m_temperature;
}

void Gpu::setUserType(Type value) {
    if (value == m_userType) {
        return;
    }
    const Type prevDerived = type();
    m_userType = value;
    emit userTypeChanged();
    if (type() != prevDerived) {
        emit typeChanged();
    }

    // Probe again when switching back to auto
    if (value == Auto) {
        detectGpu();
    }
}

void Gpu::setAutoType(Type value) {
    if (value == m_autoType) {
        return;
    }
    const Type prevDerived = type();
    m_autoType = value;
    emit autoTypeChanged();
    if (type() != prevDerived) {
        emit typeChanged();
    }
}

void Gpu::setName(QString value) {
    if (value == m_name) {
        return;
    }
    m_name = std::move(value);
    emit nameChanged();
}

void Gpu::tick() {
    const Type t = type();
    if (t == Generic) {
        readGenericUsage();
        readGpuTemperature();
    } else if (t == Nvidia) {
        startNvidiaUsage();
    } else {
        if (std::abs(m_percentage) > 0.0001) {
            m_percentage = 0.0;
            emit percentageChanged();
        }
        if (std::abs(m_temperature) > 0.05) {
            m_temperature = 0.0;
            emit temperatureChanged();
        }
    }
}

void Gpu::onStopped() {
    NvmlClient::instance().release();
}

void Gpu::detectGpu() {
    if (m_detecting) {
        return;
    }
    if (const QString procName = procNvidiaGpuName(); !procName.isEmpty()) {
        setAutoType(Nvidia);
        setName(procName);
        return;
    }
    if (const QString nvName = NvmlClient::instance().deviceName(); !nvName.isEmpty()) {
        NvmlClient::instance().release();
        setAutoType(Nvidia);
        setName(nvName);
        return;
    }
    m_detecting = true;

    // Probe in priority order, stopping at the first result
    tryNameSource(0);
}

void Gpu::tryNameSource(int index) {
    const NameSource& src = nameSources().at(static_cast<std::size_t>(index));
    runProcess(src.program, src.args, [this, index, parse = src.parse](const QByteArray& out) {
        finishNameSource(index, parse(out));
    });
}

void Gpu::finishNameSource(int index, QString name) {
    // The NVIDIA name probe doubles as the type probe: a non-empty result means an
    // NVIDIA GPU is present and queryable. Derive autoType unconditionally (even when
    // the user pins a type) so a later switch to Auto reads a correct value without
    // depending on its own re-probe, which is skipped while a probe is in flight.
    if (index == kNvidiaSource) {
        setAutoType(!name.isEmpty() ? Nvidia : (m_busyFiles.isEmpty() ? None : Generic));
    }

    if (!name.isEmpty()) {
        setName(std::move(name));
        m_detecting = false;
        return;
    }

    if (index + 1 < static_cast<int>(nameSources().size())) {
        tryNameSource(index + 1);
    } else {
        m_detecting = false;
    }
}

void Gpu::runProcess(const QString& program, const QStringList& args, std::function<void(const QByteArray&)> callback) {
    auto* proc = new QProcess(this);
    proc->setStandardErrorFile(QProcess::nullDevice());

    // Deliver the result exactly once, then tear the process down. A crash or a
    // missing binary yields empty output so the caller can fall through gracefully:
    // only FailedToStart skips finished(), and a crash reports CrashExit there.
    const auto finish = [proc, callback = std::move(callback)](const QByteArray& out) {
        callback(out);
        proc->deleteLater();
    };

    QObject::connect(proc, &QProcess::finished, this, [finish, proc](int, QProcess::ExitStatus status) {
        finish(status == QProcess::NormalExit ? proc->readAllStandardOutput() : QByteArray());
    });
    QObject::connect(proc, &QProcess::errorOccurred, this, [finish](QProcess::ProcessError err) {
        if (err == QProcess::FailedToStart) {
            finish(QByteArray());
        }
    });

    proc->start(program, args);
}

void Gpu::readGenericUsage() {
    qreal sum = 0.0;
    int count = 0;
    for (const QString& path : std::as_const(m_busyFiles)) {
        QFile f(path);
        if (!f.open(QIODevice::ReadOnly | QIODevice::Text)) {
            continue;
        }
        bool ok = false;
        const qreal v = f.readAll().trimmed().toDouble(&ok);
        f.close();
        if (ok) {
            sum += v;
            ++count;
        }
    }
    const qreal newPerc = count > 0 ? sum / count / 100.0 : 0.0;
    if (std::abs(newPerc - m_percentage) > 0.0001) {
        m_percentage = newPerc;
        emit percentageChanged();
    }
}

void Gpu::startNvidiaUsage() {
    qreal nvUsage = 0.0;
    qreal nvTemp = 0.0;
    if (NvmlClient::instance().queryMetrics(nvUsage, nvTemp)) {
        if (std::abs(nvUsage - m_percentage) > 0.0001) {
            m_percentage = nvUsage;
            emit percentageChanged();
        }
        if (std::abs(nvTemp - m_temperature) > 0.05) {
            m_temperature = nvTemp;
            emit temperatureChanged();
        }
        return;
    }

    if (m_nvidiaQuerying) {
        return;
    }
    m_nvidiaQuerying = true;
    runProcess(QStringLiteral("nvidia-smi"),
        { QStringLiteral("--query-gpu=utilization.gpu,temperature.gpu"),
            QStringLiteral("--format=csv,noheader,nounits") },
        [this](const QByteArray& out) {
            m_nvidiaQuerying = false;

            const QList<QByteArray> parts = out.trimmed().split(',');
            if (parts.size() < 2) {
                return;
            }
            bool ok1 = false;
            bool ok2 = false;
            const qreal usage = parts.at(0).trimmed().toDouble(&ok1) / 100.0;
            const qreal temp = parts.at(1).trimmed().toDouble(&ok2);
            if (ok1 && std::abs(usage - m_percentage) > 0.0001) {
                m_percentage = usage;
                emit percentageChanged();
            }
            if (ok2 && std::abs(temp - m_temperature) > 0.05) {
                m_temperature = temp;
                emit temperatureChanged();
            }
        });
}

void Gpu::readGpuTemperature() {
    const auto t = sensorslib::gpuPciAverageTemp();
    const qreal newTemp = t.value_or(0.0);
    if (std::abs(newTemp - m_temperature) > 0.05) {
        m_temperature = newTemp;
        emit temperatureChanged();
    }
}

Gpu::Type Gpu::parseType(const QString& s) {
    const QString u = s.trimmed().toUpper();
    if (u.isEmpty()) {
        return Auto;
    }
    if (u == QStringLiteral("NVIDIA")) {
        return Nvidia;
    }
    if (u == QStringLiteral("GENERIC")) {
        return Generic;
    }
    return None;
}

} // namespace caelestia::services
