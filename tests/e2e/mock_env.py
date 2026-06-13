import os
import sys
import json
import subprocess
import unittest
import unittest.mock
import tempfile
import shutil
import urllib.request
import urllib.parse
import io
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class MockProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b"", stream_lines=None, text_mode=False):
        self.returncode = returncode
        if text_mode:
            if stream_lines is not None:
                stdout_str = "".join(line.decode('utf-8') if isinstance(line, bytes) else line for line in stream_lines)
            else:
                stdout_str = stdout.decode('utf-8') if isinstance(stdout, bytes) else stdout
            stderr_str = stderr.decode('utf-8') if isinstance(stderr, bytes) else stderr
            
            self.stdout = io.StringIO(stdout_str)
            self.stderr = io.StringIO(stderr_str)
        else:
            if stream_lines is not None:
                stdout_bytes = b"".join(line.encode('utf-8') if isinstance(line, str) else line for line in stream_lines)
            else:
                stdout_bytes = stdout if isinstance(stdout, bytes) else stdout.encode('utf-8')
            stderr_bytes = stderr if isinstance(stderr, bytes) else stderr.encode('utf-8')
            
            self.stdout = io.BytesIO(stdout_bytes)
            self.stderr = io.BytesIO(stderr_bytes)
            
        self.stdin = io.StringIO() if text_mode else io.BytesIO()
        self.args = []

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def communicate(self, input=None, timeout=None):
        return (self.stdout.read(), self.stderr.read())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def normalize_command(args):
    if isinstance(args, str):
        import shlex
        return shlex.split(args)
    elif isinstance(args, (list, tuple)):
        return [str(a) for a in args]
    return []


