import QtQuick
import Quickshell

FontLoader {
    source: {
        const families = Qt.fontFamilies();
        if (families.includes("GoogleSansFlex") || families.includes("Google Sans Flex"))
            return "";
        return Quickshell.shellPath("assets/google-sans-flex/GoogleSansFlex-VariableFont_GRAD,ROND,opsz,slnt,wdth,wght.ttf");
    }
}
