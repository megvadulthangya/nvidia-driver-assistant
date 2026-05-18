"""Main entry point and argument parsing for nvidia-driver-assistant."""

import os
import sys
import json
import logging
import argparse

from .config import (
    supported_distros,
    DISTRO_REGISTRY,
    DISTRO_NON_LEGACY_DEFAULT_BRANCH,
    DISTRO_580_LEGACY_OVERRIDE_BRANCH,
    ENABLE_LEGACY_OPENKERNEL_RESTRICTION,
    ENABLE_ARCHITECTURE_CHECK,
    MANJARO_MIN_OFFICIAL_LEGACY_BRANCH,
    ARCH_MIN_REPO_LEGACY_BRANCH,
    ARCH_AUR_ONLY_BRANCHES,
    default,
    open_supported,
)
from .system import get_distro, override_distro
from .device import _safe_branch_int
from .database import simulated_gpus
from .recommendation import (
    recommend_driver,
    merge_unsupported_into_legacy,
    manjaro_get_legacy_branch,
)
from .output import (
    print_fallback_instructions,
    install_driver,
    print_instructions,
)


# JSON paths
default_directory = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
default_json_path = os.path.join(default_directory, "supported-gpus", "supported-gpus.json")
install_json_path = "/usr/share/nvidia-driver-assistant/supported-gpus/supported-gpus.json"


