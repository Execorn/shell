import subprocess
from tests.e2e.mock_env import E2ETestCase

class TestSystemUpdates(E2ETestCase):
    def test_query_updates_success(self):
        """R2.1 Verify pacman (checkupdates) and yay (-Qua) can query pending updates."""
        # Query pacman updates
        res_pacman = subprocess.run(["checkupdates"], capture_output=True, text=True)
        self.assertEqual(res_pacman.returncode, 0)
        self.assertIn("linux 6.3.1-arch1-1 -> 6.3.2-arch1-1", res_pacman.stdout)
        self.assertIn("systemd 253.4-1 -> 253.5-1", res_pacman.stdout)

        # Query yay updates
        res_yay = subprocess.run(["yay", "-Qua"], capture_output=True, text=True)
        self.assertEqual(res_yay.returncode, 0)
        self.assertIn("yay-git 12.0.0-1 -> 12.1.0-1", res_yay.stdout)

    def test_updates_details(self):
        """R2.2 Verify we can parse individual packages details and version changes."""
        # pacman details
        res_pacman = subprocess.run(["checkupdates"], capture_output=True, text=True)
        lines = res_pacman.stdout.strip().split("\n")
        self.assertEqual(len(lines), 2)
        
        # Parse package name and version details
        pkg1, versions1 = lines[0].split(" ", 1)
        self.assertEqual(pkg1, "linux")
        self.assertEqual(versions1, "6.3.1-arch1-1 -> 6.3.2-arch1-1")

        # yay details
        res_yay = subprocess.run(["yay", "-Qua"], capture_output=True, text=True)
        lines_yay = res_yay.stdout.strip().split("\n")
        self.assertEqual(len(lines_yay), 1)
        pkg_yay, versions_yay = lines_yay[0].split(" ", 1)
        self.assertEqual(pkg_yay, "yay-git")
        self.assertEqual(versions_yay, "12.0.0-1 -> 12.1.0-1")

    def test_upgrade_trigger(self):
        """R2.3 Verify the systemd service starts to trigger yay upgrade."""
        # Verify initial state is inactive
        res_check = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertNotEqual(res_check.stdout.strip(), "active")

        # Trigger upgrade
        res_start = subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_start.returncode, 0)

        # Verify service is active
        res_active = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_active.stdout.strip(), "active")

    def test_upgrade_log_streaming(self):
        """R2.4 Verify that install logs stream dynamically."""
        # Trigger upgrade
        subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"])

        # Stream logs via Popen and communicate
        proc = subprocess.Popen(["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f"], stdout=subprocess.PIPE, text=True)
        stdout, _ = proc.communicate()
        
        self.assertIn("Starting Caelestia Upgrade...", stdout)
        self.assertIn("[1/3] Syncing databases...", stdout)
        self.assertIn("[2/3] Upgrading packages...", stdout)
        self.assertIn("Upgraded linux (6.3.1 -> 6.3.2)", stdout)
        self.assertIn("Upgraded systemd (253.4 -> 253.5)", stdout)
        self.assertIn("Upgraded yay-git (12.0.0 -> 12.1.0)", stdout)
        self.assertIn("[3/3] Post-transaction hooks...", stdout)

    def test_upgrade_completion(self):
        """R2.5 Verify service transitions to inactive upon completion."""
        # Trigger upgrade
        subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"])

        # Ensure service is running
        res_active = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_active.stdout.strip(), "active")

        # Read the logs, which mock_env interprets as finishing the upgrade
        proc = subprocess.Popen(["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f"], stdout=subprocess.PIPE, text=True)
        stdout, _ = proc.communicate()
        self.assertIn("Caelestia Upgrade completed successfully.", stdout)

        # Now status should be inactive/dead
        res_inactive = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
        self.assertEqual(res_inactive.stdout.strip(), "inactive")
