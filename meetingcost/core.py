"""Core engine for MEETINGCOST.

Parses iCalendar (.ics) data, counts attendees per event, and computes the
dollar cost of each meeting using a blended hourly rate. No third-party
dependencies; standard library only.

Cost model
----------
    cost = duration_hours * attendee_count * hourly_rate

where ``hourly_rate`` defaults to a fully-loaded rate derived from an
annual salary (salary / 2080 working hours) times an overhead multiplier.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import re

# Working hours in a year (40h * 52w) used to convert salary -> hourly.
WORK_HOURS_PER_YEAR = 2080
# Fully-loaded multiplier: benefits, taxes, overhead on top of base salary.
DEFAULT_OVERHEAD = 1.4
DEFAULT_SALARY = 100_000.0


class ICSParseError(Exception):
    """Raised when .ics content cannot be parsed into any events."""


@dataclass
class Meeting:
    """A single calendar event with cost attributes."""

    uid: str
    summary: str
    start: Optional[datetime]
    end: Optional[datetime]
    attendees: int
    duration_hours: float = 0.0
    cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["start"] = self.start.isoformat() if self.start else None
        d["end"] = self.end.isoformat() if self.end else None
        d["duration_hours"] = round(self.duration_hours, 4)
        d["cost"] = round(self.cost, 2)
        return d


@dataclass
class MeetingReport:
    """Aggregate result over a set of meetings."""

    meetings: List[Meeting] = field(default_factory=list)
    hourly_rate: float = 0.0
    total_cost: float = 0.0
    total_hours: float = 0.0
    total_person_hours: float = 0.0
    meeting_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hourly_rate": round(self.hourly_rate, 2),
            "meeting_count": self.meeting_count,
            "total_hours": round(self.total_hours, 4),
            "total_person_hours": round(self.total_person_hours, 4),
            "total_cost": round(self.total_cost, 2),
            "meetings": [m.to_dict() for m in self.meetings],
        }


def blended_hourly_rate(
    salary: float = DEFAULT_SALARY, overhead: float = DEFAULT_OVERHEAD
) -> float:
    """Convert an annual salary into a fully-loaded hourly rate."""
    if salary < 0:
        raise ValueError("salary must be non-negative")
    if overhead <= 0:
        raise ValueError("overhead must be positive")
    return (salary / WORK_HOURS_PER_YEAR) * overhead


def _unfold(text: str) -> str:
    """Unfold RFC 5545 folded lines (continuation lines start with space/tab)."""
    # Normalize line endings, then join continuation lines.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)


def _parse_dt(value: str) -> Optional[datetime]:
    """Parse an iCalendar date or date-time value.

    Handles forms like:
        20260608T143000Z      (UTC)
        20260608T143000       (floating / local)
        20260608              (date only)
    """
    value = value.strip()
    if not value:
        return None
    # Date-time with explicit UTC marker.
    if value.endswith("Z"):
        try:
            dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    # Floating date-time.
    if "T" in value:
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%S")
        except ValueError:
            return None
    # Date only.
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return None


def _split_prop(line: str):
    """Split an unfolded content line into (name, params, value).

    Property name and parameters are separated from the value by the first
    unquoted colon. Example::

        DTSTART;TZID=America/New_York:20260608T143000
    """
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch == ":" and not in_quote:
            left, value = line[:i], line[i + 1 :]
            parts = left.split(";")
            name = parts[0].upper()
            params: Dict[str, str] = {}
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k.upper()] = v
            return name, params, value
    return line.upper(), {}, ""


def parse_ics(text: str) -> List[Meeting]:
    """Parse raw .ics text into a list of :class:`Meeting` objects.

    Attendee count = number of ATTENDEE lines, plus the ORGANIZER if present
    and not already counted. If no attendees are listed at all, defaults to 1.
    """
    if "BEGIN:VEVENT" not in text:
        raise ICSParseError("no VEVENT blocks found in input")

    unfolded = _unfold(text)
    meetings: List[Meeting] = []

    in_event = False
    uid = summary = ""
    start = end = None
    has_organizer = False
    organizer_id = ""
    attendee_ids = set()

    for raw_line in unfolded.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        name, _params, value = _split_prop(line)

        if name == "BEGIN" and value.upper() == "VEVENT":
            in_event = True
            uid = summary = ""
            start = end = None
            has_organizer = False
            organizer_id = ""
            attendee_ids = set()
            continue

        if name == "END" and value.upper() == "VEVENT":
            in_event = False
            count = len(attendee_ids)
            if has_organizer and organizer_id not in attendee_ids:
                count += 1
            if count == 0:
                count = 1
            meetings.append(
                Meeting(
                    uid=uid or f"event-{len(meetings) + 1}",
                    summary=summary or "(no title)",
                    start=start,
                    end=end,
                    attendees=count,
                )
            )
            continue

        if not in_event:
            continue

        if name == "UID":
            uid = value
        elif name == "SUMMARY":
            summary = value
        elif name == "DTSTART":
            start = _parse_dt(value)
        elif name == "DTEND":
            end = _parse_dt(value)
        elif name == "ATTENDEE":
            attendee_ids.add(value.strip().lower())
        elif name == "ORGANIZER":
            has_organizer = True
            organizer_id = value.strip().lower()

    if not meetings:
        raise ICSParseError("no parseable VEVENT entries")
    return meetings


def _duration_hours(m: Meeting) -> float:
    if m.start and m.end:
        delta = m.end - m.start
        return max(delta.total_seconds() / 3600.0, 0.0)
    return 0.0


def compute_costs(meetings: List[Meeting], hourly_rate: float) -> MeetingReport:
    """Populate duration/cost on each meeting and build an aggregate report."""
    if meetings is None:
        raise ValueError("meetings must not be None")
    if hourly_rate < 0:
        raise ValueError("hourly_rate must be non-negative")

    report = MeetingReport(hourly_rate=hourly_rate, meetings=meetings)
    for m in meetings:
        m.duration_hours = _duration_hours(m)
        person_hours = m.duration_hours * m.attendees
        m.cost = person_hours * hourly_rate
        report.total_hours += m.duration_hours
        report.total_person_hours += person_hours
        report.total_cost += m.cost
    report.meeting_count = len(meetings)
    return report


def summarize(
    text: str,
    salary: float = DEFAULT_SALARY,
    overhead: float = DEFAULT_OVERHEAD,
    hourly_rate: Optional[float] = None,
) -> MeetingReport:
    """Convenience: parse .ics text and return a full cost report."""
    if not text or not text.strip():
        raise ICSParseError("input is empty — expected .ics calendar data")
    rate = hourly_rate if hourly_rate is not None else blended_hourly_rate(
        salary, overhead
    )
    meetings = parse_ics(text)
    return compute_costs(meetings, rate)
