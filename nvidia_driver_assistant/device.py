"""Device class and GPU architecture logic."""

import re
import logging

from .config import (
    ARCHITECTURE_REGISTRY,
    ARCHITECTURE_MIN_DRIVER,
    OPEN_CAPABLE_ARCHS,
    OPEN_UNSUPPORTED_ARCHS,
    DISTRO_NON_LEGACY_DEFAULT_BRANCH,
    DISTRO_580_LEGACY_OVERRIDE_BRANCH,
    ENABLE_LEGACY_OPENKERNEL_RESTRICTION,
    ENABLE_ARCHITECTURE_CHECK,
    AUTO_FALLBACK,
    min_supported_legacy_branch,
    proprietary_required,
    proprietary_supported,
    default,
    open_supported,
    support_flags,
)


def _safe_branch_int(branch_str, default=-1):
    try:
        return int(branch_str.split('.')[0])
    except (ValueError, IndexError):
        return default


class Device(object):
    def __init__(self, id, name, features, legacy_branch, subvendorid=None, subdevid=None):
        super(Device, self).__init__()
        self.id = id
        self.name = name
        self.features = features
        self.original_legacy_branch = legacy_branch  # preserve original JSON legacybranch
        self.legacy_branch = legacy_branch
        self.driver_hint = ""
        self.architecture = "unknown"
        self.chip_family = ""
        self.subvendorid = subvendorid
        self.subdevid = subdevid
        self.is_laptop_gpu = self._is_laptop_gpu(name)
        self._determine_architecture()
        self.legacy_int = _safe_branch_int(self.original_legacy_branch) if self.original_legacy_branch else -1
        self._parse_features(features)

    def _is_laptop_gpu(self, name):
        """Determine if this is a laptop/mobile GPU"""
        name_lower = name.lower()

        desktop_exceptions = [
            '750 ti', '1050 ti', '1650 ti', '1660 ti',
            '2060 ti', '2070 ti', '2080 ti', '3060 ti',
            '3070 ti', '3080 ti', '3090 ti', '4060 ti',
            '4070 ti', '4080 ti', '4090 ti', 'titan',
            '750', '760', '770', '780', '950', '960', '970', '980',
        ]
        for exception in desktop_exceptions:
            if exception in name_lower:
                return False

        if re.search(r'\d{3,4}m\b', name_lower):
            return True
        if re.search(r'\bmx\d{3}\b', name_lower):
            return True
        if 'mobile' in name_lower or 'laptop' in name_lower or 'notebook' in name_lower:
            return True

        known_mobile_gpus = [
            '960m', '965m', '970m', '980m',
            '1050m', '1060m', '1070m', '1080m',
            '1650m', '1660m', '2060m', '2070m',
            '2080m', '3050m', '3060m', '3070m',
            '3080m', '4050m', '4060m', '4070m',
        ]
        for mobile_gpu in known_mobile_gpus:
            if mobile_gpu in name_lower:
                return True

        if re.search(r'\s+m\b', name_lower) and not re.search(r'\s+ti\b', name_lower):
            return True

        return False

    def _determine_architecture(self):
        """Determine GPU architecture from device name"""
        self.architecture = self._get_architecture_from_device_name(self.name)
        logging.debug("Device architecture determined: %s -> %s" % (self.name, self.architecture))

        # ARCHITECTURE VS 580: If architecture is modern but JSON says legacy (<580), prioritize architecture
        if self.architecture in OPEN_CAPABLE_ARCHS and self.original_legacy_branch:
            legacy_major = _safe_branch_int(self.original_legacy_branch)
            if legacy_major >= 0 and legacy_major < min_supported_legacy_branch:
                logging.warning(
                    "Architecture override: %s (%s) marked as legacy branch %s, but architecture %s suggests modern card. Ignoring legacy flag.",
                    self.name, self.id, self.original_legacy_branch, self.architecture
                )
                self.original_legacy_branch = None
                self.legacy_branch = None

    def _get_architecture_from_device_name(self, device_name):
        """Extract architecture from GPU device name using patterns from ARCHITECTURE_REGISTRY"""
        if not device_name:
            return "unknown"

        name_upper = device_name.upper()

        for arch, info in ARCHITECTURE_REGISTRY.items():
            for pattern in info["patterns"]:
                if re.search(pattern, name_upper, re.IGNORECASE):
                    return arch

        return "unknown"

    def _check_driver_compatibility(self, branch_major, legacy_override=False):
        if self.architecture == "unknown":
            return True, "Unknown architecture, assuming compatibility"

        try:
            requested = _safe_branch_int(branch_major)
            if requested < 0:
                return False, f"Invalid branch number: {branch_major}"
            min_driver = ARCHITECTURE_MIN_DRIVER.get(self.architecture, "390")
            min_required = _safe_branch_int(min_driver)

            if requested < min_required:
                min_supported, max_supported = self._get_supported_range(legacy_override)
                return False, f"{self.architecture} requires drivers from {min_supported}.xx to {max_supported}.xx (requested: {requested}.xx)"

            min_supported, max_supported = self._get_supported_range(legacy_override)
            max_allowed = _safe_branch_int(max_supported, default=999)

            if requested > max_allowed:
                return False, f"{self.architecture} requires drivers from {min_supported}.xx to {max_supported}.xx (requested: {requested}.xx)"

            return True, f"{self.architecture} compatible with {branch_major}.xx (supported range: {min_supported}.xx - {max_supported}.xx)"

        except ValueError:
            return False, f"Invalid branch number: {branch_major}"

    def _get_supported_range(self, legacy_override=False):
        min_driver = ARCHITECTURE_MIN_DRIVER.get(self.architecture, "390")

        if self.original_legacy_branch:
            max_driver_int = self.legacy_int
            if max_driver_int >= 0:
                return min_driver, str(max_driver_int)
            return min_driver, "470"
        elif legacy_override:
            return min_driver, "470"
        else:
            return min_driver, "999"

    def _get_safe_fallback_branch(self, legacy_override=False):
        min_driver, max_driver = self._get_supported_range(legacy_override)

        if self.original_legacy_branch:
            legacy_major = self.legacy_int
            min_required = _safe_branch_int(ARCHITECTURE_MIN_DRIVER.get(self.architecture, "390"))
            if legacy_major >= 0 and legacy_major >= min_required:
                return str(legacy_major)

        return min_driver

    def _parse_features(self, features):
        flags = []
        for feat in features:
            feat = feat.lower()
            logging.debug("Device: has following feature: %s" % (feat))
            if feat in support_flags:
                flags.append(feat)

        logging.debug("Device: has following flags: %s" % (flags))

        # 1. Non-legacy cards
        if not self.original_legacy_branch and DISTRO_NON_LEGACY_DEFAULT_BRANCH:
            compatible, message = self._check_driver_compatibility(
                DISTRO_NON_LEGACY_DEFAULT_BRANCH,
                legacy_override=False
            )
            if compatible:
                self.legacy_branch = DISTRO_NON_LEGACY_DEFAULT_BRANCH + ".00"
                self.driver_hint = proprietary_required
                logging.info(
                    "Non-legacy default: %s set to branch %s - %s"
                    % (self.name, self.legacy_branch, message)
                )
                return
            else:
                min_driver, max_driver = self._get_supported_range(legacy_override=False)
                logging.error(
                    "Non-legacy default FAILED for %s (%s): %s",
                    self.name, self.architecture, message
                )
                if AUTO_FALLBACK:
                    safe_branch = self._get_safe_fallback_branch(legacy_override=False)
                    self.legacy_branch = safe_branch + ".00"
                    self.driver_hint = proprietary_required
                    logging.warning(
                        "Auto-fallback: %s using safe branch %s (requested: %s)",
                        self.name, safe_branch, DISTRO_NON_LEGACY_DEFAULT_BRANCH
                    )
                return

        # 2. 580+ legacy cards
        if self.original_legacy_branch and DISTRO_580_LEGACY_OVERRIDE_BRANCH:
            legacy_major_int = self.legacy_int
            if legacy_major_int >= 0:
                legacy_major = str(legacy_major_int)
                if legacy_major_int >= 580:
                    compatible, message = self._check_driver_compatibility(
                        DISTRO_580_LEGACY_OVERRIDE_BRANCH,
                        legacy_override=True
                    )
                    if compatible:
                        self.legacy_branch = DISTRO_580_LEGACY_OVERRIDE_BRANCH + ".00"
                        self.driver_hint = proprietary_required
                        logging.info(
                            "580+ legacy override: %s changed from %s to %s - %s"
                            % (self.name, legacy_major, DISTRO_580_LEGACY_OVERRIDE_BRANCH, message)
                        )
                        return
                    else:
                        min_driver, max_driver = self._get_supported_range(legacy_override=True)
                        logging.error(
                            "580+ legacy override FAILED for %s (%s): %s",
                            self.name, self.architecture, message
                        )
                        if AUTO_FALLBACK:
                            safe_branch = self._get_safe_fallback_branch(legacy_override=True)

                            original_compatible, original_message = self._check_driver_compatibility(
                                legacy_major,
                                legacy_override=False
                            )

                            if original_compatible:
                                safe_branch = legacy_major
                                logging.warning(
                                    "580+ auto-fallback: %s using original JSON branch %s (%s)",
                                    self.name, safe_branch, original_message
                                )
                            else:
                                logging.warning(
                                    "580+ auto-fallback: %s using safe branch %s (JSON branch %s invalid - %s)",
                                    self.name, safe_branch, legacy_major, original_message
                                )

                            self.legacy_branch = safe_branch + ".00"
                            self.driver_hint = proprietary_required
                        return

        # 3. Legacy branch openkernel restriction
        if self.original_legacy_branch and ENABLE_LEGACY_OPENKERNEL_RESTRICTION:
            legacy_major_int = self.legacy_int
            if legacy_major_int >= 0 and legacy_major_int <= 580:
                self.driver_hint = proprietary_required
                logging.debug(
                    "Legacy branch restriction: %s with legacy branch %s forced to proprietary",
                    self.name, self.original_legacy_branch
                )
                return

        # 4. Architecture-based check
        if ENABLE_ARCHITECTURE_CHECK:
            if self.architecture in OPEN_CAPABLE_ARCHS:
                if open_supported in flags:
                    self.driver_hint = default
                else:
                    self.driver_hint = proprietary_required
            else:
                self.driver_hint = proprietary_required
            return

        # 5. Normal logic (JSON-based feature flags)
        if not flags or open_supported not in flags:
            self.driver_hint = proprietary_required
        elif proprietary_supported in flags:
            self.driver_hint = proprietary_supported
        else:
            self.driver_hint = default
