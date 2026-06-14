# Project: Caelestia Shell and Cheatsheet Audit, Test, and Cleanup

## Architecture
- **Caelestia Shell**: A Quickshell-based desktop shell configuration for Hyprland.
  - Key components include Pipewire-based audio services (`services/Audio.qml`, `modules/bar/popouts/Audio.qml`).
  - Integrated cheatsheet module to display keybindings (`modules/cheatsheet/`).
- **Cheatsheet Parser**: A Python script in `/home/execorn/teamwork_projects/hyprland_cheat_sheet` that parses Hyprland keybindings/variables and generates `keybinds.json` under `/home/execorn/.local/state/caelestia/keybinds.json`.

## Code Layout
- **Shell Repository**: `/home/execorn/ricing/shell`
  - Audio Services: `services/Audio.qml`
  - Audio UI: `modules/bar/popouts/Audio.qml`
  - Cheatsheet UI: `modules/cheatsheet/`
- **Cheatsheet Repository**: `/home/execorn/teamwork_projects/hyprland_cheat_sheet`
  - Python Parser: `parser/parse_keybinds.py`
  - Pytest Suite: `tests/`
- **Unified Tests**: `/home/execorn/ricing/shell/tests/` and `/home/execorn/teamwork_projects/hyprland_cheat_sheet/tests/`

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1. Codebase Exploration & Audit | Explore the codebase to identify bugs, edge cases, Pipewire destruction race conditions, and AI traces. | None | IN_PROGRESS (explorer_m1_1, explorer_m1_2, explorer_m1_3) |
| 2 | M2. E2E Test Suite Specification | Define test plan/specs and design/implement mock test suites for `Audio.qml` state transitions. | M1 | PLANNED |
| 3 | M3. Audio & Shell Bug Fixes | Fix Pipewire node destruction race conditions and other logic/styling errors in the shell. | M2 | PLANNED |
| 4 | M4. Cheatsheet Parser & UI Fixes | Fix parser bugs and extend Pytest coverage. Resolve any cheatsheet UI styling issues. | M2 | PLANNED |
| 5 | M5. AI Trace Cleanup | Locate and delete all transient/AI scratch files, logs, and artifacts in both directories. | M3, M4 | PLANNED |
| 6 | M6. Integration and Git Sync | Run all tests, verify correctness via Forensic Auditor, commit, and push. | M5 | PLANNED |

## Interface Contracts
### Audio State Model (`services/Audio.qml`):
- Provides properties for volume, mute state, default sink, and default source.
- Subscribes to Pipewire events and handles node addition/removal robustly.
