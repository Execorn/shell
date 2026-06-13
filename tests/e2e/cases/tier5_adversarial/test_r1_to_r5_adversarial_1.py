import os
import json
import re
import subprocess
from tests.e2e.mock_env import E2ETestCase

# --- Simulators replicating the white-box logic under test ---

class QmlDisplaySimulator:
    def __init__(self, initial_monitors_config):
        self.monitorsConfig = initial_monitors_config
        self.activeMonitors = initial_monitors_config
        self.previousConfig = []
        self.revertModal_visible = False
        self.countdown = 15
        self.countdownTimer_running = False

    def applyChanges(self, new_resolution, new_scale, new_rotation, new_refresh_rate):
        width, height = map(int, new_resolution.split("x"))
        currentConfig = self.monitorsConfig if (self.monitorsConfig and len(self.monitorsConfig) > 0) else self.activeMonitors
        
        newConfig = []
        for m in currentConfig:
            newConfig.append({
                "id": m["id"],
                "name": m["name"],
                "width": width,
                "height": height,
                "refreshRate": new_refresh_rate,
                "transform": new_rotation,
                "scale": new_scale
            })
            
        self.previousConfig = json.loads(json.dumps(currentConfig))
        self.monitorsConfig = newConfig
        self.revertModal_visible = True
        self.countdown = 15
        self.countdownTimer_running = True

    def revertChanges(self):
        self.revertModal_visible = False
        self.countdownTimer_running = False
        if self.previousConfig and len(self.previousConfig) > 0:
            self.monitorsConfig = self.previousConfig


class QmlUpdatesSimulator:
    def __init__(self):
        self.upgradeStatus = "stopped"
        self.upgradeLogs = []
        self.statusCheckPending = False

    def onLogLineRead(self, line):
        cleanedLine = line.strip()
        if not cleanedLine:
            return
        self.upgradeLogs.append(cleanedLine)
        if ("Could not resolve host" in cleanedLine or 
            "Network is unreachable" in cleanedLine or 
            "failed" in cleanedLine.lower()):
            self.upgradeLogs.append("Error: Upgrade failed due to network disconnect.")
            self.upgradeStatus = "failed"

    def onStatusCheckFinished(self, systemd_status):
        if not self.statusCheckPending:
            return
        self.statusCheckPending = False
        
        status = systemd_status.strip()
        recognized = ["active", "inactive", "failed", "activating", "deactivating", "reloading", "maintenance"]
        if not status or status not in recognized:
            if self.upgradeStatus == "running":
                self.upgradeStatus = "failed"
        elif status == "active":
            self.upgradeStatus = "running"
        elif status == "failed":
            if self.upgradeStatus == "running":
                self.upgradeStatus = "failed"
        elif status == "inactive":
            if self.upgradeStatus == "running":
                self.upgradeStatus = "stopped"


class QmlSearchSimulator:
    def __init__(self):
        self.searchStatusText = ""
        self.searchError = False
        self.api_called = False
        self.api_query = ""

    def performSearch(self, query):
        self.searchStatusText = ""
        self.searchError = False
        self.api_called = False
        self.api_query = ""

        trimmed = query.strip()
        if not trimmed:
            self.searchError = True
            self.searchStatusText = "Search query cannot be empty"
            return

        isCoords = bool(re.match(r"^[-\d.,\s]+$", trimmed))
        if isCoords:
            match = re.match(r"^\s*([\-\d\.]+)\s*,\s*([\-\d\.]+)\s*$", trimmed)
            if not match:
                self.searchError = True
                self.searchStatusText = "Invalid coordinate format. Must be 'lat,lon'"
                return
            
            self.api_called = True
            self.api_query = "reverse"
        else:
            self.api_called = True
            self.api_query = trimmed


# --- Adversarial Test Cases Class ---

