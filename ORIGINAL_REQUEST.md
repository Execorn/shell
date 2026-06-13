# Original User Request

## Initial Request — 2026-06-12T15:06:23Z

Implement the five missing settings and utility features (Display Configuration, System Updates, Plugin Management, Theme Colours, and Weather Location Picker) for Caelestia Shell and its Nexus configuration panel.

Working directory: /home/execorn/ricing/shell

Integrity mode: development

## Requirements

### R1. Display Configuration Page
- Implement the "Display" settings panel in the Nexus configuration panel.
- Retrieve active monitors dynamically via `hyprctl monitors -j`.
- Provide dropdown selectors for Resolution, Refresh Rate, and Screen Rotation, and a slider for System Scaling (1.0 to 2.0).
- Provide a visual layout map representing relative screen coordinates.
- Save configurations persistently to `~/.config/caelestia/monitors.json` (or a dedicated sourced config helper) and apply them via Hyprland IPC reload.
- Include a 15-second safety revert countdown modal when applying new settings.

### R2. System Updates Page
- Replace the "Updates" placeholder with a functional package manager panel.
- Retrieve pending updates asynchronously from pacman (`checkupdates`) and yay (`yay -Qua`).
- List pending updates showing package name, description, size, and version changes.
- Provide a prominent "Update Now" action that triggers a systemd user service (`caelestia-upgrade.service`) to run `yay -Syu --noconfirm` asynchronously.
- Stream the install logs or display a detailed percentage progress indicator.

### R3. Plugin Management Page
- Replace the "Plugins" placeholder with a dynamic plugin browser panel.
- Scan user plugins in `~/.config/caelestia/plugins/` (checking for custom plugin metadata files).
- List plugins showing metadata, status, author, version, and error logs if crashed.
- Provide toggles to enable or disable plugins, dynamically loading or unloading their QML components in the background using asynchronous loaders.

### R4. Theme Colours Page
- Replace the "Colours" wallpaper settings sub-page with a theme customizer.
- Allow selection between dynamic wallpaper-extracted theme schemes and static custom-accent colors.
- Provide a grid of Material 3 key colors or an HSL color picker.
- Allow selection of theme flavors (e.g. Tonal Spot, Vibrant, Expressive, Monochrome) and light/dark mode.
- Trigger palette regeneration using `caelestia scheme set` and reload colours dynamically without shell restart.

### R5. Weather Location Picker
- Replace the weather location text placeholder in Language & Region with a coordinate selection tool.
- Provide a map visualization (via Qt Location OSM plugin) or list-based geocoding search using the Open-Meteo Geocoding API.
- Allow the user to pin or type a city, resolve its coordinates, and update `weatherLocation` and `weatherCoordinates` in `shell.json` to refresh weather forecasts instantly.

## Acceptance Criteria

### Execution & Performance
- [ ] No "Page under construction" placeholder screens remain active in the Nexus panel.
- [ ] All features operate asynchronously without blocking the main QML event loop or causing frame drops.
- [ ] Configuration changes are saved to user files (e.g. `shell.json`, `scheme.json`, `monitors.json`) and apply instantly.
- [ ] Regular git commits are created as checkpoints after each fully functional feature implementation.
