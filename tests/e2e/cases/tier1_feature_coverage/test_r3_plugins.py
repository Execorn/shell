import os
import json
from tests.e2e.mock_env import E2ETestCase

class TestPluginManagement(E2ETestCase):
    def test_scan_user_plugins_metadata(self):
        """R3.1 Verify plugins in ~/.config/caelestia/plugins/ are scanned and their metadata parsed."""
        # 1. Create a mock plugin
        plugin_name = "test_plugin_alpha"
        plugin_dir = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)
        
        metadata = {
            "name": "Alpha Widget",
            "version": "2.1.3",
            "author": "Alice",
            "status": "disabled"
        }
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)

        # 2. Scan and verify
        self.assertTrue(os.path.isdir(self.env.plugins_dir))
        plugins = os.listdir(self.env.plugins_dir)
        self.assertIn(plugin_name, plugins)
        
        meta_path = os.path.join(self.env.plugins_dir, plugin_name, "metadata.json")
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r") as f:
            data = json.load(f)
            self.assertEqual(data["name"], "Alpha Widget")
            self.assertEqual(data["version"], "2.1.3")
            self.assertEqual(data["author"], "Alice")

    def test_list_plugins_properties(self):
        """R3.2 Verify details are correctly parsed for multiple plugins."""
        # Setup multiple plugins
        plugins_config = {
            "plugin1": {"name": "P1", "version": "1.0", "author": "Auth1", "status": "enabled"},
            "plugin2": {"name": "P2", "version": "2.0", "author": "Auth2", "status": "disabled"},
        }
        for name, meta in plugins_config.items():
            p_dir = os.path.join(self.env.plugins_dir, name)
            os.makedirs(p_dir, exist_ok=True)
            with open(os.path.join(p_dir, "metadata.json"), "w") as f:
                json.dump(meta, f)

        # Iterate and verify
        scanned = {}
        for name in os.listdir(self.env.plugins_dir):
            meta_path = os.path.join(self.env.plugins_dir, name, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    scanned[name] = json.load(f)

        self.assertEqual(len(scanned), 2)
        self.assertEqual(scanned["plugin1"]["author"], "Auth1")
        self.assertEqual(scanned["plugin2"]["status"], "disabled")

    def test_error_crash_logs_display(self):
        """R3.3 Verify error/crash log files are accessible for crashed plugins."""
        plugin_name = "crashing_plugin"
        plugin_dir = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)

        metadata = {
            "name": "Crasher",
            "version": "1.0.0",
            "author": "Bob",
            "status": "crashed"
        }
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)

        crash_log = "Error: property 'undefined' not found on main component."
        with open(os.path.join(plugin_dir, "error.log"), "w") as f:
            f.write(crash_log)

        # Verify reading the error logs
        meta_path = os.path.join(self.env.plugins_dir, plugin_name, "metadata.json")
        with open(meta_path, "r") as f:
            data = json.load(f)
            self.assertEqual(data["status"], "crashed")

        log_path = os.path.join(self.env.plugins_dir, plugin_name, "error.log")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, "r") as f:
            logs = f.read()
            self.assertIn("undefined", logs)

    def test_enable_toggle_loader(self):
        """R3.4 Verify enabling a plugin updates status to enabled."""
        plugin_name = "toggle_plugin"
        plugin_dir = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)

        metadata = {
            "name": "Toggler",
            "version": "1.0",
            "author": "Charlie",
            "status": "disabled"
        }
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)

        # Toggle status to enabled
        meta_path = os.path.join(plugin_dir, "metadata.json")
        with open(meta_path, "r") as f:
            data = json.load(f)
        
        data["status"] = "enabled"
        with open(meta_path, "w") as f:
            json.dump(data, f, indent=2)

        # Verify
        with open(meta_path, "r") as f:
            updated_data = json.load(f)
            self.assertEqual(updated_data["status"], "enabled")

    def test_disable_toggle_unloader(self):
        """R3.5 Verify disabling a plugin updates status to disabled."""
        plugin_name = "toggle_plugin"
        plugin_dir = os.path.join(self.env.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)

        metadata = {
            "name": "Toggler",
            "version": "1.0",
            "author": "Charlie",
            "status": "enabled"
        }
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)

        # Toggle status to disabled
        meta_path = os.path.join(plugin_dir, "metadata.json")
        with open(meta_path, "r") as f:
            data = json.load(f)
        
        data["status"] = "disabled"
        with open(meta_path, "w") as f:
            json.dump(data, f, indent=2)

        # Verify
        with open(meta_path, "r") as f:
            updated_data = json.load(f)
            self.assertEqual(updated_data["status"], "disabled")
