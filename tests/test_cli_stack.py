import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from arp_jarvis import cli


class CliStackTests(unittest.TestCase):
    def _write_stack(self, root: Path, profile: str) -> None:
        (root / "compose" / "profiles").mkdir(parents=True, exist_ok=True)
        (root / "compose" / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
        (root / "stack.lock.json").write_text(json.dumps({"stack_version": "0.3.8"}), encoding="utf-8")
        (root / "compose" / ".env.local").write_text(
            "\n".join(
                [
                    f"STACK_PROFILE={profile}",
                    "STACK_VERSION=0.3.8",
                    "RUN_GATEWAY_HOST_PORT=18081",
                    "RUN_COORDINATOR_HOST_PORT=18082",
                    "KEYCLOAK_HOST_PORT=18080",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "compose" / "profiles" / f"{profile}.env").write_text(
            "\n".join(
                [
                    "ARP_AUTH_PROFILE=dev-insecure",
                    "ARP_AUTH_MODE=disabled",
                    "ARP_AUTH_ISSUER=http://localhost:8080/realms/arp-dev",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_stack_up_detach_flag(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write_stack(root, "dev-insecure")

            with patch("arp_jarvis.cli.run_compose") as run_compose:
                run_compose.return_value = 0
                code = cli.main(["--stack-root", str(root), "stack", "up", "-d"])
                self.assertEqual(code, 0)
                run_compose.assert_called_once()
                self.assertEqual(run_compose.call_args.args[1], ["up", "-d"])

    def test_stack_up_build_flag(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write_stack(root, "dev-insecure")

            with patch("arp_jarvis.cli.run_compose") as run_compose:
                run_compose.return_value = 0
                code = cli.main(["--stack-root", str(root), "stack", "up", "--build"])
                self.assertEqual(code, 0)
                run_compose.assert_called_once()
                self.assertEqual(run_compose.call_args.args[1], ["up", "--build"])

    def test_stack_logs_follow_flag(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write_stack(root, "dev-insecure")

            with patch("arp_jarvis.cli.run_compose") as run_compose:
                run_compose.return_value = 0
                code = cli.main(["--stack-root", str(root), "stack", "logs", "-f", "composite-executor"])
                self.assertEqual(code, 0)
                run_compose.assert_called_once()
                self.assertEqual(run_compose.call_args.args[1], ["logs", "-f", "composite-executor"])

    def test_stack_ps_all_flag(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write_stack(root, "dev-insecure")

            with patch("arp_jarvis.cli.run_compose") as run_compose:
                run_compose.return_value = 0
                code = cli.main(["--stack-root", str(root), "stack", "ps", "--all"])
                self.assertEqual(code, 0)
                run_compose.assert_called_once()
                self.assertEqual(run_compose.call_args.args[1], ["ps", "--all"])
