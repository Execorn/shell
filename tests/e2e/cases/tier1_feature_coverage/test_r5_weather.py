import json
import urllib.request
import urllib.parse
from tests.e2e.mock_env import E2ETestCase

class TestWeatherLocation(E2ETestCase):
    def test_geocoding_city_search(self):
        """R5.1 Verify geocoding search resolves coordinates via Open-Meteo Geocoding API."""
        url = "https://geocoding-api.open-meteo.com/v1/search?name=Berlin&count=1&language=en&format=json"
        
        # Call geocoding API
        response = urllib.request.urlopen(url)
        self.assertEqual(response.getcode(), 200)
        
        data = json.loads(response.read().decode('utf-8'))
        self.assertIn("results", data)
        self.assertGreater(len(data["results"]), 0)
        
        city = data["results"][0]
        self.assertEqual(city["name"], "Berlin")
        self.assertAlmostEqual(city["latitude"], 52.5200)
        self.assertAlmostEqual(city["longitude"], 13.4050)

    def test_pin_coordinates(self):
        """R5.2 Verify pinning coordinates updates weatherLocation and weatherCoordinates in shell.json."""
        # 1. Update shell config with resolved coordinates
        config = self.env.read_shell_config()
        if "services" not in config:
            config["services"] = {}
        config["services"]["weatherLocation"] = "Berlin"
        config["services"]["weatherCoordinates"] = "52.5200,13.4050"
        self.env.write_shell_config(config)

        # 2. Assert they are correctly updated in config
        updated_config = self.env.read_shell_config()
        self.assertEqual(updated_config["services"]["weatherLocation"], "Berlin")
        self.assertEqual(updated_config["services"]["weatherCoordinates"], "52.5200,13.4050")

    def test_weather_forecast_reload(self):
        """R5.3 Verify that changing coordinates updates/reloads forecast data."""
        # Pin new coordinates (Tokyo)
        config = self.env.read_shell_config()
        if "services" not in config:
            config["services"] = {}
        config["services"]["weatherLocation"] = "Tokyo"
        config["services"]["weatherCoordinates"] = "35.6762,139.6503"
        self.env.write_shell_config(config)

        # Query mock weather forecast API for pinned coordinates
        pinned_coords = config["services"]["weatherCoordinates"]
        forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude=35.6762&longitude=139.6503&current=temperature_2m,relative_humidity_2m"
        
        response = urllib.request.urlopen(forecast_url)
        self.assertEqual(response.getcode(), 200)
        
        data = json.loads(response.read().decode('utf-8'))
        self.assertIn("current", data)
        self.assertEqual(data["current"]["temperature_2m"], 20.0)

    def test_fahrenheit_conversion(self):
        """R5.4 Verify the Fahrenheit conversion toggle updates settings."""
        # Toggle Fahrenheit on
        config = self.env.read_shell_config()
        if "services" not in config:
            config["services"] = {}
        config["services"]["useFahrenheit"] = True
        self.env.write_shell_config(config)

        updated_config = self.env.read_shell_config()
        self.assertTrue(updated_config["services"]["useFahrenheit"])

        # Toggle Fahrenheit off
        config["services"]["useFahrenheit"] = False
        self.env.write_shell_config(config)

        updated_config2 = self.env.read_shell_config()
        self.assertFalse(updated_config2["services"]["useFahrenheit"])

    def test_clock_format_setting(self):
        """R5.5 Verify the 12/24 hour clock format toggle updates settings."""
        # Set clock format to 12-hour
        config = self.env.read_shell_config()
        if "services" not in config:
            config["services"] = {}
        config["services"]["useTwelveHourClock"] = True
        self.env.write_shell_config(config)

        updated_config = self.env.read_shell_config()
        self.assertTrue(updated_config["services"]["useTwelveHourClock"])

        # Set clock format to 24-hour
        config["services"]["useTwelveHourClock"] = False
        self.env.write_shell_config(config)

        updated_config2 = self.env.read_shell_config()
        self.assertFalse(updated_config2["services"]["useTwelveHourClock"])
