import QtQuick
import QtQuick.Layouts
import Caelestia
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    property string searchStatusText: ""
    property bool searchError: false

    function performSearch(query) {
        root.searchStatusText = "";
        root.searchError = false;

        const trimmed = query.trim();
        if (!trimmed) {
            root.searchError = true;
            root.searchStatusText = qsTr("Search query cannot be empty");
            return;
        }

        // Coordinates-like check: input containing only digits, minus, dots, commas, spaces
        const isCoords = /^[-\d.,\s]+$/.test(trimmed);
        if (isCoords) {
            const match = trimmed.match(/^\s*([\-\d\.]+)\s*,\s*([\-\d\.]+)\s*$/);
            if (!match) {
                root.searchError = true;
                root.searchStatusText = qsTr("Invalid coordinate format. Must be 'lat,lon'");
                return;
            }
            const lat = parseFloat(match[1]);
            const lon = parseFloat(match[2]);
            if (isNaN(lat) || isNaN(lon)) {
                root.searchError = true;
                root.searchStatusText = qsTr("Coordinates must be numbers");
                return;
            }
            if (lat < -90.0 || lat > 90.0) {
                root.searchError = true;
                root.searchStatusText = qsTr("Latitude must be between -90 and 90");
                return;
            }
            if (lon < -180.0 || lon > 180.0) {
                root.searchError = true;
                root.searchStatusText = qsTr("Longitude must be between -180 and 180");
                return;
            }

            root.searchStatusText = qsTr("Resolving coordinates...");
            const coordsStr = match[1] + "," + match[2];

            // Resolve location name via OpenStreetMap Nominatim reverse geocoding API
            const nominatimUrl = "https://nominatim.openstreetmap.org/reverse?lat=" + lat + "&lon=" + lon + "&format=geocodejson";
            Requests.get(nominatimUrl, text => {
                try {
                    const response = JSON.parse(text);
                    const geo = response.features?.[0]?.properties?.geocoding;
                    let resolvedCity = "";
                    if (geo) {
                        resolvedCity = geo.type === "city" ? geo.name : geo.city;
                    }
                    if (!resolvedCity) {
                        const fallbackUrl = "https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=" + lat + "&longitude=" + lon + "&localityLanguage=en";
                        Requests.get(fallbackUrl, textFallback => {
                            try {
                                const geoFallback = JSON.parse(textFallback);
                                const geoCity = geoFallback.city || geoFallback.locality;
                                if (geoCity) {
                                    root.saveLocation(geoCity, coordsStr);
                                } else {
                                    root.saveLocation("Custom Location", coordsStr);
                                }
                            } catch (e) {
                                root.saveLocation("Custom Location", coordsStr);
                            }
                        }, errText => {
                            root.saveLocation("Custom Location", coordsStr);
                        });
                    } else {
                        root.saveLocation(resolvedCity, coordsStr);
                    }
                } catch (e) {
                    root.saveLocation("Custom Location", coordsStr);
                }
            }, err => {
                const fallbackUrl = "https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=" + lat + "&longitude=" + lon + "&localityLanguage=en";
                Requests.get(fallbackUrl, textFallback => {
                    try {
                        const geoFallback = JSON.parse(textFallback);
                        const geoCity = geoFallback.city || geoFallback.locality;
                        if (geoCity) {
                            root.saveLocation(geoCity, coordsStr);
                        } else {
                            root.saveLocation("Custom Location", coordsStr);
                        }
                    } catch (e) {
                        root.saveLocation("Custom Location", coordsStr);
                    }
                }, errText => {
                    root.saveLocation("Custom Location", coordsStr);
                });
            });
        } else {
            root.searchStatusText = qsTr("Searching city...");
            const url = "https://geocoding-api.open-meteo.com/v1/search?name=" + encodeURIComponent(trimmed) + "&count=1&language=en&format=json";
            Requests.get(url, text => {
                root.searchStatusText = "";
                try {
                    const response = JSON.parse(text);
                    const results = response.results;
                    if (!results || results.length === 0) {
                        root.searchError = true;
                        root.searchStatusText = qsTr("City not found");
                        return;
                    }
                    const city = results[0];
                    const resolvedCoords = city.latitude + "," + city.longitude;
                    root.saveLocation(city.name, resolvedCoords);
                } catch (e) {
                    root.searchError = true;
                    root.searchStatusText = qsTr("Error: Failed to parse search results");
                }
            }, err => {
                root.searchStatusText = "";
                root.searchError = true;
                root.searchStatusText = qsTr("Network error: ") + (err || qsTr("Unknown error"));
            });
        }
    }

    function saveLocation(cityName, coordsStr) {
        root.searchStatusText = qsTr("Location updated!");
        root.searchError = false;
        GlobalConfig.services.weatherLocation = cityName;
        GlobalConfig.services.weatherCoordinates = coordsStr;
    }

    // Temperature units (index 0 = Celsius, 1 = Fahrenheit — matches Weather.formatTemp)
    readonly property list<MenuItem> tempItems: [
        MenuItem {
            text: "°C"
        },
        MenuItem {
            text: "°F"
        }
    ]

    // Clock format (index 0 = 24-hour, 1 = 12-hour — matches Time.useTwelveHourClock)
    readonly property list<MenuItem> clockItems: [
        MenuItem {
            text: qsTr("24-hour")
        },
        MenuItem {
            text: qsTr("12-hour")
        }
    ]

    title: qsTr("Language & region")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        // Language
        SectionHeader {
            first: true
            text: qsTr("Language")
        }

        // Read-only: the shell follows the system locale (no in-shell translations yet)
        ConnectedRect {
            Layout.fillWidth: true
            first: true
            last: true
            implicitHeight: localeLayout.implicitHeight + localeLayout.anchors.margins * 2

            RowLayout {
                id: localeLayout

                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                anchors.leftMargin: Tokens.padding.largeIncreased
                anchors.rightMargin: Tokens.padding.largeIncreased
                spacing: Tokens.spacing.medium

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    StyledText {
                        Layout.fillWidth: true
                        text: qsTr("System language")
                        font: Tokens.font.body.small
                        elide: Text.ElideRight
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: qsTr("Follows your system locale (%1)").arg(Qt.locale().name)
                        color: Colours.palette.m3outline
                        font: Tokens.font.label.small
                        elide: Text.ElideRight
                    }
                }

                StyledText {
                    text: Qt.locale().nativeLanguageName || Qt.locale().name
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.small
                }
            }
        }

        // Weather
        SectionHeader {
            text: qsTr("Weather")
        }

        ConnectedRect {
            id: weatherLocationPicker
            Layout.fillWidth: true
            first: true
            last: true
            implicitHeight: layoutContainer.implicitHeight + Tokens.padding.large * 2

            ColumnLayout {
                id: layoutContainer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: Tokens.padding.large
                spacing: Tokens.spacing.medium

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.medium

                    MaterialIcon {
                        text: "my_location"
                        color: Colours.palette.m3primary
                        fontStyle: Tokens.font.icon.large
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        StyledText {
                            text: qsTr("Current Location")
                            font: Tokens.font.body.builders.small.weight(Font.DemiBold).build()
                            color: Colours.palette.m3onSurface
                        }

                        StyledText {
                            text: {
                                const locName = GlobalConfig.services.weatherLocation;
                                const locCoords = GlobalConfig.services.weatherCoordinates;
                                if (locName && locCoords) {
                                    return locName + " (" + locCoords + ")";
                                } else if (locName) {
                                    return locName;
                                } else if (locCoords) {
                                    return locCoords;
                                }
                                return qsTr("None set (Using Auto-IP geolocation)");
                            }
                            font: Tokens.font.label.small
                            color: Colours.palette.m3outline
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.medium

                    StyledInputField {
                        id: searchInput
                        Layout.fillWidth: true
                        placeholderText: qsTr("Enter city name or 'lat,lon'")
                        horizontalAlignment: TextInput.AlignLeft
                        onEditingFinished: {
                            root.performSearch(searchInput.text)
                        }
                    }

                    TextButton {
                        text: qsTr("Pin")
                        type: ButtonBase.Tonal
                        implicitWidth: 70
                        implicitHeight: searchInput.implicitHeight
                        onClicked: {
                            root.performSearch(searchInput.text)
                        }
                    }
                }

                StyledText {
                    id: statusLabel
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: root.searchStatusText
                    color: root.searchError ? Colours.palette.m3error : Colours.palette.m3primary
                    font: Tokens.font.body.small
                    wrapMode: Text.WordWrap
                }
            }
        }

        // Units
        SectionHeader {
            text: qsTr("Units")
        }

        SelectRow {
            Layout.fillWidth: true
            first: true
            label: qsTr("Temperature")
            subtext: qsTr("Units for weather temperatures")
            menuItems: root.tempItems
            active: root.tempItems[GlobalConfig.services.useFahrenheit ? 1 : 0]
            onSelected: item => GlobalConfig.services.useFahrenheit = root.tempItems.indexOf(item) === 1
        }

        SelectRow {
            Layout.fillWidth: true
            last: true
            label: qsTr("System temperatures")
            subtext: qsTr("Units for CPU and GPU temperatures")
            menuItems: root.tempItems
            active: root.tempItems[GlobalConfig.services.useFahrenheitPerformance ? 1 : 0]
            onSelected: item => GlobalConfig.services.useFahrenheitPerformance = root.tempItems.indexOf(item) === 1
        }

        // Time & date
        SectionHeader {
            text: qsTr("Time & date")
        }

        SelectRow {
            Layout.fillWidth: true
            first: true
            last: true
            label: qsTr("Clock format")
            subtext: qsTr("How times are shown across the shell")
            menuItems: root.clockItems
            active: root.clockItems[GlobalConfig.services.useTwelveHourClock ? 1 : 0]
            onSelected: item => GlobalConfig.services.useTwelveHourClock = root.clockItems.indexOf(item) === 1
        }
    }
}
