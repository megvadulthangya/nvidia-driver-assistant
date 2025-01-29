#!/usr/bin/python3

"""Driver package query/installation tool for NVIDIA GPUs on Linux"""

# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
# Author: Alberto Milone <amilone@nvidia.com>

import os
import logging
import re
import json
import argparse
import string
import sys


default_directory = os.path.dirname(os.path.realpath(__file__))
default_json_path = os.path.join(default_directory, "supported-gpus", "supported-gpus.json")
install_json_path = "/usr/share/nvidia-driver-assistant/supported-gpus/supported-gpus.json"

# Quite old up to Fermi (Legacy, up to 470.x)
vdpau_group_a = [chr(x) for x in range(ord("a"), ord("c") + 1)]

# Maxwell, Pascal, Volta - closedRM
vdpau_group_b = [chr(x) for x in range(ord("d"), ord("i") + 1)]

# Turing, Ampere, Ada - closedRM if mixed
vdpau_group_c = [chr(x) for x in range(ord("j"), ord("k") + 1)]

proprietary_required = "proprietary_required"
proprietary_supported = "gsp_proprietary_supported"
default = "open_required"
open_supported = "kernelopen"
support_flags = (open_supported, proprietary_supported)


# Make sure that the PATH environment variable is set
if not os.environ.get("PATH"):
    os.environ["PATH"] = "/sbin:/usr/sbin:/bin:/usr/bin"

supported_distros = [
    "amzn",
    "debian",
    "ubuntu",
    "fedora",
    "kylin",
    "azurelinux",
    "rhel",
    "rocky",
    "ol",
    "opensuse",
    "sles",
]


# If the entry is a dictionary, the key has to be either an int or a float
# and its value has to be a list of instructions.
#
# e.g. 7 : [ ... ] means instructions apply from version_id >= 7
instructions = {
    "amzn-closed": ["sudo dnf -y module install nvidia-driver:latest-dkms"],
    "amzn-open": ["sudo dnf -y module install nvidia-driver:open-dkms"],
    "debian-closed": ["sudo apt-get install -Vy cuda-drivers"],
    "debian-open": ["sudo apt-get install -Vy nvidia-open"],
    "fedora-closed": ["sudo dnf -y install cuda-drivers"],
    "fedora-open": ["sudo dnf -y install nvidia-open"],
    "azurelinux-closed": ["Not supported"],
    "azurelinux-open": ["sudo tdnf -y install nvidia-open"],
    "kylin-closed": ["sudo dnf -y module install nvidia-driver:latest-dkms"],
    "kylin-open": ["sudo dnf -y module install nvidia-driver:open-dkms"],
    "opensuse-closed": ["sudo zypper --verbose install -y cuda-drivers"],
    "opensuse-open": ["sudo zypper install -y nvidia-open"],
    "sles-closed": ["sudo zypper install -y cuda-drivers"],
    "sles-open": ["sudo zypper install -y nvidia-open"],
    "rhel-closed": {
        7: ["sudo dnf -y module install nvidia-driver:latest-dkms"],
        10: ["sudo dnf -y install cuda-drivers"],
    },
    "rhel-open": {
        7: ["sudo dnf -y module install nvidia-driver:open-dkms"],
        10: ["sudo dnf -y install nvidia-open"],
    },
    "ubuntu-closed": ["sudo apt-get install -y cuda-drivers"],
    "ubuntu-open": ["sudo apt-get install -y nvidia-open"],
}

