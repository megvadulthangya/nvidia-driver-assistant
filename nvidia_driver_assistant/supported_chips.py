"""Parser for NVIDIA supportedchips.html (authoritative GPU -> branch source).

The HTML is gtk-doc generated.  Each section is anchored by an
`<a name="...">` tag placed immediately before its heading/table:

  <p><a name="Current" id="Current"></a></p>
  <h3>Current NVIDIA GPUs</h3>
  ...
  <p><a name="legacy_580.xx" id="legacy_580.xx"></a> The 580.xx
  driver supports the following set of GPUs:</p>
  ...
  <p><a name="legacy_173.14.xx" id="legacy_173.14.xx"></a> The
  173.14.xx driver supports the following set of GPUs:</p>

GPU rows are <tr id="devidXXXX"> (or <tr id="devidXXXX_VVVV_DDDD"> for
subsystem variants).  Each row inherits the branch of the nearest
preceding anchor.  If the same base device ID appears in both "current"
and a legacy section, the legacy section wins (defensive against
NVIDIA marking modern cards as legacy, and vice versa).
"""

import os
import re
import logging

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")
_CHIPS_FILE = os.path.join(_DATA_DIR, "supportedchips.html")

# <a name="Current" ...> or <a name="legacy_580.xx" ...> or legacy_173.14.xx
_SECTION_RE = re.compile(
    r'<a\s+name="(Current|legacy_(\d+)(?:\.\d+)*\.xx)"',
    re.IGNORECASE,
)

# <tr id="devidXXXX"> or <tr id="devidXXXX_VVVV_DDDD">
_ROW_RE = re.compile(
    r'<tr\s+id="devid([0-9A-Fa-f]{4})(?:_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4})?"',
    re.IGNORECASE,
)


def _collect_sections(content):
    """Return sorted list of (position, branch) section anchors."""
    sections = []
    for m in _SECTION_RE.finditer(content):
        if m.group(1).lower() == "current":
            branch = "current"
        else:
            branch = m.group(2)  # e.g. "580", "173", "96", "71"
        sections.append((m.start(), branch))
    return sections


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

    sections = _collect_sections(content)
    if not sections:
        logging.warning("supported_chips: no section anchors in %s", path)
        return None

    branches_found = sorted({b for _, b in sections})
    logging.debug(
        "supported_chips: %d section anchors found: %s",
        len(sections), branches_found,
    )

    has_current = any(b == "current" for _, b in sections)
    has_legacy = any(b != "current" for _, b in sections)
    if not has_current or not has_legacy:
        logging.warning(
            "supported_chips: unexpected section set in %s "
            "(current=%s, legacy=%s) — legacy detection may be incomplete",
            path, has_current, has_legacy,
        )

    result = {}
    for m in _ROW_RE.finditer(content):
        devid = m.group(1).lower()
        row_pos = m.start()

        branch = None
        for marker_pos, marker_branch in sections:
            if marker_pos < row_pos:
                branch = marker_branch
            else:
                break

        if branch is None:
            continue

        # Legacy wins over current if the same devid appears in both
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
    from collections import Counter

    target = sys.argv[1] if len(sys.argv) > 1 else _CHIPS_FILE
    logging.basicConfig(level=logging.DEBUG if "-v" in sys.argv else logging.INFO)

    data = parse(target)
    if data is None:
        print("Parser returned None (file missing or no entries)")
        sys.exit(1)

    counts = Counter(data.values())

    def _sort_key(item):
        branch, _count = item
        if branch == "current":
            return (1, 0)
        try:
            return (0, -int(branch.split(".")[0]))
        except ValueError:
            return (0, 0)

    print("Total unique device IDs: %d" % len(data))
    for branch, count in sorted(counts.items(), key=_sort_key):
        print("  %-8s %d entries" % (branch, count))

    print("\nSpot checks:")
    expected = [
        ("1380", "580"),   # GTX 750 Ti (Maxwell, legacy 580)
        ("1b06", "580"),   # GTX 1080 Ti (Pascal, legacy 580)
        ("1d81", "580"),   # TITAN V (Volta, legacy 580)
        ("0fc6", "470"),   # GTX 650 (Kepler, legacy 470)
        ("06c0", "390"),   # GTX 480 (Fermi, legacy 390)
        ("00c2", "304"),   # 6800 LE (pre-Curie, legacy 304)
        ("2783", "current"),  # RTX 4070 SUPER (Ada)
        ("2d18", "current"),  # RTX 5070 Laptop (Blackwell)
    ]
    all_ok = True
    for devid, expected_branch in expected:
        actual = data.get(devid)
        status = "OK" if actual == expected_branch else "MISMATCH"
        if actual != expected_branch:
            all_ok = False
        print("  %s -> %-8s (expected %-8s) [%s]"
              % (devid, actual, expected_branch, status))

    print()
    if all_ok:
        print("All spot checks passed.")
        sys.exit(0)
    else:
        print("Some spot checks failed.")
        sys.exit(1)