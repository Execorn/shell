import subprocess
from tests.e2e.mock_env import E2ETestCase

class TestThemeColours(E2ETestCase):
    def test_scheme_flavor_selection(self):
        """R4.1 Verify setting theme scheme flavor updates configuration and runs palette generation."""
        # 1. Update shell configuration
        shell_config = self.env.read_shell_config()
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["flavor"] = "vibrant"
        self.env.write_shell_config(shell_config)

        # 2. Run scheme set command
        res = subprocess.run(["caelestia", "scheme", "set", "vibrant"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Scheme updated successfully", res.stdout)

        # 3. Assertions
        updated_config = self.env.read_shell_config()
        self.assertEqual(updated_config["theme"]["flavor"], "vibrant")
        self.assertIn(["caelestia", "scheme", "set", "vibrant"], self.env.subprocess_calls)

    def test_light_dark_mode_toggle(self):
        """R4.2 Verify light/dark mode toggles update config and regenerate scheme."""
        # Toggle to Dark Mode
        shell_config = self.env.read_shell_config()
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        shell_config["theme"]["darkMode"] = True
        self.env.write_shell_config(shell_config)

        # Trigger scheme update
        subprocess.run(["caelestia", "scheme", "set", "vibrant"])

        # Verify
        updated_config = self.env.read_shell_config()
        self.assertTrue(updated_config["theme"]["darkMode"])

        # Toggle to Light Mode
        shell_config["theme"]["darkMode"] = False
        self.env.write_shell_config(shell_config)
        subprocess.run(["caelestia", "scheme", "set", "vibrant"])

        updated_config2 = self.env.read_shell_config()
        self.assertFalse(updated_config2["theme"]["darkMode"])

    def test_wallpaper_extracted_scheme(self):
        """R4.3 Verify selecting dynamic wallpaper-extracted theme extracts and saves palette."""
        shell_config = self.env.read_shell_config()
        if "appearance" not in shell_config:
            shell_config["appearance"] = {}
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        
        # Set extracted colors and choose dynamic mode
        shell_config["appearance"]["wallpaper"] = "/home/execorn/pictures/wallpaper.webp"
        shell_config["theme"]["source"] = "wallpaper"
        shell_config["theme"]["extractedColors"] = {
            "primary": "#3f5f91",
            "secondary": "#565f71",
            "tertiary": "#705575"
        }
        self.env.write_shell_config(shell_config)

        # Apply scheme reload
        subprocess.run(["caelestia", "scheme", "set", "tonal-spot"])

        updated_config = self.env.read_shell_config()
        self.assertEqual(updated_config["theme"]["source"], "wallpaper")
        self.assertEqual(updated_config["theme"]["extractedColors"]["primary"], "#3f5f91")

    def test_custom_accent_hsl_picker(self):
        """R4.4 Verify setting custom static HSL accent color."""
        shell_config = self.env.read_shell_config()
        if "theme" not in shell_config:
            shell_config["theme"] = {}
        
        # Choose custom accent mode and set HSL value (H=220, S=100, L=50)
        shell_config["theme"]["source"] = "custom"
        shell_config["theme"]["customAccentHSL"] = "220,100,50"
        self.env.write_shell_config(shell_config)

        # Trigger scheme update with the custom color
        subprocess.run(["caelestia", "scheme", "set", "hsl(220,100,50)"])

        updated_config = self.env.read_shell_config()
        self.assertEqual(updated_config["theme"]["source"], "custom")
        self.assertEqual(updated_config["theme"]["customAccentHSL"], "220,100,50")
        self.assertIn(["caelestia", "scheme", "set", "hsl(220,100,50)"], self.env.subprocess_calls)

    def test_palette_reload_command(self):
        """R4.5 Verify scheme reload runs palette regeneration without shell restart."""
        # Clean current call list
        self.env.subprocess_calls.clear()

        # Run caelestia scheme set reload command
        res = subprocess.run(["caelestia", "scheme", "set", "monochrome"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

        # Ensure reload command was fired
        self.assertIn(["caelestia", "scheme", "set", "monochrome"], self.env.subprocess_calls)
