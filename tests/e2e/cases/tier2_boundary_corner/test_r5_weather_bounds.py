import json
import os
import re
import urllib.request
import urllib.parse
from tests.e2e.mock_env import E2ETestCase

class WeatherLocationManager:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.shell_config_path = os.path.join(self.config_dir, "shell.json")

    def validate_coordinates(self, coords_str):
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


class TestWeatherBounds(E2ETestCase):
    def setUp(self):
        super().setUp()
        self.manager = WeatherLocationManager(self.env.caelestia_config_dir)

    def test_city_not_found(self):
        # Configure http mock to return empty results for "Xyzzystan"
        self.env.http_mocks["geocoding-api.open-meteo.com"] = (200, json.dumps({"results": []}))

        res, err = self.manager.search_city("Xyzzystan")
        self.assertIsNone(res)
        self.assertEqual(err, "City not found")

    def test_geocoding_api_timeout(self):
        # Configure http mock to raise/fail on open-meteo request
        def error_handler(url, query):
            # To raise URLError from standard urllib:
            import urllib.error
            raise urllib.error.URLError("Connection timed out")
            
        self.env.http_mocks["geocoding-api.open-meteo.com"] = error_handler

        res, err = self.manager.search_city("Berlin")
        self.assertIsNone(res)
        self.assertIn("Network error", err)

    def test_invalid_coordinate_text_input(self):
        # 1. Invalid characters
        success, err = self.manager.update_config("Invalid", "abc,def")
        self.assertFalse(success)
        self.assertEqual(err, "Invalid coordinate format. Must be 'lat,lon'")

        # 2. Out of range values
        success, err = self.manager.update_config("Invalid", "95.0,20.0")
        self.assertFalse(success)
        self.assertEqual(err, "Latitude must be between -90 and 90")

        # 3. Missing comma
        success, err = self.manager.update_config("Invalid", "45.0 20.0")
        self.assertFalse(success)
        self.assertEqual(err, "Invalid coordinate format. Must be 'lat,lon'")

    def test_empty_search_query(self):
        res, err = self.manager.search_city("")
        self.assertIsNone(res)
        self.assertEqual(err, "Search query cannot be empty")

        res, err = self.manager.search_city("   ")
        self.assertIsNone(res)
        self.assertEqual(err, "Search query cannot be empty")

    def test_extreme_coordinates_bounds(self):
        # 1. Valid extreme boundary
        success, err = self.manager.update_config("SouthPoleEdge", "-90.0,-180.0")
        self.assertTrue(success)
        config = self.env.read_shell_config()
        self.assertEqual(config["services"]["weatherCoordinates"], "-90.0,-180.0")

        # 2. Invalid extreme boundary (lat too low)
        success, err = self.manager.update_config("TooSouth", "-90.1,-180.0")
        self.assertFalse(success)
        self.assertEqual(err, "Latitude must be between -90 and 90")

        # 3. Invalid extreme boundary (lon too high)
        success, err = self.manager.update_config("TooEast", "90.0,180.1")
        self.assertFalse(success)
        self.assertEqual(err, "Longitude must be between -180 and 180")
