#pragma once

#include "configobject.hpp"

#include <qdir.h>
#include <qstandardpaths.h>
#include <qstring.h>

namespace caelestia::config {

using Qt::StringLiterals::operator""_s;

class UserPaths : public ConfigObject {
    Q_OBJECT
    QML_ANONYMOUS

    CONFIG_GLOBAL_PROPERTY(
        QString, wallpaperDir, QStandardPaths::writableLocation(QStandardPaths::PicturesLocation) + u"/Wallpapers"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, lyricsDir, QStandardPaths::writableLocation(QStandardPaths::MusicLocation) + u"/Lyrics/"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, screenshotHelper, u"/home/execorn/scripts/screenshot_helper.sh"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, screenshotDir, QStandardPaths::writableLocation(QStandardPaths::PicturesLocation) + u"/Screenshots"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, cheatsheetParser, u"/home/execorn/teamwork_projects/hyprland_cheat_sheet/parser/parse_keybinds.py"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, eqControlScript, u"/home/execorn/scripts/eq-control.py"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, eqPresetsDir, u"~/.config/pipewire/eq-presets"_s)
    CONFIG_GLOBAL_PROPERTY(
        QString, recordingDir, QStandardPaths::writableLocation(QStandardPaths::MoviesLocation) + u"/Recordings"_s)
    CONFIG_PROPERTY(QString, sessionGif, u"root:/assets/kurukuru.gif"_s)
    CONFIG_PROPERTY(QString, mediaGif, u"root:/assets/bongocat.gif"_s)
    CONFIG_PROPERTY(QString, noNotifsPic, u"root:/assets/dino.png"_s)
    CONFIG_PROPERTY(QString, lockNoNotifsPic, u"root:/assets/dino.png"_s)

public:
    explicit UserPaths(QObject* parent = nullptr)
        : ConfigObject(parent) {}
};

} // namespace caelestia::config
