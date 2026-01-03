import unittest

from arp_jarvis import cli


class CliOutputFlagTests(unittest.TestCase):
    def test_output_flag_after_subcommand_moves_to_front(self) -> None:
        argv = ["runs", "start", "--goal", "x", "-o", "json"]
        normalized = cli._normalize_global_flags(argv)
        self.assertEqual(normalized, ["-o", "json", "runs", "start", "--goal", "x"])

    def test_output_equals_variant_moves_to_front(self) -> None:
        argv = ["runs", "start", "--goal", "x", "--output=json"]
        normalized = cli._normalize_global_flags(argv)
        self.assertEqual(normalized, ["--output=json", "runs", "start", "--goal", "x"])

    def test_json_flag_after_subcommand_moves_to_front(self) -> None:
        argv = ["runs", "start", "--goal", "x", "--json"]
        normalized = cli._normalize_global_flags(argv)
        self.assertEqual(normalized, ["--json", "runs", "start", "--goal", "x"])

    def test_flags_after_double_dash_are_untouched(self) -> None:
        argv = ["stack", "logs", "--", "-o", "json"]
        normalized = cli._normalize_global_flags(argv)
        self.assertEqual(normalized, argv)

