import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arp_jarvis.config import resolve_config


class ConfigTests(unittest.TestCase):
    def _write_stack(self, root: Path, profile: str) -> None:
        (root / "compose" / "profiles").mkdir(parents=True, exist_ok=True)
        (root / "compose" / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
        (root / "stack.lock.json").write_text(
            json.dumps({"stack_version": "0.3.7"}), encoding="utf-8"
        )
        (root / "compose" / ".env.local").write_text(
            "\n".join(
                [
                    f"STACK_PROFILE={profile}",
                    "STACK_VERSION=0.3.7",
                    "RUN_GATEWAY_HOST_PORT=18081",
                    "RUN_COORDINATOR_HOST_PORT=18082",
                    "KEYCLOAK_HOST_PORT=18080",
                ]
            ),
            encoding="utf-8",
        )
        (root / "compose" / "profiles" / f"{profile}.env").write_text(
            "\n".join(
                [
                    "ARP_AUTH_PROFILE=dev-insecure",
                    "ARP_AUTH_MODE=disabled",
                    "ARP_AUTH_ISSUER=http://localhost:8080/realms/arp-dev",
                ]
            ),
            encoding="utf-8",
        )

    def test_resolve_config(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write_stack(root, "dev-insecure")
            config = resolve_config(
                stack_root_flag=str(root),
                stack_profile_flag=None,
                gateway_url_flag=None,
                coordinator_url_flag=None,
                keycloak_url_flag=None,
            )
            self.assertEqual(config.stack_profile.value, "dev-insecure")
            self.assertEqual(config.stack_version.value, "0.3.7")
            self.assertEqual(config.gateway_url.value, "http://localhost:18081")
            self.assertEqual(config.coordinator_url.value, "http://localhost:18082")
            self.assertEqual(config.keycloak_url.value, "http://localhost:18080")
            self.assertEqual(config.auth_mode.value, "disabled")
