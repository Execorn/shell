import os
import json
import subprocess
from tests.e2e.mock_env import E2ETestCase

class DisplayManager:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.monitors_path = os.path.join(self.config_dir, 'monitors.json')
        
    def get_active_monitors(self):
        try:
            res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
            if res.returncode != 0 or not res.stdout.strip():
                return []
            return json.loads(res.stdout)
        except Exception:
            return []

    def load_config(self):
        if not os.path.exists(self.monitors_path):
            return self.recover_corrupted()
        try:
            with open(self.monitors_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return self.recover_corrupted()
                return json.loads(content)
        except Exception:
            return self.recover_corrupted()

    def recover_corrupted(self):
        monitors = self.get_active_monitors()
        self.save_config(monitors)
        return monitors

    def save_config(self, config):
        with open(self.monitors_path, 'w') as f:
            json.dump(config, f, indent=2)

    def apply_settings(self, monitor_id, resolution, refresh_rate, rotation, scale, confirm_callback=None):
        scale = max(1.0, min(2.0, scale))
        current_config = self.load_config()
        
        monitor_found = False
        new_config = []
        width, height = map(int, resolution.split("x"))
        
        for m in current_config:
            if m.get("id") == monitor_id:
                monitor_found = True
                if (m.get("width") == width and m.get("height") == height and 
                    m.get("refreshRate") == refresh_rate and m.get("transform") == rotation and 
                    m.get("scale") == scale):
                    new_config.append(m)
                    continue
                m_copy = m.copy()
                m_copy.update({
                    "width": width,
                    "height": height,
                    "refreshRate": refresh_rate,
                    "transform": rotation,
                    "scale": scale
                })
                new_config.append(m_copy)
            else:
                new_config.append(m)
                
        if not monitor_found:
            new_config.append({
                "id": monitor_id,
                "width": width,
                "height": height,
                "refreshRate": refresh_rate,
                "transform": rotation,
                "scale": scale
            })

        # Check optimization
        if os.path.exists(self.monitors_path):
            try:
                with open(self.monitors_path, 'r') as f:
                    old_file_content = json.load(f)
                if old_file_content == new_config:
                    return True
            except Exception:
                pass

        previous_config = current_config
        self.save_config(new_config)
        
        subprocess.run(["hyprctl", "reload"])

        if confirm_callback:
            confirmed = confirm_callback()
        else:
            confirmed = False
            
        if not confirmed:
            self.save_config(previous_config)
            subprocess.run(["hyprctl", "reload"])
            return False
            
        return True


class TestDisplayBounds(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = DisplayManager(self.env.caelestia_config_dir)

    def test_scaling_boundaries(self):
        # 1. Scaling below 1.0 (should clamp to 1.0)
        self.manager.apply_settings(0, "1920x1080", 60.0, 0, 0.5, lambda: True)
        config = self.manager.load_config()
        self.assertEqual(config[0]["scale"], 1.0)

        # 2. Scaling above 2.0 (should clamp to 2.0)
        self.manager.apply_settings(0, "1920x1080", 60.0, 0, 2.5, lambda: True)
        config = self.manager.load_config()
        self.assertEqual(config[0]["scale"], 2.0)

    def test_empty_monitors_output(self):
        # Setup mock env to return empty/invalid hyprctl output
        self.env.active_monitors = []
        monitors = self.manager.get_active_monitors()
        self.assertEqual(monitors, [])

        # Should recover gracefully (empty monitors file is created)
        recovered = self.manager.recover_corrupted()
        self.assertEqual(recovered, [])
        self.assertTrue(os.path.exists(self.manager.monitors_path))

    def test_safety_revert_timeout(self):
        # Set initial config
        initial = [{"id": 0, "width": 1920, "height": 1080, "refreshRate": 60.0, "transform": 0, "scale": 1.0}]
        self.manager.save_config(initial)

        # Clear subprocess calls track
        self.env.subprocess_calls.clear()

        # Apply settings, simulate user countdown timeout (confirm_callback returns False)
        applied = self.manager.apply_settings(0, "1280x720", 60.0, 0, 1.2, lambda: False)
        self.assertFalse(applied)

        # Config should be reverted to initial
        config = self.manager.load_config()
        self.assertEqual(config[0]["width"], 1920)
        self.assertEqual(config[0]["scale"], 1.0)

        # Assert hyprctl reload was run twice (once to apply, once to revert)
        reloads = [c for c in self.env.subprocess_calls if c == ["hyprctl", "reload"]]
        self.assertEqual(len(reloads), 2)

    def test_duplicate_config_optimization(self):
        # Set initial config
        initial = [{"id": 0, "width": 1920, "height": 1080, "refreshRate": 60.0, "transform": 0, "scale": 1.0}]
        self.manager.save_config(initial)

        # Clear calls track
        self.env.subprocess_calls.clear()

        # Apply same settings
        applied = self.manager.apply_settings(0, "1920x1080", 60.0, 0, 1.0, lambda: True)
        self.assertTrue(applied)

        # Should skip reload
        reloads = [c for c in self.env.subprocess_calls if c == ["hyprctl", "reload"]]
        self.assertEqual(len(reloads), 0)

    def test_corrupted_monitors_json_recovery(self):
        # Write corrupted content
        with open(self.manager.monitors_path, 'w') as f:
            f.write("{invalid_json:")

        # Load config should automatically recover and return active monitors from hyprctl
        config = self.manager.load_config()
        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["name"], "eDP-1")
        self.assertEqual(config[0]["scale"], 1.0)
