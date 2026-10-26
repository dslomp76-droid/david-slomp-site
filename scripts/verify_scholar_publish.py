#!/usr/bin/env python3
"""Confirm the saved snapshot AND generated HTML reached the public site."""
import json
from pathlib import Path
import sys
import time
import urllib.request

from refresh_scholar import render_section

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://davidslomp.ca"


def live_matches(expected, fetch):
    query = "?scholar_check=" + expected["checked_at"].replace(":", "")
    raw = fetch(SITE + "/data/scholar-metrics.json" + query)
    page = fetch(SITE + "/" + query).decode("utf-8")
    return json.loads(raw) == expected and render_section(expected) in page


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read(2_000_000)


def main():
    expected = json.loads((ROOT / "data/scholar-metrics.json").read_text())
    if not expected.get("checked_at"):
        print("No verified snapshot to check.", file=sys.stderr)
        return 1
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        try:
            if live_matches(expected, fetch):
                print("The validated snapshot and generated homepage are live at https://davidslomp.ca/.")
                return 0
        except Exception:
            pass  # A warming CDN/build may briefly return 404 or the previous version.
        time.sleep(15)
    print("Pages has not served the expected snapshot within 8 minutes. Check the Pages build; do not assume publication succeeded.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
