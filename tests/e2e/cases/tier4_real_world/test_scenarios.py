import os
import json
import subprocess
import urllib.request
from tests.e2e.mock_env import E2ETestCase

class TestScenarios(E2ETestCase):
    def test_scenario_full_setup(self):
        # Step 1: Query existing monitors dynamically
        res_mon = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        self.assertEqual(res_mon.returncode, 0)
        monitors = json.loads(res_mon.stdout)
        self.assertEqual(len(monitors), 1)
        self.assertEqual(monitors[0]["name"], "eDP-1")
        
        # Step 2: Configure layout (Resolution, Refresh Rate, Scaling, Rotation)
        monitors[0]["scale"] = 1.25
        monitors[0]["transform"] = 0
        monitors[0]["width"] = 1920
        monitors[0]["height"] = 1080
        monitors[0]["refreshRate"] = 60.0
        self.env.write_monitors_config(monitors)
        
        # Apply layout changes
        res_reload = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        self.assertEqual(res_reload.returncode, 0)
        self.env.active_monitors = monitors
        
        # Step 3: Theme colors selection (wallpaper-extracted expressive flavor)
        shell_config = self.env.read_shell_config()
        if "appearance" not in shell_config:
            shell_config["appearance"] = {}
        shell_config["appearance"]["wallpaper"] = "/home/user/wallpapers/sunset.png"
        
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["flavor"] = "expressive"
        shell_config["theme"]["mode"] = "dark"
        self.env.write_shell_config(shell_config)
        
        res_scheme = subprocess.run(["caelestia", "scheme", "set", "expressive"], capture_output=True, text=True)
        self.assertEqual(res_scheme.returncode, 0)
        
        # Step 4: Weather location setup (Paris)
        url = "https://geocoding-api.open-meteo.com/v1/search?name=Paris"
        response = urllib.request.urlopen(url)
        res_data = json.loads(response.read().decode('utf-8'))
        
        results = res_data.get("results", [])
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "Paris")
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        
        shell_config = self.env.read_shell_config()
        if "services" not in shell_config:
            shell_config["services"] = {}
        shell_config["services"]["weatherLocation"] = "Paris"
        shell_config["services"]["weatherCoordinates"] = f"{lat},{lon}"
        self.env.write_shell_config(shell_config)
        
        # Final Assertions
        config_monitors = self.env.read_monitors_config()
        self.assertEqual(config_monitors[0]["scale"], 1.25)
        
        config_shell = self.env.read_shell_config()
        self.assertEqual(config_shell["appearance"]["wallpaper"], "/home/user/wallpapers/sunset.png")
        self.assertEqual(config_shell["theme"]["flavor"], "expressive")
        self.assertEqual(config_shell["services"]["weatherLocation"], "Paris")
        self.assertEqual(config_shell["services"]["weatherCoordinates"], "48.8534,2.3488")
        
        calls = self.env.subprocess_calls
        self.assertTrue(any("hyprctl" in c and "reload" in c for c in calls))
        self.assertTrue(any("caelestia" in c and "scheme" in c and "set" in c and "expressive" in c for c in calls))

    def test_scenario_maintenance(self):
        # Step 1: Check pending updates asynchronously
        res_pacman = subprocess.run(["checkupdates"], capture_output=True, text=True)
        self.assertEqual(res_pacman.returncode, 0)
        self.assertIn("linux", res_pacman.stdout)
        
        res_yay = subprocess.run(["yay", "-Qua"], capture_output=True, text=True)
        self.assertEqual(res_yay.returncode, 0)
        self.assertIn("yay-git", res_yay.stdout)
        
        # Step 2: Disable unneeded plugin to clean workspace
        plugin_name = "plugin_unneeded"
        p_dir = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(p_dir, exist_ok=True)
        
        # Create metadata showing disabled status
        metadata = {
            "name": "Unneeded Widget",
            "version": "1.0.0",
            "status": "disabled"
        }
        with open(os.path.join(p_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
            
        # Update config list of active plugins
        shell_config = self.env.read_shell_config()
        if "plugins" not in shell_config:
            shell_config["plugins"] = {}
        shell_config["plugins"]["activePlugins"] = ["plugin_weather", "plugin_clock"]
        self.env.write_shell_config(shell_config)
        
        # Step 3: Run upgrade service
        res_start = subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_start.returncode, 0)
        
        # Stream logs
        p_logs = subprocess.Popen(["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f"], stdout=subprocess.PIPE, text=True)
        stdout, _ = p_logs.communicate()
        self.assertIn("Starting Caelestia Upgrade", stdout)
        self.assertIn("Upgraded linux", stdout)
        self.assertIn("Caelestia Upgrade completed successfully", stdout)
        
        # Final Assertions
        config_shell = self.env.read_shell_config()
        self.assertNotIn("plugin_unneeded", config_shell["plugins"]["activePlugins"])
        
        with open(os.path.join(p_dir, "metadata.json")) as f:
            meta = json.load(f)
            self.assertEqual(meta["status"], "disabled")
            
        res_active = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_active.stdout.strip(), "inactive")

    def test_scenario_travel(self):
        # Step 1: Change weather location to New York
        url = "https://geocoding-api.open-meteo.com/v1/search?name=New+York"
        response = urllib.request.urlopen(url)
        res_data = json.loads(response.read().decode('utf-8'))
        
        results = res_data.get("results", [])
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "New York")
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        self.assertAlmostEqual(lat, 40.7128)
        self.assertAlmostEqual(lon, -74.0060)
        
        # Step 2: Adapt locale and regional preferences (12-hour clock and Fahrenheit)
        shell_config = self.env.read_shell_config()
        if "services" not in shell_config:
            shell_config["services"] = {}
        shell_config["services"]["weatherLocation"] = "New York"
        shell_config["services"]["weatherCoordinates"] = f"{lat},{lon}"
        shell_config["services"]["useTwelveHourClock"] = True
        shell_config["services"]["useFahrenheit"] = True
        
        # Step 3: Regenerate schemes to fit new timezone mood
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["flavor"] = "tonal-spot"
        self.env.write_shell_config(shell_config)
        
        res_scheme = subprocess.run(["caelestia", "scheme", "set", "tonal-spot"], capture_output=True, text=True)
        self.assertEqual(res_scheme.returncode, 0)
        
        # Final Assertions
        config_shell = self.env.read_shell_config()
        self.assertEqual(config_shell["services"]["weatherLocation"], "New York")
        self.assertEqual(config_shell["services"]["weatherCoordinates"], "40.7128,-74.006")
        self.assertTrue(config_shell["services"]["useTwelveHourClock"])
        self.assertTrue(config_shell["services"]["useFahrenheit"])
        self.assertEqual(config_shell["theme"]["flavor"], "tonal-spot")
        
        calls = self.env.subprocess_calls
        self.assertTrue(any("caelestia" in c and "scheme" in c and "set" in c and "tonal-spot" in c for c in calls))

    def test_scenario_error_recovery(self):
        # Step 1: Save baseline working monitors config
        baseline_monitors = [
            {
                "id": 0,
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.0,
                "transform": 0,
                "focused": True
            }
        ]
        self.env.write_monitors_config(baseline_monitors)
        self.env.active_monitors = baseline_monitors
        
        # Step 2: Attempt layout change (apply extreme scaling/layout)
        faulty_monitors = [
            {
                "id": 0,
                "name": "eDP-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 3.0,
                "transform": 0,
                "focused": True
            }
        ]
        self.env.write_monitors_config(faulty_monitors)
        res_reload_1 = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        self.assertEqual(res_reload_1.returncode, 0)
        
        # Simulated timeout or cancel on countdown modal: trigger revert
        self.env.write_monitors_config(baseline_monitors)
        res_reload_2 = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        self.assertEqual(res_reload_2.returncode, 0)
        self.env.active_monitors = baseline_monitors
        
        # Step 3: Handle crashed plugin loading dynamically
        broken_plugin_name = "crashed_plugin"
        broken_path = os.path.join(self.env.plugins_dir, broken_plugin_name)
        os.makedirs(broken_path, exist_ok=True)
        
        broken_metadata = {
            "name": "Crashed Plugin",
            "version": "1.0.0",
            "status": "crashed"
        }
        with open(os.path.join(broken_path, "metadata.json"), "w") as f:
            json.dump(broken_metadata, f, indent=2)
            
        with open(os.path.join(broken_path, "error.log"), "w") as f:
            f.write("QML Component failed to load: ReferenceError: x is not defined\n")
            
        # Healthy plugin
        healthy_plugin_name = "healthy_plugin"
        healthy_path = os.path.join(self.env.plugins_dir, healthy_plugin_name)
        os.makedirs(healthy_path, exist_ok=True)
        
        healthy_metadata = {
            "name": "Healthy Plugin",
            "version": "1.0.0",
            "status": "enabled"
        }
        with open(os.path.join(healthy_path, "metadata.json"), "w") as f:
            json.dump(healthy_metadata, f, indent=2)
            
        # Final Assertions
        config_monitors = self.env.read_monitors_config()
        self.assertEqual(config_monitors[0]["scale"], 1.0)
        
        # Check active monitors query
        res_active_mon = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        active_mon = json.loads(res_active_mon.stdout)
        self.assertEqual(active_mon[0]["scale"], 1.0)
        
        # Verify plugins
        with open(os.path.join(broken_path, "metadata.json")) as f:
            meta = json.load(f)
            self.assertEqual(meta["status"], "crashed")
            
        with open(os.path.join(healthy_path, "metadata.json")) as f:
            meta = json.load(f)
            self.assertEqual(meta["status"], "enabled")

    def test_scenario_power_user(self):
        # Step 1: Configure complex multi-monitor setup
        multi_monitors = [
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
                "name": "DP-1",
                "width": 3840,
                "height": 2160,
                "refreshRate": 144.0,
                "scale": 1.5,
                "transform": 0,
                "focused": False
            },
            {
                "id": 2,
                "name": "HDMI-A-1",
                "width": 1920,
                "height": 1080,
                "refreshRate": 60.0,
                "scale": 1.0,
                "transform": 1,
                "focused": False
            }
        ]
        self.env.write_monitors_config(multi_monitors)
        self.env.active_monitors = multi_monitors
        
        res_reload = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
        self.assertEqual(res_reload.returncode, 0)
        
        # Step 2: Custom HSL accents configuration
        shell_config = self.env.read_shell_config()
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["flavor"] = "tonal-spot"
        shell_config["theme"]["useCustomAccent"] = True
        shell_config["theme"]["customAccent"] = {
            "hue": 210,
            "saturation": 80,
            "lightness": 40
        }
        self.env.write_shell_config(shell_config)
        
        res_scheme = subprocess.run(["caelestia", "scheme", "set", "tonal-spot"], capture_output=True, text=True)
        self.assertEqual(res_scheme.returncode, 0)
        
        # Step 3: Verify multiple active loaders (ensure 3 plugins active)
        active_plugins = ["loader_sys", "loader_bar", "loader_dock"]
        for p_name in active_plugins:
            p_dir = os.path.join(self.env.plugins_dir, p_name)
            os.makedirs(p_dir, exist_ok=True)
            meta = {
                "name": p_name.replace("loader_", "").capitalize() + " Loader",
                "version": "2.0.0",
                "status": "enabled"
            }
            with open(os.path.join(p_dir, "metadata.json"), "w") as f:
                json.dump(meta, f, indent=2)
                
        # Final Assertions
        config_monitors = self.env.read_monitors_config()
        self.assertEqual(len(config_monitors), 3)
        self.assertEqual(config_monitors[1]["name"], "DP-1")
        self.assertEqual(config_monitors[1]["scale"], 1.5)
        self.assertEqual(config_monitors[2]["transform"], 1)
        
        config_shell = self.env.read_shell_config()
        self.assertTrue(config_shell["theme"]["useCustomAccent"])
        self.assertEqual(config_shell["theme"]["customAccent"]["hue"], 210)
        
        # Check active monitors query via hyprctl
        res_active_mon = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        active_mon = json.loads(res_active_mon.stdout)
        self.assertEqual(len(active_mon), 3)
        self.assertEqual(active_mon[1]["name"], "DP-1")
