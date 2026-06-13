import subprocess
from tests.e2e.mock_env import E2ETestCase

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
                        if len(parts) >= 4:
                            updates.append({
                                "name": parts[0],
                                "source": "pacman",
                                "old_version": parts[1],
                                "new_version": parts[3],
                                "description": f"System package {parts[0]}",
                                "size": "Unknown"
                            })
            elif res_pac.returncode not in (0, 2):
                # Handle unexpected error codes gracefully (don't crash, log/skip)
                pass
        except Exception:
            pass

        try:
            res_yay = subprocess.run(["yay", "-Qua"], capture_output=True, text=True)
            if res_yay.returncode == 0:
                for line in res_yay.stdout.splitlines():
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4:
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
                # Handle unexpected error codes gracefully
                pass
        except Exception:
            pass

        return updates

    def trigger_upgrade(self):
        res = subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"])
        return res.returncode == 0

    def get_upgrade_status(self):
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-active", "caelestia-upgrade.service"], 
                capture_output=True, text=True, timeout=2.0
            )
            status = res.stdout.strip()
            if status == "active":
                return "running"
            elif status == "inactive":
                return "stopped"
            else:
                return "failed"
        except subprocess.TimeoutExpired:
            return "timeout"
        except Exception:
            return "failed"

    def get_upgrade_logs(self):
        try:
            # Command could fail, check returncode
            res = subprocess.run(
                ["journalctl", "--user", "-u", "caelestia-upgrade.service"], 
                capture_output=True, text=True
            )
            if res.returncode != 0:
                return []
            
            logs = res.stdout.splitlines()
            # Check for network error/failure signature
            for line in logs:
                if "Could not resolve host" in line or "Network is unreachable" in line or "failed" in line.lower():
                    return logs + ["Error: Upgrade failed due to network disconnect."]
            return logs
        except Exception:
            return []


class TestUpdatesBounds(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = UpdatesManager()

    def test_zero_updates_pending(self):
        # Configure env to return no updates (checkupdates returncode=2, yay returncode=1)
        self.env.pacman_updates = []
        self.env.yay_updates = []
        
        updates = self.manager.get_pending_updates()
        self.assertEqual(updates, [])

    def test_command_failures(self):
        # Configure checkupdates to fail with exit code 127
        self.env.custom_commands["checkupdates"] = (127, b"", b"checkupdates: command not found")
        # yay-Qua works fine
        self.env.yay_updates = ["yay-git 12.0.0-1 -> 12.1.0-1"]

        updates = self.manager.get_pending_updates()
        # Should gracefully skip checkupdates and return yay updates
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["name"], "yay-git")

    def test_service_status_check_timeouts(self):
        # Mock systemctl command to time out by raising TimeoutExpired
        def timeout_handler(cmd):
            raise subprocess.TimeoutExpired(cmd, 2.0)
            
        self.env.custom_commands["systemctl --user is-active caelestia-upgrade.service"] = timeout_handler

        status = self.manager.get_upgrade_status()
        self.assertEqual(status, "timeout")

    def test_extremely_large_update_lists(self):
        # 1000 packages pending update
        large_list = [f"pkg-{i} 1.0.0 -> 2.0.0" for i in range(1000)]
        self.env.pacman_updates = large_list
        self.env.yay_updates = []

        updates = self.manager.get_pending_updates()
        self.assertEqual(len(updates), 1000)
        self.assertEqual(updates[0]["name"], "pkg-0")
        self.assertEqual(updates[999]["name"], "pkg-999")

    def test_network_disconnect_during_upgrade(self):
        # Start upgrade service
        self.manager.trigger_upgrade()
        
        # Inject network failure message in logs
        self.env.upgrade_logs = [
            "Starting Caelestia Upgrade...\n",
            "[1/3] Syncing databases...\n",
            "Error: Could not resolve host: archlinux.org\n",
            "Upgrade transaction aborted.\n"
        ]

        logs = self.manager.get_upgrade_logs()
        self.assertTrue(any("Could not resolve host" in line for line in logs))
        self.assertTrue(any("Upgrade failed due to network disconnect" in line for line in logs))
