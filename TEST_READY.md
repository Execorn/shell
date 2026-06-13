# E2E Test Suite Ready

## Test Runner
- Command: `python3 tests/e2e/run_tests.py`
- Expected: all tests pass with exit code 0

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 25 | 5 test cases per feature (R1 to R5) covering happy-path requirements |
| 2. Boundary & Corner | 25 | 5 test cases per feature covering edge cases, limits, timeouts, failures, and recovery |
| 3. Cross-Feature | 5 | Pairwise feature interaction scenarios (combinations of display, theme, weather, updates, plugins) |
| 4. Real-World Application | 5 | Composite end-to-end user flows (initial setup, maintenance, travel, recovery, power user) |
| **Total** | **60** | |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|:------:|:------:|:------:|:------:|
| R1. Display Configuration | 5 / 5 | 5 / 5 | ✓ | ✓ |
| R2. System Updates | 5 / 5 | 5 / 5 | ✓ | ✓ |
| R3. Plugin Management | 5 / 5 | 5 / 5 | ✓ | ✓ |
| R4. Theme Colours | 5 / 5 | 5 / 5 | ✓ | ✓ |
| R5. Weather Location Picker | 5 / 5 | 5 / 5 | ✓ | ✓ |

## Running the Verification
To run the full test suite and confirm that all tests pass, execute:
```bash
python3 tests/e2e/run_tests.py
```

All 60 tests execute against the sandboxed `MockEnvironment` defined in `tests/e2e/mock_env.py` which:
1. Simulates Hyprland (`hyprctl`), Pacman/Yay (`checkupdates`, `yay`), Systemd (`systemctl`), and Journalctl CLI tools.
2. Mocks external HTTP APIs (Open-Meteo Geocoding, Nominatim Reverse Geocoding, IPInfo, etc.).
3. Isolates all file writes to a temporary `HOME` and `XDG_CONFIG_HOME` directory, safeguarding the host machine's configuration files.
