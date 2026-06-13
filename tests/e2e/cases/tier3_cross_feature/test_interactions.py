import os
import json
import subprocess
import urllib.request
from tests.e2e.mock_env import E2ETestCase

class TestInteractions(E2ETestCase):
    def test_display_scaling_effects_scheme(self):
        # 1. Update display settings (resolution, refresh, scale, rotation)
        monitors = [
            {
                "id": 0,
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.25,
                "transform": 1,
                "focused": True
            }
        ]
        self.env.write_monitors_config(monitors)
        
        # Apply layout changes
        res_reload = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        self.assertEqual(res_reload.returncode, 0)
        
        # Update active monitors in env to reflect change for subsequent checks
        self.env.active_monitors = monitors
        
        # 2. Select theme scheme color flavor
        res_scheme = subprocess.run(["caelestia", "scheme", "set", "vibrant"], capture_output=True, text=True)
        self.assertEqual(res_scheme.returncode, 0)
        self.assertIn("Scheme updated successfully", res_scheme.stdout)
        
        # 3. Assertions
        config_monitors = self.env.read_monitors_config()
        self.assertEqual(len(config_monitors), 1)
        self.assertEqual(config_monitors[0]["scale"], 1.25)
        self.assertEqual(config_monitors[0]["transform"], 1)
        
        # Query active monitors via hyprctl to verify reload
        res_mon = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        active_mon = json.loads(res_mon.stdout)
        self.assertEqual(active_mon[0]["scale"], 1.25)
        
        # Verify subprocess calls
        calls = self.env.subprocess_calls
        self.assertTrue(any("hyprctl" in c and "reload" in c for c in calls))
        self.assertTrue(any("caelestia" in c and "scheme" in c and "set" in c and "vibrant" in c for c in calls))

    def test_update_service_runs_with_plugins(self):
        # 1. Setup active plugins in sandbox
        plugins = {
            "plugin_weather": {
                "metadata.json": {
                    "name": "Weather Widget",
                    "version": "1.0.0",
                    "author": "Developer A",
                    "status": "enabled"
                }
            },
            "plugin_clock": {
                "metadata.json": {
                    "name": "Clock Widget",
                    "version": "1.1.0",
                    "author": "Developer B",
                    "status": "enabled"
                }
            }
        }
        for name, files in plugins.items():
            p_dir = os.path.join(self.env.plugins_dir, name)
            os.makedirs(p_dir, exist_ok=True)
            for fname, content in files.items():
                with open(os.path.join(p_dir, fname), 'w') as f:
                    json.dump(content, f, indent=2)
                    
        # 2. Start upgrade service
        res_start = subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_start.returncode, 0)
        
        # Verify it is active
        res_active = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_active.stdout.strip(), "active")
        
        # Stream upgrade logs
        p_logs = subprocess.Popen(["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f"], stdout=subprocess.PIPE, text=True)
        stdout, _ = p_logs.communicate()
        self.assertIn("Starting Caelestia Upgrade", stdout)
        self.assertIn("Caelestia Upgrade completed successfully", stdout)
        
        # 3. Assertions
        # Verify service is now inactive after log streaming finishes (as designed in mock_env)
        res_status = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_status.stdout.strip(), "inactive")
        
        # Verify plugins are still intact
        self.assertTrue(os.path.exists(os.path.join(self.env.plugins_dir, "plugin_weather", "metadata.json")))
        self.assertTrue(os.path.exists(os.path.join(self.env.plugins_dir, "plugin_clock", "metadata.json")))
        
        with open(os.path.join(self.env.plugins_dir, "plugin_weather", "metadata.json")) as f:
            data = json.load(f)
            self.assertEqual(data["status"], "enabled")

    def test_weather_locale_change_theme_dark(self):
        # 1. Update weather location to Tokyo, resolving coordinates via API
        # Using geocoding mock from mock_env
        url = "https://geocoding-api.open-meteo.com/v1/search?name=Tokyo"
        response = urllib.request.urlopen(url)
        res_data = json.loads(response.read().decode('utf-8'))
        
        results = res_data.get("results", [])
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "Tokyo")
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        self.assertAlmostEqual(lat, 35.6762)
        self.assertAlmostEqual(lon, 139.6503)
        
        # Update shell config
        shell_config = self.env.read_shell_config()
        if "services" not in shell_config:
            shell_config["services"] = {}
        shell_config["services"]["weatherLocation"] = "Tokyo"
        shell_config["services"]["weatherCoordinates"] = f"{lat},{lon}"
        
        # Coinciding with Light/Dark theme toggle
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["darkMode"] = True
        shell_config["theme"]["flavor"] = "vibrant"
        self.env.write_shell_config(shell_config)
        
        # Trigger palette regeneration
        res_scheme = subprocess.run(["caelestia", "scheme", "set", "vibrant"], capture_output=True, text=True)
        self.assertEqual(res_scheme.returncode, 0)
        
        # Assertions
        updated_config = self.env.read_shell_config()
        self.assertEqual(updated_config["services"]["weatherLocation"], "Tokyo")
        self.assertEqual(updated_config["services"]["weatherCoordinates"], "35.6762,139.6503")
        self.assertTrue(updated_config["theme"]["darkMode"])
        
        calls = self.env.subprocess_calls
        self.assertTrue(any("caelestia" in c and "scheme" in c and "set" in c and "vibrant" in c for c in calls))

    def test_scheme_regenerated_on_wallpaper_extracted(self):
        # 1. Change wallpaper
        shell_config = self.env.read_shell_config()
        if "appearance" not in shell_config:
            shell_config["appearance"] = {}
        wallpaper_path = "/home/execorn/pictures/wallpaper.jpg"
        shell_config["appearance"]["wallpaper"] = wallpaper_path
        self.env.write_shell_config(shell_config)
        
        # 2. Extract colors (simulate extracting a palette of Material 3 key colors)
        # We simulate extraction by setting custom static colors in the config
        extracted_colors = {
            "primary": "#ffb4ab",
            "secondary": "#e7bdb7",
            "tertiary": "#dec48f",
            "error": "#ffb4ab"
        }
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["extractedColors"] = extracted_colors
        shell_config["theme"]["flavor"] = "tonal-spot"
        self.env.write_shell_config(shell_config)
        
        # Apply scheme reload
        res_scheme = subprocess.run(["caelestia", "scheme", "set", "tonal-spot"], capture_output=True, text=True)
        self.assertEqual(res_scheme.returncode, 0)
        
        # Assertions
        updated_config = self.env.read_shell_config()
        self.assertEqual(updated_config["appearance"]["wallpaper"], wallpaper_path)
        self.assertEqual(updated_config["theme"]["extractedColors"]["primary"], "#ffb4ab")
        self.assertEqual(updated_config["theme"]["flavor"], "tonal-spot")
        
        calls = self.env.subprocess_calls
        self.assertTrue(any("caelestia" in c and "scheme" in c and "set" in c and "tonal-spot" in c for c in calls))

    def test_plugin_crashes_during_upgrade(self):
        # 1. Start upgrade service
        res_start = subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_start.returncode, 0)
        
        # 2. Simulate plugin crash during the upgrade log streaming
        plugin_name = "faulty_plugin"
        plugin_path = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(plugin_path, exist_ok=True)
        
        # Write metadata showing crashed status
        metadata = {
            "name": "Faulty Plugin",
            "version": "1.0.0",
            "author": "Tester",
            "status": "crashed"
        }
        with open(os.path.join(plugin_path, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
            
        # Write error log
        stack_trace = "Error: Cannot load QML module. Segmentation fault.\n"
        with open(os.path.join(plugin_path, "error.log"), "w") as f:
            f.write(stack_trace)
            
        # Stream logs (which transitions service to inactive)
        p_logs = subprocess.Popen(["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f"], stdout=subprocess.PIPE, text=True)
        stdout, _ = p_logs.communicate()
        self.assertIn("Starting Caelestia Upgrade", stdout)
        self.assertIn("Caelestia Upgrade completed successfully", stdout)
        
        # Assertions
        res_status = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_status.stdout.strip(), "inactive")
        
        # Verify plugin crash status and logs
        plugin_meta_path = os.path.join(self.env.plugins_dir, plugin_name, "metadata.json")
        plugin_log_path = os.path.join(self.env.plugins_dir, plugin_name, "error.log")
        self.assertTrue(os.path.exists(plugin_meta_path))
        self.assertTrue(os.path.exists(plugin_log_path))
        
        with open(plugin_meta_path) as f:
            meta = json.load(f)
            self.assertEqual(meta["status"], "crashed")
            
        with open(plugin_log_path) as f:
            log_content = f.read()
            self.assertIn("Segmentation fault", log_content)
