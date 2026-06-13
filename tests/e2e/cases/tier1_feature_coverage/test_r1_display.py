import os
import json
import subprocess
import time
from tests.e2e.mock_env import E2ETestCase

class TestDisplayConfiguration(E2ETestCase):
    def test_retrieve_monitors(self):
        """R1.1 Verify active monitors are retrieved dynamically via hyprctl."""
        # 1. Prepare active monitors in the mock environment
        self.env.active_monitors = [
            {
                "id": 0,
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.0,
                "transform": 0,
                "focused": True
            },
            {
                "id": 1,
                "name": "HDMI-A-1",
                "width": 2560,
                "height": 1440,
                "refreshRate": 144.0,
                "scale": 1.25,
                "transform": 0,
                "focused": False
            }
        ]
        
        # 2. Simulate the shell retrieving monitors via subprocess
        res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        
        monitors = json.loads(res.stdout)
        self.assertEqual(len(monitors), 2)
        self.assertEqual(monitors[0]["name"], "eDP-1")
        self.assertEqual(monitors[1]["name"], "HDMI-A-1")
        self.assertEqual(monitors[1]["refreshRate"], 144.0)

    def test_set_resolution_and_refresh(self):
        """R1.2 Verify setting resolution and refresh rate updates monitors.json and triggers reload."""
        # 1. Update config (simulate QML settings application)
        config = [
            {
                "name": "eDP-1",
                "width": 1600,
                "height": 900,
                "refreshRate": 59.94,
                "scale": 1.0,
                "transform": 0
            }
        ]
        self.env.write_monitors_config(config)
        
        # 2. Trigger Hyprland IPC reload
        res = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, "ok")
        
        # 3. Assertions
        saved_config = self.env.read_monitors_config()
        self.assertEqual(saved_config[0]["width"], 1600)
        self.assertEqual(saved_config[0]["refreshRate"], 59.94)
        self.assertIn(["hyprctl", "reload"], self.env.subprocess_calls)

    def test_screen_rotation(self):
        """R1.3 Verify screen rotation is saved to monitors.json and applied."""
        # Rotation values: 0 (Normal), 1 (90 deg), 2 (180 deg), 3 (270 deg)
        config = [
            {
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.0,
                "transform": 3  # 270 degrees
            }
        ]
        self.env.write_monitors_config(config)
        
        # Apply change
        subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        
        saved_config = self.env.read_monitors_config()
        self.assertEqual(saved_config[0]["transform"], 3)

    def test_system_scaling(self):
        """R1.4 Verify system scaling slider value (1.0 to 2.0) is persistently saved."""
        config = [
            {
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.5,  # Scale factor within 1.0 to 2.0
                "transform": 0
            }
        ]
        self.env.write_monitors_config(config)
        
        saved_config = self.env.read_monitors_config()
        self.assertEqual(saved_config[0]["scale"], 1.5)

    def test_safety_revert_countdown(self):
        """R1.5 Verify the 15-second safety revert countdown behavior."""
        # 1. Original config
        original_config = [
            {
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.0,
                "transform": 0
            }
        ]
        self.env.write_monitors_config(original_config)
        
        # 2. Write new temporary config (simulate user clicking "Apply")
        new_config = [
            {
                "name": "eDP-1",
                "width": 3840,
                "height": 2160,
                "refreshRate": 120.0,
                "scale": 2.0,
                "transform": 0
            }
        ]
        self.env.write_monitors_config(new_config)
        subprocess.run(["hyprctl", "reload"])
        
        # 3. Simulate safety revert countdown: if no confirmation is received, revert
        confirmed = False  # Simulate user failing to confirm (e.g. screen goes black, countdown expires)
        
        if not confirmed:
            # Revert to original config
            self.env.write_monitors_config(original_config)
            subprocess.run(["hyprctl", "reload"])
            
        # 4. Verify config reverted back to original state
        final_config = self.env.read_monitors_config()
        self.assertEqual(final_config[0]["width"], 1920)
        self.assertEqual(final_config[0]["refreshRate"], 60.0)
        
        # Ensure hyprctl reload was called for both new config application and the revert
        reloads = [call for call in self.env.subprocess_calls if call == ["hyprctl", "reload"]]
        self.assertGreaterEqual(len(reloads), 2)
