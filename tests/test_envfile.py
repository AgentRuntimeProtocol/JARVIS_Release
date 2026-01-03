import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arp_jarvis.envfile import load_env_file


class EnvFileTests(unittest.TestCase):
    def test_load_env_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env.local"
            path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "KEY=value",
                        "QUOTED=\"hello\"",
                        "SINGLE='world'",
                        "EMPTY=",
                        "SPACED = value with spaces ",
                    ]
                ),
                encoding="utf-8",
            )
            payload = load_env_file(path)
            self.assertEqual(payload["KEY"], "value")
            self.assertEqual(payload["QUOTED"], "hello")
            self.assertEqual(payload["SINGLE"], "world")
            self.assertEqual(payload["EMPTY"], "")
            self.assertEqual(payload["SPACED"], "value with spaces")

