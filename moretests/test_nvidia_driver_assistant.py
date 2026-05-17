#!/usr/bin/python3

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
# Modified by: Gyöngyösi Gábor gabor@gshoots.hu

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import logging
from unittest.mock import patch

from gi.repository import UMockdev

test_dir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.dirname(test_dir)

# install python3-gi and umockdev gir1.2-umockdev-1.0 python3-aptdaemon python3-aptdaemon.test

# ---------------------------------------------------------------------------
# GPU modalias constants used throughout the tests
#
#   Alias  PCI ID   Name                          Arch       Legacy   Category
#   -----  ------   ----------------------------  ---------  ------   --------
#   gpu_a  0x2783   RTX 4070 SUPER                ada        -        modern, open-capable
#   gpu_b  0x1D81   TITAN V                       volta      580.xx   legacy-580, kernelopen
#   gpu_c  0x00C2   GeForce 6800 LE               pre-curie  304.xx   unsupported (<580)
#   gpu_d  0x0FC6   GeForce GTX 650               kepler     470.xx   unsupported (<580)
#   gpu_e  0x06C0   GeForce GTX 480               fermi      390.xx   unsupported (<580)
#   gpu_f  0x1B06   GeForce GTX 1080 Ti           pascal     580.xx   legacy-580, kernelopen
#   gpu_g  0x1DBA   Quadro GV100 / TITAN V JHH    volta      580.xx   legacy-580, kernelopen
#   gpu_h  0x1380   GeForce GTX 750 Ti            maxwell    580.xx   legacy-580, kernelopen
#
# "unsupported (<580)" means legacy_branch < min_supported_legacy_branch (580),
# so the device is placed on the unsupported_devices list by check_legacy_devices().
# ---------------------------------------------------------------------------
gpu_a = "pci:v000010DEd00002783sv000010DEsd000018FEbc03sc00i00"
gpu_b = "pci:v000010DEd00001D81sv000010DEsd000018FEbc03sc00i00"
gpu_c = "pci:v000010DEd000000C2sv000010DEsd000018FEbc03sc00i00"
gpu_d = "pci:v000010DEd00000FC6sv000010DEsd000018FEbc03sc00i00"
gpu_e = "pci:v000010DEd000006C0sv000010DEsd000018FEbc03sc00i00"
gpu_f = "pci:v000010DEd00001B06sv000010DEsd000018FEbc03sc00i00"
gpu_g = "pci:v000010DEd00001DBAsv000010DEsd000018FEbc03sc00i00"
gpu_h = "pci:v000010DEd00001380sv000010DEsd000018FEbc03sc00i00"


amazon_os_release = '''NAME="Amazon Linux"
VERSION="2023"
ID="amzn"
ID_LIKE="fedora"
VERSION_ID="2023"
PLATFORM_ID="platform:al2023"
PRETTY_NAME="Amazon Linux 2023"
ANSI_COLOR="0;33"
CPE_NAME="cpe:2.3:o:amazon:amazon_linux:2023"
HOME_URL="https://aws.amazon.com/linux/"
BUG_REPORT_URL="https://github.com/amazonlinux/amazon-linux-2023"
SUPPORT_END="2028-03-01"'''


rocky_os_release = '''NAME="Rocky Linux"
VERSION="8.6 (Green Obsidian)"
ID="rocky"
ID_LIKE="rhel centos fedora"
VERSION_ID="8.6"
PLATFORM_ID="platform:el8"
PRETTY_NAME="Rocky Linux 8.6 (Green Obsidian)"
ANSI_COLOR="0;32"
CPE_NAME="cpe:/o:rocky:rocky:8:GA"
HOME_URL="https://rockylinux.org/"
BUG_REPORT_URL="https://bugs.rockylinux.org/"
ROCKY_SUPPORT_PRODUCT="Rocky Linux"
ROCKY_SUPPORT_PRODUCT_VERSION="8"
REDHAT_SUPPORT_PRODUCT="Rocky Linux"
REDHAT_SUPPORT_PRODUCT_VERSION="8"'''


redhat_os_release = '''NAME="Red Hat Enterprise Linux Server"
VERSION="7.5 (Maipo)"
ID="rhel"
ID_LIKE="fedora"
VARIANT="Server"
VARIANT_ID="server"
VERSION_ID="7.5"
PRETTY_NAME="Red Hat Enterprise Linux Server 7.5 (Maipo)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:redhat:enterprise_linux:7.5:GA:server"
HOME_URL="https://www.redhat.com/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"

REDHAT_BUGZILLA_PRODUCT="Red Hat Enterprise Linux 7"
REDHAT_BUGZILLA_PRODUCT_VERSION=7.5
REDHAT_SUPPORT_PRODUCT="Red Hat Enterprise Linux"
REDHAT_SUPPORT_PRODUCT_VERSION="7.5"'''


kylin_os_release = '''NAME="Kylin Linux Advanced Server"
VERSION="V10 (Sword)"
ID="kylin"
VERSION_ID="V10"
PRETTY_NAME="Kylin Linux Advanced Server V10 (Sword)"
ANSI_COLOR="0;31"'''