class TestR1ToR5Adversarial(E2ETestCase):

    def test_r1_display_revert_overwrite_bug(self):
        """R1 Adversarial: Verify safety revert countdown state overwrite vulnerability."""
        initial_config = [{"id": 0, "name": "eDP-1", "width": 1920, "height": 1080, "refreshRate": 60.0, "transform": 0, "scale": 1.0}]
        sim = QmlDisplaySimulator(initial_config)
        
        # User triggers first scaling change to 1.2
        sim.applyChanges("1280x720", 1.2, 0, 60.0)
        self.assertEqual(sim.previousConfig[0]["scale"], 1.0)
        self.assertEqual(sim.monitorsConfig[0]["scale"], 1.2)
        
        # User triggers second scaling change to 1.5 before confirming or countdown expires
        sim.applyChanges("1280x720", 1.5, 0, 60.0)
        
        # Revert changes triggers (countdown expires)
        sim.revertChanges()
        
        # EXPECTED: Revert should go back to original configuration (scale 1.0)
        # ACTUAL: Revert goes back to intermediate configuration (scale 1.2) because previousConfig was overwritten
        self.assertEqual(sim.monitorsConfig[0]["scale"], 1.2)
        self.assertNotEqual(sim.monitorsConfig[0]["scale"], 1.0)

    def test_r2_updates_race_condition(self):
        """R2 Adversarial: Verify system updates stream-timer status race condition."""
        sim = QmlUpdatesSimulator()
        sim.upgradeStatus = "running"
        
        # Status poll is in progress (pending)
        sim.statusCheckPending = True
        
        # Network failure log stream arrives, marking status as failed
        sim.onLogLineRead("Error: Pacman upgrade transaction failed")
        self.assertEqual(sim.upgradeStatus, "failed")
        
        # Concurrent status poll check finishes and returns "active" (since daemon is slow to terminate)
        sim.onStatusCheckFinished("active")
        
        # ACTUAL: The "failed" status gets incorrectly overwritten back to "running"
        self.assertEqual(sim.upgradeStatus, "running")

    def test_r3_plugin_scan_race_condition(self):
        """R3 Adversarial: Verify concurrent scanning and write operations create corrupt plugin status."""
        plugin_name = "race_plugin"
        plugin_dir = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)
        
        # Simulate intermediate empty file state during write (truncation)
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            pass
            
        # Run the QML Python scan script logic on the folder in-process
        plugins_dir = self.env.plugins_dir
        parsed = {}
        
        if os.path.exists(plugins_dir):
            for item in os.listdir(plugins_dir):
                item_path = os.path.join(plugins_dir, item)
                if os.path.isdir(item_path):
                    meta_path = os.path.join(item_path, 'metadata.json')
                    if not os.path.exists(meta_path):
                        parsed[item] = {"id": item, "status": "invalid"}
                        continue
                    try:
                        with open(meta_path, 'r') as f:
                            meta = json.load(f)
                        parsed[item] = {"id": item, "status": meta.get("status", "disabled")}
                    except json.JSONDecodeError:
                        parsed[item] = {"id": item, "status": "corrupt"}
        
        # ACTUAL: The scanner marks the status as corrupt
        self.assertEqual(parsed[plugin_name]["status"], "corrupt")


    def test_r5_weather_zipcode_geocoding_bug(self):
        """R5 Adversarial: Verify coordinates check regex incorrectly intercepts and errors out ZIP codes/numeric queries."""
        sim = QmlSearchSimulator()
        
        # Standard query works
        sim.performSearch("Berlin")
        self.assertFalse(sim.searchError)
        self.assertEqual(sim.api_query, "Berlin")
        
        # Numeric ZIP code/city name query
        sim.performSearch("90210")
        
        # ACTUAL: Query is intercepted by the coordinates check regex, fails comma match, and errors out without querying API
        self.assertTrue(sim.searchError)
        self.assertEqual(sim.searchStatusText, "Invalid coordinate format. Must be 'lat,lon'")
        self.assertFalse(sim.api_called)
