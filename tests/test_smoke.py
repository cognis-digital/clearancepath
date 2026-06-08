"""Smoke tests for CLEARANCEPATH. Standard library only, no network."""

import datetime as dt
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clearancepath import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    Person,
    Severity,
    assess_person,
    parse_date,
)
from clearancepath.cli import main  # noqa: E402

AS_OF = dt.date(2026, 6, 8)
ROSTER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos", "01-basic", "roster.json",
)


class TestMeta(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(TOOL_NAME, "clearancepath")
        self.assertTrue(TOOL_VERSION)


class TestParse(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2026-01-15"), dt.date(2026, 1, 15))
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date(""))
        with self.assertRaises(ValueError):
            parse_date("not-a-date")


class TestEngine(unittest.TestCase):
    def test_overdue_investigation_is_critical(self):
        p = Person(name="X", eligibility="TS/SCI",
                   last_investigation=dt.date(2019, 1, 1))
        rep = assess_person(p, as_of=AS_OF)
        inv = [f for f in rep.findings if f.category == "investigation"][0]
        self.assertEqual(inv.severity, Severity.CRITICAL)
        self.assertEqual(rep.status, Severity.CRITICAL)

    def test_current_secret_is_ok(self):
        p = Person(name="Y", eligibility="SECRET",
                   last_investigation=dt.date(2021, 11, 2))
        rep = assess_person(p, as_of=AS_OF)
        inv = [f for f in rep.findings if f.category == "investigation"][0]
        self.assertEqual(inv.severity, Severity.OK)

    def test_unreported_travel_critical(self):
        p = Person.from_dict({
            "name": "Z",
            "eligibility": "SECRET",
            "last_investigation": "2024-01-01",
            "reportables": [
                {"kind": "foreign_travel", "occurred": "2026-05-01"},
            ],
        })
        rep = assess_person(p, as_of=AS_OF)
        s3 = [f for f in rep.findings if f.category == "sead3"][0]
        self.assertEqual(s3.severity, Severity.CRITICAL)

    def test_timely_report_ok(self):
        p = Person.from_dict({
            "name": "W",
            "eligibility": "SECRET",
            "last_investigation": "2024-01-01",
            "reportables": [
                {"kind": "arrest", "occurred": "2026-03-01",
                 "reported": "2026-03-03"},
            ],
        })
        rep = assess_person(p, as_of=AS_OF)
        s3 = [f for f in rep.findings if f.category == "sead3"][0]
        self.assertEqual(s3.severity, Severity.OK)

    def test_expired_training_critical(self):
        p = Person.from_dict({
            "name": "T",
            "eligibility": "SECRET",
            "last_investigation": "2024-01-01",
            "trainings": [
                {"item": "insider_threat", "completed": "2024-12-01"},
            ],
        })
        rep = assess_person(p, as_of=AS_OF)
        tr = [f for f in rep.findings if f.category == "training"][0]
        self.assertEqual(tr.severity, Severity.CRITICAL)

    def test_missing_name_raises(self):
        with self.assertRaises(ValueError):
            Person.from_dict({"eligibility": "SECRET"})


class TestCLI(unittest.TestCase):
    def test_assess_table_exit1(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--as-of", "2026-06-08", "assess", ROSTER])
        self.assertEqual(code, 1)  # Doe has CRITICAL findings
        self.assertIn("Doe", buf.getvalue())

    def test_assess_json_shape(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--as-of", "2026-06-08", "--format", "json",
                         "assess", ROSTER])
        self.assertEqual(code, 1)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["tool"], "clearancepath")
        self.assertEqual(payload["summary"]["count"], 2)
        self.assertGreaterEqual(payload["summary"]["critical"], 1)

    def test_due_filters_to_attention(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["--as-of", "2026-06-08", "--format", "json",
                  "due", ROSTER])
        payload = json.loads(buf.getvalue())
        for person in payload["personnel"]:
            for f in person["findings"]:
                self.assertIn(f["severity"], ("WARN", "CRITICAL"))

    def test_missing_file_usage_error(self):
        with self.assertRaises(SystemExit):
            main(["assess", "no_such_roster_12345.json"])


if __name__ == "__main__":
    unittest.main()
