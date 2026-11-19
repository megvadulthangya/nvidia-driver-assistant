"""Driver recommendation logic."""

import logging
import platform

from .config import (
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
    """Determine the kernel-module flavour from the resolved device hints."""
    hints = [dev.driver_hint for dev in devices.values()]

    for dev in devices.values():
        logging.debug(
            "Device analysis: %s (ID: %s) - NVIDIA branch: %s - "
            "Legacy branch: %s - 580 Current: %s - Latest 6xx Current: %s - "
            "JSON features: %s - Final hint: %s",
            dev.name,
            dev.id,
            dev.nvidia_supported_branch,
            dev.original_legacy_branch,
            dev.supports_580,
            dev.supports_latest_6xx,
            dev.features,
            dev.driver_hint,
        )

    all_support_open = all(
        hint in (default, proprietary_supported)
        for hint in hints
    )
    all_require_closed = all(
        hint == proprietary_required
        for hint in hints
    )
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

    logging.error("Unimplemented driver hints: %s", " ".join(hints))
    return None


def check_legacy_devices(devices):
    """Return the highest supported legacy branch and unsupported legacy GPUs."""
    legacy_branch = None
    unsupported_devices = []

    for dev in devices.values():
        if dev.original_legacy_branch:
            branch_int = dev.legacy_int

            if branch_int < 0:
                unsupported_devices.append(dev)
                logging.debug(
                    "check_legacy_devices(): device %s (%s) has invalid "
                    "legacy branch format %s",
                    dev.id,
                    dev.name,
                    dev.original_legacy_branch,
                )
                continue

            branch_major = str(branch_int)

            if branch_int >= min_supported_legacy_branch:
                if legacy_branch and legacy_branch != branch_major:
                    logging.warning(
                        "Multiple legacy branches detected: %s and %s",
                        legacy_branch,
                        branch_major,
                    )
                    legacy_branch = max(
                        legacy_branch,
                        branch_major,
                        key=int,
                    )
                else:
                    legacy_branch = branch_major

                logging.debug(
                    "check_legacy_devices(): device %s (%s) requires "
                    "supported legacy branch %s",
                    dev.id,
                    dev.name,
                    branch_major,
                )
            else:
                unsupported_devices.append(dev)
                logging.debug(
                    "check_legacy_devices(): device %s (%s) requires "
                    "unsupported legacy branch %s",
                    dev.id,
                    dev.name,
                    branch_major,
                )

    return legacy_branch, unsupported_devices


def _resolve_580_and_latest_6xx_mix(devices, legacy_branch, unsupported_devices):
    """Resolve a mixed system containing a 580 legacy GPU and a latest 6xx GPU.

    A common 580 driver is selected only when every detected GPU appears in
    supportedchips580.html's Current table. Otherwise the 580 legacy GPUs
    are returned as incompatible devices so the caller can prioritise the
    latest driver required by the modern GPU.
    """
    legacy_580_devices = [
        dev
        for dev in devices.values()
        if dev.original_legacy_branch and dev.legacy_int == 580
    ]

    latest_6xx_devices = [
        dev
        for dev in devices.values()
        if dev.supports_latest_6xx
    ]

    if not legacy_580_devices or not latest_6xx_devices:
        return None, legacy_branch, unsupported_devices

    # This is specifically a 580 common-driver decision. Do not infer
    # compatibility for another legacy branch from the 580 document.
    if legacy_branch != "580":
        return None, legacy_branch, unsupported_devices

    all_devices_support_580 = all(
        dev.supports_580
        for dev in devices.values()
    )

    if all_devices_support_580:
        logging.info(
            "Mixed GPU compatibility: every detected GPU is listed in "
            "the 580 Current table. Selecting branch 580 with the "
            "proprietary kernel module."
        )
        return "closed", "580", unsupported_devices

    # There is no common 580 driver for the complete system.
    # The latest 6xx driver is selected for the modern GPU(s), while the
    # 580 legacy GPU(s) are explicitly passed to the existing incompatibility
    # handling in cli.py.
    for dev in legacy_580_devices:
        if dev not in unsupported_devices:
            unsupported_devices.append(dev)

    logging.warning(
        "Mixed GPU incompatibility: at least one detected GPU is absent "
        "from supportedchips580.html Current. The 580 legacy GPU(s) cannot "
        "share a driver with the latest 6xx GPU(s). Prioritising latest 6xx."
    )

    return "open", None, unsupported_devices


def recommend_driver(
    sys_path=None,
    supported_gpus=None,
    simulate_gpu=None,
    simulate_multi=None,
    suppress_warnings=False,
):
    """Recommend a driver.

    Returns a 4-tuple:
        (module_flavour, legacy_branch, unsupported_devices, devices_dict)
    """
    devices = get_nvidia_devices(
        sys_path,
        supported_gpus,
        simulate_gpu,
        simulate_multi,
        suppress_warnings,
    )

    if not suppress_warnings:
        print_pretty_gpu_summary(devices)

    if not devices:
        return None, None, [], None

    legacy_branch, unsupported_devices = check_legacy_devices(devices)
    driver = get_driver_from_json_hints(devices)

    if not driver:
        return None, legacy_branch, unsupported_devices, devices

    mixed_driver, legacy_branch, unsupported_devices = (
        _resolve_580_and_latest_6xx_mix(
            devices,
            legacy_branch,
            unsupported_devices,
        )
    )

    if mixed_driver:
        driver = mixed_driver

    return driver, legacy_branch, unsupported_devices, devices


def merge_unsupported_into_legacy(unsupported_devices, legacy_branch):
    """Merge unsupported devices' legacy branches into the selected branch."""
    for dev in unsupported_devices:
        if dev.legacy_int >= 0:
            branch_major = str(dev.legacy_int)
            if (
                legacy_branch is None
                or dev.legacy_int > _safe_branch_int(legacy_branch)
            ):
                legacy_branch = branch_major

    return legacy_branch


def manjaro_get_kernel_package():
    """Get the Manjaro kernel package name (for example, linux618)."""
    try:
        kernel_release = platform.release().split(".")
        if len(kernel_release) >= 2:
            return "linux%s%s" % (kernel_release[0], kernel_release[1])
    except Exception as exc:
        logging.debug("Failed to get kernel package name: %s", exc)

    return "linux"


def manjaro_get_legacy_branch(devices):
    """Get the highest legacy branch detected on a Manjaro system."""
    highest_branch = None
    highest_int = -1

    for dev in devices.values():
        if dev.original_legacy_branch and dev.legacy_int >= 0:
            if dev.legacy_int > highest_int:
                highest_int = dev.legacy_int
                highest_branch = str(dev.legacy_int)

    return highest_branch
