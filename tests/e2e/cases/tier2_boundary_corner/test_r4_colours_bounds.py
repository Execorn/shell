import os
import json
import subprocess
from tests.e2e.mock_env import E2ETestCase

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
                    import re
                    m = re.match(r"hsl\(\s*([\d\.]+)\s*,\s*([\d\.]+)%\s*,\s*([\d\.]+)%\s*\)", custom_color)
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


class TestColoursBounds(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = ColoursManager(self.env.caelestia_config_dir)

    def test_invalid_scheme_flavor_fallback(self):
        # Apply theme with invalid flavor "SuperVibrant"
        success, err = self.manager.apply_theme("dark", "SuperVibrant", "static", "#ffffff")
        self.assertTrue(success)
        
        # Verify it fallback to "tonal-spot"
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["flavor"], "tonal-spot")

    def test_malformed_color_fallback(self):
        # Malformed hex format
        success, _ = self.manager.apply_theme("dark", "vibrant", "static", "#xyz")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")

        # Malformed HSL out of range
        success, _ = self.manager.apply_theme("dark", "vibrant", "static", "hsl(400, 150%, 50%)")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")

    def test_scheme_reload_cli_failure(self):
        # Mock caelestia scheme command to fail with code 1
        self.env.custom_commands["caelestia scheme set vibrant #ffffff"] = (1, b"", b"Error: scheme failed")
        
        success, err = self.manager.apply_theme("dark", "vibrant", "static", "#ffffff")
        self.assertFalse(success)
        self.assertIn("failed with code 1", err)

    def test_extreme_hsl_values(self):
        # Pure Black (lightness = 0)
        hex_black = self.manager.hsl_to_hex(180, 50, 0)
        self.assertEqual(hex_black, "#000000")

        # Pure White (lightness = 100)
        hex_white = self.manager.hsl_to_hex(180, 50, 100)
        self.assertEqual(hex_white, "#ffffff")

        # Zero Saturation (grey)
        hex_grey = self.manager.hsl_to_hex(180, 0, 50)
        self.assertEqual(hex_grey, "#7f7f7f")

    def test_empty_wallpaper_directory(self):
        # Apply theme with dynamic wallpaper extraction but wallpaper path does not exist
        success, _ = self.manager.apply_theme("dark", "vibrant", "dynamic", wallpaper_path="/nonexistent/wallpaper.png")
        self.assertTrue(success)
        
        # It should fall back to static mode and default color
        config = self.env.read_shell_config()
        self.assertEqual(config["theme"]["colorSource"], "static")
        self.assertEqual(config["theme"]["accentColor"], "#6750A4")
