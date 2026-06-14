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


# ---------------------------------------------------------------------------
# Hardening tests: edge cases and bad input
# ---------------------------------------------------------------------------

class TestHardening(unittest.TestCase):
    """Tests for the hardening additions: validation, edge cases, bad input."""

    # ---- core.py: Person.from_dict input validation ----

    def test_reportable_non_dict_raises(self):
        """A reportable that is a plain string must raise ValueError."""
        with self.assertRaises(ValueError):
            Person.from_dict({
                "name": "Bad",
                "reportables": ["not-a-dict"],
            })

    def test_training_non_dict_raises(self):
        """A training item that is an integer must raise ValueError."""
        with self.assertRaises(ValueError):
            Person.from_dict({
                "name": "Bad",
                "trainings": [42],
            })

    def test_validity_days_negative_raises(self):
        """Negative validity_days must raise ValueError."""
        with self.assertRaises(ValueError):
            Person.from_dict({
                "name": "Bad",
                "trainings": [{"item": "insider_threat", "validity_days": -5}],
            })

    def test_validity_days_zero_raises(self):
        """Zero validity_days must raise ValueError."""
        with self.assertRaises(ValueError):
            Person.from_dict({
                "name": "Bad",
                "trainings": [{"item": "insider_threat", "validity_days": 0}],
            })

    def test_sead4_concerns_as_string_raises(self):
        """sead4_concerns passed as a bare string must raise ValueError."""
        with self.assertRaises(ValueError):
            Person.from_dict({
                "name": "Bad",
                "sead4_concerns": "some concern",
            })

    def test_future_investigation_date_is_info(self):
        """An investigation date after as_of must produce an INFO finding,
        not CRITICAL."""
        import datetime as dt2
        p = Person(
            name="Future",
            eligibility="SECRET",
            last_investigation=dt2.date(2030, 1, 1),
        )
        rep = assess_person(p, as_of=dt2.date(2026, 1, 1))
        inv = [f for f in rep.findings if f.category == "investigation"][0]
        from clearancepath import Severity
        self.assertEqual(inv.severity, Severity.INFO)

    # ---- core.py: empty roster ----

    def test_assess_empty_roster(self):
        """assess_roster([]) must return an empty list without error."""
        from clearancepath.core import assess_roster
        result = assess_roster([])
        self.assertEqual(result, [])

    # ---- cli.py: malformed JSON gives SystemExit ----

    def test_malformed_json_raises_system_exit(self):
        """A file with invalid JSON must raise SystemExit."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False) as tmp:
            tmp.write("{not valid json}")
            tmppath = tmp.name
        try:
            with self.assertRaises(SystemExit):
                main(["assess", tmppath])
        finally:
            os.unlink(tmppath)

    def test_non_object_roster_items_raise_system_exit(self):
        """A JSON array containing strings instead of objects must raise SystemExit."""
        import tempfile
        import os
        import json
        data = ["Alice", "Bob"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False) as tmp:
            json.dump(data, tmp)
            tmppath = tmp.name
        try:
            with self.assertRaises(SystemExit):
                main(["assess", tmppath])
        finally:
            os.unlink(tmppath)

    def test_empty_roster_file_exits_clean(self):
        """A JSON file with an empty array must exit 0 (nothing to flag)."""
        import tempfile
        import os
        import json
        import io
        from contextlib import redirect_stdout
        data = []
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False) as tmp:
            json.dump(data, tmp)
            tmppath = tmp.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(["assess", tmppath])
            self.assertEqual(code, 0)
        finally:
            os.unlink(tmppath)

    def test_bad_as_of_date_returns_usage_error(self):
        """--as-of with a non-date string must return exit code 3 (usage error)."""
        import tempfile
        import os
        import json
        roster = [{"name": "X", "eligibility": "SECRET",
                   "last_investigation": "2024-01-01"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False) as tmp:
            json.dump(roster, tmp)
            tmppath = tmp.name
        try:
            code = main(["--as-of", "not-a-date", "assess", tmppath])
            self.assertEqual(code, 3)
        finally:
            os.unlink(tmppath)