def _print_unsupported_error(unsupported_devices, distro_info):
    """Print error for unsupported legacy devices with optional Nouveau hint."""
    print(
        "\nError: The following GPU(s) require a legacy driver that is no longer supported:",
        file=sys.stderr,
    )
    for dev in unsupported_devices:
        print(
            "  %s (%s) - requires legacy branch %s" % (dev.name, dev.id, dev.original_legacy_branch),
            file=sys.stderr,
        )
    print(
        "\nThese GPUs are not supported by current NVIDIA drivers. "
        "Please consider upgrading your hardware.",
        file=sys.stderr,
    )

    # Nouveau hint for very old GPUs
    nouveau_below = distro_info.get("nouveau_hint_below") if distro_info else None
    if nouveau_below:
        nouveau_devs = [
            dev for dev in unsupported_devices
            if dev.legacy_int >= 0 and dev.legacy_int < nouveau_below
        ]
        if nouveau_devs:
            print(
                "\nTip: The open-source Nouveau driver may provide basic display support "
                "for these older devices. Nouveau is usually included with your "
                "distribution's default installation.",
                file=sys.stderr,
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install the recommended driver",
        default=False,
    )
    parser.add_argument(
        "--branch",
        nargs="?",
        type=str,
        help="Specify a NVIDIA Driver branch",
    )
    parser.add_argument(
        "--list-supported-distros",
        action="store_true",
        help="Print out the list of the supported Linux distributions",
        default=False,
    )
    parser.add_argument(
        "--supported-gpus",
        nargs="?",
        type=str,
        help="Use a different supported-gpus.json file",
    )
    parser.add_argument(
        "--sys-path",
        nargs="?",
        type=str,
        help="Use a different /sys path. Useful for testing",
    )
    parser.add_argument(
        "--os-release-path",
        nargs="?",
        type=str,
        help="Use a different path for the os-release file. Useful for testing",
    )
    parser.add_argument(
        "--distro",
        nargs="?",
        type=str,
        help='Specify a Linux distro using the "DISTRO:VERSION" or "DISTRO" pattern. Useful for testing',
    )
    parser.add_argument(
        "--module-flavor",
        nargs="?",
        type=str,
        help='Specify a kernel module flavor; "open" and "closed" are accepted values. Useful for testing',
    )
    multi_gpu_scenarios = [k for k, v in simulated_gpus.items() if isinstance(v, list)]
    single_gpu_choices = [k for k, v in simulated_gpus.items() if isinstance(v, dict)]
    sim_group = parser.add_mutually_exclusive_group()
    sim_group.add_argument(
        "--simulate-gpu",
        choices=single_gpu_choices,
        nargs="?",
        type=str,
        help="Specify a simulated gpu; Useful for testing",
    )
    sim_group.add_argument(
        "--simulate-mixed",
        action="store_true",
        default=False,
        help="Simulate a mixed-GPU system (GTX 750 Ti + RTX 5070); Useful for testing",
    )
    sim_group.add_argument(
        "--simulate-badmix",
        action="store_true",
        default=False,
        help="Simulate a mixed-GPU system (740A + RTX 5070); Useful for testing",
    )
    parser.add_argument(
        "--mhwd",
        action="store_true",
        help='Signal mhwd to use "open" or "closed" driver',
        default=False,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output decision as JSON (for installer / scripting)",
        default=False,
    )
    parser.add_argument(
        "--verbose", action="store_true", help="[OPTIONAL] Verbose output", default=False
    )
    args = parser.parse_args()

    needs_install = args.install
    branch_locked = args.branch
    supported_gpus = args.supported_gpus
    sys_path = args.sys_path
    os_release_path = args.os_release_path
    distro_override = args.distro
    module_override = args.module_flavor
    print_supported_distros = args.list_supported_distros
    mhwd = args.mhwd
    simulate_gpu = args.simulate_gpu
    simulate_mixed = args.simulate_mixed
    simulate_badmix = args.simulate_badmix
    json_output = args.json
    system_info = None

    if print_supported_distros:
        print("The following are the currently accepted distribution aliases:")
        for distro in supported_distros:
            print("  %s" % distro)
        exit(0)

    if not supported_gpus:
        if os.path.isfile(install_json_path):
            supported_gpus = install_json_path
        elif os.path.isfile(default_json_path):
            supported_gpus = default_json_path

    if branch_locked:
        try:
            int_branch = int(branch_locked)
        except ValueError:
            print("Error: %s is not an integer value" % branch_locked, file=sys.stderr)
            exit(1)
        else:
            if int_branch < 560:
                print("Error: only releases >= 560 are allowed", file=sys.stderr)
                exit(1)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    simulate_multi = None
    if simulate_mixed:
        simulate_multi = "mixed"
    elif simulate_badmix:
        simulate_multi = "badmix"

    suppress_warnings = mhwd or json_output
    driver, legacy_branch, unsupported_devices, devices = recommend_driver(
        sys_path=sys_path,
        supported_gpus=supported_gpus,
        simulate_gpu=simulate_gpu,
        simulate_multi=simulate_multi,
        suppress_warnings=suppress_warnings,
    )

    if not driver:
        print("Error: Failed to find a suitable driver", file=sys.stderr)
        exit(1)

    # Determine distribution (needed for Manjaro/Arch legacy override)
    if distro_override:
        system_info = override_distro(distro_override.lower())
        print("Detected system:\n  %s %s\n" % (system_info.id, system_info.version_id))
    else:
        system_info = get_distro(os_release_path)

    if not system_info:
        exit(1)

    skip_legacy_fallback = False

    # --- Mixed-GPU priority: open-capable device + legacy < 580 ---
    if unsupported_devices and devices:
        has_open_capable = any(
            dev.driver_hint in (default, open_supported)
            for dev in devices.values()
        )
        if has_open_capable:
            legacy_names = [
                f"{dev.name} (PCI ID: {dev.id}, legacy branch: {dev.original_legacy_branch})"
                for dev in unsupported_devices
            ]
            if not suppress_warnings:
                print(
                    "\nNote: The following legacy GPU(s) are incompatible with the "
                    "driver required by your modern GPU(s):"
                )
                for name in legacy_names:
                    print(f"  {name}")
                print(
                    "\nThe legacy driver branch is too old to support your modern GPU. "
                    "Recommending the latest driver for the modern card(s).\n"
                    "The legacy GPU(s) listed above will NOT function with this driver.\n"
                )
            logging.debug(
                "Mixed-GPU priority: discarding unsupported legacy devices in favour of "
                "open-capable modern device(s). Legacy devices: %s",
                ", ".join(legacy_names)
            )
            unsupported_devices = []
            legacy_branch = None
            driver = "open"
            skip_legacy_fallback = True

    # --- Distro-specific legacy handling (registry-driven) ---
    distro_info = DISTRO_REGISTRY.get(system_info.id)
    if distro_info and unsupported_devices:
        min_branch = distro_info.get("min_official_branch")
        fallback = distro_info.get("fallback_method", "error")

        if min_branch is not None:
            # Separate: repo-available vs truly-unsupported
            repo_devices = [
                dev for dev in unsupported_devices
                if dev.legacy_int >= 0 and dev.legacy_int >= min_branch
            ]
            fallback_devices = [
                dev for dev in unsupported_devices
                if dev.legacy_int < 0 or dev.legacy_int < min_branch
            ]
        else:
            repo_devices = []
            fallback_devices = list(unsupported_devices)

        # Handle repo-available devices first
        if repo_devices and not fallback_devices:
            repo_note = distro_info.get("repo_available_note")
            if repo_note:
                print("\n%s" % repo_note, file=sys.stderr)
            legacy_branch = merge_unsupported_into_legacy(repo_devices, legacy_branch)
            unsupported_devices = []
        elif repo_devices and fallback_devices:
            # Some are repo-available, some need fallback
            repo_note = distro_info.get("repo_available_note")
            if repo_note:
                print("\n%s" % repo_note, file=sys.stderr)
            legacy_branch = merge_unsupported_into_legacy(repo_devices, legacy_branch)
            unsupported_devices = fallback_devices
        else:
            unsupported_devices = fallback_devices

        # Handle fallback devices
        if unsupported_devices and fallback == "aur":
            device_header = distro_info.get("fallback_device_header", "Legacy GPU(s) detected:")
            print("\n%s" % device_header.format(min_branch=min_branch))
            for dev in unsupported_devices:
                print(f"  {dev.name} (PCI ID: {dev.id}) requires the legacy driver branch {dev.original_legacy_branch}")
            branches = sorted({dev.legacy_int for dev in unsupported_devices if dev.legacy_int >= 0})
            print_fallback_instructions(system_info.id, branches)
            exit(0)
        elif unsupported_devices and fallback == "error":
            _print_unsupported_error(unsupported_devices, distro_info)
            exit(1)

    # Handle unsupported legacy devices when no distro_info exists
    if unsupported_devices:
        _print_unsupported_error(unsupported_devices, distro_info)
        exit(1)

    # Use detected legacy branch if no branch was specified (NVIDIA 0.51)
    if legacy_branch and not branch_locked:
        print("Legacy GPU detected. Using driver branch %s.\n" % legacy_branch)
        branch_locked = legacy_branch

    # --- Legacy branch + open driver catch-all (final safety net) ---
    if driver == "open" and branch_locked:
        effective_branch = _safe_branch_int(str(branch_locked))
        if effective_branch >= 0 and effective_branch <= 580:
            logging.debug(
                "Legacy branch %s does not support open kernel modules; "
                "switching recommendation from open to closed.", branch_locked
            )
            driver = "closed"

    # Fallback-only branches (supported but not in official repos, e.g. AUR)
    if not distro_info:
        distro_info = DISTRO_REGISTRY.get(system_info.id)
    if distro_info and branch_locked:
        _bl = _safe_branch_int(str(branch_locked))
        fb_branches = distro_info.get("fallback_branches", ())
        if _bl >= 0 and _bl in fb_branches:
            fallback = distro_info.get("fallback_method", "error")
            if fallback == "aur":
                print("\n%s official repositories no longer include branch %s.xx." % (
                    system_info.id.capitalize(), _bl
                ))
                pkg_tpl = distro_info.get("fallback_package_template", "nvidia-{branch}xx-dkms")
                print("You can find it in the AUR (Arch User Repository) as:")
                print("  - %s" % pkg_tpl.format(branch=_bl))
                print("  - nvidia-%sxx-utils" % _bl)
                print("\nPlease use your preferred AUR helper (e.g., yay, paru) to install them.")
                print("Note for Pamac users: Enable AUR support in 'Preferences' > 'Third Party' > 'Enable AUR support'.")
            else:
                print("\n%s official repositories no longer include branch %s.xx." % (
                    system_info.id.capitalize(), _bl
                ))
                print("\nYou may need to install this driver branch manually.")
            exit(0)

    logging.debug("Recommended driver: %s" % driver)

    if mhwd:
        print(driver)
        exit(0)

    if json_output:
        device_list = []
        for dev in devices.values() if devices else []:
            min_driver, max_driver = dev._get_supported_range(legacy_override=False)
            device_info = {
                "pci_id": dev.id,
                "name": dev.name,
                "architecture": dev.architecture,
                "type": "mobile" if dev.is_laptop_gpu else "desktop",
                "is_laptop": dev.is_laptop_gpu,
                "is_legacy": bool(dev.original_legacy_branch),
                "subsystem_vendor": dev.subvendorid,
                "subsystem_device": dev.subdevid,
                "supported_min_driver": min_driver,
                "supported_max_driver": max_driver,
                "legacy": dev.original_legacy_branch if dev.original_legacy_branch else None
            }
            device_list.append(device_info)

        result = {
            "driver": "nvidia",
            "module_flavor": driver,
            "branch": branch_locked,
            "distro_non_legacy_default": DISTRO_NON_LEGACY_DEFAULT_BRANCH,
            "distro_580_legacy_override": DISTRO_580_LEGACY_OVERRIDE_BRANCH,
            "legacy_openkernel_restriction": ENABLE_LEGACY_OPENKERNEL_RESTRICTION,
            "architecture_check_enabled": ENABLE_ARCHITECTURE_CHECK,
            "manjaro_min_official_legacy_branch": MANJARO_MIN_OFFICIAL_LEGACY_BRANCH,
            "arch_min_repo_legacy_branch": ARCH_MIN_REPO_LEGACY_BRANCH,
            "arch_aur_only_branches": list(ARCH_AUR_ONLY_BRANCHES),
            "devices": device_list
        }
        print(json.dumps(result, indent=2))
        exit(0)

    if module_override:
        driver = module_override.lower()
        if driver not in ("open", "closed"):
            print(
                'Error: invalid module flavor. Accepted values are "open" and "closed".',
                file=sys.stderr,
            )
            exit(1)

    logging.debug("OS detected: %s" % system_info.id)

    # For Manjaro, if no branch locked yet, try to get from devices (fallback)
    if not branch_locked and not skip_legacy_fallback and system_info.id == "manjaro" and devices:
        manjaro_branch = manjaro_get_legacy_branch(devices)
        if manjaro_branch:
            branch_locked = manjaro_branch

    if needs_install:
        success = install_driver(driver, system_info.id, system_info.version_id, branch_locked)
        if not success:
            sys.exit(1)
    else:
        exit(
            0
            if print_instructions(driver, system_info.id, system_info.version_id, branch_locked)
            else 1
        )
