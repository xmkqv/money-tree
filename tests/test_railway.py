import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class RailwayConfigurationTest(unittest.TestCase):
    def load(self, name: str) -> dict:
        with (ROOT / name).open("rb") as configuration_file:
            return tomllib.load(configuration_file)

    def test_worker_configuration(self) -> None:
        configuration = self.load("railway.toml")

        self.assertEqual(configuration["build"]["builder"], "RAILPACK")
        self.assertEqual(
            configuration["deploy"]["startCommand"],
            'uv run --no-sync mt trade --strategy "$STRATEGY"',
        )
        self.assertEqual(configuration["deploy"]["restartPolicyType"], "ALWAYS")
        self.assertEqual(configuration["deploy"]["restartPolicyMaxRetries"], 10)
        self.assertNotIn("healthcheckPath", configuration["deploy"])

    def test_web_configuration(self) -> None:
        configuration = self.load("railway.web.toml")

        self.assertEqual(configuration["build"]["builder"], "RAILPACK")
        self.assertEqual(
            configuration["build"]["watchPatterns"],
            ["src/**", "pyproject.toml", "uv.lock", "railway.web.toml"],
        )
        self.assertEqual(
            configuration["deploy"]["startCommand"],
            'uv run --no-sync uvicorn ui.app:create_app --factory --host 0.0.0.0 --port "$PORT"',
        )
        self.assertEqual(configuration["deploy"]["healthcheckPath"], "/healthz")
        self.assertEqual(configuration["deploy"]["healthcheckTimeout"], 100)
        self.assertEqual(configuration["deploy"]["restartPolicyType"], "ON_FAILURE")
        self.assertEqual(configuration["deploy"]["restartPolicyMaxRetries"], 10)


if __name__ == "__main__":
    unittest.main()