class MockEnvironment:
    def __init__(self, initial_shell_json=None, initial_monitors_json=None, initial_plugins=None):
        self.initial_shell_json = initial_shell_json or {
            "services": {
                "weatherLocation": "Paris",
                "weatherCoordinates": "48.8534,2.3488",
                "useTwelveHourClock": False,
                "useFahrenheit": False
            }
        }
        self.initial_monitors_json = initial_monitors_json or []
        self.initial_plugins = initial_plugins or {}
        
        self.active_monitors = [
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
        
        self.pacman_updates = [
            "linux 6.3.1-arch1-1 -> 6.3.2-arch1-1",
            "systemd 253.4-1 -> 253.5-1"
        ]
        
        self.yay_updates = [
            "yay-git 12.0.0-1 -> 12.1.0-1"
        ]
        
        self.upgrade_service_active = False
        
        self.upgrade_logs = [
            "Starting Caelestia Upgrade...\n",
            "[1/3] Syncing databases...\n",
            "[2/3] Upgrading packages...\n",
            "Upgraded linux (6.3.1 -> 6.3.2)\n",
            "Upgraded systemd (253.4 -> 253.5)\n",
            "Upgraded yay-git (12.0.0 -> 12.1.0)\n",
            "[3/3] Post-transaction hooks...\n",
            "Caelestia Upgrade completed successfully.\n"
        ]
        
        self.custom_commands = {}
        self.http_mocks = {}
        self.subprocess_calls = []
        
        self.temp_dir = None
        self.old_home = None
        self.old_xdg = None
        self.caelestia_config_dir = None
        self.plugins_dir = None
        
        self.urlopen_patcher = None
        self.popen_patcher = None
        self.run_patcher = None
        self.call_patcher = None
        self.check_output_patcher = None
        self.check_call_patcher = None
        
        self.server = None
        self.server_thread = None
        self.port = None

    def __enter__(self):
        # Sandboxed directories
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get('HOME')
        self.old_xdg = os.environ.get('XDG_CONFIG_HOME')
        
        temp_home = self.temp_dir.name
        os.environ['HOME'] = temp_home
        os.environ['XDG_CONFIG_HOME'] = os.path.join(temp_home, '.config')
        
        self.caelestia_config_dir = os.path.join(temp_home, '.config', 'caelestia')
        self.plugins_dir = os.path.join(self.caelestia_config_dir, 'plugins')
        os.makedirs(self.plugins_dir, exist_ok=True)
        
        shell_path = os.path.join(self.caelestia_config_dir, 'shell.json')
        monitors_path = os.path.join(self.caelestia_config_dir, 'monitors.json')
        
        with open(shell_path, 'w') as f:
            json.dump(self.initial_shell_json, f, indent=2)
        with open(monitors_path, 'w') as f:
            json.dump(self.initial_monitors_json, f, indent=2)
            
        for plugin_name, plugin_data in self.initial_plugins.items():
            plugin_path = os.path.join(self.plugins_dir, plugin_name)
            os.makedirs(plugin_path, exist_ok=True)
            for filename, content in plugin_data.items():
                file_path = os.path.join(plugin_path, filename)
                with open(file_path, 'w') as f:
                    if isinstance(content, (dict, list)):
                        json.dump(content, f, indent=2)
                    else:
                        f.write(str(content))
        
        # Save original urlopen
        self.original_urlopen = urllib.request.urlopen
        
        # Mock HTTP requests (urllib.request.urlopen)
        self.urlopen_patcher = unittest.mock.patch('urllib.request.urlopen', side_effect=self._mock_urlopen)
        self.urlopen_patcher.start()
        
        # Mock subprocess functions
        self.popen_patcher = unittest.mock.patch('subprocess.Popen', side_effect=self._mock_popen)
        self.popen_patcher.start()
        
        self.run_patcher = unittest.mock.patch('subprocess.run', side_effect=self._mock_run)
        self.run_patcher.start()

        self.call_patcher = unittest.mock.patch('subprocess.call', side_effect=self._mock_call)
        self.call_patcher.start()

        self.check_output_patcher = unittest.mock.patch('subprocess.check_output', side_effect=self._mock_check_output)
        self.check_output_patcher.start()

        self.check_call_patcher = unittest.mock.patch('subprocess.check_call', side_effect=self._mock_check_call)
        self.check_call_patcher.start()

        # Start mock HTTP server
        self._start_http_server()
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join()
            
        self.urlopen_patcher.stop()
        self.popen_patcher.stop()
        self.run_patcher.stop()
        self.call_patcher.stop()
        self.check_output_patcher.stop()
        self.check_call_patcher.stop()
        
        if self.old_home is not None:
            os.environ['HOME'] = self.old_home
        else:
            os.environ.pop('HOME', None)
            
        if self.old_xdg is not None:
            os.environ['XDG_CONFIG_HOME'] = self.old_xdg
        else:
            os.environ.pop('XDG_CONFIG_HOME', None)
            
        if self.temp_dir:
            self.temp_dir.cleanup()

    def read_shell_config(self):
        with open(os.path.join(self.caelestia_config_dir, 'shell.json'), 'r') as f:
            return json.load(f)

    def write_shell_config(self, data):
        with open(os.path.join(self.caelestia_config_dir, 'shell.json'), 'w') as f:
            json.dump(data, f, indent=2)

    def read_monitors_config(self):
        with open(os.path.join(self.caelestia_config_dir, 'monitors.json'), 'r') as f:
            return json.load(f)

    def write_monitors_config(self, data):
        with open(os.path.join(self.caelestia_config_dir, 'monitors.json'), 'w') as f:
            json.dump(data, f, indent=2)

    def _set_upgrade_active(self, active):
        self.upgrade_service_active = active

    def _is_upgrade_active(self):
        return self.upgrade_service_active

    def _resolve_city(self, name):
        name_lower = name.lower()
        cities = {
            "paris": (48.8534, 2.3488, "France"),
            "berlin": (52.5200, 13.4050, "Germany"),
            "london": (51.5074, -0.1278, "United Kingdom"),
            "new york": (40.7128, -74.0060, "United States"),
            "tokyo": (35.6762, 139.6503, "Japan"),
        }
        for k, v in cities.items():
            if k in name_lower:
                return v
        return 45.0, 45.0, "Unknown Country"

    def _resolve_coords(self, lat, lon):
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except ValueError:
            return "Unknown City"
            
        cities = {
            "Paris": (48.8534, 2.3488),
            "Berlin": (52.5200, 13.4050),
            "London": (51.5074, -0.1278),
            "New York": (40.7128, -74.0060),
            "Tokyo": (35.6762, 139.6503),
        }
        closest_city = "Unknown City"
        min_dist = float('inf')
        for name, coords in cities.items():
            dist = (lat_f - coords[0])**2 + (lon_f - coords[1])**2
            if dist < min_dist:
                min_dist = dist
                closest_city = name
        if min_dist < 1.0:
            return closest_city
        return "Unknown City"

    def _dispatch_command(self, args):
        cmd = normalize_command(args)
        if not cmd:
            return 0, b"", b""
        
        self.subprocess_calls.append(cmd)
        cmd_name = cmd[0]
        cmd_str = " ".join(cmd)
        
        # Check custom commands first to allow overriding defaults
        for pattern, mock_val in self.custom_commands.items():
            if pattern == cmd or (isinstance(pattern, str) and (pattern == cmd_str or pattern == cmd_name)):
                if callable(mock_val):
                    return mock_val(cmd)
                return mock_val
        
        if cmd_name == "hyprctl":
            if len(cmd) > 1 and cmd[1] == "monitors":
                if "-j" in cmd or "--json" in cmd:
                    return 0, json.dumps(self.active_monitors).encode('utf-8'), b""
            elif len(cmd) > 1 and cmd[1] == "reload":
                return 0, b"ok", b""
                
        elif cmd_name == "checkupdates":
            if self.pacman_updates:
                updates_str = "\n".join(self.pacman_updates) + "\n"
                return 0, updates_str.encode('utf-8'), b""
            else:
                return 2, b"", b""
                
        elif cmd_name == "yay":
            if len(cmd) > 1 and cmd[1] == "-Qua":
                if self.yay_updates:
                    updates_str = "\n".join(self.yay_updates) + "\n"
                    return 0, updates_str.encode('utf-8'), b""
                else:
                    return 1, b"", b""
                    
        elif cmd_name == "caelestia":
            if len(cmd) > 2 and cmd[1] == "scheme" and cmd[2] == "set":
                return 0, b"Scheme updated successfully", b""
                
        elif cmd_name == "systemctl":
            if "--user" in cmd:
                service_name = None
                for part in cmd:
                    if part.endswith(".service"):
                        service_name = part
                if service_name == "caelestia-upgrade.service":
                    if "start" in cmd:
                        self._set_upgrade_active(True)
                        return 0, b"", b""
                    elif "is-active" in cmd:
                        if self._is_upgrade_active():
                            return 0, b"active\n", b""
                        else:
                            return 3, b"inactive\n", b""
                    elif "status" in cmd:
                        if self._is_upgrade_active():
                            return 0, b"Active: active (running)\n", b""
                        else:
                            return 3, b"Active: inactive (dead)\n", b""
                            
        elif cmd_name == "journalctl":
            is_upgrade_log = False
            for part in cmd:
                if "caelestia-upgrade" in part:
                    is_upgrade_log = True
            if is_upgrade_log:
                self._set_upgrade_active(False)
                return 0, self.upgrade_logs, b""
                
        return 0, b"", b""

    def _mock_popen(self, args, *popenargs, **kwargs):
        retcode, stdout_data, stderr_data = self._dispatch_command(args)
        
        is_text = kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding') or kwargs.get('errors')
        
        if isinstance(stdout_data, list):
            proc = MockProcess(retcode, stream_lines=stdout_data, stderr=stderr_data, text_mode=is_text)
        else:
            proc = MockProcess(retcode, stdout=stdout_data, stderr=stderr_data, text_mode=is_text)
            
        proc.args = args
        return proc

    def _mock_run(self, args, *runargs, **kwargs):
        retcode, stdout_data, stderr_data = self._dispatch_command(args)
        if isinstance(stdout_data, list):
            stdout_data = b"".join(line.encode('utf-8') if isinstance(line, str) else line for line in stdout_data)
        
        is_text = kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding') or kwargs.get('errors')
        if is_text:
            stdout_data = stdout_data.decode('utf-8') if isinstance(stdout_data, bytes) else stdout_data
            stderr_data = stderr_data.decode('utf-8') if isinstance(stderr_data, bytes) else stderr_data
            
        if kwargs.get('check') and retcode != 0:
            raise subprocess.CalledProcessError(retcode, args, output=stdout_data, stderr=stderr_data)
            
        return subprocess.CompletedProcess(args, retcode, stdout_data, stderr_data)

    def _mock_call(self, args, *callargs, **kwargs):
        retcode, _, _ = self._dispatch_command(args)
        return retcode

    def _mock_check_output(self, args, *callargs, **kwargs):
        retcode, stdout_data, stderr_data = self._dispatch_command(args)
        if isinstance(stdout_data, list):
            stdout_data = b"".join(line.encode('utf-8') if isinstance(line, str) else line for line in stdout_data)
            
        is_text = kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding') or kwargs.get('errors')
        if is_text:
            stdout_data = stdout_data.decode('utf-8') if isinstance(stdout_data, bytes) else stdout_data
            stderr_data = stderr_data.decode('utf-8') if isinstance(stderr_data, bytes) else stderr_data
            
        if retcode != 0:
            raise subprocess.CalledProcessError(retcode, args, output=stdout_data, stderr=stderr_data)
        return stdout_data

    def _mock_check_call(self, args, *callargs, **kwargs):
        retcode, stdout_data, stderr_data = self._dispatch_command(args)
        if isinstance(stdout_data, list):
            stdout_data = b"".join(line.encode('utf-8') if isinstance(line, str) else line for line in stdout_data)
            
        is_text = kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding') or kwargs.get('errors')
        if is_text:
            stdout_data = stdout_data.decode('utf-8') if isinstance(stdout_data, bytes) else stdout_data
            stderr_data = stderr_data.decode('utf-8') if isinstance(stderr_data, bytes) else stderr_data
            
        if retcode != 0:
            raise subprocess.CalledProcessError(retcode, args, output=stdout_data, stderr=stderr_data)
        return 0

    def _mock_urlopen(self, url, data=None, *args, **kwargs):
        if hasattr(url, 'full_url'):
            url_str = url.full_url
        else:
            url_str = url

        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url_str)
        hostname = parsed.hostname or ""
        path = parsed.path or ""
        query = parse_qs(parsed.query)

        if hostname in ("127.0.0.1", "localhost"):
            return self.original_urlopen(url, data, *args, **kwargs)

        status_code = 200
        response_data = b"{}"

        if "geocoding-api.open-meteo.com" in hostname and "/v1/search" in path:
            name_param = query.get('name', [''])[0]
            lat, lon, country = self._resolve_city(name_param)
            if lat is not None:
                res = {
                    "results": [
                        {
                            "id": 1,
                            "name": name_param,
                            "latitude": lat,
                            "longitude": lon,
                            "country": country
                        }
                    ]
                }
            else:
                res = {"results": []}
            response_data = json.dumps(res).encode('utf-8')

        elif "nominatim.openstreetmap.org" in hostname and "/reverse" in path:
            lat = query.get('lat', ['0'])[0]
            lon = query.get('lon', ['0'])[0]
            city_name = self._resolve_coords(lat, lon)
            res = {
                "features": [
                    {
                        "properties": {
                            "geocoding": {
                                "type": "city",
                                "name": city_name,
                                "city": city_name
                            }
                        }
                    }
                ]
            }
            response_data = json.dumps(res).encode('utf-8')

        elif "api.bigdatacloud.net" in hostname and "/data/reverse-geocode-client" in path:
            lat = query.get('latitude', ['0'])[0]
            lon = query.get('longitude', ['0'])[0]
            city_name = self._resolve_coords(lat, lon)
            res = {
                "city": city_name,
                "locality": city_name
            }
            response_data = json.dumps(res).encode('utf-8')

        elif "ipinfo.io" in hostname:
            res = {
                "loc": "48.8534,2.3488",
                "city": "Paris",
                "country": "FR"
            }
            response_data = json.dumps(res).encode('utf-8')

        elif "api.open-meteo.com" in hostname and "/v1/forecast" in path:
            res = {
                "current": {
                    "temperature_2m": 20.0,
                    "relative_humidity_2m": 50,
                    "apparent_temperature": 21.0,
                    "is_day": 1,
                    "weather_code": 0,
                    "wind_speed_10m": 10.0
                },
                "daily": {
                    "time": ["2026-06-12"],
                    "temperature_2m_max": [25.0],
                    "temperature_2m_min": [15.0],
                    "weather_code": [0],
                    "sunrise": ["2026-06-12T06:00"],
                    "sunset": ["2026-06-12T21:00"]
                },
                "hourly": {
                    "time": ["2026-06-12T18:00"],
                    "temperature_2m": [20.0],
                    "precipitation_probability": [0],
                    "weather_code": [0]
                }
            }
            response_data = json.dumps(res).encode('utf-8')

        for pattern, handler in self.http_mocks.items():
            if pattern in url_str:
                if callable(handler):
                    status_code, response_data = handler(url_str, query)
                else:
                    status_code, response_data = handler
                if isinstance(response_data, str):
                    response_data = response_data.encode('utf-8')
                break

        return MockHTTPResponse(response_data, status=status_code)

    def _start_http_server(self):
        env_instance = self
        
        class MockHTTPHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
                
            def do_GET(self):
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                path = parsed.path
                
                status_code = 200
                response_data = b"{}"
                
                if "/v1/search" in path:
                    name_param = query.get('name', [''])[0]
                    lat, lon, country = env_instance._resolve_city(name_param)
                    if lat is not None:
                        res = {
                            "results": [
                                {
                                    "id": 1,
                                    "name": name_param,
                                    "latitude": lat,
                                    "longitude": lon,
                                    "country": country
                                }
                            ]
                        }
                    else:
                        res = {"results": []}
                    response_data = json.dumps(res).encode('utf-8')
                elif "/reverse" in path:
                    lat = query.get('lat', ['0'])[0]
                    lon = query.get('lon', ['0'])[0]
                    city_name = env_instance._resolve_coords(lat, lon)
                    res = {
                        "features": [
                            {
                                "properties": {
                                    "geocoding": {
                                        "type": "city",
                                        "name": city_name,
                                        "city": city_name
                                    }
                                }
                            }
                        ]
                    }
                    response_data = json.dumps(res).encode('utf-8')
                elif "/data/reverse-geocode-client" in path:
                    lat = query.get('latitude', ['0'])[0]
                    lon = query.get('longitude', ['0'])[0]
                    city_name = env_instance._resolve_coords(lat, lon)
                    res = {
                        "city": city_name,
                        "locality": city_name
                    }
                    response_data = json.dumps(res).encode('utf-8')
                elif "/json" in path:
                    res = {
                        "loc": "48.8534,2.3488",
                        "city": "Paris",
                        "country": "FR"
                    }
                    response_data = json.dumps(res).encode('utf-8')
                elif "/v1/forecast" in path:
                    res = {
                        "current": {
                            "temperature_2m": 20.0,
                            "relative_humidity_2m": 50,
                            "apparent_temperature": 21.0,
                            "is_day": 1,
                            "weather_code": 0,
                            "wind_speed_10m": 10.0
                        },
                        "daily": {
                            "time": ["2026-06-12"],
                            "temperature_2m_max": [25.0],
                            "temperature_2m_min": [15.0],
                            "weather_code": [0],
                            "sunrise": ["2026-06-12T06:00"],
                            "sunset": ["2026-06-12T21:00"]
                        },
                        "hourly": {
                            "time": ["2026-06-12T18:00"],
                            "temperature_2m": [20.0],
                            "precipitation_probability": [0],
                            "weather_code": [0]
                        }
                    }
                    response_data = json.dumps(res).encode('utf-8')
                else:
                    status_code = 404
                    response_data = b"Not Found"

                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response_data)))
                self.end_headers()
                self.wfile.write(response_data)

        self.server = HTTPServer(('127.0.0.1', 0), MockHTTPHandler)
        self.port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()


