"""MEETINGCOST MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from meetingcost.core import scan, to_json

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
    def meetingcost_scan(target: str) -> str:
        """Compute the dollar cost of meetings from your calendar (.ics). Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
