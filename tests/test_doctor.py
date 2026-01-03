import unittest
from unittest.mock import patch
from types import SimpleNamespace

from arp_jarvis.doctor import _check_http
from arp_jarvis import doctor


class DoctorTests(unittest.TestCase):
    def test_check_http_handles_connection_reset(self):
        with patch("arp_jarvis.doctor.urlopen", side_effect=ConnectionResetError("reset")):
            result = _check_http("http://example.test/v1/health")
        self.assertFalse(result["ok"])
        self.assertIn("ConnectionResetError", result["error"])

    def test_compose_status_parses_warning_prefix(self):
        fake = SimpleNamespace(
            returncode=0,
            stdout="WARN[0000] deprecated option\n[{}]\n",
            stderr="",
        )
        with patch("arp_jarvis.doctor.compose_base_command", return_value=["docker", "compose"]):
            with patch("arp_jarvis.doctor.subprocess.run", return_value=fake):
                result = doctor._compose_status(object())
        self.assertIn("services", result)

    def test_compose_status_parses_ndjson(self):
        fake = SimpleNamespace(
            returncode=0,
            stdout='{"Service":"run-gateway","State":"running"}\n',
            stderr="",
        )
        with patch("arp_jarvis.doctor.compose_base_command", return_value=["docker", "compose"]):
            with patch("arp_jarvis.doctor.subprocess.run", return_value=fake):
                result = doctor._compose_status(object())
        self.assertIn("services", result)