# If the entry is a dictionary, the key has to be either an int or a float
# and its value has to be a list of instructions.
#
# e.g. 7 : [ ... ] means instructions apply from version_id >= 7
branch_instructions = {
    "amzn-closed": ["sudo dnf -y module install nvidia-driver:BRANCH-dkms"],
    "amzn-open": ["sudo dnf -y module install nvidia-driver:BRANCH-open"],
    "debian-closed": ["sudo apt-get install -Vy cuda-drivers-BRANCH"],
    "debian-open": ["sudo apt-get install -Vy nvidia-open-BRANCH"],
    "fedora-closed": ["sudo dnf -y install cuda-drivers-BRANCH"],
    "fedora-open": ["sudo dnf -y install nvidia-open-BRANCH"],
    "azurelinux-closed": ["Not supported"],
    "azurelinux-open": ["sudo tdnf -y install nvidia-open-BRANCH"],
    "kylin-closed": ["sudo dnf -y module install nvidia-driver:BRANCH-dkms"],
    "kylin-open": ["sudo dnf -y module install nvidia-driver:BRANCH-open"],
    "opensuse-closed": ["sudo zypper --verbose install -y cuda-drivers-BRANCH"],
    "opensuse-open": ["sudo zypper install -y nvidia-open-BRANCH"],
    "sles-closed": ["sudo zypper install -y cuda-drivers-BRANCH"],
    "sles-open": ["sudo zypper install -y nvidia-open-BRANCH"],
    "rhel-closed": {
        7: ["sudo dnf -y module install nvidia-driver:BRANCH-dkms"],
        10: ["sudo dnf -y install cuda-drivers-BRANCH"],
    },
    "rhel-open": {
        7: ["sudo dnf -y module install nvidia-driver:BRANCH-open"],
        10: ["sudo dnf -y install nvidia-open-BRANCH"],
    },
    "ubuntu-closed": ["sudo apt-get install -y cuda-drivers-BRANCH"],
    "ubuntu-open": ["sudo apt-get install -y nvidia-open-BRANCH"],
}

### ADD CLEANUP INSTRUCTIONS? https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html#switching-between-driver-module-flavors


class SystemInfo(object):
    """Class to represent the information from the os-release file"""

    def __init__(self, id, version_id, pretty_name):
        super(SystemInfo, self).__init__()
        self.id = id
        self.original_id = id
        self.version_id = version_id
        self.pretty_name = pretty_name
        self.update_info()

    def update_info(self):
        if self.id in ["opensuse-leap", "opensuse-tumbleweed"]:
            self.id = "opensuse"
        elif self.id in ["cm", "mariner"]:
            self.id = "azurelinux"
        elif self.id in ["rocky", "ol"]:
            self.id = "rhel"

        if self.id != self.original_id:
            logging.debug("get_distro(): detected %s, setting to %s" % (self.original_id, self.id))


class Device(object):
    """Class to represent devices and their features"""

    def __init__(self, id, name, features, legacy_branch):
        super(Device, self).__init__()
        self.id = id
        self.name = name
        self.vdpau_feat = ""
        self.legacy_branch = legacy_branch
        self.driver_hint = ""
        self._parse_features(features)

    def _parse_features(self, features):
        flags = []
        for feat in features:
            feat = feat.lower()
            if feat.find("vdpaufeatureset") != -1:
                self.vdpau_feat = feat.replace("vdpaufeatureset", "")[0]
            elif feat in support_flags:
                flags.append(feat)

        if not flags or not open_supported in flags:
            self.driver_hint = proprietary_required
        elif proprietary_supported in flags:
            self.driver_hint = proprietary_supported
        else:
            if open_supported in flags:
                self.driver_hint = default
            else:
                # This should not happen
                # Broken flags in the json file?
                self.driver_hint = ""
                logging.warning(
                    "device %s support level not flagged as %s" % (self.id, open_supported)
                )

        # Legacy drivers <= 470
        if not self.driver_hint:
            if self.legacy_branch and self.legacy_branch.split(".")[0] <= "470":
                self.driver_hint = proprietary_required


def get_distro(path=None):
    """Get the linux distribution from /etc/os-release"""
    release_file = "/etc/os-release" if not path else path
    distro_id = ""
    version_id = ""
    name = ""
    id_pattern = "ID="
    ver_pattern = "VERSION_ID="
    name_pattern_a = "NAME="
    name_pattern_b = "PRETTY_NAME="
    system_info = None
    try:
        with open(release_file, "r") as stream:
            for line in stream.readlines():
                if line.startswith(id_pattern):
                    distro_id = line.strip().replace(id_pattern, "").replace('"', "")
                elif line.startswith(ver_pattern):
                    version_id = line.strip().replace(ver_pattern, "").replace('"', "")
                elif line.startswith(name_pattern_a) or line.startswith(name_pattern_b):
                    name = (
                        line.strip()
                        .replace(name_pattern_b, "")
                        .replace(name_pattern_a, "")
                        .replace('"', "")
                    )
        if distro_id and version_id and name:
            system_info = SystemInfo(distro_id, version_id, name)
        else:
            logging.error(
                "failed to detect Linux distribution: cannot extract valid values from %s"
                % (release_file)
            )
            return system_info
    except (IOError, FileNotFoundError, PermissionError) as e:
        logging.error(
            "failed to detect Linux distribution: cannot read %s: %s" % (release_file, e)
        )
        return system_info

    if system_info.id in supported_distros:
        logging.debug(
            "get_distro(): detected %s%s %s distribution is supported"
            % (
                system_info.original_id,
                " (%s)" % system_info.id if system_info.id != system_info.original_id else "",
                system_info.version_id,
            )
        )
        print(
            "Detected system:\n  %s %s\n"
            % (
                (
                    system_info.pretty_name.replace(system_info.version_id, "").strip()
                    if system_info.pretty_name
                    else system_info.id
                ),
                system_info.version_id,
            )
        )
    else:
        logging.debug(
            "get_distro(): detected %s %s distribution is not supported"
            % (system_info.id, system_info.version_id)
        )
        logging.error(
            "Error: detected %s%s %s distribution is not supported"
            % (
                system_info.original_id,
                " (%s)" % system_info.id if system_info.id != system_info.original_id else "",
                system_info.version_id,
            )
        )

    return system_info


