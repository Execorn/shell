#pragma once

#include "configobject.hpp"
#include <qstring.h>

namespace caelestia::config {

class ExtractedColorsConfig : public ConfigObject {
    Q_OBJECT
    QML_ANONYMOUS

    CONFIG_PROPERTY(QString, primary, QStringLiteral("#3f5f91"))
    CONFIG_PROPERTY(QString, secondary, QStringLiteral("#565f71"))
    CONFIG_PROPERTY(QString, tertiary, QStringLiteral("#705575"))

public:
    explicit ExtractedColorsConfig(QObject* parent = nullptr)
        : ConfigObject(parent) {}
};

class ThemeConfig : public ConfigObject {
    Q_OBJECT
    QML_ANONYMOUS

    CONFIG_PROPERTY(QString, mode, QStringLiteral("dark"))
    CONFIG_PROPERTY(bool, darkMode, true)
    CONFIG_PROPERTY(QString, flavor, QStringLiteral("tonal-spot"))
    CONFIG_PROPERTY(QString, colorSource, QStringLiteral("dynamic"))
    CONFIG_PROPERTY(QString, source, QStringLiteral("wallpaper"))
    CONFIG_PROPERTY(QString, accentColor, QStringLiteral("wallpaper"))
    CONFIG_PROPERTY(QString, customAccentHSL, QStringLiteral("220,100,50"))
    CONFIG_SUBOBJECT(ExtractedColorsConfig, extractedColors)

public:
    explicit ThemeConfig(QObject* parent = nullptr)
        : ConfigObject(parent)
        , m_extractedColors(new ExtractedColorsConfig(this)) {}
};

} // namespace caelestia::config
