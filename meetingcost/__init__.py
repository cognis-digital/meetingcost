"""MEETINGCOST - Compute the dollar cost of meetings from your calendar (.ics).

A zero-install, standard-library-only CLI for surfacing the true cost of
meetings parsed straight out of an iCalendar (.ics) export.
"""

from .core import (
    Meeting,
    MeetingReport,
    parse_ics,
    compute_costs,
    summarize,
)

TOOL_NAME = "meetingcost"
TOOL_VERSION = "1.0.0"

__all__ = [
    "Meeting",
    "MeetingReport",
    "parse_ics",
    "compute_costs",
    "summarize",
    "TOOL_NAME",
    "TOOL_VERSION",
]