def override_distro(distro_override):
    """Process the --distro argument and return a SystemInfo object"""
    if ":" in distro_override:
        distro_id = distro_override.strip().split(":")[0]
        version_id = distro_override.strip().split(":")[-1]
    else:
        distro_id = distro_override.rstrip(string.digits)
        version_id = distro_override[len(distro_id) :]

    return SystemInfo(distro_id, version_id, "")


def get_system_modaliases(sys_path=None):
    """Get a dictionary with modaliases and paths in the system"""
    modaliases = {}
    devices = "/sys/devices" if not sys_path else "%s/devices" % (sys_path)
    for path, dirs, files in os.walk(devices):
        modalias = None
        # Get the devices that have a modalias file, ignoring
        # the ones which mention them in the uevent file.
        if "modalias" in files:
            try:
                with open(os.path.join(path, "modalias")) as file:
                    modalias = file.read().strip()
            except IOError as e:
                logging.debug("get_system_modaliases(): failed to read %s/modalias: %s", path, e)
                continue

        if not modalias:
            continue

        # Ignore built-in modules
        driver_path = os.path.join(path, "driver")
        module_path = os.path.join(driver_path, "module")

        if os.path.islink(driver_path) and not os.path.islink(module_path):
            continue
        modaliases[modalias] = path

    return modaliases


def ubuntu_get_latest_driver_branch(path="/"):
    "Get the latest driver branch in Ubuntu"
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
    pattern = "nvidia-driver-([0-9]+)-open"
    for package in cache.packages:
        branch = re.search(r"nvidia-driver-([0-9]+)-open", package.name)
        if branch:
            candidates.append(branch.group(1))

    if candidates:
        candidates.sort()
        return candidates[-1]
    else:
        return None


def get_nvidia_devices(sys_path, supported_gpus):
    """Get a dictionary with all the NVIDIA graphics devices

    Returns {str PCI_ID: Device object, etc.}
    """
    # PCI_CLASS_DISPLAY 0x03
    pci_class_display = "03"
    modaliases = get_system_modaliases(sys_path)
    json_path = supported_gpus

    # PCI IDs we should consider
    candidates = []

    # Dictionary with {str PCI_ID: class Device}
    devices = {}
    for alias, syspath in modaliases.items():
        modalias_pattern = re.compile("(.+):v(.+)d(.+)sv(.+)sd(.+)bc(.+)sc(.+)i.*")
        # DEBUG:root:pci:v000010DEd00002783sv000010DEsd000018FEbc03sc00i00
        # DEBUG:root:Processing Vendor: 10DE, Device ID: 0x22BC
        # DEBUG:root:pci:v000010DEd000022BCsv000010DEsd000018FEbc04sc03i00

        details = modalias_pattern.match(alias)
        if details:
            if details.group(1) == "pci":
                vendor = details.group(2)[4:]
                devid = "0x%s" % details.group(3)[4:]
                classid = details.group(6)
                full_class = "0x%s%s" % (details.group(6), details.group(7))

                # logging.debug("Processing Vendor: %s, Device ID: %s" % (vendor, devid))
                if vendor.lower() == "10de" and classid == pci_class_display:
                    logging.debug(
                        "get_nvidia_devices(): Processing Vendor: %s, Device ID: %s, class %s"
                        % (vendor, devid, full_class)
                    )
                    logging.debug(details.group(0))
                    candidates.append(devid)
    try:
        with open(json_path, "r") as stream:
            try:
                gpus = list(json.load(stream)["chips"])
            except Exception as e:
                logging.error("failed to load %s: %s" % json_path)
                return None
            for gpu in gpus:
                for dev_id in candidates:
                    if gpu["devid"] == dev_id:
                        device = Device(
                            dev_id, gpu["name"], gpu["features"], gpu.get("legacybranch")
                        )
                        devices[dev_id] = device
    except (IOError, FileNotFoundError, PermissionError) as e:
        logging.error("failed to read read %s: %s" % (json_path, e))
        return None

    # Unknown GPU IDs - assume they require Open
    unknown_devices = len(devices.keys()) < len(candidates)
    for candidate in candidates:
        if candidate not in devices.keys():
            dev = Device(candidate, "unknown", [], "")
            dev.driver_hint = default
            devices[candidate] = dev
    return devices


