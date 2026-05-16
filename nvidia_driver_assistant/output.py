"""Output formatting, instruction display, and driver installation."""

import os
import sys
import string
import logging

from .config import (
    DISTRO_REGISTRY,
    default,
    open_supported,
    instructions,
    branch_instructions,
)


def print_pretty_gpu_summary(devices):
    """Print a formatted summary of detected GPUs"""
    if not devices:
        print("No NVIDIA GPUs detected")
        return

    print("Detected GPUs:")
    print("-" * 70)
    for dev_id, dev in devices.items():
        arch_info = f" [{dev.architecture}]" if dev.architecture != "unknown" else ""
        type_info = " (Mobile)" if dev.is_laptop_gpu else " (Desktop)"
        legacy_info = f" (legacy: {dev.legacy_branch})" if dev.legacy_branch else ""
        subsystem_info = ""
        if dev.subvendorid and dev.subdevid:
            subsystem_info = f" [Subsystem: {dev.subvendorid}:{dev.subdevid}]"
        print(f"  {dev.name}{arch_info}{type_info}{subsystem_info}")
        print(f"    PCI ID: {dev_id}{legacy_info}")
        if dev.driver_hint:
            driver_type = "open" if dev.driver_hint in [default, open_supported] else "proprietary"
            print(f"    → Recommended driver type: {driver_type}")
        print()
    print("-" * 70)
    print()


def show_multiple_match_warning(device_id, selected_name, all_names):
    """Show a warning when multiple GPU models match the same device ID"""
    print("\n" + "=" * 70, file=sys.stderr)
    print("NOTICE: Multiple GPU models found in database for device ID:", file=sys.stderr)
    print(f"  Device ID: {device_id}", file=sys.stderr)
    print(f"  Selected model: {selected_name}", file=sys.stderr)
    print("  Other possible models in database:", file=sys.stderr)
    for name in all_names:
        if name != selected_name:
            print(f"    - {name}", file=sys.stderr)
    print("\n  Note: The driver selection is the same for all these models,", file=sys.stderr)
    print("  so this does not affect functionality or compatibility.", file=sys.stderr)
    print("  We automatically selected the most appropriate model based on", file=sys.stderr)
    print("  your system configuration and available information.", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)


def print_aur_instructions(distro_id, branches):
    """Print AUR installation instructions using DISTRO_REGISTRY data"""
    distro = DISTRO_REGISTRY.get(distro_id, {})
    msg = distro.get("aur_message_template")
    if msg:
        print("\n%s" % msg)
    print("You can find them in the AUR (Arch User Repository) as:")
    for branch in branches:
        print("  - nvidia-%sxx-dkms" % branch)
        print("  - nvidia-%sxx-utils" % branch)
    print("\nPlease use your preferred AUR helper (e.g., yay, paru) to install them.")
    print("Note for Pamac users: Enable AUR support in 'Preferences' > 'Third Party' > 'Enable AUR support'.")


def get_conditional_instructions(distro_id, version_id, instructions_dict):
    """Instructions may depend on the specific distro release (robust version parsing)"""
    numeric_version = version_id.lstrip(string.ascii_letters).lstrip()
    if not numeric_version:
        return instructions_dict.get(min(instructions_dict.keys()))

    versions = []
    for cond in instructions_dict.keys():
        from_ver = float(cond)
        try:
            if float(numeric_version) >= from_ver:
                versions.append(from_ver)
        except ValueError:
            continue

    if versions:
        return instructions_dict.get(max(versions))
    else:
        return instructions_dict.get(min(instructions_dict.keys()))


def process_results(driver, distro_id, version_id, branch_id=None, install=False):
    """Process and display/execute installation instructions"""
    if branch_id:
        candidates = branch_instructions.get("%s-%s" % (distro_id, driver))
    else:
        candidates = instructions.get("%s-%s" % (distro_id, driver))

    if not candidates:
        print(
            "Error: could not find the instructions for %s-%s" % (distro_id, driver),
            file=sys.stderr,
        )
        return False

    try:
        if isinstance(candidates, dict):
            candidates = get_conditional_instructions(distro_id, version_id, candidates)
    except AttributeError:
        pass

    if distro_id == "ubuntu" and not branch_id:
        from .recommendation import ubuntu_get_latest_driver_branch
        latest_branch = ubuntu_get_latest_driver_branch()
        if latest_branch:
            branch_id = latest_branch
        else:
            print("Error: failed to get the latest driver branch", file=sys.stderr)
            return False

    distro_info = DISTRO_REGISTRY.get(distro_id)
    if distro_info and distro_info.get("kernel_substitution"):
        from .recommendation import manjaro_get_kernel_package
        kernel_package = manjaro_get_kernel_package()
        if kernel_package:
            candidates = [line.replace("KERNEL", kernel_package) for line in candidates]

    if branch_id:
        suffix = distro_info.get("branch_suffix", "") if distro_info else ""
        effective_branch = str(branch_id) + suffix
        candidates = [line.replace("BRANCH", effective_branch) for line in candidates]

    if install:
        print(
            "Installing the following package%s for the %s kernel module flavour:"
            % ("s" if len(candidates) > 1 else "", "legacy" if driver == "closed" else "open")
        )
        for line in candidates:
            print("  %s\n" % line)
            status = os.system(line)
            if status != 0:
                print(
                    "\nError: failed to execute the following command:\n  %s" % line,
                    file=sys.stderr,
                )
                break
        return status == 0
    else:
        print(
            "Please copy and paste the following command%s to install the %s kernel module flavour:"
            % ("s" if len(candidates) > 1 else "", "legacy" if driver == "closed" else "open")
        )
        for line in candidates:
            print("  %s" % line)
    return True


def install_driver(driver, distro_id, version_id, branch_id=None):
    """Install the driver and show EULA notice"""
    print(
        "Using the NVIDIA driver implies acceptance of the NVIDIA Software\n"
        'License Agreement, contained in the "LICENSE" file in the\n'
        '"/usr/share/nvidia-driver-assistant/driver_eula" directory\n'
    )
    return process_results(driver, distro_id, version_id, branch_id=branch_id, install=True)


def print_instructions(driver, distro_id, version_id, branch_id=None):
    """Print installation instructions without executing them"""
    return process_results(driver, distro_id, version_id, branch_id=branch_id, install=False)
