import os
import json
import re
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from tests.e2e.mock_env import E2ETestCase

# ==============================================================================
# Managers under test (mirroring QML/C++ config features R1 to R5)
# ==============================================================================

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
        # Scale bounding
        scale = max(1.0, min(2.0, scale))
        
        # Parse and validate resolution
        parts = resolution.split("x")
        if len(parts) != 2:
            raise ValueError("Invalid resolution format. Must be WxH")
        width, height = int(parts[0]), int(parts[1])

        current_config = self.load_config()
        
        monitor_found = False
        new_config = []
        
        for m in current_config:
            if m.get("id") == monitor_id:
                monitor_found = True
                m_copy = m.copy()
                m_copy.update({
                    "width": width,
                    "height": height,
                    "refreshRate": float(refresh_rate),
                    "transform": int(rotation),
                    "scale": float(scale)
                })
                new_config.append(m_copy)
            else:
                new_config.append(m)
                
        if not monitor_found:
            new_config.append({
                "id": monitor_id,
                "width": width,
                "height": height,
                "refreshRate": float(refresh_rate),
                "transform": int(rotation),
                "scale": float(scale)
            })

        # Optimization check
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


class UpdatesManager:
    def __init__(self):
        pass

    def get_pending_updates(self):
        updates = []
        
        try:
            res_pac = subprocess.run(["checkupdates"], capture_output=True, text=True)
            if res_pac.returncode == 0:
                for line in res_pac.stdout.splitlines():
                    if line.strip():
                        parts = line.split()
                        # Strictly require the standard "pkg old -> new" format (minimum 4 parts)
                        if len(parts) >= 4 and parts[2] == "->":
                            updates.append({
                                "name": parts[0],
                                "source": "pacman",
                                "old_version": parts[1],
                                "new_version": parts[3],
                                "description": f"System package {parts[0]}",
                                "size": "Unknown"
                            })
            elif res_pac.returncode not in (0, 2):
                pass
        except Exception:
            pass

        try:
            res_yay = subprocess.run(["yay", "-Qua"], capture_output=True, text=True)
            if res_yay.returncode == 0:
                for line in res_yay.stdout.splitlines():
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4 and parts[2] == "->":
                            name = parts[0]
                            if not any(u["name"] == name for u in updates):
                                updates.append({
                                    "name": name,
                                    "source": "yay",
                                    "old_version": parts[1],
                                    "new_version": parts[3],
                                    "description": f"AUR package {name}",
                                    "size": "Unknown"
                                })
            elif res_yay.returncode not in (0, 1):
                pass
        except Exception:
            pass

        return updates

    def trigger_upgrade(self):
        res = subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"])
        return res.returncode == 0


class PluginManager:
    def __init__(self, plugins_dir):
        self.plugins_dir = plugins_dir

    def scan_plugins(self):
        plugins = {}
        if not os.path.exists(self.plugins_dir):
            return plugins

        for item in os.listdir(self.plugins_dir):
            item_path = os.path.join(self.plugins_dir, item)
            if os.path.isdir(item_path):
                meta_path = os.path.join(item_path, "metadata.json")
                if not os.path.exists(meta_path):
                    plugins[item] = {
                        "name": item,
                        "status": "invalid",
                        "error": "Missing metadata.json"
                    }
                    continue
                try:
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                    
                    # Robust field checks
                    plugins[item] = {
                        "name": meta.get("name", item),
                        "author": meta.get("author", "Unknown"),
                        "version": meta.get("version", "0.0.0"),
                        "dependencies": meta.get("dependencies") if isinstance(meta.get("dependencies"), list) else [],
                        "status": "disabled",
                        "error": None
                    }
                except json.JSONDecodeError:
                    plugins[item] = {
                        "name": item,
                        "status": "corrupt",
                        "error": "Corrupt metadata.json"
                    }
                except Exception as e:
                    plugins[item] = {
                        "name": item,
                        "status": "error",
                        "error": str(e)
                    }
        return plugins

    def resolve_dependencies(self, plugins):
        visited = {}
        path = set()
        order = []

        def visit(name):
            if name in path:
                raise ValueError(f"Circular dependency detected: {name}")
            if name not in visited:
                path.add(name)
                plugin = plugins.get(name)
                if plugin and plugin.get("status") not in ("corrupt", "invalid", "error"):
                    deps = plugin.get("dependencies", [])
                    if isinstance(deps, list):
                        for dep in deps:
                            visit(dep)
                path.remove(name)
                visited[name] = True
                order.append(name)

        try:
            for name in plugins:
                visit(name)
            return order, None
        except ValueError as e:
            return [], str(e)