def print_pretty_gpu_summary(devices):
    device_lines = []
    for dev in devices.values():
        device_lines.append("  %s - (pci_id %s)" % (dev.name, dev.id))
    it = 0
    if device_lines:
        print("Detected GPUs:")
        print("\n".join(device_lines))
        if it == len(devices) - 1:
            print("")
        it += 1
    else:
        print("No NVIDIA GPUs detected")


def get_driver_from_vdpau_feat(devices):
    """Use the supported VDPAU feature sets to recommend a driver"""
    hints = []
    for dev in devices.values():
        if dev.vdpau_feat:
            if dev.vdpau_feat in vdpau_group_a:
                hint = proprietary_required
                logging.debug(
                    "get_driver_from_vdpau_feat(): skipping device %s (%s) - since vdpau_group_a = %s"
                    % (dev.id, dev.name, dev.vdpau_feat)
                )
                continue
            elif dev.vdpau_feat in vdpau_group_b:
                hint = proprietary_required
                logging.debug(
                    "get_driver_from_vdpau_feat(): proprietary_required by device %s:\n %s belongs to vdpau_group_b = %s"
                    % (dev.id, dev.name, dev.vdpau_feat)
                )
            elif dev.vdpau_feat in vdpau_group_c:
                hint = proprietary_supported
                logging.debug(
                    "get_driver_from_vdpau_feat(): proprietary_supported by device %s:\n %s belongs to since vdpau_group_c = %s"
                    % (dev.id, dev.name, dev.vdpau_feat)
                )
            else:
                # TODO: something newer??
                hint = default
                logging.debug(
                    "get_driver_from_vdpau_feat(): default option for device %s:\n %s belongs to new vdpau_group = %s"
                    % (dev.id, dev.name, dev.vdpau_feat)
                )
        else:
            if dev.legacy_branch and int(dev.legacy_branch.split(".")[0]) <= 470:
                hint = proprietary_required
                logging.debug(
                    "get_driver_from_vdpau_feat(): proprietary_required by device %s:\n %s belongs to legacybranch = %s"
                    % (dev.id, dev.name, dev.legacy_branch)
                )
            else:
                # Unknown device that we added
                logging.debug(
                    "get_driver_from_vdpau_feat(): default option for device %s: %s device"
                    % (dev.id, dev.name)
                )
                hint = default
        logging.debug(
            "get_driver_from_vdpau_feat(): device %s:\n %s - hint %s" % (dev.id, dev.name, hint)
        )
        hints.append(hint)

    if default in hints:
        # Higher priority to Open
        logging.debug("get_driver_from_vdpau_feat(): recommend open")
        return "open"
    else:
        if proprietary_required in hints:
            logging.debug("get_driver_from_vdpau_feat(): recommend closed")
            return "closed"
        else:
            logging.debug("get_driver_from_vdpau_feat(): recommend open")
            return "open"

    return None


def get_driver_from_json_hints(devices):
    """Use the flags in supported-gpus.json to recommend a driver"""
    hints = [dev.driver_hint for dev in devices.values()]
    all_support_open = all(hint in (default, proprietary_supported) for hint in hints)
    all_require_closed = all(hint == proprietary_required for hint in hints)
    any_default = any(hint == default for hint in hints)
    any_require_closed = any(hint == proprietary_required for hint in hints)

    if all_support_open:
        logging.debug("recommend_driver(): all devices support open")
        return "open"
    elif all_require_closed:
        logging.debug("recommend_driver(): all devices require closed")
        return "closed"
    elif any_default:
        # one default / unknown - open
        logging.debug("recommend_driver(): at least one devices requires open")
        return "open"
    elif any_require_closed:
        # one closed - closed
        logging.debug("recommend_driver(): at least one devices requires closed")
        return "closed"
    else:
        logging.error("unimplemented - hints:\n%s" % (" ".join(hints)))
        return None


