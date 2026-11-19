"""Parsers for NVIDIA supportedchips.html documents across driver generations.

The New Feature Branch and 580 documents use NVIDIA's section anchors and
``devidXXXX`` table-row IDs. Older 470/390/340 documents use ordinary HTML
tables with a ``Device PCI ID`` column and append one or more older legacy
driver lists after the current driver's supported products. The legacy parser
reads only the document's own supported-products tables and stops at NVIDIA's
legacy-section introduction.
"""

import logging
import os
import re
from html.parser import HTMLParser

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")
_CHIPS_FILE = os.path.join(_DATA_DIR, "supportedchips.html")
_CHIPS_580_FILE = os.path.join(_DATA_DIR, "supportedchips580.html")
_CHIPS_470_FILE = os.path.join(_DATA_DIR, "supportedchips470.html")
_CHIPS_390_FILE = os.path.join(_DATA_DIR, "supportedchips390.html")
_CHIPS_340_FILE = os.path.join(_DATA_DIR, "supportedchips340.html")

_SECTION_RE = re.compile(r"^legacy_(\d+)(?:\.\d+)*\.xx$", re.IGNORECASE)
_ROW_RE = re.compile(
    r"^devid([0-9a-f]{4})(?:_[0-9a-f]{4}_[0-9a-f]{4})?$",
    re.IGNORECASE,
)
_PCI_ID_TOKEN_RE = re.compile(
    r"(?<![0-9a-f])(?:0x)?([0-9a-f]{4})(?![0-9a-f])",
    re.IGNORECASE,
)
_LEGACY_INTRO_RE = re.compile(
    r"below\s+are\s+the\s+legacy\s+gpus\s+that\s+are\s+no\s+longer\s+"
    r"supported\s+in\s+the\s+unified\s+driver"
    r"|the\s+\d{3}\.xx\s+driver\s+supports\s+the\s+following\s+set\s+of\s+gpus",
    re.IGNORECASE,
)


class _SupportedChipsHTMLParser(HTMLParser):
    """Collect modern document rows and the section active when each begins."""

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


class _LegacySupportedChipsHTMLParser(HTMLParser):
    """Read old-style Device PCI ID tables before the embedded legacy lists."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row_cells = None
        self.current_cell_parts = None
        self.table_device_id_column = None
        self.legacy_section_started = False
        self.text_probe = ""
        self.rows = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "table":
            self.in_table = True
            self.table_device_id_column = None
            return

        if not self.in_table:
            return

        if tag == "tr":
            self.in_row = True
            self.current_row_cells = []
            self.current_cell_parts = None
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell_parts = []

    def handle_data(self, data):
        # NVIDIA's legacy-section introduction is outside the tables. Keeping a
        # rolling text window also handles the phrase being split by HTML tags.
        self.text_probe = (self.text_probe + " " + data).lower()[-600:]
        if _LEGACY_INTRO_RE.search(self.text_probe):
            self.legacy_section_started = True

        if self.in_cell and self.current_cell_parts is not None:
            self.current_cell_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in ("td", "th") and self.in_cell:
            cell_text = " ".join("".join(self.current_cell_parts or []).split())
            self.current_row_cells.append(cell_text)
            self.current_cell_parts = None
            self.in_cell = False
            return

        if tag == "tr" and self.in_row:
            self._finish_row()
            self.current_row_cells = None
            self.current_cell_parts = None
            self.in_row = False
            self.in_cell = False
            return

        if tag == "table":
            self.in_table = False
            self.table_device_id_column = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def _finish_row(self):
        cells = self.current_row_cells or []
        normalized = [" ".join(cell.split()).lower() for cell in cells]

        # NVIDIA repeats the table header for each product family. Identify the
        # PCI column per table instead of assuming every table has the same
        # column layout.
        for index, cell in enumerate(normalized):
            if "device pci id" in cell:
                self.table_device_id_column = index
                return

        if self.legacy_section_started or self.table_device_id_column is None:
            return

        column = self.table_device_id_column
        if column >= len(cells):
            return

        # The PCI-ID cell may contain either one device ID or a device ID plus
        # subsystem vendor/device IDs. Only the first token is the PCI device ID.
        matches = _PCI_ID_TOKEN_RE.findall(cells[column])
        if not matches:
            return

        name = cells[0] if cells else ""
        self.rows.append(
            {
                "device_id": matches[0].lower(),
                "name_text": name,
                "branch": None,
            }
        )


def parse_html(content):
    """Parse modern NVIDIA HTML and return row records, or None if empty."""
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


def parse_legacy_html(content):
    """Parse an older NVIDIA document's own tables, excluding later legacy lists.

    Returns row records with normalized four-character device IDs. The parser
    requires NVIDIA's legacy-section boundary to be present; otherwise it
    refuses to guess where the document's own list ends.
    """
    if not isinstance(content, str) or not content.strip():
        return None

    parser = _LegacySupportedChipsHTMLParser()
    try:
        parser.feed(content)
        parser.close()
    except Exception as exc:
        logging.warning("supported_chips: legacy HTML parsing failed: %s", exc)
        return None

    if not parser.legacy_section_started:
        logging.warning(
            "supported_chips: legacy section boundary not found in older NVIDIA document"
        )
        return None

    return parser.rows or None


def _read_document(path, label):
    if not os.path.isfile(path):
        logging.debug("supported_chips: %s not found", path)
        return None

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as stream:
            return stream.read()
    except OSError as exc:
        logging.warning("supported_chips: cannot read %s: %s", path, exc)
        return None


def parse_records(path=None):
    """Return modern parser records from a file, or None when unavailable."""
    if path is None:
        path = _CHIPS_FILE

    content = _read_document(path, "modern")
    if content is None:
        return None

    rows = parse_html(content)
    if rows is None:
        logging.warning("supported_chips: no device rows found in %s", path)
    return rows


def parse_legacy_records(path):
    """Return old-style table records from a file, or None when unavailable."""
    content = _read_document(path, "legacy")
    if content is None:
        return None

    rows = parse_legacy_html(content)
    if rows is None:
        logging.warning("supported_chips: no supported-device tables found in %s", path)
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

        # Preserve existing precedence: an explicit legacy row wins over
        # Current, and the last legacy occurrence wins across legacy sections.
        if device_id not in result or branch != "current":
            result[device_id] = branch

    return result or None


def parse_current(path=None):
    """Return IDs in this document's Current table only."""
    if path is None:
        path = _CHIPS_580_FILE

    rows = parse_records(path)
    if not rows:
        return None

    result = {row["device_id"] for row in rows if row["branch"] == "current"}
    return result or None