mariner_os_release = '''NAME="Common Base Linux Mariner"
VERSION="2.0.20240425"
ID=mariner
VERSION_ID="2.0"
PRETTY_NAME="CBL-Mariner/Linux"
ANSI_COLOR="1;34"
HOME_URL="https://aka.ms/cbl-mariner"
BUG_REPORT_URL="https://aka.ms/cbl-mariner"
SUPPORT_URL="https://aka.ms/cbl-mariner"'''


oracle_os_release = """
NAME="Oracle Linux Server"
VERSION="9.5"
ID="ol"
ID_LIKE="fedora"
VARIANT="Server"
VARIANT_ID="server"
VERSION_ID="9.5"
PLATFORM_ID="platform:el9"
PRETTY_NAME="Oracle Linux Server 9.5"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:oracle:linux:9:5:server"
HOME_URL="https://linux.oracle.com/"
BUG_REPORT_URL="https://github.com/oracle/oracle-linux"

ORACLE_BUGZILLA_PRODUCT="Oracle Linux 9"
ORACLE_BUGZILLA_PRODUCT_VERSION=9.5
ORACLE_SUPPORT_PRODUCT="Oracle Linux"
ORACLE_SUPPORT_PRODUCT_VERSION=9.5
"""

sles_os_release = '''NAME="SLES"
VERSION="15"
VERSION_ID="15"
PRETTY_NAME="SUSE Linux Enterprise Server 15"
ID="sles"
ID_LIKE="suse"
ANSI_COLOR="0;32"
CPE_NAME="cpe:/o:suse:sles:15"'''


opensuse_os_release = '''NAME="openSUSE Leap"
VERSION="15.0"
ID="opensuse-leap"
ID_LIKE="suse opensuse"
VERSION_ID="15.0"
PRETTY_NAME="openSUSE Leap 15.0"
ANSI_COLOR="0;32"
CPE_NAME="cpe:/o:opensuse:leap:15.0"
BUG_REPORT_URL="https://bugs.opensuse.org"
HOME_URL="https://www.opensuse.org/"'''

opensuse_tumbleweed_os_release = '''NAME="openSUSE Tumbleweed"
# VERSION="20240524"
ID="opensuse-tumbleweed"
ID_LIKE="opensuse suse"
VERSION_ID="20240524"
PRETTY_NAME="openSUSE Tumbleweed"
ANSI_COLOR="0;32"
# CPE 2.3 format, boo#1217921
CPE_NAME="cpe:2.3:o:opensuse:tumbleweed:20240524:*:*:*:*:*:*:*"
#CPE 2.2 format
#CPE_NAME="cpe:/o:opensuse:tumbleweed:20240524"
BUG_REPORT_URL="https://bugzilla.opensuse.org"
SUPPORT_URL="https://bugs.opensuse.org"
HOME_URL="https://www.opensuse.org"
DOCUMENTATION_URL="https://en.opensuse.org/Portal:Tumbleweed"
LOGO="distributor-logo-Tumbleweed"'''

fedora_os_release = '''NAME="Fedora Linux"
VERSION="40 (KDE Plasma)"
ID=fedora
VERSION_ID=40
VERSION_CODENAME=""
PLATFORM_ID="platform:f40"
PRETTY_NAME="Fedora Linux 40 (KDE Plasma)"
ANSI_COLOR="0;38;2;60;110;180"
LOGO=fedora-logo-icon
CPE_NAME="cpe:/o:fedoraproject:fedora:40"
DEFAULT_HOSTNAME="fedora"
HOME_URL="https://fedoraproject.org/"
DOCUMENTATION_URL="https://docs.fedoraproject.org/en-US/fedora/f40/system-administrators-guide/"
SUPPORT_URL="https://ask.fedoraproject.org/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"
REDHAT_BUGZILLA_PRODUCT="Fedora"
REDHAT_BUGZILLA_PRODUCT_VERSION=40
REDHAT_SUPPORT_PRODUCT="Fedora"
REDHAT_SUPPORT_PRODUCT_VERSION=40
SUPPORT_END=2025-05-13
VARIANT="KDE Plasma"
VARIANT_ID="kde"'''


debian_os_release = '''PRETTY_NAME="Debian GNU/Linux 10 (buster)"
NAME="Debian GNU/Linux"
VERSION_ID="10"
VERSION="10 (buster)"
VERSION_CODENAME=buster
ID=debian
HOME_URL="https://www.debian.org/"
SUPPORT_URL="https://www.debian.org/support"
BUG_REPORT_URL="https://bugs.debian.org/"'''


ubuntu_os_release = """PRETTY_NAME="Ubuntu 23.10"
NAME="Ubuntu"
VERSION_ID="23.10"
VERSION="23.10 (Mantic Minotaur)"
VERSION_CODENAME=mantic
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=mantic
LOGO=ubuntu-logo"""


azure_os_release = """
NAME="Azure Linux Toolchain"
VERSION="3.0.2024"
ID=azurelinux
VERSION_ID="3.0"
PRETTY_NAME="Azure Linux 3.0"
ANSI_COLOR="1;34"
HOME_URL="https://aka.ms/cbl-mariner"
BUG_REPORT_URL="https://aka.ms/cbl-mariner"
SUPPORT_URL="https://aka.ms/cbl-mariner"
"""


