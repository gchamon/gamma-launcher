from argparse import ArgumentTypeError
from unittest import TestCase

from launcher.common import parse_duration


class ParseDurationTestCase(TestCase):

    def test_parse_duration_with_units(self):
        self.assertEqual(parse_duration("30s"), 30)
        self.assertEqual(parse_duration("10m"), 600)
        self.assertEqual(parse_duration("1h"), 3600)

    def test_parse_duration_plain_seconds(self):
        self.assertEqual(parse_duration("45"), 45)

    def test_parse_duration_rejects_invalid_values(self):
        for value in ("", "abc", "1d", "0", "-1"):
            with self.subTest(value=value), self.assertRaises(ArgumentTypeError):
                parse_duration(value)
