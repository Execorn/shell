import os
import json
from tests.e2e.mock_env import E2ETestCase

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
                    plugins[item] = {
                        "name": meta.get("name", item),
                        "author": meta.get("author", "Unknown"),
                        "version": meta.get("version", "0.0.0"),
                        "dependencies": meta.get("dependencies", []),
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
                    for dep in plugin.get("dependencies", []):
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

    def load_plugin(self, name, plugins):
        plugin = plugins.get(name)
        if not plugin or plugin.get("status") in ("corrupt", "invalid", "error"):
            return False, plugin.get("error") if plugin else "Plugin not found"
        
        main_qml = os.path.join(self.plugins_dir, name, "main.qml")
        if not os.path.exists(main_qml):
            plugin["status"] = "crashed"
            plugin["error"] = "Entry point main.qml missing"
            return False, plugin["error"]

        try:
            with open(main_qml, 'r') as f:
                content = f.read()
            if "import" not in content or "{" not in content:
                plugin["status"] = "crashed"
                plugin["error"] = "QML syntax error in main.qml"
                return False, plugin["error"]
        except Exception as e:
            plugin["status"] = "crashed"
            plugin["error"] = str(e)
            return False, plugin["error"]

        plugin["status"] = "enabled"
        return True, None


class TestPluginsBounds(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = PluginManager(self.env.plugins_dir)

    def test_empty_plugins_folder(self):
        # Empty plugins directory
        plugins = self.manager.scan_plugins()
        self.assertEqual(plugins, {})

    def test_plugin_folder_missing_metadata(self):
        # Create folder but no metadata.json
        os.makedirs(os.path.join(self.env.plugins_dir, "bad_plugin"), exist_ok=True)
        
        plugins = self.manager.scan_plugins()
        self.assertIn("bad_plugin", plugins)
        self.assertEqual(plugins["bad_plugin"]["status"], "invalid")
        self.assertEqual(plugins["bad_plugin"]["error"], "Missing metadata.json")

    def test_corrupt_plugin_metadata(self):
        # Create folder with invalid JSON in metadata.json
        plugin_dir = os.path.join(self.env.plugins_dir, "corrupt_plugin")
        os.makedirs(plugin_dir, exist_ok=True)
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            f.write("{invalid_json}")

        plugins = self.manager.scan_plugins()
        self.assertIn("corrupt_plugin", plugins)
        self.assertEqual(plugins["corrupt_plugin"]["status"], "corrupt")
        self.assertEqual(plugins["corrupt_plugin"]["error"], "Corrupt metadata.json")

    def test_loader_failure(self):
        # Create plugin with metadata but missing main.qml
        plugin_dir = os.path.join(self.env.plugins_dir, "no_main")
        os.makedirs(plugin_dir, exist_ok=True)
        with open(os.path.join(plugin_dir, "metadata.json"), "w") as f:
            json.dump({"name": "No Main Plugin", "version": "1.0"}, f)

        plugins = self.manager.scan_plugins()
        success, err = self.manager.load_plugin("no_main", plugins)
        self.assertFalse(success)
        self.assertEqual(err, "Entry point main.qml missing")
        self.assertEqual(plugins["no_main"]["status"], "crashed")

        # Create plugin with syntax error main.qml
        plugin_dir2 = os.path.join(self.env.plugins_dir, "bad_qml")
        os.makedirs(plugin_dir2, exist_ok=True)
        with open(os.path.join(plugin_dir2, "metadata.json"), "w") as f:
            json.dump({"name": "Bad QML Plugin", "version": "1.0"}, f)
        with open(os.path.join(plugin_dir2, "main.qml"), "w") as f:
            f.write("this is not qml code")

        plugins = self.manager.scan_plugins()
        success, err = self.manager.load_plugin("bad_qml", plugins)
        self.assertFalse(success)
        self.assertEqual(err, "QML syntax error in main.qml")
        self.assertEqual(plugins["bad_qml"]["status"], "crashed")

    def test_circular_dependency_loader(self):
        # Create circular dependency: A depends on B, B depends on A
        plugin_a = os.path.join(self.env.plugins_dir, "plugin_a")
        os.makedirs(plugin_a, exist_ok=True)
        with open(os.path.join(plugin_a, "metadata.json"), "w") as f:
            json.dump({"name": "A", "dependencies": ["plugin_b"]}, f)

        plugin_b = os.path.join(self.env.plugins_dir, "plugin_b")
        os.makedirs(plugin_b, exist_ok=True)
        with open(os.path.join(plugin_b, "metadata.json"), "w") as f:
            json.dump({"name": "B", "dependencies": ["plugin_a"]}, f)

        plugins = self.manager.scan_plugins()
        order, err = self.manager.resolve_dependencies(plugins)
        self.assertEqual(order, [])
        self.assertIn("Circular dependency detected", err)
