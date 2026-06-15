"""Hardening tests: edge cases, bad input, and error paths for meetingcost."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meetingcost import (  # noqa: E402
    compute_costs,
    parse_ics,
    summarize,
)
from meetingcost.core import ICSParseError, blended_hourly_rate  # noqa: E402
from meetingcost.cli import main  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal valid ICS fixture
# ---------------------------------------------------------------------------
MINIMAL_ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:x@test
SUMMARY:Solo
DTSTART:20260608T100000Z
DTEND:20260608T110000Z
END:VEVENT
END:VCALENDAR
"""


class TestCoreEdgeCases(unittest.TestCase):
    """Edge cases in the core parsing / cost engine."""

    def test_summarize_empty_string_raises(self):
        """summarize('') must raise ICSParseError, not a raw AttributeError."""
        with self.assertRaises(ICSParseError):
            summarize("")

    def test_summarize_whitespace_only_raises(self):
        with self.assertRaises(ICSParseError):
            summarize("   \n\t  ")

    def test_compute_costs_empty_list_returns_zero_totals(self):
        """compute_costs with zero meetings should return a valid empty report."""
        report = compute_costs([], hourly_rate=50.0)
        self.assertEqual(report.meeting_count, 0)
        self.assertEqual(report.total_cost, 0.0)
        self.assertEqual(report.total_hours, 0.0)
        self.assertEqual(report.total_person_hours, 0.0)

    def test_compute_costs_none_meetings_raises(self):
        with self.assertRaises((ValueError, TypeError)):
            compute_costs(None, hourly_rate=50.0)  # type: ignore[arg-type]

    def test_blended_rate_zero_salary_returns_zero(self):
        """salary=0 is valid (volunteer); result should be 0."""
        self.assertEqual(blended_hourly_rate(0, 1.4), 0.0)

    def test_blended_rate_negative_salary_raises(self):
        with self.assertRaises(ValueError):
            blended_hourly_rate(-1, 1.4)

    def test_blended_rate_zero_overhead_raises(self):
        with self.assertRaises(ValueError):
            blended_hourly_rate(100_000, 0)

    def test_blended_rate_negative_overhead_raises(self):
        with self.assertRaises(ValueError):
            blended_hourly_rate(100_000, -1.0)

    def test_event_with_end_before_start_gives_zero_cost(self):
        """Reversed timestamps must not produce negative cost."""
        backwards = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:back@test
SUMMARY:Backwards
DTSTART:20260608T110000Z
DTEND:20260608T100000Z
ATTENDEE:mailto:a@x
END:VEVENT
END:VCALENDAR
"""
        report = summarize(backwards, hourly_rate=100.0)
        self.assertEqual(len(report.meetings), 1)
        self.assertGreaterEqual(report.meetings[0].cost, 0.0)
        self.assertGreaterEqual(report.meetings[0].duration_hours, 0.0)

    def test_event_no_attendees_defaults_to_one(self):
        """An event with no ATTENDEE lines must count as 1 person."""
        no_att = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:alone@test
SUMMARY:Lone wolf
DTSTART:20260608T100000Z
DTEND:20260608T110000Z
END:VEVENT
END:VCALENDAR
"""
        meetings = parse_ics(no_att)
        self.assertEqual(meetings[0].attendees, 1)

    def test_ics_no_vevent_raises(self):
        with self.assertRaises(ICSParseError):
            parse_ics("BEGIN:VCALENDAR\nEND:VCALENDAR\n")

    def test_report_to_dict_structure(self):
        """MeetingReport.to_dict() must include all required keys."""
        report = summarize(MINIMAL_ICS, hourly_rate=50.0)
        d = report.to_dict()
        for key in ("hourly_rate", "meeting_count", "total_hours",
                    "total_person_hours", "total_cost", "meetings"):
            self.assertIn(key, d)


class TestCLIHardening(unittest.TestCase):
    """CLI error handling and exit-code contracts."""

    def _run(self, argv):
        """Run main() capturing stdout/stderr, returning (rc, out, err)."""
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            rc = main(argv)
        return rc, out_buf.getvalue(), err_buf.getvalue()

    # --- pre-existing contracts (must stay green) ---
    def test_missing_file_returns_2(self):
        rc, _, _ = self._run(["cost", "no-such-file-xyz.ics"])
        self.assertEqual(rc, 2)

    def test_bad_calendar_returns_1(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False,
                                        encoding="utf-8") as fh:
            fh.write("not ics at all")
            tmp = fh.name
        try:
            rc, _, err = self._run(["cost", tmp])
            self.assertEqual(rc, 1)
            self.assertIn("error", err.lower())
        finally:
            os.unlink(tmp)

    # --- new hardening contracts ---
    def test_empty_file_returns_nonzero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False,
                                        encoding="utf-8") as fh:
            fh.write("")
            tmp = fh.name
        try:
            rc, _, err = self._run(["cost", tmp])
            self.assertNotEqual(rc, 0)
            self.assertTrue(err.strip(), "expected an error message on stderr")
        finally:
            os.unlink(tmp)

    def test_negative_hourly_rate_exits_nonzero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False,
                                        encoding="utf-8") as fh:
            fh.write(MINIMAL_ICS)
            tmp = fh.name
        try:
            # argparse.error() raises SystemExit; catch it.
            with self.assertRaises(SystemExit) as cm:
                main(["cost", tmp, "--hourly-rate", "-5"])
            self.assertNotEqual(cm.exception.code, 0)
        finally:
            os.unlink(tmp)

    def test_negative_salary_exits_nonzero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False,
                                        encoding="utf-8") as fh:
            fh.write(MINIMAL_ICS)
            tmp = fh.name
        try:
            with self.assertRaises(SystemExit) as cm:
                main(["cost", tmp, "--salary", "-1"])
            self.assertNotEqual(cm.exception.code, 0)
        finally:
            os.unlink(tmp)

    def test_zero_overhead_exits_nonzero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False,
                                        encoding="utf-8") as fh:
            fh.write(MINIMAL_ICS)
            tmp = fh.name
        try:
            with self.assertRaises(SystemExit) as cm:
                main(["cost", tmp, "--overhead", "0"])
            self.assertNotEqual(cm.exception.code, 0)
        finally:
            os.unlink(tmp)

    def test_valid_input_still_returns_0(self):
        """Smoke-check: good input must still succeed after hardening."""
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False,
                                        encoding="utf-8") as fh:
            fh.write(MINIMAL_ICS)
            tmp = fh.name
        try:
            rc, out, _ = self._run(["cost", tmp, "--format", "json"])
            self.assertEqual(rc, 0)
            import json
            data = json.loads(out)
            self.assertEqual(data["meeting_count"], 1)
        finally:
            os.unlink(tmp)


class TestModuleCompiles(unittest.TestCase):
    """All Python modules must import cleanly (no broken dead imports)."""

    def test_init_imports(self):
        import meetingcost
        self.assertEqual(meetingcost.TOOL_NAME, "meetingcost")
        self.assertTrue(meetingcost.TOOL_VERSION)

    def test_core_imports(self):
        import meetingcost.core  # noqa: F401

    def test_cli_imports(self):
        import meetingcost.cli  # noqa: F401

    def test_mcp_server_imports_without_mcp_package(self):
        """mcp_server.py must import cleanly even if 'mcp' is not installed."""
        import meetingcost.mcp_server  # noqa: F401


if __name__ == "__main__":
    unittest.main()
