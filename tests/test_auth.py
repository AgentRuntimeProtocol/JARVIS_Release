import unittest

from arp_jarvis.auth import build_public_endpoints


class AuthEndpointTests(unittest.TestCase):
    def test_build_public_endpoints_rewrites_base(self):
        endpoints = build_public_endpoints(
            issuer="http://keycloak:8080/realms/arp-dev",
            token_endpoint=None,
            client_id="arp-dev-cli",
            client_secret=None,
            public_base_url="http://localhost:8080",
        )
        self.assertEqual(
            endpoints.token_endpoint,
            "http://localhost:8080/realms/arp-dev/protocol/openid-connect/token",
        )
        self.assertEqual(
            endpoints.device_endpoint,
            "http://localhost:8080/realms/arp-dev/protocol/openid-connect/auth/device",
        )
        self.assertEqual(endpoints.issuer, "http://keycloak:8080/realms/arp-dev")