def parse_legacy_supportedchips(path):
    """Return the set of device IDs in an older driver's own supported tables."""
    rows = parse_legacy_records(path)
    if not rows:
        return None
    return {row["device_id"] for row in rows} or None


def validate_documents(latest_path=None, legacy580_path=None):
    """Validate the existing 6xx and 580 documents (backward-compatible API)."""
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


def validate_all_documents(
    latest_path=None,
    legacy580_path=None,
    legacy470_path=None,
    legacy390_path=None,
    legacy340_path=None,
):
    """Validate all five NVIDIA sources and return per-driver ID sets/maps."""
    latest, current580 = validate_documents(latest_path, legacy580_path)

    legacy_paths = {
        "470": legacy470_path or _CHIPS_470_FILE,
        "390": legacy390_path or _CHIPS_390_FILE,
        "340": legacy340_path or _CHIPS_340_FILE,
    }
    result = {
        "6xx": {device_id for device_id, branch in latest.items() if branch == "current"},
        "580": current580,
    }

    for branch, path in legacy_paths.items():
        supported_ids = parse_legacy_supportedchips(path)
        if not supported_ids:
            raise ValueError(
                "supportedchips%s.html contains no validated %s driver device IDs"
                % (branch, branch)
            )
        result[branch] = supported_ids

    logging.info(
        "supported_chips: validated per-driver sets: %s",
        ", ".join("%s=%d" % (branch, len(ids)) for branch, ids in result.items()),
    )
    return result


# Load data at import time. Source-tree tests may run without vendor documents;
# the PKGBUILD and CI validate all five files before packaging/testing.
SUPPORTED_CHIPS = parse()
SUPPORTED_CHIPS_6XX = (
    {device_id for device_id, branch in SUPPORTED_CHIPS.items() if branch == "current"}
    if SUPPORTED_CHIPS
    else None
)
SUPPORTED_CHIPS_580 = parse_current()
SUPPORTED_CHIPS_580_CURRENT = SUPPORTED_CHIPS_580
SUPPORTED_CHIPS_470 = parse_legacy_supportedchips(_CHIPS_470_FILE)
SUPPORTED_CHIPS_390 = parse_legacy_supportedchips(_CHIPS_390_FILE)
SUPPORTED_CHIPS_340 = parse_legacy_supportedchips(_CHIPS_340_FILE)

SUPPORTED_CHIPS_BY_DRIVER = {
    branch: ids
    for branch, ids in {
        "6xx": SUPPORTED_CHIPS_6XX,
        "580": SUPPORTED_CHIPS_580,
        "470": SUPPORTED_CHIPS_470,
        "390": SUPPORTED_CHIPS_390,
        "340": SUPPORTED_CHIPS_340,
    }.items()
    if ids is not None
}


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