class MockHTTPResponse(io.BytesIO):
    def __init__(self, content, status=200, headers=None):
        super().__init__(content)
        self.status = status
        self.code = status
        self.headers = headers or {}

    def getcode(self):
        return self.status

    def info(self):
        from email.message import Message
        msg = Message()
        for k, v in self.headers.items():
            msg.add_header(k, v)
        return msg


class E2ETestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_env = MockEnvironment()
        self.env = self.mock_env.__enter__()

    def tearDown(self):
        self.mock_env.__exit__(None, None, None)
        super().tearDown()


# Verification Suite (Self-test)
class TestMockEnvironment(unittest.TestCase):
    def test_sandboxed_directories(self):
        initial_shell = {"test": "config"}
        initial_monitors = [{"monitor": "config"}]
        initial_plugins = {"my_plugin": {"metadata.json": '{"name": "My Plugin"}'}}
        
        with MockEnvironment(initial_shell, initial_monitors, initial_plugins) as env:
            self.assertNotEqual(os.environ.get('HOME'), env.old_home)
            self.assertTrue(os.path.isdir(env.caelestia_config_dir))
            self.assertTrue(os.path.isdir(env.plugins_dir))
            
            self.assertEqual(env.read_shell_config(), initial_shell)
            self.assertEqual(env.read_monitors_config(), initial_monitors)
            
            plugin_meta_path = os.path.join(env.plugins_dir, "my_plugin", "metadata.json")
            self.assertTrue(os.path.exists(plugin_meta_path))
            with open(plugin_meta_path, 'r') as f:
                self.assertEqual(json.load(f), {"name": "My Plugin"})
                
            env.write_shell_config({"new": "state"})
            self.assertEqual(env.read_shell_config(), {"new": "state"})
            
    def test_subprocess_mocks(self):
        with MockEnvironment() as env:
            # 1. hyprctl monitors -j
            res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            monitors = json.loads(res.stdout)
            self.assertEqual(len(monitors), 1)
            self.assertEqual(monitors[0]["name"], "eDP-1")
            
            # 2. hyprctl reload
            res = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "ok")
            
            # 3. checkupdates
            res = subprocess.run(["checkupdates"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("linux", res.stdout)
            
            # Empty checkupdates
            env.pacman_updates = []
            res = subprocess.run(["checkupdates"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 2)
            
            # 4. yay -Qua
            res = subprocess.run(["yay", "-Qua"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("yay-git", res.stdout)
            
            # 5. caelestia scheme set
            res = subprocess.run(["caelestia", "scheme", "set", "vibrant"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            
            # 6. systemctl & journalctl
            self.assertFalse(env._is_upgrade_active())
            subprocess.run(["systemctl", "--user", "start", "caelestia-upgrade.service"])
            self.assertTrue(env._is_upgrade_active())
            
            res = subprocess.run(["systemctl", "--user", "is-active", "caelestia-upgrade.service"], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "active")
            
            p = subprocess.Popen(["journalctl", "--user", "-u", "caelestia-upgrade.service", "-f"], stdout=subprocess.PIPE, text=True)
            lines = p.stdout.readlines()
            self.assertTrue(len(lines) > 0)
            self.assertIn("Starting Caelestia Upgrade", lines[0])
            self.assertFalse(env._is_upgrade_active())
            
            self.assertIn(["hyprctl", "monitors", "-j"], env.subprocess_calls)
            self.assertIn(["systemctl", "--user", "start", "caelestia-upgrade.service"], env.subprocess_calls)

    def test_http_interceptor(self):
        with MockEnvironment() as env:
            url = "https://geocoding-api.open-meteo.com/v1/search?name=Berlin&count=1&language=en&format=json"
            response = urllib.request.urlopen(url)
            data = json.loads(response.read().decode('utf-8'))
            self.assertEqual(data["results"][0]["name"], "Berlin")
            self.assertAlmostEqual(data["results"][0]["latitude"], 52.52)
            
            url_rev = "https://nominatim.openstreetmap.org/reverse?lat=48.8534&lon=2.3488&format=geocodejson"
            response_rev = urllib.request.urlopen(url_rev)
            data_rev = json.loads(response_rev.read().decode('utf-8'))
            self.assertEqual(data_rev["features"][0]["properties"]["geocoding"]["name"], "Paris")
            
            local_url = f"http://127.0.0.1:{env.port}/v1/search?name=London"
            response_local = urllib.request.urlopen(local_url)
            data_local = json.loads(response_local.read().decode('utf-8'))
            self.assertEqual(data_local["results"][0]["name"], "London")
            self.assertAlmostEqual(data_local["results"][0]["latitude"], 51.5074)


if __name__ == "__main__":
    unittest.main()
