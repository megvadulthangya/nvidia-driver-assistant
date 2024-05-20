"""NVIDIA hardware and driver package detection for driver-assistant."""

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
import subprocess
import re
import json
import argparse
import sys


default_supported_gpus = "/usr/share/driver-assistant/supported-gpus/supported-gpus.json"

supported_distros = [
    "amzn",
    "debian",
    "ubuntu",
    "fedora" "kylin",
    "mariner",
    "rhel",
    "rocky",
    "opensuse-leap",
    "sles",
]

# Quite old up to Fermi (Legacy, up to 470.x)
vdpau_group_a = [chr(x).upper() for x in range(ord("a"), ord("c") + 1)]

# Maxwell, Pascal, Volta - closedRM
vdpau_group_b = [chr(x).upper() for x in range(ord("d"), ord("i") + 1)]

# Turing, Ampere, Ada - closedRM if mixed
vdpau_group_c = [chr(x).upper() for x in range(ord("j"), ord("k") + 1)]

proprietary_required = "proprietary_required"
proprietary_supported = "proprietary_supported"
default = "open_required"
proprietary_prefs = (proprietary_required, proprietary_supported)
driver_hints_available = False


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
        global driver_hints_available
        for feat in features:
            feat = feat.lower()
            if feat.find("vdpaufeatureset") != -1:
                self.vdpau_feat = feat.replace("vdpaufeatureset", "")[0]
            elif feat in proprietary_prefs:
                self.driver_hint = feat
                driver_hints_available = True
        # Legacy drivers <= 470
        if not self.driver_hint:
            if self.legacy_branch and self.legacy_branch.split(".")[0] <= 470:
                self.driver_hint = proprietary_required


def get_distro(path=None):
    """Get the linux distribution from /etc/os-release"""
    release_file = "/etc/os-release" if not path else path
    distro_id = ""
    version_id = ""
    id_pattern = "ID="
    ver_pattern = "VERSION_ID="
    try:
        with open(release_file, "r") as stream:
            for line in stream.readlines():
                if line.startswith(id_pattern):
                    distro_id = line.strip().replace(id_pattern, "")
                elif line.startswith(ver_pattern):
                    version_id = line.strip().replace(ver_pattern, "").replace('"', "")
    except (IOError, FileNotFoundError, PermissionError) as e:
        logging.error(
            "failed to detect Linux distribution: cannot read %s: %s" % (release_file, e)
        )
        return (distro_id, version_id)

    if distro_id == "opensuse":
        logging.debug("get_distro(): detected %s, setting to opensuse-leap" % (distro_id))
        distro_id = "opensuse-leap"

    if distro_id in supported_distros:
        logging.debug(
            "get_distro(): detected %s %s distribution is supported" % (distro_id, version_id)
        )
    else:
        logging.debug(
            "get_distro(): detected %s %s distribution is not supported" % (distro_id, version_id)
        )
        logging.error(
            "Error: detected %s %s distribution is not supported" % (distro_id, version_id),
        )
        distro_id = ""

    return (distro_id, version_id)


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
                logging.debug("get_system_modaliases(): Cannot read %s/modalias: %s", path, e)
                continue

        if not modalias:
            continue

        # Ignore built-in modules
        driver_path = os.path.join(path, "driver")
        module_path = os.path.join(driver_path, "module")
        if os.path.islink(driver_path) and not os.path.islink(module_path):
            # logging.debug("get_system_modaliases(): ignoring device %s which has no module (built into kernel)", path)
            continue

        modaliases[modalias] = path

    return modaliases


def ubuntu_get_latest_driver_branch(path="/"):
    "Get the latest driver branch in Ubuntu"
    import apt_pkg

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
    json_path = default_supported_gpus if not supported_gpus else supported_gpus

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
                for did in candidates:
                    if gpu["devid"] == did:
                        device = Device(did, gpu["name"], gpu["features"], gpu.get("legacybranch"))
                        devices[did] = device
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
            if dev.legacy_branch and dev.legacy_branch.split(".")[0] <= 470:
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


def recommend_driver(sys_path=None, supported_gpus=None):
    """Recommend a driver using the available logic"""
    devices = get_nvidia_devices(sys_path, supported_gpus)
    if not devices:
        return None

    logging.debug("recommend_driver(): Do device IDs support the open driver?")

    if driver_hints_available:
        logging.debug("recommend_driver(): using json logic")
        return get_driver_from_json_hints(devices)
    else:
        logging.debug("recommend_driver(): using VDPAU logic")
        return get_driver_from_vdpau_feat(devices)
    return None
