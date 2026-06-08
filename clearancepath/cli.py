"""CLEARANCEPATH command-line interface."""
from cognis_core import build_cli
from clearancepath.core import scan, TOOL_NAME, TOOL_VERSION

main = build_cli(
    tool_name=TOOL_NAME,
    tool_version=TOOL_VERSION,
    description="Personnel clearance hygiene tracker — SF-86, SEAD-3/4, training currency",
    scan_fn=scan,
)

if __name__ == "__main__":
    import sys
    sys.exit(main())
