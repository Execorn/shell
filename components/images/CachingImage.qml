import QtQuick
import Quickshell
import Caelestia.Images

Image {
    id: root

    property string path

    asynchronous: true
    cache: false
    fillMode: Image.PreserveAspectCrop
    source: (path && width > 0 && height > 0) ? IUtils.urlForPath(path, fillMode) : ""
    sourceSize: {
        const dpr = (QsWindow.window as QsWindow)?.devicePixelRatio ?? 1;
        return Qt.size(Math.max(1, Math.ceil(width * dpr)), Math.max(1, Math.ceil(height * dpr)));
    }
}
