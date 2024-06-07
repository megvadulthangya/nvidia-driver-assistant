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

import json
import os
import subprocess
import sys
import tempfile
import unittest

from gi.repository import UMockdev

import DriverAssistant.detect

test_dir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.dirname(test_dir)

# install python3-gi and umockdev gir1.2-umockdev-1.0 python3-aptdaemon python3-aptdaemon.test

# supported - vdpaufeaturesetK and proprietary_supported
gpu_modalias_1 = "pci:v000010DEd00002783sv000010DEsd000018FEbc03sc00i00"

# supported - vdpaufeaturesetI and proprietary_required
gpu_modalias_2 = "pci:v000010DEd00001D81sv000010DEsd000018FEbc03sc00i00"

# 304.xx - EOL
legacy_gpu_modalias_1 = "pci:v000010DEd000000C2sv000010DEsd000018FEbc03sc00i00"
# 470.xx
legacy_gpu_modalias_2 = "pci:v000010DEd00000FC6sv000010DEsd000018FEbc03sc00i00"

# 390.xx - EOL - vdpaufeaturesetC and proprietary_required
legacy_gpu_modalias_3 = "pci:v000010DEd000006C0sv000010DEsd000018FEbc03sc00i00"


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
    "sles": sles_os_release,
    "opensuse-leap": opensuse_os_release,
    "opensuse-tumbleweed": opensuse_tumbleweed_os_release,
    "fedora": fedora_os_release,
    "debian": debian_os_release,
    "ubuntu": ubuntu_os_release,
}


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


def get_json_file():
    return os.path.join(root_dir, "supported-gpus", "supported-gpus.json")


class DetectTest(unittest.TestCase):
    """Test DriversAssistant.detect"""

    def setUp(self):
        """Create a fake sysfs"""

        self.umockdev = generate_fake_hardware()

    def run_driver_assistant(self, distro_id):
        """Run driver-assistant and return (stdout, stderr)"""
        os_release = generate_os_release(distro_id)
        command = [
            "%s/driver-assistant" % root_dir,
            "--supported-gpus",
            get_json_file(),
            "--sys-path",
            self.umockdev.get_sys_dir(),
            "--os-release-path",
            os_release.name,
        ]

        assistant = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return assistant.communicate()

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

            system_info = DriverAssistant.detect.get_distro(release_file.name)

            self.assertTrue(system_info)
            self.assertTrue(distro in [system_info.id, system_info.original_id])
            self.assertTrue(system_info.version_id)

        os.unlink(release_file.name)
        del release_file

    def test_distro_override(self):
        original_id = "fedora"
        fake_id = "ubuntu"
        system_info = DriverAssistant.detect.override_distro(fake_id)

        self.assertTrue(system_info)
        self.assertTrue(fake_id in [system_info.id, system_info.original_id])
        self.assertFalse(system_info.version_id)

        # Let's try overriding the version too
        fake_id = "ubuntu:24.04"
        system_info = DriverAssistant.detect.override_distro(fake_id)

        self.assertTrue(system_info)
        self.assertTrue(fake_id.split(":")[0] in [system_info.id, system_info.original_id])
        self.assertTrue(system_info.version_id)

    def test_get_system_modaliases(self):
        """Test get_system_modaliases() using our fake hardware"""

        # Add 3 GPUS
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_1", None, ["modalias", legacy_gpu_modalias_1], []
        )
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_2", None, ["modalias", legacy_gpu_modalias_2], []
        )

        modaliases = DriverAssistant.detect.get_system_modaliases(self.umockdev.get_sys_dir())

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
                    gpu_modalias_1,
                    legacy_gpu_modalias_1,
                    legacy_gpu_modalias_2,
                ]
            ),
        )

    def test_get_nvidia_devices(self):
        """Test get_nvidia_devices()"""
        json_file = get_json_file()

        # Add 3 GPUS
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_1", None, ["modalias", legacy_gpu_modalias_1], []
        )
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_2", None, ["modalias", legacy_gpu_modalias_2], []
        )

        devices = DriverAssistant.detect.get_nvidia_devices(self.umockdev.get_sys_dir(), json_file)

        # Not invalid
        self.assertFalse(not devices)
        # print("Devices: %s" % devices)
        self.assertTrue(len(devices) == 3)

    def test_driver_assistant_1(self):
        """Test driver assistant scenario 1"""
        # Add 1 supported GPU (e.g. 4070 super)
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])

        stdout, stderr = self.run_driver_assistant("fedora")

        self.assertEqual(len(stderr), 0)


if __name__ == "__main__":
    print("Please run as follows, instead of running this file directly:", file=sys.stderr)
    print("PYTHONPATH=. tests/run --suite %s" % (os.path.basename(__file__)), file=sys.stderr)
    exit(1)
