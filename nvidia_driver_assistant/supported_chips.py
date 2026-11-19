"""Parsers for NVIDIA's per-driver supportedchips.html documents.

The New Feature Branch document is parsed as a complete device-to-branch
map. The 580 document is parsed separately and contributes only its
Current table, because its legacy sections describe older drivers rather
than 580 compatibility.
"""

import logging
import os
import re
from html.parser import HTMLParser

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")
_CHIPS_FILE = os.path.join(_DATA_DIR, "supportedchips.html")
_CHIPS_580_FILE = os.path.join(_DATA_DIR, "supportedchips580.html")

_SECTION_RE = re.compile(r"^legacy_(\d+)(?:\.\d+)*\.xx$", re.IGNORECASE)
_ROW_RE = re.compile(
    r"^devid([0-9a-f]{4})(?:_[0-9a-f]{4}_[0-9a-f]{4})?$",
    re.IGNORECASE,
)


class _SupportedChipsHTMLParser(HTMLParser):
    """Collect device rows and the section anchor active when each begins."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current_branch = None
        self.current_row = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs if value is not None}

        if tag.lower() == "a":
            anchor = attrs.get("name") or attrs.get("id")
            if anchor:
                if anchor.lower() == "current":
                    self.current_branch = "current"
                else:
                    match = _SECTION_RE.match(anchor)
                    if match:
                        self.current_branch = match.group(1)
            return

        if tag.lower() == "tr":
            row_id = attrs.get("id", "")
            match = _ROW_RE.match(row_id)
            if match and self.current_branch:
                self.current_row = {
                    "device_id": match.group(1).lower(),
                    "branch": self.current_branch,
                    "text": [],
                }

    def handle_data(self, data):
        if self.current_row is not None and data.strip():
            self.current_row["text"].append(data.strip())

    def handle_endtag(self, tag):
        if tag.lower() == "tr" and self.current_row is not None:
            self.current_row["name_text"] = " ".join(self.current_row.pop("text"))
            self.rows.append(self.current_row)
            self.current_row = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def parse_html(content):
    """Parse HTML text and return row records, or None if no device rows exist."""
    if not isinstance(content, str) or not content.strip():
        return None

    parser = _SupportedChipsHTMLParser()
    try:
        parser.feed(content)
        parser.close()
    except Exception as exc:
        logging.warning("supported_chips: HTML parsing failed: %s", exc)
        return None

    return parser.rows or None


def parse_records(path=None):
    """Return parsed row records from a file, or None when unavailable."""
    if path is None:
        path = _CHIPS_FILE

    if not os.path.isfile(path):
        logging.debug("supported_chips: %s not found", path)
        return None

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as stream:
            content = stream.read()
    except OSError as exc:
        logging.warning("supported_chips: cannot read %s: %s", path, exc)
        return None

    rows = parse_html(content)
    if rows is None:
        logging.warning("supported_chips: no device rows found in %s", path)
    return rows


def parse(path=None):
    """Parse the complete New Feature Branch document as {PCI ID: branch}.

    If a device ID occurs in both Current and a legacy section, the legacy
    section wins. This prevents a duplicate Current row from hiding an
    explicit legacy assignment.
    """
    rows = parse_records(path)
    if not rows:
        return None

    result = {}
    for row in rows:
        device_id = row["device_id"]
        branch = row["branch"]

        # Preserve the existing precedence: every explicit legacy row wins
        # over Current, and the last legacy occurrence wins if NVIDIA repeats
        # a base device ID in multiple legacy sections.
        if device_id not in result or branch != "current":
            result[device_id] = branch

    return result or None


def parse_current(path=None):
    """Return IDs found in this document's Current table only.

    In particular, legacy sections later in supportedchips580.html are
    ignored. A device appearing in both Current and a later legacy section
    remains part of the Current set for this driver's compatibility check.
    """
    if path is None:
        path = _CHIPS_580_FILE

    rows = parse_records(path)
    if not rows:
        return None

    result = {row["device_id"] for row in rows if row["branch"] == "current"}
    return result or None


def validate_documents(latest_path=None, legacy580_path=None):
    """Validate both source documents and return their parsed data.

    Raises ValueError when either file is missing, malformed, or does not
    contain the expected section data. The PKGBUILD uses this at build time
    so a broken download or changed NVIDIA HTML layout cannot produce a
    package with incomplete compatibility data.
    """
    latest = parse(latest_path)
    if not latest:
        raise ValueError("supportedchips.html contains no parseable NVIDIA device rows")

    branches = set(latest.values())
    if "current" not in branches:
        raise ValueError("supportedchips.html has no parseable Current GPU rows")
    if not any(branch != "current" for branch in branches):
        raise ValueError("supportedchips.html has no parseable legacy GPU rows")

    current580 = parse_current(legacy580_path)
    if not current580:
        raise ValueError("supportedchips580.html has no parseable Current GPU rows")

    logging.info(
        "supported_chips: validated %d latest device IDs (%d branches) and %d 580 Current IDs",
        len(latest), len(branches), len(current580),
    )
    return latest, current580


# Load at import time. The Arch package build validates that both files are
# present; source-tree tests may run without the vendor documents installed.
SUPPORTED_CHIPS = parse()
SUPPORTED_CHIPS_580 = parse_current()
SUPPORTED_CHIPS_580_CURRENT = SUPPORTED_CHIPS_580


if __name__ == "__main__":
    import sys
    from collections import Counter

    target = sys.argv[1] if len(sys.argv) > 1 else _CHIPS_FILE
    logging.basicConfig(level=logging.INFO)
    data = parse(target)
    if data is None:
        print("Parser returned no device entries")
        raise SystemExit(1)

    counts = Counter(data.values())
    print("Total unique device IDs: %d" % len(data))
    for branch, count in sorted(
        counts.items(),
        key=lambda item: (item[0] == "current", -int(item[0]) if item[0].isdigit() else 0),
    ):
        print("  %-8s %d entries" % (branch, count))

    if len(sys.argv) > 2:
        current = parse_current(sys.argv[2])
        if not current:
            print("580 Current parser returned no device entries")
            raise SystemExit(1)
        print("580 Current unique device IDs: %d" % len(current))
