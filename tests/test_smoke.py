"""Smoke tests for MEETINGCOST. Standard library only, no network."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meetingcost import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    compute_costs,
    parse_ics,
    summarize,
)
from meetingcost.core import (  # noqa: E402
    ICSParseError,
    blended_hourly_rate,
)
from meetingcost.cli import main  # noqa: E402

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:a@x
SUMMARY:Standup
DTSTART:20260608T140000Z
DTEND:20260608T143000Z
ATTENDEE:mailto:a@x
ATTENDEE:mailto:b@x
ATTENDEE:mailto:c@x
END:VEVENT
BEGIN:VEVENT
UID:b@x
SUMMARY:Planning
DTSTART:20260609T150000Z
DTEND:20260609T170000Z
ORGANIZER:mailto:lead@x
ATTENDEE:mailto:a@x
ATTENDEE:mailto:b@x
END:VEVENT
END:VCALENDAR
"""

DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos",
    "01-basic",
    "team-week.ics",
)


class TestParsing(unittest.TestCase):
    def test_parse_counts_events_and_attendees(self):
        meetings = parse_ics(ICS)
        self.assertEqual(len(meetings), 2)
        self.assertEqual(meetings[0].attendees, 3)
        # Organizer not in attendee list -> counted: 2 attendees + 1 organizer.
        self.assertEqual(meetings[1].attendees, 3)

    def test_durations(self):
        meetings = parse_ics(ICS)
        self.assertAlmostEqual(meetings[0].duration_hours, 0.0)  # not yet computed
        report = compute_costs(meetings, 100.0)
        self.assertAlmostEqual(report.meetings[0].duration_hours, 0.5)
        self.assertAlmostEqual(report.meetings[1].duration_hours, 2.0)

    def test_bad_input_raises(self):
        with self.assertRaises(ICSParseError):
            parse_ics("not a calendar at all")

    def test_folded_line_unfolding(self):
        with open(DEMO, encoding="utf-8") as fh:
            meetings = parse_ics(fh.read())
        titles = [m.summary for m in meetings]
        self.assertTrue(
            any("status update" in t and "email" in t for t in titles),
            "folded SUMMARY should be unfolded into a single line",
        )


class TestCostModel(unittest.TestCase):
    def test_blended_rate(self):
        self.assertAlmostEqual(blended_hourly_rate(100_000, 1.4), 67.30769, places=4)

    def test_cost_math(self):
        report = summarize(ICS, hourly_rate=100.0)
        # Standup: 0.5h * 3 * 100 = 150 ; Planning: 2h * 3 * 100 = 600
        costs = {m.summary: round(m.cost, 2) for m in report.meetings}
        self.assertEqual(costs["Standup"], 150.0)
        self.assertEqual(costs["Planning"], 600.0)
        self.assertEqual(round(report.total_cost, 2), 750.0)
        self.assertAlmostEqual(report.total_person_hours, 7.5)

    def test_negative_rate_rejected(self):
        with self.assertRaises(ValueError):
            compute_costs(parse_ics(ICS), -5.0)


class TestCLI(unittest.TestCase):
    def test_version(self):
        self.assertEqual(TOOL_NAME, "meetingcost")
        self.assertTrue(TOOL_VERSION)
        with self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_json_output_on_demo(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["cost", DEMO, "--format", "json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["meeting_count"], 4)
        self.assertGreater(data["total_cost"], 0)
        self.assertEqual(len(data["meetings"]), 4)

    def test_table_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["cost", DEMO, "--hourly-rate", "50", "--format", "table"])
        self.assertEqual(rc, 0)
        self.assertIn("TOTAL COST", buf.getvalue())

    def test_missing_file_nonzero_exit(self):
        rc = main(["cost", "does-not-exist-12345.ics"])
        self.assertEqual(rc, 2)

    def test_bad_calendar_nonzero_exit(self):
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", suffix=".ics", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("garbage, no events")
            tmp = fh.name
        try:
            rc = main(["cost", tmp])
            self.assertEqual(rc, 1)
        finally:
            os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()
