import unittest
from unittest.mock import patch

from arp_jarvis.doctor import _check_http


class DoctorTests(unittest.TestCase):
    def test_check_http_handles_connection_reset(self):
        with patch("arp_jarvis.doctor.urlopen", side_effect=ConnectionResetError("reset")):
            result = _check_http("http://example.test/v1/health")
        self.assertFalse(result["ok"])
        self.assertIn("ConnectionResetError", result["error"])

