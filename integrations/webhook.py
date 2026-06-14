#!/usr/bin/env python3
"""Minimal, dependency-free webhook forwarder for Cognis findings.

Reads JSON findings on stdin and POSTs them to a URL (SIEM/Slack/Jira bridge).
Usage:  <tool> scan . --format json | python integrations/webhook.py --url URL
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Destination URL (http/https)")
    ap.add_argument("--header", action="append", default=[],
                    help="Extra header in 'Key: Value' format")
    args = ap.parse_args()

    # Validate URL scheme up-front for a clear error before any I/O.
    if not args.url.startswith(("http://", "https://")):
        print(f"webhook: URL must start with http:// or https://: {args.url!r}",
              file=sys.stderr)
        return 1

    # Validate header format before reading stdin.
    for h in args.header:
        if ":" not in h:
            print(f"webhook: --header must be 'Key: Value', got {h!r}",
                  file=sys.stderr)
            return 1

    payload = sys.stdin.buffer.read()
    if not payload:
        print("webhook: stdin was empty; nothing to post", file=sys.stderr)
        return 1

    req = urllib.request.Request(args.url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    for h in args.header:
        k, _, v = h.partition(":")
        req.add_header(k.strip(), v.strip())
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"posted {len(payload)} bytes -> {r.status}")
        return 0
    except urllib.error.HTTPError as e:
        print(f"webhook: HTTP {e.code} {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"webhook: connection error: {e.reason}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"webhook: unexpected error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