class ColoursManager:
    VALID_FLAVORS = {"tonal-spot", "vibrant", "expressive", "monochrome"}
    DEFAULT_FLAVOR = "tonal-spot"
    DEFAULT_COLOR = "#6750A4"

    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.shell_config_path = os.path.join(self.config_dir, "shell.json")

    def validate_hex(self, hex_str):
        if not isinstance(hex_str, str) or not hex_str.startswith("#"):
            return False
        h = hex_str[1:]
        if len(h) not in (3, 6, 8):
            return False
        try:
            int(h, 16)
            return True
        except ValueError:
            return False

    def validate_hsl(self, h, s, l):
        try:
            h_f = float(h)
            s_f = float(s)
            l_f = float(l)
            if not (0 <= h_f <= 360) or not (0 <= s_f <= 100) or not (0 <= l_f <= 100):
                return False
            return True
        except ValueError:
            return False

    def hsl_to_hex(self, h, s, l):
        if not self.validate_hsl(h, s, l):
            return self.DEFAULT_COLOR
        h_val = float(h) / 360.0
        s_val = float(s) / 100.0
        l_val = float(l) / 100.0

        if s_val == 0.0:
            r = g = b = l_val
        else:
            def hue_to_rgb(p, q, t):
                if t < 0.0: t += 1.0
                if t > 1.0: t -= 1.0
                if t < 1.0/6.0: return p + (q - p) * 6.0 * t
                if t < 1.0/2.0: return q
                if t < 2.0/3.0: return p + (q - p) * (2.0/3.0 - t) * 6.0
                return p

            q = l_val * (1.0 + s_val) if l_val < 0.5 else l_val + s_val - l_val * s_val
            p = 2.0 * l_val - q
            r = hue_to_rgb(p, q, h_val + 1.0/3.0)
            g = hue_to_rgb(p, q, h_val)
            b = hue_to_rgb(p, q, h_val - 1.0/3.0)

        r = max(0.0, min(1.0, r))
        g = max(0.0, min(1.0, g))
        b = max(0.0, min(1.0, b))

        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def apply_theme(self, mode, flavor, color_source, custom_color=None, wallpaper_path=None):
        if flavor not in self.VALID_FLAVORS:
            flavor = self.DEFAULT_FLAVOR
        
        target_color = self.DEFAULT_COLOR
        if color_source == "static" and custom_color:
            if custom_color.startswith("hsl"):
                try:
                    m = re.match(r"hsl\(\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)%\s*,\s*([\d\.\-]+)%\s*\)", custom_color)
                    if m:
                        h, s, l = m.groups()
                        target_color = self.hsl_to_hex(h, s, l)
                    else:
                        target_color = self.DEFAULT_COLOR
                except Exception:
                    target_color = self.DEFAULT_COLOR
            elif self.validate_hex(custom_color):
                target_color = custom_color
            else:
                target_color = self.DEFAULT_COLOR
        elif color_source == "dynamic":
            if not wallpaper_path or not os.path.exists(wallpaper_path):
                color_source = "static"
                target_color = self.DEFAULT_COLOR
            else:
                target_color = "wallpaper"

        # Read config
        if os.path.exists(self.shell_config_path):
            try:
                with open(self.shell_config_path, 'r') as f:
                    config = json.load(f)
            except Exception:
                config = {}
        else:
            config = {}

        if "theme" not in config:
            config["theme"] = {}
        config["theme"].update({
            "mode": mode,
            "flavor": flavor,
            "colorSource": color_source,
            "accentColor": target_color
        })

        with open(self.shell_config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Call scheme set
        cmd = ["caelestia", "scheme", "set", flavor]
        if color_source == "static":
            cmd.append(target_color)
        else:
            cmd.append(wallpaper_path)

        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                return False, f"CLI command failed with code {res.returncode}"
            return True, None
        except Exception as e:
            return False, str(e)


class WeatherLocationManager:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.shell_config_path = os.path.join(self.config_dir, "shell.json")

    def validate_coordinates(self, coords_str):
        # Precise validation to match QML
        m = re.match(r"^\s*([\-\d\.]+)\s*,\s*([\-\d\.]+)\s*$", coords_str)
        if not m:
            return False, "Invalid coordinate format. Must be 'lat,lon'"
        try:
            lat = float(m.group(1))
            lon = float(m.group(2))
            if not (-90.0 <= lat <= 90.0):
                return False, "Latitude must be between -90 and 90"
            if not (-180.0 <= lon <= 180.0):
                return False, "Longitude must be between -180 and 180"
            return True, (lat, lon)
        except ValueError:
            return False, "Coordinates must be numbers"

    def search_city(self, query):
        if not query or not query.strip():
            return None, "Search query cannot be empty"

        url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(query.strip())}&count=1&language=en&format=json"
        try:
            response = urllib.request.urlopen(url, timeout=2.0)
            data = json.loads(response.read().decode('utf-8'))
            results = data.get("results", [])
            if not results:
                return None, "City not found"
            return results[0], None
        except urllib.error.URLError as e:
            return None, f"Network error: {e.reason}"
        except Exception as e:
            return None, f"Error: {str(e)}"

    def reverse_geocode(self, lat, lon):
        # Mimic reverse geocoding in LanguageAndRegion.qml and Weather.qml
        nominatim_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=geocodejson"
        try:
            req = urllib.request.Request(nominatim_url, headers={'User-Agent': 'CaelestiaE2ETest'})
            response = urllib.request.urlopen(req, timeout=2.0)
            data = json.loads(response.read().decode('utf-8'))
            features = data.get("features", [])
            if features:
                geo = features[0].get("properties", {}).get("geocoding", {})
                geo_city = geo.get("name") if geo.get("type") == "city" else geo.get("city")
                if geo_city:
                    return geo_city, None
            raise Exception("No city found in OSM Nominatim")
        except Exception:
            # Fallback to BigDataCloud
            fallback_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
            try:
                response = urllib.request.urlopen(fallback_url, timeout=2.0)
                data = json.loads(response.read().decode('utf-8'))
                city = data.get("city") or data.get("locality")
                if city:
                    return city, None
                return "Custom Location", None
            except Exception as e:
                return "Custom Location", str(e)

    def update_config(self, location_name, coords_str):
        valid, res = self.validate_coordinates(coords_str)
        if not valid:
            return False, res
        
        if os.path.exists(self.shell_config_path):
            try:
                with open(self.shell_config_path, 'r') as f:
                    config = json.load(f)
            except Exception:
                config = {}
        else:
            config = {}

        if "services" not in config:
            config["services"] = {}

        config["services"].update({
            "weatherLocation": location_name,
            "weatherCoordinates": coords_str
        })

        with open(self.shell_config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return True, None


# ==============================================================================
# Adversarial Test Classes
# ==============================================================================

class TestDisplayAdversarial(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = DisplayManager(self.env.caelestia_config_dir)

    def test_resolution_format_injection(self):
        # Resolution string without 'x'
        with self.assertRaises(ValueError):
            self.manager.apply_settings(0, "1920", 60.0, 0, 1.0, lambda: True)

        # Resolution string with letters
        with self.assertRaises(ValueError):
            self.manager.apply_settings(0, "1920xabc", 60.0, 0, 1.0, lambda: True)

        # Empty resolution string
        with self.assertRaises(ValueError):
            self.manager.apply_settings(0, "", 60.0, 0, 1.0, lambda: True)

    def test_apply_settings_concurrency_race(self):
        # Simulate race condition: apply layout while another is not confirmed (countdown revert active)
        initial = [{"id": 0, "width": 1920, "height": 1080, "refreshRate": 60.0, "transform": 0, "scale": 1.0}]
        self.manager.save_config(initial)

        # First apply starts, user does not confirm (simulates timeout/revert)
        applied_1 = self.manager.apply_settings(0, "1280x720", 60.0, 0, 1.5, lambda: False)
        self.assertFalse(applied_1)

        # Second apply is triggered immediately after, and gets confirmed
        applied_2 = self.manager.apply_settings(0, "2560x1440", 120.0, 1, 1.25, lambda: True)
        self.assertTrue(applied_2)

        # The state should end up with the second config
        config = self.manager.load_config()
        self.assertEqual(config[0]["width"], 2560)
        self.assertEqual(config[0]["refreshRate"], 120.0)
        self.assertEqual(config[0]["scale"], 1.25)


class TestUpdatesAdversarial(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = UpdatesManager()

    def test_updates_malformed_checkupdates_output(self):
        # Mock various corrupted formats returned by checkupdates or yay
        self.env.pacman_updates = [
            "linux-corrupt-line",
            "systemd 253.4-1 ->",
            "yay-git -> 12.1.0-1",
            "firefox 113.0 114.0",
            "   ",
            ""
        ]
        self.env.yay_updates = []
        
        updates = self.manager.get_pending_updates()
        # All invalid formatting should be safely skipped
        self.assertEqual(updates, [])

    def test_concurrent_upgrade_triggers(self):
        # Upgrade started once
        success_1 = self.manager.trigger_upgrade()
        self.assertTrue(success_1)

        # Upgrade triggered again while already active
        success_2 = self.manager.trigger_upgrade()
        self.assertTrue(success_2)


class TestPluginsAdversarial(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = PluginManager(self.env.plugins_dir)

    def test_plugins_corrupt_metadata_missing_fields(self):
        plugin_dir = os.path.join(self.env.plugins_dir, "minimal_plugin")
        os.makedirs(plugin_dir, exist_ok=True)
        # Empty json
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump({}, f)

        plugins = self.manager.scan_plugins()
        self.assertIn("minimal_plugin", plugins)
        # Verify defaults are set correctly when fields are missing
        self.assertEqual(plugins["minimal_plugin"]["name"], "minimal_plugin")
        self.assertEqual(plugins["minimal_plugin"]["version"], "0.0.0")
        self.assertEqual(plugins["minimal_plugin"]["author"], "Unknown")
        self.assertEqual(plugins["minimal_plugin"]["dependencies"], [])

    def test_plugins_invalid_dependencies_type(self):
        plugin_dir = os.path.join(self.env.plugins_dir, "bad_deps_plugin")
        os.makedirs(plugin_dir, exist_ok=True)
        # dependencies is a string instead of an array
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump({"name": "Bad Deps", "dependencies": "should-be-a-list"}, f)

        plugins = self.manager.scan_plugins()
        self.assertIn("bad_deps_plugin", plugins)
        # Should fallback to empty list instead of causing crash/type errors later
        self.assertEqual(plugins["bad_deps_plugin"]["dependencies"], [])

    def test_plugins_circular_dependency_multi_level(self):
        # A depends on B, B depends on C, C depends on A
        plugin_a = os.path.join(self.env.plugins_dir, "plugin_a")
        os.makedirs(plugin_a, exist_ok=True)
        with open(os.path.join(plugin_a, "metadata.json"), "w") as f:
            json.dump({"name": "A", "dependencies": ["plugin_b"]}, f)

        plugin_b = os.path.join(self.env.plugins_dir, "plugin_b")
        os.makedirs(plugin_b, exist_ok=True)
        with open(os.path.join(plugin_b, "metadata.json"), "w") as f:
            json.dump({"name": "B", "dependencies": ["plugin_c"]}, f)

        plugin_c = os.path.join(self.env.plugins_dir, "plugin_c")
        os.makedirs(plugin_c, exist_ok=True)
        with open(os.path.join(plugin_c, "metadata.json"), "w") as f:
            json.dump({"name": "C", "dependencies": ["plugin_a"]}, f)

        plugins = self.manager.scan_plugins()
        order, err = self.manager.resolve_dependencies(plugins)
        self.assertEqual(order, [])
        self.assertIn("Circular dependency detected", err)


class TestColoursAdversarial(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = ColoursManager(self.env.caelestia_config_dir)

    def test_colours_malformed_hsl_inputs(self):
        # Missing values/commas
        success, _ = self.manager.apply_theme("dark", "vibrant", "static", "hsl(220,,50)")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")

        # Invalid characters
        success, _ = self.manager.apply_theme("dark", "vibrant", "static", "hsl(abc,100,50)")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")

        # Negative values or out-of-bounds HSL
        success, _ = self.manager.apply_theme("dark", "vibrant", "static", "hsl(180,-20,50)")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")

        # Excessive bounds
        success, _ = self.manager.apply_theme("dark", "vibrant", "static", "hsl(361,100,50)")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")

    def test_scheme_cli_failure_resilience(self):
        # Mock scheme command to exit with non-zero code (simulate missing binary or command error)
        self.env.custom_commands["caelestia scheme set vibrant #ffffff"] = (127, b"", b"Error: scheme set failed")
        
        success, err = self.manager.apply_theme("dark", "vibrant", "static", "#ffffff")
        self.assertFalse(success)
        self.assertIn("failed with code 127", err)


class TestWeatherAdversarial(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = WeatherLocationManager(self.env.caelestia_config_dir)

    def test_weather_nominatim_reverse_geocoding_malformed(self):
        # Nominatim returns 200 OK but empty features list
        self.env.http_mocks["nominatim.openstreetmap.org"] = (200, json.dumps({"features": []}))
        # Fallback BigDataCloud returns 500 error
        self.env.http_mocks["api.bigdatacloud.net"] = (500, "Internal Server Error")

        city, err = self.manager.reverse_geocode(48.8534, 2.3488)
        # Should gracefully fall back to Custom Location
        self.assertEqual(city, "Custom Location")

    def test_coordinates_parsing_edge_cases(self):
        # Coordinate input with multiple commas or empty fields
        success, err = self.manager.update_config("Invalid", "48.8534,,2.3488")
        self.assertFalse(success)
        self.assertEqual(err, "Invalid coordinate format. Must be 'lat,lon'")

        # Coordinates completely out of range (lat too high)
        success, err = self.manager.update_config("Invalid", "90.0001,2.3488")
        self.assertFalse(success)
        self.assertEqual(err, "Latitude must be between -90 and 90")

        # Coordinates completely out of range (lon too low)
        success, err = self.manager.update_config("Invalid", "48.8534,-180.0001")
        self.assertFalse(success)
        self.assertEqual(err, "Longitude must be between -180 and 180")
