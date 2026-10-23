"""Parser for NVIDIA supportedchips.html (authoritative GPU -> branch source)."""

import os
import re
import html
import logging

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")
_CHIPS_FILE = os.path.join(_DATA_DIR, "supportedchips.html")

# Matches both "A1. CURRENT NVIDIA GPUS" and "The 580.xx driver supports ..."
_SECTION_PATTERN = re.compile(
    r'<h[1-6][^>]*>\s*'
    r'(?:A1\.\s+CURRENT\s+NVIDIA\s+GPUS|The\s+(\d+)\.xx\s+driver\s+supports)'
    r'[^<]*</h[1-6]>',
    re.IGNORECASE,
)

_GPU_NAME_PATTERN = re.compile(
    r'(GeForce|Quadro|Tesla|TITAN|RTX|GTX|NVIDIA)',
    re.IGNORECASE,
)

_DEVID_PATTERN = re.compile(r'([0-9A-Fa-f]{4})\b')


def parse(path=None):
    """Parse supportedchips.html -> {device_id_lowercase: branch}.

    branch is "current" for A1. CURRENT NVIDIA GPUS, or the major version
    string (e.g. "580", "470") for legacy sections.

    Returns None if the file is missing or no sections are found.
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

    sections = []
    for m in _SECTION_PATTERN.finditer(content):
        branch = "current" if m.group(1) is None else m.group(1)
        sections.append((m.start(), m.end(), branch))

    if not sections:
        logging.warning("supported_chips: no recognizable sections in %s", path)
        return None

    result = {}
    for idx, (start, heading_end, branch) in enumerate(sections):
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(content)
        section_html = content[heading_end:end]

        # Handle table-based sections: convert </td> to tabs, </tr> to newlines
        if re.search(r'</t[dh]>', section_html, re.IGNORECASE):
            section_html = re.sub(r'</t[dh]>', '\t', section_html, flags=re.IGNORECASE)
            section_html = re.sub(r'</tr>', '\n', section_html, flags=re.IGNORECASE)

        # Strip tags, decode entities (&nbsp; -> space, etc.)
        text = re.sub(r'<[^>]+>', '', section_html)
        text = html.unescape(text)

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Split into columns on tab or 2+ whitespace
            columns = re.split(r'\t|\s{2,}', stripped)
            if len(columns) < 2:
                continue

            model_col = columns[0].strip()
            if not _GPU_NAME_PATTERN.search(model_col):
                continue

            id_col = columns[1].strip()
            m = _DEVID_PATTERN.match(id_col)
            if not m:
                continue

            devid = m.group(1).lower()
            # Legacy sections override "current" if the same device is in both
            if devid not in result or branch != "current":
                result[devid] = branch

    if not result:
        logging.warning("supported_chips: parsed zero entries from %s", path)
        return None

    logging.debug("supported_chips: loaded %d entries from %s", len(result), path)
    return result


# Load at import time.  Missing/invalid file -> None -> JSON fallback path.
SUPPORTED_CHIPS = parse()