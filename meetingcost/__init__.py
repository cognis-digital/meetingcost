"""meetingcost — part of the Cognis Neural Suite."""
try:  # re-export the tool's public API + identity from core
    from meetingcost.core import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass
try:
    from meetingcost.core import TOOL_NAME, TOOL_VERSION
except Exception:  # pragma: no cover
    TOOL_NAME = "meetingcost"
    TOOL_VERSION = "0.1.0"
__version__ = TOOL_VERSION
