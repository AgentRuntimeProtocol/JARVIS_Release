import unittest
from types import SimpleNamespace
from unittest.mock import patch

from arp_jarvis import cli


class CliRunsTests(unittest.TestCase):
    def test_inspect_fetches_root_node_run_without_bearer(self) -> None:
        args = SimpleNamespace(
            runs_cmd="inspect",
            run_id="run_123",
            include_node_runs=True,
            include_candidates=False,
            include_events=False,
        )

        with patch("arp_jarvis.cli._maybe_token", return_value=(None, "disabled")):
            with patch("arp_jarvis.cli.get_run", return_value={"run_id": "run_123", "root_node_run_id": "node_1"}):
                with patch("arp_jarvis.cli.get_node_run", return_value={"node_run_id": "node_1"}) as get_node_run:
                    with patch("arp_jarvis.cli.print_json"):
                        code = cli._cmd_runs(SimpleNamespace(), args, output="json")
        self.assertEqual(code, 0)
        get_node_run.assert_called_once()
