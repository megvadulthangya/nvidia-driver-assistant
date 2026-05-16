"""Driver recommendation logic."""

import os
import re
import sys
import logging
import platform

from .config import (
    OPEN_UNSUPPORTED_ARCHS,
    min_supported_legacy_branch,
    proprietary_required,
    default,
    open_supported,
    proprietary_supported,
)
from .device import _safe_branch_int
from .database import get_nvidia_devices
from .output import print_pretty_gpu_summary


def get_driver_from_json_hints(devices):
    """Use the flags in supported-gpus.json to recommend a driver (primary method)"""
    hints = [dev.driver_hint for dev in devices.values()]

    for dev in devices.values():
        logging.debug(
            "Device analysis: %s (ID: %s) - Arch: %s - Type: %s - Subsystem: %s:%s - JSON hint: %s - Final hint: %s",
            dev.name, dev.id, dev.architecture,
            "Mobile" if dev.is_laptop_gpu else "Desktop",
            dev.subvendorid or "N/A", dev.subdevid or "N/A",
            "open" if open_supported in dev.features else "proprietary",
            dev.driver_hint
        )

    proprietary_forced_devices = [
        dev.name for dev in devices.values()
        if dev.architecture in OPEN_UNSUPPORTED_ARCHS and
        dev.driver_hint == proprietary_required
    ]
    if proprietary_forced_devices:
        logging.debug(
            "JSON corrections applied for architectures that don't support open kernel: %s",
            ", ".join(proprietary_forced_devices)
        )

    all_support_open = all(hint in (default, proprietary_supported) for hint in hints)
    all_require_closed = all(hint == proprietary_required for hint in hints)
    any_default = any(hint == default for hint in hints)
    any_require_closed = any(hint == proprietary_required for hint in hints)

    if all_support_open:
        return "open"
    elif all_require_closed:
        return "closed"
    elif any_default:
        return "open"
    elif any_require_closed:
        return "closed"
    else:
        logging.error("unimplemented - hints:\n%s" % (" ".join(hints)))
        return None


def check_legacy_devices(devices):
    """Check for legacy devices and return legacy branch info (NVIDIA 0.51 logic).

    Returns a tuple: (legacy_branch, unsupported_devices)
    - legacy_branch: The legacy branch to use (e.g., "580"), or None if no legacy devices
    - unsupported_devices: List of devices with unsupported legacy branches (< min_supported_legacy_branch)
    """
    legacy_branch = None
    unsupported_devices = []

    for dev in devices.values():
        # Use original_legacy_branch from JSON, not modified by overrides
        if dev.original_legacy_branch:
            branch_int = dev.legacy_int
            if branch_int < 0:
                unsupported_devices.append(dev)
                logging.debug(
                    "check_legacy_devices(): device %s (%s) has invalid legacy branch format %s"
                    % (dev.id, dev.name, dev.original_legacy_branch)
                )
                continue
            branch_major = str(branch_int)
            if branch_int >= min_supported_legacy_branch:
                if legacy_branch and legacy_branch != branch_major:
                    logging.warning(
                        "Multiple legacy branches detected: %s and %s"
                        % (legacy_branch, branch_major)
                    )
                    legacy_branch = max(legacy_branch, branch_major, key=int)
                else:
                    legacy_branch = branch_major
                logging.debug(
                    "check_legacy_devices(): device %s (%s) requires supported legacy branch %s"
                    % (dev.id, dev.name, branch_major)
                )
            else:
                unsupported_devices.append(dev)
                logging.debug(
                    "check_legacy_devices(): device %s (%s) requires unsupported legacy branch %s"
                    % (dev.id, dev.name, branch_major)
                )

    return legacy_branch, unsupported_devices


def recommend_driver(sys_path=None, supported_gpus=None,
                     simulate_gpu=None, simulate_multi=None, suppress_warnings=False):
    """Recommend a driver using the available logic.

    Returns a 4-tuple: (driver, legacy_branch, unsupported_devices, devices_dict)
    """
    devices = get_nvidia_devices(sys_path, supported_gpus, simulate_gpu, simulate_multi, suppress_warnings)
    if not suppress_warnings:
        print_pretty_gpu_summary(devices)

    if not devices:
        return None, None, [], None

    # Check legacy devices first (NVIDIA 0.51)
    legacy_branch, unsupported_devices = check_legacy_devices(devices)

    logging.debug("recommend_driver(): Do device IDs support the open driver?")

    logging.debug("recommend_driver(): using json logic")
    driver = get_driver_from_json_hints(devices)

    return driver, legacy_branch, unsupported_devices, devices


def merge_unsupported_into_legacy(unsupported_devices, legacy_branch):
    """Merge unsupported devices' legacy branches into the legacy_branch selection"""
    for dev in unsupported_devices:
        if dev.legacy_int >= 0:
            branch_major = str(dev.legacy_int)
            if legacy_branch is None or dev.legacy_int > _safe_branch_int(legacy_branch):
                legacy_branch = branch_major
    return legacy_branch


def ubuntu_get_latest_driver_branch(path="/"):
    """Get the latest driver branch available in Ubuntu's repositories"""
    try:
        import apt_pkg
    except ModuleNotFoundError:
        print(
            "Error: please install the following package and try again:\n  python3-apt",
            file=sys.stderr,
        )
        exit(1)

    apt_pkg.init_config()
    dpkg_status = os.path.abspath(os.path.join(path, "var", "lib", "dpkg", "status"))
    apt_pkg.config.set("Dir::State::status", dpkg_status)
    apt_pkg.init_system()
    cache = apt_pkg.Cache(None)
    candidates = []
    for package in cache.packages:
        branch = re.search(r"nvidia-driver-([0-9]+)-open", package.name)
        if branch:
            candidates.append(branch.group(1))

    if candidates:
        candidates.sort()
        return candidates[-1]
    else:
        return None


def manjaro_get_kernel_package():
    """Get kernel package name for Manjaro (e.g., linux618 from 6.18.xx)"""
    try:
        kernel_release = platform.release().split(".")
        if len(kernel_release) >= 2:
            return f"linux{kernel_release[0]}{kernel_release[1]}"
    except Exception as e:
        logging.debug("Failed to get kernel package name: %s", e)
    return "linux"


def manjaro_get_legacy_branch(devices):
    """Get legacy branch for Manjaro based on detected devices"""
    highest_branch = None
    highest_int = -1
    for dev in devices.values():
        if dev.original_legacy_branch and dev.legacy_int >= 0:
            if dev.legacy_int > highest_int:
                highest_int = dev.legacy_int
                highest_branch = str(dev.legacy_int)
    return highest_branch
