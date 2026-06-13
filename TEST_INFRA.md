# E2E Test Infra: Caelestia Shell Nexus Configuration Panel

## Test Philosophy
- **Opaque-box, requirement-driven**: Tests verify features based on requirements (R1-R5) and their external interfaces (files, commands, environment, mock signals) without relying on internal QML/C++ class structures.
- **Methodology**: Apply Category-Partition to identify inputs/states, Boundary Value Analysis (BVA) for limits, Pairwise Combinatorial testing for interactions, and Real-World Workload testing for daily user flows.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | Display Configuration | ORIGINAL_REQUEST R1 | 5      | 5      | ✓      |
| 2 | System Updates | ORIGINAL_REQUEST R2 | 5      | 5      | ✓      |
| 3 | Plugin Management | ORIGINAL_REQUEST R3 | 5      | 5      | ✓      |
| 4 | Theme Colours | ORIGINAL_REQUEST R4 | 5      | 5      | ✓      |
| 5 | Weather Location Picker | ORIGINAL_REQUEST R5 | 5      | 5      | ✓      |

## Test Architecture

### Directory Layout
All testing files are situated under the `tests/e2e` directory:
```
tests/e2e/
├── run_tests.py                 # Core test runner orchestrator
├── mock_env.py                  # Mocks system commands, files, and services (hyprctl, pacman, yay, systemd, open-meteo)
├── cases/                       # Test case definitions
│   ├── tier1_feature_coverage/  # Happy-path feature verification
│   │   ├── test_r1_display.py
│   │   ├── test_r2_updates.py
│   │   ├── test_r3_plugins.py
│   │   ├── test_r4_colours.py
│   │   └── test_r5_weather.py
│   ├── tier2_boundary_corner/   # Boundary cases, timeouts, invalid data
│   │   ├── test_r1_display_bounds.py
│   │   ├── test_r2_updates_bounds.py
│   │   ├── test_r3_plugins_bounds.py
│   │   ├── test_r4_colours_bounds.py
│   │   └── test_r5_weather_bounds.py
│   ├── tier3_cross_feature/     # Pairwise feature interaction tests
│   │   └── test_interactions.py
│   └── tier4_real_world/        # Composite user scenario flows
│       └── test_scenarios.py
```

### Test Case Format
E2E test cases are implemented as Python test classes inheriting from a custom `E2ETestCase` class.
- **Inputs**: Mock environment configuration (e.g. system files, CLI commands outputs, environment variables).
- **Triggers**: Simulated user action calls, CLI updates, or config file changes.
- **Assertions**: Verify state changes in `shell.json`, `monitors.json`, scheme configurations, or IPC commands emitted.

### Test Runner & Invocation
The test runner is invoked from the project root using:
```bash
python3 tests/e2e/run_tests.py
```
- **Exit Code**: `0` on success, non-zero on failure.
- **Pass/Fail Semantics**: Every test case must successfully execute setup, action, assertion, and cleanup without unexpected errors or assertions failing.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Desktop Setup | R1 (Display config) + R4 (Theme colours) | Medium |
| 2 | Routine Maintenance | R2 (System updates) + R3 (Plugin updates) | Medium |
| 3 | Travel / Relocation | R5 (Weather Location) + R4 (Theme palette update) | Medium |
| 4 | Recovery from Error | R1 (Safety revert) + R3 (Crashed plugin loading) | High |
| 5 | Power User Workspace | R1 (Multi-monitor) + R3 (Plugins) + R4 (Colors) + R5 (Weather) | High |

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: ≥5 test cases per feature (Total 25)
- **Tier 2 (Boundary & Corner)**: ≥5 test cases per feature (Total 25)
- **Tier 3 (Cross-Feature)**: ≥5 test cases representing major feature interactions (Total 5)
- **Tier 4 (Real-World Application)**: ≥5 comprehensive application-level test cases (Total 5)
- **Total E2E test cases**: 60 test cases minimum
