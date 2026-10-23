"""Parser for NVIDIA supportedchips.html (authoritative GPU -> branch source).

The HTML is gtk-doc generated.  Sections are delimited by <h1>..<h6>
headings; GPU rows are <tr id="devidXXXX"> or <tr id="devidXXXX_VVVV_DDDD">
with <td>Name</td><td>DeviceID</td><td>Feature</td> cells.

The parser pairs each row with the nearest preceding classified heading:
  "Current NVIDIA GPUs"           -> "current"
  "The <NNN>.xx driver supports"  -> "<NNN>"

If the same device ID appears in both Current and a legacy section, the
legacy section wins (defensive against NVIDIA marking modern cards as
legacy, and vice versa).
"""

import os
import re
import html
import logging

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")
_CHIPS_FILE = os.path.join(_DATA_DIR, "supportedchips.html")

_HEADING_RE = re.compile(r'<h[1-6][^>]*>(.*?)</h[1-6]>', re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')
_ROW_RE = re.compile(
    r'<tr\s+id="devid([0-9A-Fa-f]{4})(?:_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4})?"',
    re.IGNORECASE,
)

_CURRENT_RE = re.compile(r'\bcurrent\b', re.IGNORECASE)
_LEGACY_RE = re.compile(r'\b(\d{2,3})\.xx\b')


def _clean_heading_text(raw):
    text = _TAG_RE.sub(' ', raw)
    text = html.unescape(text)
    text = text.replace('\xa0', ' ').replace('\u00a0', ' ')
    return ' '.join(text.split())


def _classify_heading(text):
    if _CURRENT_RE.search(text):
        return "current"
    m = _LEGACY_RE.search(text)
    if m:
        return m.group(1)
    return None


def parse(path=None):
    """Parse supportedchips.html -> {device_id_lowercase: branch}.

    Returns None if the file is missing or no entries are found.
    """
    if path is None:
        path = _CHIPS_FILE

    if not os.path.isfile(path):
        logging.debug("supported_chips: %s not found", path)
        return None

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        logging.warning("supported_chips: cannot read %s: %s", path, e)
        return None

    # 1. Collect classified headings: (end_position, branch)
    headings = []
    for m in _HEADING_RE.finditer(content):
        text = _clean_heading_text(m.group(1))
        branch = _classify_heading(text)
        if branch is not None:
            headings.append((m.end(), branch))
            logging.debug("supported_chips: heading '%s' -> %s", text[:80], branch)

    if not headings:
        logging.warning("supported_chips: no classified headings in %s", path)
        return None

    # 2. Pair each row with the nearest preceding classified heading
    result = {}
    for m in _ROW_RE.finditer(content):
        devid = m.group(1).lower()
        row_pos = m.start()

        branch = None
        for end_pos, h_branch in headings:
            if end_pos <= row_pos:
                branch = h_branch
            else:
                break

        if branch is None:
            continue

        # Legacy overrides current if the same device appears in both
        if devid not in result or branch != "current":
            result[devid] = branch

    if not result:
        logging.warning("supported_chips: parsed zero entries from %s", path)
        return None

    logging.debug("supported_chips: loaded %d entries from %s", len(result), path)
    return result


# Load at import time.  Missing/invalid file -> None -> JSON fallback path.
SUPPORTED_CHIPS = parse()


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else _CHIPS_FILE
    logging.basicConfig(level=logging.INFO)
    data = parse(target)
    if data is None:
        print("Parser returned None (file missing or no entries)")
        sys.exit(1)
    from collections import Counter
    counts = Counter(data.values())
    print("Total entries: %d" % len(data))
    for branch, count in sorted(counts.items(), key=lambda x: (x[0] != "current", x[0])):
        print("  %-8s %d entries" % (branch, count))
    print("\nSpot checks:")
    for devid, label in [
        ("1380", "GTX 750 Ti (expect 580 legacy)"),
        ("1b06", "GTX 1080 Ti (expect 580 legacy)"),
        ("2783", "RTX 4070 SUPER (expect current)"),
        ("1d81", "TITAN V (expect 580 legacy)"),
        ("2d18", "RTX 5070 (expect current)"),
    ]:
        print("  %s (%s) -> %s" % (devid, label, data.get(devid)))