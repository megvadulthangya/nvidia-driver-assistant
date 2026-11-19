"""GPU device classification using NVIDIA's supportedchips documents."""

import logging

from .config import (
    proprietary_required,
    proprietary_supported,
    default,
    open_supported,
    support_flags,
)

try:
    from .supported_chips import SUPPORTED_CHIPS, SUPPORTED_CHIPS_580
except ImportError:
    SUPPORTED_CHIPS = None
    SUPPORTED_CHIPS_580 = None


def _safe_branch_int(branch_str, default=-1):
    """Return the numeric major version of a legacy branch."""
    try:
        return int(str(branch_str).split(".")[0])
    except (ValueError, IndexError, AttributeError, TypeError):
        return default


def _normalise_pci_id(device_id):
    """Normalise a PCI device ID to the four-character NVIDIA device ID."""
    value = str(device_id or "").strip().lower()

    if value.startswith("0x"):
        value = value[2:]

    return value


def _normalise_legacy_branch(branch):
    """Keep legacy branch values in the conventional NVIDIA xx.xx format."""
    if branch is None:
        return None

    value = str(branch).strip()
    if not value:
        return None

    if value.isdigit():
        return value + ".xx"

    return value


class Device(object):
    def __init__(
        self,
        id,
        name,
        features,
        legacy_branch,
        subvendorid=None,
        subdevid=None,
    ):
        super(Device, self).__init__()

        self.id = id
        self.pci_id_key = _normalise_pci_id(id)
        self.name = name
        self.features = features or []

        # Keep the JSON legacybranch as the primary legacy classification.
        self.json_legacy_branch = _normalise_legacy_branch(legacy_branch)
        self.original_legacy_branch = self.json_legacy_branch
        self.legacy_branch = self.json_legacy_branch

        self.subvendorid = subvendorid
        self.subdevid = subdevid

        # NVIDIA's latest supportedchips.html is the source for the latest
        # driver branch classification. Its Current section identifies GPUs
        # supported by the latest 6xx driver.
        self.nvidia_supported_branch = None
        if SUPPORTED_CHIPS:
            self.nvidia_supported_branch = SUPPORTED_CHIPS.get(self.pci_id_key)

        # The JSON legacybranch remains authoritative when it is present.
        # The NVIDIA document fills in a legacy branch only when JSON has none.
        if not self.original_legacy_branch:
            html_branch = self.nvidia_supported_branch
            if html_branch and html_branch != "current":
                self.original_legacy_branch = _normalise_legacy_branch(html_branch)
                self.legacy_branch = self.original_legacy_branch

        elif self.nvidia_supported_branch:
            json_major = _safe_branch_int(self.original_legacy_branch)
            html_major = _safe_branch_int(self.nvidia_supported_branch)

            if self.nvidia_supported_branch == "current" or (
                html_major >= 0 and json_major >= 0 and html_major != json_major
            ):
                logging.warning(
                    "NVIDIA supportedchips classification for %s (%s) is %s, "
                    "while supported-gpus.json assigns legacy branch %s. "
                    "Keeping the JSON legacybranch value.",
                    self.name,
                    self.id,
                    self.nvidia_supported_branch,
                    self.original_legacy_branch,
                )

        self.legacy_int = (
            _safe_branch_int(self.original_legacy_branch)
            if self.original_legacy_branch
            else -1
        )

        # A device is considered current only if NVIDIA lists it in Current
        # and the JSON database does not assign it a legacy branch.
        self.supports_latest_6xx = (
            self.nvidia_supported_branch == "current"
            and not self.original_legacy_branch
        )

        # This set comes only from the Current section of supportedchips580.html.
        self.supports_580 = bool(
            SUPPORTED_CHIPS_580
            and self.pci_id_key in SUPPORTED_CHIPS_580
        )

        self.driver_hint = ""
        self._parse_features(self.features)

    def _parse_features(self, features):
        """Determine the permitted kernel-module flavour for this GPU."""
        flags = set()

        for feature in features:
            feature_name = str(feature).lower()
            logging.debug(
                "Device %s: supported-gpus.json feature: %s",
                self.id,
                feature_name,
            )
            if feature_name in support_flags:
                flags.add(feature_name)

        logging.debug(
            "Device %s: NVIDIA branch=%s, legacy=%s, supports_580=%s, "
            "supports_latest_6xx=%s, JSON flags=%s",
            self.id,
            self.nvidia_supported_branch,
            self.original_legacy_branch,
            self.supports_580,
            self.supports_latest_6xx,
            sorted(flags),
        )

        # Hard safety rule:
        # every GPU assigned to a legacy branch <=580 must use the proprietary
        # kernel module, regardless of any kernelopen flag in JSON.
        if self.original_legacy_branch:
            if self.legacy_int < 0 or self.legacy_int <= 580:
                self.driver_hint = proprietary_required
                logging.debug(
                    "Legacy kernel-module restriction: %s (%s), branch %s "
                    "requires the proprietary kernel module.",
                    self.name,
                    self.id,
                    self.original_legacy_branch,
                )
                return

        # NVIDIA's latest 6xx Current list is the authoritative indicator
        # that the GPU is supported by the latest driver generation.
        # As agreed, drivers newer than 580 use the open kernel module.
        if self.supports_latest_6xx:
            self.driver_hint = default
            logging.debug(
                "NVIDIA Current GPU: %s (%s) requires the open kernel module.",
                self.name,
                self.id,
            )
            return

        # For devices not listed in the latest Current table, retain the
        # feature-based fallback supplied by supported-gpus.json.
        if open_supported not in flags:
            self.driver_hint = proprietary_required
        elif proprietary_supported in flags:
            self.driver_hint = proprietary_supported
        else:
            self.driver_hint = default
