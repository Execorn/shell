#include "imagecacher.hpp"

#include <qcryptographichash.h>
#include <qdatetime.h>
#include <qdir.h>
#include <qfile.h>
#include <qfileinfo.h>
#include <qhash.h>
#include <qimage.h>
#include <qimagereader.h>
#include <qloggingcategory.h>
#include <qmutex.h>
#include <qpainter.h>
#include <qsavefile.h>
#include <qthreadpool.h>

Q_LOGGING_CATEGORY(lcCacher, "caelestia.images.cacher", QtInfoMsg)

namespace caelestia::images {

namespace {

struct CachedHashEntry {
    qint64 fileSize = -1;
    qint64 mtimeMsecs = -1;
    QString sha256;
};

QMutex& hashCacheMutex() {
    static QMutex s_mutex;
    return s_mutex;
}

QHash<QString, CachedHashEntry>& hashCache() {
    static QHash<QString, CachedHashEntry> s_cache;
    return s_cache;
}

QString sha256sum(const QString& path) {
    const QFileInfo info(path);
    if (!info.exists() || !info.isFile()) {
        return {};
    }

    const QString canonical = info.canonicalFilePath().isEmpty() ? info.absoluteFilePath() : info.canonicalFilePath();
    const qint64 fsize = info.size();
    const qint64 mtime = info.lastModified().toMSecsSinceEpoch();

    {
        QMutexLocker locker(&hashCacheMutex());
        const auto it = hashCache().constFind(canonical);
        if (it != hashCache().cend() && it->fileSize == fsize && it->mtimeMsecs == mtime) {
            return it->sha256;
        }
    }

    QFile file(canonical);
    if (!file.open(QIODevice::ReadOnly)) {
        qCWarning(lcCacher).noquote() << "sha256sum: failed to open" << path;
        return {};
    }

    QCryptographicHash hash(QCryptographicHash::Sha256);
    hash.addData(&file);
    file.close();

    const QString hex = QString::fromLatin1(hash.result().toHex());
    {
        QMutexLocker locker(&hashCacheMutex());
        hashCache().insert(canonical, CachedHashEntry{ fsize, mtime, hex });
    }
    return hex;
}

QString fillSuffix(ImageCacher::FillMode fillMode) {
    switch (fillMode) {
    case ImageCacher::FillMode::Crop:
        return QStringLiteral("crop");
    case ImageCacher::FillMode::Fit:
        return QStringLiteral("fit");
    default:
        return QStringLiteral("stretch");
    }
}

} // namespace

const QString& ImageCacher::cacheDir() {
    static const QString s_dir = [] {
        QString cache = qEnvironmentVariable("XDG_CACHE_HOME");
        if (cache.isEmpty())
            cache = QDir::homePath() + QStringLiteral("/.cache");
        return cache + QStringLiteral("/caelestia/imagecache");
    }();
    return s_dir;
}

QString ImageCacher::cachePathFor(const QString& sourcePath, const QSize& size, FillMode fillMode) {
    const QString sha = sha256sum(sourcePath);
    if (sha.isEmpty())
        return {};

    const QString filename =
        QStringLiteral("%1@%2x%3-%4.png")
            .arg(sha, QString::number(size.width()), QString::number(size.height()), fillSuffix(fillMode));

    return cacheDir() + QLatin1Char('/') + filename;
}

QImage ImageCacher::decodeAndScale(const QString& sourcePath, const QSize& size, FillMode fillMode) {
    Qt::AspectRatioMode scaleMode = Qt::IgnoreAspectRatio;
    switch (fillMode) {
    case FillMode::Crop:
        scaleMode = Qt::KeepAspectRatioByExpanding;
        break;
    case FillMode::Fit:
        scaleMode = Qt::KeepAspectRatio;
        break;
    case FillMode::Stretch:
        scaleMode = Qt::IgnoreAspectRatio;
        break;
    }

    QImageReader reader(sourcePath);
    if (size.isValid()) {
        const QSize srcSize = reader.size();
        if (srcSize.isValid() && (srcSize.width() > size.width() * 2 || srcSize.height() > size.height() * 2)) {
            reader.setScaledSize(srcSize.scaled(size * 2, scaleMode));
        }
    }
    QImage image = reader.read();
    if (image.isNull()) {
        qCWarning(lcCacher).noquote() << "Failed to decode source" << sourcePath;
        return {};
    }

    image.convertTo(QImage::Format_ARGB32);
    image = image.scaled(size, scaleMode, Qt::SmoothTransformation);

    if (image.isNull()) {
        qCWarning(lcCacher).noquote() << "Failed to scale" << sourcePath;
        return {};
    }

    if (fillMode == FillMode::Stretch || image.size() == size) {
        return image;
    }

    QImage canvas(size, QImage::Format_ARGB32);
    canvas.fill(Qt::transparent);

    QPainter painter(&canvas);
    painter.drawImage((size.width() - image.width()) / 2, (size.height() - image.height()) / 2, image);
    painter.end();
    return canvas;
}

ImageCacher* ImageCacher::instance() {
    static ImageCacher s_instance;
    return &s_instance;
}

ImageCacher::ImageCacher(QObject* parent)
    : QObject(parent) {}

void ImageCacher::schedule(const QString& sourcePath, const QSize& size, FillMode fillMode) {
    schedule(sourcePath, cachePathFor(sourcePath, size, fillMode), size, fillMode);
}

void ImageCacher::schedule(const QString& sourcePath, const QString& cachePath, const QSize& size, FillMode fillMode) {
    if (cachePath.isEmpty())
        return;

    {
        QMutexLocker locker(&m_mutex);
        if (m_inflight.contains(cachePath))
            return;
        m_inflight.insert(cachePath);
    }

    QThreadPool::globalInstance()->start([this, sourcePath, cachePath, size, fillMode]() {
        runJob(sourcePath, cachePath, size, fillMode);
        QMutexLocker locker(&m_mutex);
        m_inflight.remove(cachePath);
    });
}

void ImageCacher::scheduleSave(const QString& cachePath, const QImage& image) {
    if (cachePath.isEmpty() || image.isNull())
        return;

    {
        QMutexLocker locker(&m_mutex);
        if (m_inflight.contains(cachePath))
            return;
        m_inflight.insert(cachePath);
    }

    QThreadPool::globalInstance()->start([this, cachePath, image]() {
        saveToCache(cachePath, image);
        QMutexLocker locker(&m_mutex);
        m_inflight.remove(cachePath);
    });
}

void ImageCacher::runJob(const QString& sourcePath, const QString& cachePath, const QSize& size, FillMode fillMode) {
    if (QFile::exists(cachePath)) {
        return;
    }

    const QImage canvas = decodeAndScale(sourcePath, size, fillMode);
    if (!canvas.isNull()) {
        saveToCache(cachePath, canvas);
    }
}

void ImageCacher::saveToCache(const QString& cachePath, const QImage& image) {
    if (QFile::exists(cachePath)) {
        return;
    }

    const QString parent = QFileInfo(cachePath).absolutePath();
    if (!QDir().mkpath(parent)) {
        qCWarning(lcCacher).noquote() << "Failed to create cache dir" << parent;
        return;
    }

    QSaveFile saveFile(cachePath);
    if (!saveFile.open(QIODevice::WriteOnly) || !image.save(&saveFile, "PNG", 80) || !saveFile.commit()) {
        qCWarning(
            lcCacher, "Failed to save to %s: %s", qUtf8Printable(cachePath), qUtf8Printable(saveFile.errorString()));
        return;
    }

    qCDebug(lcCacher).noquote() << "Saved to" << cachePath;
}

} // namespace caelestia::images
