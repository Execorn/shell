# Project: Caelestia Shell Nexus configuration panel features

## Architecture
- Caelestia Shell is a Qt/QML based shell powered by Quickshell (which runs Qt6).
- Configuration settings are loaded and saved persistently via a C++ singleton `GlobalConfig` to `~/.config/caelestia/shell.json`.
- Settings are exposed to QML components.
- Inter-process communication and reloading are triggered via Hyprland IPC and/or caelestia CLI commands.
- We need to implement 5 new features/pages:
  1. Display Configuration (R1) - read/write `~/.config/caelestia/monitors.json` and call Hyprland IPC to apply.
  2. System Updates (R2) - query pacman/yay and run upgrade service via systemd.
  3. Plugin Management (R3) - scan and load plugins dynamically in QML.
  4. Theme Colours (R4) - selection of colors, scheme flavors, and dark/light mode, then calling `caelestia scheme set`.
  5. Weather Location Picker (R5) - OSM map or Open-Meteo geocoding search to update weather config in `shell.json`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Testing Track | Test suite design and creation (Tiers 1-4) | None | PLANNED |
| 2 | C++ Config Upgrades | Add C++ support for weatherCoordinates | None | PLANNED |
| 3 | Display Configuration | R1 panel in Nexus, monitors.json, countdown, Hyprland IPC | M1 | PLANNED |
| 4 | System Updates | R2 updates panel, systemd service, log streaming | M1 | PLANNED |
| 5 | Plugin Management | R3 plugins panel, scan plugins, enable/disable toggle | M1 | PLANNED |
| 6 | Theme Colours | R4 customizer, grid/HSL picker, flavors, scheme set | M1 | PLANNED |
| 7 | Weather Location Picker | R5 location picker, open-meteo API, shell.json update | M1, M2 | PLANNED |
| 8 | E2E Verification & Hardening | Dual track integration, Tier 5 whitebox adversarial tests | M3, M4, M5, M6, M7 | PLANNED |

## Interface Contracts
### Config ↔ QML
- `GlobalConfig.services.weatherLocation` (QString): Weather location name/coords.
- `GlobalConfig.services.weatherCoordinates` (QString): Lat,lon coordinates for weather.
- `~/.config/caelestia/monitors.json`: JSON storing resolutions, refresh rates, rotations, and scales.
- `~/.config/caelestia/plugins/`: Plugins folder containing metadata and components.
