"""MEETINGCOST MCP server — exposes summarize() as an MCP tool for Cognis.Studio."""
from __future__ import annotations

import json

from meetingcost.core import ICSParseError, summarize


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-meetingcost[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-meetingcost[mcp]'")
        return 1
    app = FastMCP("meetingcost")

    @app.tool()
    def meetingcost_scan(ics_text: str, hourly_rate: float = 67.31) -> str:
        """Compute the dollar cost of meetings from .ics text. Returns JSON."""
        try:
            report = summarize(ics_text, hourly_rate=hourly_rate)
        except ICSParseError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(report.to_dict(), indent=2)

    app.run()
    return 0
