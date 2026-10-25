#include "cachingimageprovider.hpp"

#include "imagecacher.hpp"

#include <qfileinfo.h>
#include <qicon.h>
#include <qimage.h>
#include <qimagereader.h>
#include <qloggingcategory.h>
#include <qrunnable.h>
#include <qthreadpool.h>

Q_LOGGING_CATEGORY(lcCProv, "caelestia.images.cacheprovider", QtInfoMsg)

namespace caelestia::images {

namespace {

class CachingImageResponse final : public QQuickImageResponse, public QRunnable {
public:
    CachingImageResponse(const QString& id, const QSize& requestedSize, ImageCacher::FillMode fillMode)
        : m_id(id)
        , m_requestedSize(requestedSize)
        , m_fillMode(fillMode) {
        setAutoDelete(false);
    }

    [[nodiscard]] QQuickTextureFactory* textureFactory() const override {
        return QQuickTextureFactory::textureFactoryForImage(m_image);
    }

    [[nodiscard]] QString errorString() const override { return m_error; }

    void run() override {
        process();
        emit finished();
    }

private:
    void process() {
        QString path = QString::fromUtf8(m_id.toUtf8().percentDecoded());
        if (!path.startsWith(QLatin1Char('/')))
            path.prepend(QLatin1Char('/'));

        if (!QFileInfo::exists(path)) {
            m_error = QStringLiteral("Source file does not exist: ") + path;
            qCWarning(lcCProv).noquote() << m_error;
            return;
        }

        QSize size = m_requestedSize;
        bool needsW = size.width() <= 0;
        bool needsH = size.height() <= 0;

        if (needsW && needsH) {
            size = QSize(512, 0);
            needsW = false;
        }

        // If one dimension is missing, derive it from the source aspect ratio
        if (needsW || needsH) {
            const QImageReader sourceReader(path);
            const QSize sourceSize = sourceReader.size();
            if (!sourceSize.isValid() || sourceSize.isEmpty()) {
                m_error = QStringLiteral("Could not determine source size for: ") + path;
                qCWarning(lcCProv).noquote() << m_error;
                return;
            }

            if (needsW)
                size.setWidth(qRound(size.height() * sourceSize.width() / static_cast<qreal>(sourceSize.height())));
            else
                size.setHeight(qRound(size.width() * sourceSize.height() / static_cast<qreal>(sourceSize.width())));
        }

        // Try to use cached image
        const auto cachePath = ImageCacher::cachePathFor(path, size, m_fillMode);
        if (!cachePath.isEmpty()) {
            QImageReader cacheReader(cachePath);
            if (cacheReader.canRead()) {
                m_image = cacheReader.read();
                if (!m_image.isNull())
                    return;
            }
        }

        m_image = ImageCacher::decodeAndScale(path, size, m_fillMode);
        if (m_image.isNull()) {
            m_error = QStringLiteral("Failed to decode source: ") + path;
            qCWarning(lcCProv).noquote() << m_error;
            return;
        }

        ImageCacher::instance()->scheduleSave(cachePath, m_image);
    }

    QString m_id;
    QSize m_requestedSize;
    ImageCacher::FillMode m_fillMode;
    QImage m_image;
    QString m_error;
};

} // namespace

CachingImageProvider::CachingImageProvider(FillMode fillMode)
    : m_fillMode(fillMode) {
    (void)QIcon::fromTheme(QStringLiteral("application-x-executable")).pixmap(16, 16);
    (void)QThreadPool::globalInstance();
    (void)ImageCacher::instance();
}

QQuickImageResponse* CachingImageProvider::requestImageResponse(const QString& id, const QSize& requestedSize) {
    auto* const response = new CachingImageResponse(id, requestedSize, m_fillMode);
    QThreadPool::globalInstance()->start(response);
    return response;
}

} // namespace caelestia::images
