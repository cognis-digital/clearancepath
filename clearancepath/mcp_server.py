"""CLEARANCEPATH MCP server — exposes assess_roster as an MCP tool.

This module requires the optional ``mcp`` extra
(``pip install cognis-clearancepath[mcp]``).
It is not imported by the core package and will not be loaded unless explicitly
requested, so the missing optional dependency does not affect normal CLI usage.
"""
from __future__ import annotations

try:
    from cognis_core.mcp import build_mcp_server  # type: ignore[import]
except ImportError as _err:
    raise ImportError(
        "cognis_core is required to run the MCP server. "
        "Install it or use the CLI directly."
    ) from _err

from clearancepath import TOOL_NAME
from clearancepath.core import assess_roster

run_mcp_server = build_mcp_server(
    tool_name=TOOL_NAME,
    description=(
        "Personnel clearance hygiene tracker"
        " — SF-86, SEAD-3/4, training currency"
    ),
    scan_fn=assess_roster,
)

if __name__ == "__main__":
    run_mcp_server()