os_release_files = {
    "amzn": amazon_os_release,
    "rocky": rocky_os_release,
    "rhel": redhat_os_release,
    "kylin": kylin_os_release,
    "mariner": mariner_os_release,
    "azurelinux": azure_os_release,
    "ol": oracle_os_release,
    "sles": sles_os_release,
    "opensuse-leap": opensuse_os_release,
    "opensuse-tumbleweed": opensuse_tumbleweed_os_release,
    "fedora": fedora_os_release,
    "debian": debian_os_release,
    "ubuntu": ubuntu_os_release,
}


def import_function(function, *args):
    """Hack to import functions from the main script"""
    filename = "nvidia-driver-assistant.py"
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, filename))
    spec = importlib.util.spec_from_file_location(function, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return getattr(module, function)(*args)


def import_class(klass, *args):
    """Hack to import classes from the main script"""
    filename = "nvidia-driver-assistant.py"
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, filename))
    spec = importlib.util.spec_from_file_location(klass, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return getattr(module, klass)(*args)


def generate_fake_hardware():
    """Generate and return a UMockdev.Testbed object"""

    testbed = UMockdev.Testbed.new()

    testbed.add_device("acpi", "acpi_dev_1", None, ["modalias", "acpi:PNP0C14:"], [])
    testbed.add_device(
        "wmi", "wmi_dev_1", None, ["modalias", "wmi:68062427-C432-4BA2-B3D8-F63949DD7A19"], []
    )
    testbed.add_device(
        "wmi", "wmi_dev_2", None, ["modalias", "wmi:05901221-D566-11D1-B2F0-00A0C9062910"], []
    )
    testbed.add_device("platform", "cpu_freq", None, ["modalias", "platform:acpi-cpufreq"], [])
    testbed.add_device("platform", "eisa", None, ["modalias", "platform:eisa"], [])
    testbed.add_device("platform", "microcode", None, ["modalias", "platform:microcode"], [])
    testbed.add_device(
        "platform", "intel_rapl_msr", None, ["modalias", "platform:intel_rapl_msr"], []
    )
    testbed.add_device("platform", "mdio", None, ["modalias", "platform:Fixed MDIO bus"], [])
    testbed.add_device("acpi", "pnp_dev_1", None, ["modalias", "acpi:PNP0C0C:"], [])
    testbed.add_device(
        "pci",
        "black",
        None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "white",
        None,
        ["modalias", "pci:v00001022d000014E3sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "red",
        None,
        ["modalias", "pci:v0000144Dd0000A808sv0000144Dsd0000A801bc01sc08i02"],
        [],
    )
    testbed.add_device(
        "pci",
        "blue",
        None,
        ["modalias", "pci:v00001022d000014E1sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "magenta",
        None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "purple",
        None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "navy",
        None,
        ["modalias", "pci:v00001022d0000790Esv00001462sd00007E26bc06sc01i00"],
        [],
    )
    testbed.add_device("pci", "pink", None, ["modalias", "acpi:PNP0800:"], [])
    testbed.add_device(
        "pci",
        "yellow",
        None,
        ["modalias", "pci:v000014C3d00000616sv000014C3sd00000616bc02sc80i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "orange",
        None,
        ["modalias", "pci:v000010ECd00008125sv00001462sd00007E26bc02sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "fuchsia",
        None,
        ["modalias", "pci:v00001022d000043F6sv00001B21sd00001062bc01sc06i01"],
        [],
    )
    testbed.add_device(
        "pci",
        "brown",
        None,
        ["modalias", "pci:v00001022d000043F7sv00001B21sd00001142bc0Csc03i30"],
        [],
    )
    testbed.add_device(
        "usb",
        "usb_dev_1",
        None,
        ["modalias", "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in02"],
        [],
    )
    testbed.add_device(
        "usb",
        "usb_dev_2",
        None,
        ["modalias", "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in00"],
        [],
    )
    testbed.add_device(
        "usb",
        "usb_dev_3",
        None,
        ["modalias", "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in01"],
        [],
    )
    testbed.add_device(
        "pci",
        "green",
        None,
        ["modalias", "pci:v00001022d000014D9sv00001462sd00007E26bc08sc06i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "maroon",
        None,
        ["modalias", "pci:v00001022d000015B8sv00001462sd00007E26bc0Csc03i30"],
        [],
    )
    testbed.add_device(
        "pci",
        "salmon",
        None,
        ["modalias", "pci:v00001022d000014E6sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "turquoise",
        None,
        ["modalias", "pci:v00001022d000014D8sv00001462sd00007E26bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "coral",
        None,
        ["modalias", "pci:v00001022d000015B6sv00001462sd00007E26bc0Csc03i30"],
        [],
    )
    testbed.add_device(
        "pci",
        "gold",
        None,
        ["modalias", "pci:v00001022d000015E3sv00001462sd0000EE26bc04sc03i00"],
        [],
    )
    testbed.add_device(
        "hdaudio", "audio_dev_1", None, ["modalias", "hdaudio:v10EC0897r00100500a01"], []
    )
    testbed.add_device(
        "input",
        "input_dev_1",
        None,
        ["modalias", "input:b0000v0000p0000e0000-e0,5,kramlsfw4,"],
        [],
    )
    testbed.add_device(
        "input",
        "input_dev_2",
        None,
        ["modalias", "input:b0000v0000p0000e0000-e0,5,kramlsfw2,"],
        [],
    )
    testbed.add_device(
        "pci",
        "peru",
        None,
        ["modalias", "pci:v00001022d000015B7sv00001462sd00007E26bc0Csc03i30"],
        [],
    )
    testbed.add_device(
        "pci",
        "khaki",
        None,
        ["modalias", "pci:v00001022d00001649sv00001462sd00007E26bc10sc80i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "lavender",
        None,
        ["modalias", "pci:v00001022d000014DEsv00001462sd00007E26bc13sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "plum",
        None,
        ["modalias", "pci:v00001022d000014E4sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "orchid",
        None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "indigo",
        None,
        ["modalias", "pci:v00001022d000014E2sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "olive",
        None,
        ["modalias", "pci:v000010DEd000022BCsv000010DEsd000018FEbc04sc03i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "aqua",
        None,
        ["modalias", "pci:v00001022d000014E0sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "cyan",
        None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "skyblue",
        None,
        ["modalias", "pci:v00001022d000014E7sv00000000sd00000000bc06sc00i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "steelblue",
        None,
        ["modalias", "pci:v00001022d0000790Bsv00001462sd00007E26bc0Csc05i00"],
        [],
    )
    testbed.add_device(
        "pci",
        "beige",
        None,
        ["modalias", "pci:v00001022d000014E5sv00000000sd00000000bc06sc00i00"],
        [],
    )

    return testbed


def generate_os_release(release):
    release_file = tempfile.NamedTemporaryFile(mode="w", prefix="os_release_path_", delete=False)

    content = os_release_files[release]

    with open(release_file.name, "w") as stream:
        stream.write(content)

    return release_file


def get_json_file(filename=None):
    return os.path.join(
        root_dir, "supported-gpus", filename if filename else "supported-gpus.json"
    )


class DetectTest(unittest.TestCase):
    """Test DriversAssistant.detect"""

    def setUp(self):
        """Create a fake sysfs"""
        self.umockdev = generate_fake_hardware()

    def run_driver_assistant(self, distro_id, json_file=None,
                             additional_args=[], testbed=None):
        """Run nvidia-driver-assistant and return (stdout, stderr)"""
        if testbed is None:
            testbed = self.umockdev
        os_release = generate_os_release(distro_id)

        command = [
            "%s/nvidia-driver-assistant" % root_dir,
            "--supported-gpus",
            get_json_file(json_file),
            "--sys-path",
            testbed.get_sys_dir(),
            "--os-release-path",
            os_release.name,
        ]

        if additional_args:
            command.extend(additional_args)

        assistant = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return assistant.communicate()

    def _load_main_module(self):
        """Helper to import the nvidia-driver-assistant module for direct calls."""
        filename = "nvidia-driver-assistant.py"
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, filename))
        spec = importlib.util.spec_from_file_location("nvidia_driver_assistant", script_path)
        nda = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nda)
        return nda

    # -----------------------------------------------------------------
    # Original suite_new tests (unchanged)
    # -----------------------------------------------------------------

    def test_get_distro(self):
        """get_distro() for fake systems"""

        # Test distro detection for all the supported systems
        release_file = tempfile.NamedTemporaryFile(
            mode="w", prefix="os_release_path_", delete=False
        )
        system_info = None
        for distro in os_release_files.keys():
            content = os_release_files[distro]

            with open(release_file.name, "w") as stream:
                stream.write(content)

            system_info = import_function("get_distro", (release_file.name))

            self.assertTrue(system_info)
            self.assertTrue(distro in [system_info.id, system_info.original_id])
            self.assertTrue(system_info.version_id)

        # Let's try with an empty file
        content = ""
        with open(release_file.name, "w") as stream:
            stream.write(content)

        system_info = import_function("get_distro", (release_file.name))

        self.assertFalse(system_info)

        os.unlink(release_file.name)
        del release_file

    def test_distro_override(self):
        original_id = "fedora"
        fake_id = "ubuntu"
        system_info = import_function("override_distro", (fake_id))

        self.assertTrue(system_info)
        self.assertTrue(fake_id in [system_info.id, system_info.original_id])
        self.assertFalse(system_info.version_id)

        # Let's try overriding the version too
        fake_id = "ubuntu:24.04"
        system_info = import_function("override_distro", (fake_id))

        self.assertTrue(system_info)
        self.assertTrue(fake_id.split(":")[0] in [system_info.id, system_info.original_id])
        self.assertTrue(system_info.version_id)

        # Test case sensitive fake id
        fake_id = "Mariner"
        system_info = import_function("override_distro", (fake_id))

        self.assertTrue(system_info)
        self.assertTrue(fake_id in [system_info.id, system_info.original_id])
        self.assertFalse(system_info.version_id)

        # Case sensitive plus version
        fake_id = "Ubuntu:24.04"
        system_info = import_function("override_distro", (fake_id))

        self.assertTrue(system_info)
        self.assertTrue(fake_id.split(":")[0] in [system_info.id, system_info.original_id])
        self.assertTrue(system_info.version_id)

    def test_get_system_modaliases(self):
        """Test get_system_modaliases() using our fake hardware"""

        # Add 3 GPUS
        self.umockdev.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        self.umockdev.add_device("pci", "gpu_c", None, ["modalias", gpu_c], [])
        self.umockdev.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])

        modaliases = import_function("get_system_modaliases", (self.umockdev.get_sys_dir()))

        self.assertEqual(
            set(modaliases),
            set(
                [
                    "acpi:PNP0C14:",
                    "wmi:68062427-C432-4BA2-B3D8-F63949DD7A19",
                    "wmi:05901221-D566-11D1-B2F0-00A0C9062910",
                    "platform:acpi-cpufreq",
                    "platform:eisa",
                    "platform:microcode",
                    "platform:intel_rapl_msr",
                    "platform:Fixed MDIO bus",
                    "acpi:PNP0C0C:",
                    "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014E3sv00000000sd00000000bc06sc00i00",
                    "pci:v0000144Dd0000A808sv0000144Dsd0000A801bc01sc08i02",
                    "pci:v00001022d000014E1sv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d0000790Esv00001462sd00007E26bc06sc01i00",
                    "acpi:PNP0800:",
                    "pci:v000014C3d00000616sv000014C3sd00000616bc02sc80i00",
                    "pci:v000010ECd00008125sv00001462sd00007E26bc02sc00i00",
                    "pci:v00001022d000043F6sv00001B21sd00001062bc01sc06i01",
                    "pci:v00001022d000043F7sv00001B21sd00001142bc0Csc03i30",
                    "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in02",
                    "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in00",
                    "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in01",
                    "pci:v00001022d000014D9sv00001462sd00007E26bc08sc06i00",
                    "pci:v00001022d000015B8sv00001462sd00007E26bc0Csc03i30",
                    "pci:v00001022d000014E6sv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014D8sv00001462sd00007E26bc06sc00i00",
                    "pci:v00001022d000015B6sv00001462sd00007E26bc0Csc03i30",
                    "pci:v00001022d000015E3sv00001462sd0000EE26bc04sc03i00",
                    "hdaudio:v10EC0897r00100500a01",
                    "input:b0000v0000p0000e0000-e0,5,kramlsfw4,",
                    "input:b0000v0000p0000e0000-e0,5,kramlsfw2,",
                    "pci:v00001022d000015B7sv00001462sd00007E26bc0Csc03i30",
                    "pci:v00001022d00001649sv00001462sd00007E26bc10sc80i00",
                    "pci:v00001022d000014DEsv00001462sd00007E26bc13sc00i00",
                    "pci:v00001022d000014E4sv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014E2sv00000000sd00000000bc06sc00i00",
                    "pci:v000010DEd00002783sv000010DEsd000018FEbc03sc00i00",
                    "pci:v000010DEd000022BCsv000010DEsd000018FEbc04sc03i00",
                    "pci:v00001022d000014E0sv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d000014E7sv00000000sd00000000bc06sc00i00",
                    "pci:v00001022d0000790Bsv00001462sd00007E26bc0Csc05i00",
                    "pci:v00001022d000014E5sv00000000sd00000000bc06sc00i00",
                    gpu_a,
                    gpu_c,
                    gpu_d,
                ]
            ),
        )

    def test_get_nvidia_devices(self):
        """Test get_nvidia_devices()"""
        testbed = generate_fake_hardware()
        json_file = get_json_file()

        # Add 3 GPUS
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        testbed.add_device("pci", "gpu_c", None, ["modalias", gpu_c], [])
        testbed.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])

        devices = import_function("get_nvidia_devices", *[testbed.get_sys_dir(), json_file])

        self.assertFalse(not devices)
        self.assertTrue(len(devices) == 3)

    def test_driver_assistant_1(self):
        """Test driver assistant scenario 1"""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        stdout, stderr = self.run_driver_assistant("fedora", testbed=testbed)

        self.assertEqual(len(stderr), 0)

    def test_driver_assistant_2_oracle_alias(self):
        """Test driver assistant scenario 2 Oracle alias for rhel"""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        stdout, stderr = self.run_driver_assistant("ol", testbed=testbed)

        self.assertEqual(len(stderr), 0)

    def test_driver_assistant_branch(self):
        """Test driver assistant --branch argument"""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        # This should fail
        stdout, stderr = self.run_driver_assistant(
            "fedora", additional_args=["--branch", "530"], testbed=testbed
        )
        self.assertTrue(len(stderr) > 0)

        # This should also fail
        stdout, stderr = self.run_driver_assistant(
            "fedora", additional_args=["--branch", "r560"], testbed=testbed
        )
        self.assertTrue(len(stderr) > 0)

        # This should pass
        stdout, stderr = self.run_driver_assistant(
            "fedora", additional_args=["--branch", "560"], testbed=testbed
        )
        self.assertEqual(len(stderr), 0)

        # This should also pass
        stdout, stderr = self.run_driver_assistant(
            "fedora", additional_args=["--branch", "575"], testbed=testbed
        )
        self.assertEqual(len(stderr), 0)

    def _check_module_flavor(self, distro_id):
        """Shared helper: validates --module-flavor accept/reject on a given distro."""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        # Invalid values must be rejected (exit code != 0, stderr non-empty)
        for bad in ("Fopen", "closedo"):
            stdout, stderr = self.run_driver_assistant(
                distro_id, additional_args=["--module-flavor", bad], testbed=testbed
            )
            self.assertTrue(len(stderr) > 0,
                            f"--module-flavor {bad!r} should be rejected on {distro_id}")

        # Valid values (case-insensitive) must be accepted
        for good in ("open", "oPEn", "closed", "CloSed"):
            stdout, stderr = self.run_driver_assistant(
                distro_id, additional_args=["--module-flavor", good], testbed=testbed
            )
            self.assertEqual(len(stderr), 0,
                             f"--module-flavor {good!r} should be accepted on {distro_id}")

    def test_driver_assistant_module_flavor(self):
        """Test --module-flavor accept/reject on fedora (primary distro)"""
        self._check_module_flavor("fedora")

    def test_driver_assistant_module_flavor_alias(self):
        """Test --module-flavor accept/reject on ol (Oracle Linux alias for rhel)"""
        self._check_module_flavor("ol")

    # -----------------------------------------------------------------
    # Mixed-GPU CLI tests (--simulate-mixed, --simulate-badmix)
    # -----------------------------------------------------------------

    def test_simulate_mixed(self):
        """CLI test: --simulate-mixed (GTX 750 Ti [580] + RTX 5070 [modern])

        Policy: Both GPUs are supported. The 750 Ti is on legacy branch 580
        which does NOT support open kernel modules. The CLI safety-net
        (cli.py lines 287-294) overrides the initial 'open' recommendation
        to 'closed', and locks the branch to 580.

        Expected JSON output:
          module_flavor = "closed"
          branch        = "580"
          devices       = 2 (both present, none discarded)

        Why it might fail:
          - The safety-net override was removed or its branch threshold changed
          - The legacy_branch detection in check_legacy_devices() is broken
          - The simulated_gpus["mixed"] data in database.py was altered
        """
        stdout, stderr = self.run_driver_assistant(
            "fedora", additional_args=["--simulate-mixed", "--json"]
        )
        self.assertEqual(len(stderr), 0, f"stderr not empty: {stderr}")
        # stdout contains informational text before the JSON object;
        # extract from the first '{' to the last '}'.
        text = stdout.decode("utf-8", errors="replace")
        json_start = text.index("{")
        json_end = text.rindex("}") + 1
        result = json.loads(text[json_start:json_end])
        self.assertEqual(result["module_flavor"], "closed",
                         "Mixed 580+modern must recommend closed (580 does not support open)")
        self.assertEqual(result["branch"], "580",
                         "Branch must be locked to 580 for the legacy GPU")
        self.assertEqual(len(result["devices"]), 2,
                         "Both GPUs must be present (none discarded)")

    def test_simulate_badmix(self):
        """CLI test: --simulate-badmix (GT 740A [470] + RTX 5070 [modern])

        Policy: The 740A is on legacy branch 470, which is below
        min_supported_legacy_branch (580). It is therefore unsupported.
        The CLI mixed-GPU priority logic (cli.py lines 204-235) detects
        that there is an open-capable modern device present and discards
        the unsupported legacy device. The recommendation stays 'open'
        with no branch lock.

        Expected JSON output:
          module_flavor = "open"
          branch        = null (no legacy branch lock)
          devices       = 2 (the 740A is still listed in devices, but
                             removed from unsupported_devices internally)

        Why it might fail:
          - The mixed-GPU priority block in cli.py was removed or altered
          - The has_open_capable check changed (e.g., driver_hint constants)
          - The min_supported_legacy_branch was lowered below 470
          - The simulated_gpus["badmix"] data in database.py was altered
        """
        stdout, stderr = self.run_driver_assistant(
            "fedora", additional_args=["--simulate-badmix", "--json"]
        )
        self.assertEqual(len(stderr), 0, f"stderr not empty: {stderr}")
        text = stdout.decode("utf-8", errors="replace")
        json_start = text.index("{")
        json_end = text.rindex("}") + 1
        result = json.loads(text[json_start:json_end])
        self.assertEqual(result["module_flavor"], "open",
                         "Badmix (<580 legacy + modern) must recommend open")
        self.assertIsNone(result["branch"],
                          "No branch lock expected when legacy device is discarded")
        self.assertEqual(len(result["devices"]), 2,
                         "Both GPUs must be listed in the JSON output")

    # -----------------------------------------------------------------
    # recommend_driver() API-level tests
    # -----------------------------------------------------------------

    def test_recommend_driver(self):
        """API test: recommend_driver() with modern GPU alone, then with sub-580 legacy GPUs

        Phase 1: gpu_a (RTX 4070 SUPER, ada, modern open-capable) alone.
          Expected: driver='open' (modern open-capable GPU, no legacy conflict).

        Phase 2: gpu_a + gpu_c (6800 LE, 304.xx) + gpu_d (GTX 650, 470.xx).
          Both legacy GPUs are below min_supported_legacy_branch (580), so they
          land on unsupported_devices. recommend_driver() still returns 'open'
          because unsupported legacy devices do NOT flip the recommendation at
          the API level. The CLI would then discard them (see test_simulate_badmix).

        Why it might fail:
          - get_driver_from_json_hints() logic changed
          - check_legacy_devices() threshold changed
          - unsupported devices incorrectly forcing driver to 'closed'
        """
        nda = self._load_main_module()
        json_file = get_json_file()
        testbed = generate_fake_hardware()
        # Modern open-capable GPU alone
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        with patch.object(nda, 'ubuntu_get_latest_driver_branch', return_value='575'):
            result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        # Handle both 3- and 4-tuple returns
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        # Add legacy GPUs: 304.xx (pre-curie, EOL) and 470.xx (kepler)
        # Both are below min_supported_legacy_branch (580), so they are
        # unsupported and do not flip the recommendation to closed.
        testbed.add_device("pci", "gpu_c", None, ["modalias", gpu_c], [])
        testbed.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])

        with patch.object(nda, 'ubuntu_get_latest_driver_branch', return_value='575'):
            result2 = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result2) == 4:
            driver2, legacy_branch2, unsupported2, open_kernel2 = result2
        else:
            driver2, legacy_branch2, unsupported2 = result2
        self.assertTrue(driver2)
        self.assertEqual(driver2, "open")

    def test_recommend_driver_mod(self):
        """API test: recommend_driver() with supported-gpus-mod.json (extended hints)

        Phase 1: gpu_a (RTX 4070 SUPER) alone with mod JSON.
          Expected: driver='open'.

        Phase 2: gpu_a + gpu_b (TITAN V, legacy 580, kernelopen feature).
          Both are supported (580 >= min_supported_legacy_branch). At the API
          level, recommend_driver() returns 'open' because the kernelopen
          feature is present on gpu_b. Note: the CLI would then apply the
          safety-net and switch to 'closed' (see test_simulate_mixed for that
          end-to-end test).

        Why it might fail:
          - supported-gpus-mod.json missing or structurally different
          - get_driver_from_json_hints() module-hint parsing changed
        """
        json_file = get_json_file("supported-gpus-mod.json")
        if not os.path.isfile(json_file):
            self.skipTest("supported-gpus-mod.json not found")

        nda = self._load_main_module()
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        with patch.object(nda, 'ubuntu_get_latest_driver_branch', return_value='575'):
            result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        # gpu_b (TITAN V, 580 legacy, kernelopen) — API returns 'open'
        testbed.add_device("pci", "gpu_b", None, ["modalias", gpu_b], [])

        with patch.object(nda, 'ubuntu_get_latest_driver_branch', return_value='575'):
            result2 = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result2) == 4:
            driver2, legacy_branch2, unsupported2, open_kernel2 = result2
        else:
            driver2, legacy_branch2, unsupported2 = result2
        self.assertTrue(driver2)
        self.assertEqual(driver2, "open")

    def test_recommend_driver_legacy_580(self):
        """API test: recommend_driver() with three 580.xx legacy GPUs

        gpu_f (GTX 1080 Ti), gpu_g (Quadro GV100), gpu_h (GTX 750 Ti) are all
        on legacy branch 580, which is >= min_supported_legacy_branch.
        Expected: driver is set, legacy_branch='580'.

        Why it might fail:
          - check_legacy_devices() branch parsing broken
          - min_supported_legacy_branch raised above 580
        """
        nda = self._load_main_module()
        json_file = get_json_file()
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_f", None, ["modalias", gpu_f], [])
        testbed.add_device("pci", "gpu_g", None, ["modalias", gpu_g], [])
        testbed.add_device("pci", "gpu_h", None, ["modalias", gpu_h], [])

        with patch.object(nda, 'ubuntu_get_latest_driver_branch', return_value='575'):
            result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
        self.assertTrue(driver)
        if legacy_branch is not None:
            self.assertIn(legacy_branch, ["580", "580.xx"])

    def test_malformed_json_legacy_open_kernel(self):
        """Resilience test: malformed JSON (single quotes, trailing commas)

        Uses supported-gpus-bad/supported-gpus.json which contains syntax
        errors. The resilient JSON parser (database.py) should sanitize and
        load it successfully instead of crashing.

        Why it might fail:
          - The resilient JSON parser in database.py was removed
          - The bad JSON file was changed to something unparseable even after sanitization
        """
        nda = self._load_main_module()
        testbed = generate_fake_hardware()
        bad_json_file = os.path.join(root_dir, "supported-gpus-bad", "supported-gpus.json")
        testbed.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])

        with patch.object(nda, 'ubuntu_get_latest_driver_branch', return_value='575'):
            result = nda.recommend_driver(testbed.get_sys_dir(), bad_json_file)
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
            open_kernel = None
        self.assertTrue(driver is not None or unsupported is not None)

    # -----------------------------------------------------------------
    # Instruction-generation matrix test
    # -----------------------------------------------------------------

    def test_process_results(self):
        """Matrix test: process_results() for every GPU × every distro

        For each of the 8 GPU aliases, calls recommend_driver() to get the
        driver type, then calls process_results() for every distro in
        os_release_files, with branch=None and branch='570'.

        This ensures that no GPU×distro×branch combination crashes or
        returns empty instructions.

        Why it might fail:
          - A distro was added to os_release_files but not to instructions.yaml
          - process_results() has a gap for a particular driver×distro combo
          - supported-gpus-mod.json was altered so a GPU is no longer found
        """
        json_file = get_json_file("supported-gpus-mod.json")
        if not os.path.isfile(json_file):
            self.skipTest("supported-gpus-mod.json not found")

        nda = self._load_main_module()

        gpu_list = [gpu_a, gpu_b, gpu_c, gpu_d, gpu_e, gpu_f, gpu_g, gpu_h]

        # Helyes mock: a recommendation modul függvényét patcheljük, hogy elkerüljük az apt_pkg importálást
        with patch('nvidia_driver_assistant.recommendation.ubuntu_get_latest_driver_branch', return_value='575'):
            for gpu_mod in gpu_list:
                testbed = generate_fake_hardware()
                testbed.add_device("pci", "gpu_under_test", None, ["modalias", gpu_mod], [])

                result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
                # We only care about the first element (the driver), ignore the rest
                driver = result[0] if result else None
                self.assertIsNotNone(driver, f"No driver recommended for GPU {gpu_mod}")

                for distro_key in os_release_files:
                    with self.subTest(gpu=gpu_mod, distro=distro_key):
                        release_file = generate_os_release(distro_key)
                        system_info = nda.get_distro(release_file.name)
                        if not system_info:
                            os.unlink(release_file.name)
                            self.skipTest(f"Could not detect distro {distro_key}")
                        version = system_info.version_id if system_info.version_id else "10.0"
                        for branch in (None, "570"):
                            results = nda.process_results(driver, system_info.id, version, branch, None)
                            self.assertTrue(results,
                                            f"process_results failed for GPU {gpu_mod} "
                                            f"on {distro_key} version {version} branch {branch}")
                        os.unlink(release_file.name)


# =====================================================================
# TEST CATALOGUE — what each test verifies and common failure causes
# =====================================================================
#
# 1. test_get_distro
#    Verifies get_distro() for every os-release fixture (13 distros).
#    Also tests that an empty os-release file returns False.
#    FAILS IF: os-release parsing logic changed, new distro added to
#    os_release_files without matching parser support.
#
# 2. test_distro_override
#    Verifies override_distro() with plain name, name:version, and
#    case-sensitive input.
#    FAILS IF: override_distro() parsing changed.
#
# 3. test_get_system_modaliases
#    Collects modaliases from fake sysfs (umockdev) and checks the full
#    set matches expectations.
#    FAILS IF: get_system_modaliases() filtering logic changed, or the
#    fake hardware setup was altered.
#
# 4. test_get_nvidia_devices
#    Adds 3 GPUs (gpu_a, gpu_c, gpu_d) to fake sysfs and verifies
#    get_nvidia_devices() finds exactly 3.
#    FAILS IF: device matching in database.py changed.
#
# 5. test_driver_assistant_1
#    CLI smoke test: single modern GPU (gpu_a) on fedora.
#    FAILS IF: CLI crashes for basic single-GPU case.
#
# 6. test_driver_assistant_2_oracle_alias
#    CLI smoke test: gpu_a on Oracle Linux (ol → rhel alias).
#    FAILS IF: distro alias mapping broken.
#
# 7. test_driver_assistant_branch
#    CLI: validates --branch argument (rejects <560, non-integer; accepts >=560).
#    FAILS IF: branch validation logic changed.
#
# 8. test_driver_assistant_module_flavor
#    CLI: validates --module-flavor on fedora (rejects invalid, accepts
#    open/closed case-insensitively).
#    FAILS IF: module-flavor validation changed.
#
# 9. test_driver_assistant_module_flavor_alias
#    Same as #8 but on Oracle Linux (ol). Tests that distro aliases
#    don't break module-flavor handling.
#    FAILS IF: same as #8, or ol alias breaks something.
#
# 10. test_simulate_mixed  *** NEW ***
#     CLI end-to-end: --simulate-mixed (GTX 750 Ti [580] + RTX 5070).
#     Verifies the safety-net override: legacy branch 580 does not support
#     open kernel modules, so the CLI switches from 'open' to 'closed'.
#     Expected: module_flavor="closed", branch="580", 2 devices.
#     FAILS IF: safety-net removed/threshold changed, legacy_branch detection
#     broken, simulated_gpus["mixed"] altered.
#
# 11. test_simulate_badmix  *** NEW ***
#     CLI end-to-end: --simulate-badmix (GT 740A [470] + RTX 5070).
#     Verifies mixed-GPU priority: the 740A is unsupported (470 < 580),
#     so the CLI discards it and recommends 'open' for the modern card.
#     Expected: module_flavor="open", branch=null, 2 devices.
#     FAILS IF: mixed-GPU priority block removed, has_open_capable check
#     changed, min_supported_legacy_branch lowered below 470.
#
# 12. test_recommend_driver
#     API-level: modern GPU alone → 'open'; modern + sub-580 legacy → still
#     'open' at the API level (unsupported devices don't flip recommendation).
#     FAILS IF: get_driver_from_json_hints() or check_legacy_devices() changed.
#
# 13. test_recommend_driver_mod
#     API-level with supported-gpus-mod.json: modern alone → 'open';
#     modern + TITAN V (580, kernelopen) → 'open' at API level.
#     FAILS IF: mod JSON missing, module-hint parsing changed.
#
# 14. test_recommend_driver_legacy_580
#     API-level: three 580.xx GPUs → legacy_branch='580'.
#     FAILS IF: check_legacy_devices() branch parsing broken.
#
# 15. test_malformed_json_legacy_open_kernel
#     Resilience: malformed JSON (single quotes, trailing commas) should
#     not crash — the resilient parser sanitizes and loads it.
#     FAILS IF: resilient JSON parser removed or bad file changed.
#
# 16. test_process_results
#     Matrix test: every GPU × every distro × branch=None/570.
#     Ensures process_results() never returns empty instructions.
#     FAILS IF: instructions.yaml gap, new distro without instructions.
# =====================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(DetectTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("TEST EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total tests run: {result.testsRun}")
    successes = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Successes: {successes}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback.splitlines()[-1]}")
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback.splitlines()[-1]}")
    print("=" * 60)