def recommend_driver(sys_path=None, supported_gpus=None, use_driver_hints=False):
    """Recommend a driver using the available logic"""
    devices = get_nvidia_devices(sys_path, supported_gpus)
    print_pretty_gpu_summary(devices)
    if not devices:
        return None

    logging.debug("recommend_driver(): Do device IDs support the open driver?")

    if use_driver_hints:
        logging.debug("recommend_driver(): using json logic")
        return get_driver_from_json_hints(devices)
    else:
        logging.debug("recommend_driver(): using VDPAU logic")
        return get_driver_from_vdpau_feat(devices)
    return None


####


def get_conditional_instructions(distro_id, version_id, instructions_dict):
    """Instructions may depend on the specific distro release"""
    versions = []
    for cond in instructions_dict.keys():
        from_ver = float(cond)
        if float(version_id) >= from_ver:
            versions.append(from_ver)
    return instructions_dict.get(max(versions))


def process_results(driver, distro_id, version_id, branch_id=None, install=False):
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
        # If this is a dictionary, instructions differ per distro release range
        if candidates.keys():
            candidates = get_conditional_instructions(distro_id, version_id, candidates)
    except AttributeError:
        pass

    if distro_id == "ubuntu" and not branch_id:
        # Check the available branch and pick the latest
        latest_branch = ubuntu_get_latest_driver_branch()
        if latest_branch:
            branch_id = latest_branch
        else:
            print("Error: failed to get the latest driver branch", file=sys.stderr)
            return False

    if branch_id:
        it = 0
        for line in candidates:
            candidates[it] = line.replace("BRANCH", branch_id)
            it += 1

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
                    "\nError: failed to execute the following command:\n  %s" % (line),
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
    # Point users to the EULA
    print(
        "Using the NVIDIA driver implies acceptance of the NVIDIA Software\n"
        'License Agreement, contained in the "LICENSE" file in the\n'
        '"/usr/share/nvidia-driver-assistant/driver_eula" directory\n'
    )
    return process_results(driver, distro_id, version_id, branch_id=branch_id, install=True)


def print_instructions(driver, distro_id, version_id, branch_id=None):
    return process_results(driver, distro_id, version_id, branch_id=branch_id, install=False)


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
    system_info = None

    if print_supported_distros:
        print("The following are the currently accepted distribution aliases:")
        for distro in supported_distros:
            print("  %s" % (distro))
        exit(0)

    if not supported_gpus:
        if os.path.isfile(install_json_path):
            supported_gpus = install_json_path
        elif os.path.isfile(default_json_path):
            supported_gpus = default_json_path

    # Sanity check for the branch argument
    if branch_locked:
        try:
            int_branch = int(branch_locked)
        except ValueError:
            print("Error: %s is not an integer value" % (branch_locked), file=sys.stderr)
            exit(1)
        else:
            if int_branch < 560:
                print("Error: only releases >= 560 are allowed", file=sys.stderr)
                exit(1)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    driver = recommend_driver(
        sys_path=sys_path, supported_gpus=supported_gpus, use_driver_hints=True
    )
    if not driver:
        print("Error: Failed to find a suitable driver", file=sys.stderr)
        exit(1)
    logging.debug("Recommended driver: %s" % driver)

    if module_override:
        driver = module_override.lower()
        if not driver in ("open", "closed"):
            print(
                'Error: invalid module flavor. Accepted values are "open" and "closed".',
                file=sys.stderr,
            )
            exit(1)

    if distro_override:
        system_info = override_distro(distro_override.lower())
        print("Detected system:\n  %s %s\n" % (system_info.id, system_info.version_id))
    else:
        system_info = get_distro(os_release_path)

    if not system_info:
        # print("Error: unsupported Linux distribution", file=sys.stderr)
        exit(1)
    logging.debug("OS detected: %s" % system_info.id)
    if needs_install:
        install_driver(driver, system_info.id, system_info.version_id, branch_locked)
    else:
        exit(
            0
            if print_instructions(driver, system_info.id, system_info.version_id, branch_locked)
            else 1
        )


if __name__ == "__main__":
    main()
