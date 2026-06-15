"""meetingcost — part of the Cognis Neural Suite."""
from meetingcost.core import (  # noqa: F401
    ICSParseError,
    Meeting,
    MeetingReport,
    blended_hourly_rate,
    compute_costs,
    parse_ics,
    summarize,
)

# Identity constants: defined here so cli.py and tests can import them.
TOOL_NAME = "meetingcost"
TOOL_VERSION = "0.1.0"
__version__ = TOOL_VERSION
