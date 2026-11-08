import unittest

from engine.screenplay.timestamps import format_timestamp, parse_timestamp


class ParseTimestampTests(unittest.TestCase):
    def test_valid_forms(self):
        cases = {"00:00.00": 0.0, "00:04.80": 4.8, "02:18.00": 138.0, "03:20.75": 200.75,
                 "01:05": 65.0, "00:01.5": 1.5, "1:02:03.25": 3723.25, " 00:09.80 ": 9.8}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_timestamp(raw), expected)

    def test_invalid_forms_return_none_and_are_never_repaired(self):
        for raw in ["00:0x.00", "00:60.00", "1:60:00", "", "abc", "00:04.8000", "-00:01.00", "00.04.80", "4.8"]:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_timestamp(raw))

    def test_format(self):
        self.assertEqual(format_timestamp(138.0), "02:18.00")
        self.assertEqual(format_timestamp(4.8), "00:04.80")
        self.assertEqual(format_timestamp(None), "??:??.??")
