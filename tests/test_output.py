import unittest

from arp_jarvis.output import format_error


class OutputTests(unittest.TestCase):
    def test_format_error_shape(self):
        payload = format_error("bad", "Something broke", hint="try again")
        self.assertIn("error", payload)
        self.assertEqual(payload["error"]["code"], "bad")
        self.assertEqual(payload["error"]["message"], "Something broke")
        self.assertEqual(payload["error"]["hint"], "try again")

