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

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import logging

import gi
gi.require_version('UMockdev', '1.0')
from gi.repository import UMockdev

test_dir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.dirname(test_dir)

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


manjaro_os_release = '''NAME="Manjaro Linux"
ID=manjaro
ID_LIKE=arch
BUILD_ID=rolling
PRETTY_NAME="Manjaro Linux"
ANSI_COLOR="32;1;24;144;200"
HOME_URL="https://manjaro.org/"
DOCUMENTATION_URL="https://wiki.manjaro.org/"
SUPPORT_URL="https://forum.manjaro.org/"
BUG_REPORT_URL="https://manjaro.org/"
PRIVACY_POLICY_URL="https://manjaro.org/privacy-policy/"
LOGO=manjarolinux
VERSION_ID=25.0'''


fedora_os_release = '''NAME="Fedora Linux"
VERSION="40 (KDE Plasma)"
ID=fedora
VERSION_ID=40
PRETTY_NAME="Fedora Linux 40 (KDE Plasma)"'''

ubuntu_os_release = """PRETTY_NAME="Ubuntu 23.10"
NAME="Ubuntu"
VERSION_ID="23.10"
ID=ubuntu
ID_LIKE=debian"""


os_release_files = {
    "manjaro": manjaro_os_release,
    "fedora": fedora_os_release,
    "ubuntu": ubuntu_os_release,
}


def import_function(function, *args):
    """Import functions directly from the nvidia_driver_assistant package.

    This bypasses the historical `nvidia-driver-assistant.py` copy that
    tests/run creates, because that copy is fragile and can pick up the
    wrong file contents in CI.  The package is the single source of truth.
    """
    import nvidia_driver_assistant
    if not hasattr(nvidia_driver_assistant, function):
        raise AttributeError(
            "nvidia_driver_assistant package has no attribute '%s'. Available: %s"
            % (
                function,
                sorted(
                    k for k in dir(nvidia_driver_assistant) if not k.startswith("_")
                ),
            )
        )
    return getattr(nvidia_driver_assistant, function)(*args)


def import_class(klass, *args):
    """Import classes directly from the nvidia_driver_assistant package."""
    import nvidia_driver_assistant
    return getattr(nvidia_driver_assistant, klass)(*args)


def generate_fake_hardware():
    """Generate and return a UMockdev.Testbed object"""
    testbed = UMockdev.Testbed.new()
    testbed.add_device("acpi", "acpi_dev_1", None, ["modalias", "acpi:PNP0C14:"], [])
    testbed.add_device(
        "pci", "black", None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"], [],
    )
    testbed.add_device(
        "pci", "olive", None,
        ["modalias", "pci:v000010DEd000022BCsv000010DEsd000018FEbc04sc03i00"], [],
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


def _subprocess_env():
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root_dir + (":" + existing if existing else "")
    return env


class DetectTest(unittest.TestCase):
    """Test DriversAssistant.detect"""

    def setUp(self):
        self.umockdev = generate_fake_hardware()

    def run_driver_assistant(self, distro_id, json_file=None, additional_args=[]):
        """Invoke the CLI via the package entry point (bypasses the wrapper copy)."""
        os_release = generate_os_release(distro_id)
        args = [
            "--supported-gpus", get_json_file(json_file),
            "--sys-path", self.umockdev.get_sys_dir(),
            "--os-release-path", os_release.name,
        ]
        if additional_args:
            args.extend(additional_args)
        code = (
            "import sys; sys.argv = ['nvidia-driver-assistant'] + sys.argv[1:]; "
            "from nvidia_driver_assistant.cli import main; main()"
        )
        command = [sys.executable, "-c", code] + args
        assistant = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_subprocess_env()
        )
        return assistant.communicate()

    def _diagnose_stderr(self, stderr):
        if len(stderr) > 0:
            print("\n--- STDERR (%d bytes) ---\n%s--- END ---\n"
                  % (len(stderr), stderr.decode("utf-8", errors="replace")),
                  file=sys.stderr)

    def test_package_loads(self):
        """nvidia_driver_assistant package exposes all required symbols"""
        import nvidia_driver_assistant as nda
        required = ["override_distro", "get_distro", "recommend_driver",
                    "get_nvidia_devices", "get_system_modaliases", "process_results"]
        missing = [n for n in required if not hasattr(nda, n)]
        self.assertFalse(missing,
                         "nvidia_driver_assistant is missing: %s" % missing)

    def test_wrapper_script_exists(self):
        """The nvidia-driver-assistant wrapper exists and starts with a shebang"""
        wrapper = os.path.join(root_dir, "nvidia-driver-assistant")
        self.assertTrue(os.path.isfile(wrapper),
                        "Missing wrapper script: %s" % wrapper)
        with open(wrapper, "r") as f:
            first_line = f.readline().strip()
        self.assertTrue(first_line.startswith("#!"),
                        "Wrapper does not start with a shebang: %r" % first_line)

    def test_get_distro(self):
        """get_distro() for fake systems (Manjaro-only)"""
        release_file = tempfile.NamedTemporaryFile(
            mode="w", prefix="os_release_path_", delete=False
        )
        for distro in os_release_files.keys():
            content = os_release_files[distro]
            with open(release_file.name, "w") as stream:
                stream.write(content)
            system_info = import_function("get_distro", (release_file.name))
            if distro == "manjaro":
                self.assertTrue(system_info)
                self.assertTrue(distro in [system_info.id, system_info.original_id])
                self.assertTrue(system_info.version_id)
            else:
                self.assertFalse(system_info)

        content = ""
        with open(release_file.name, "w") as stream:
            stream.write(content)
        system_info = import_function("get_distro", (release_file.name))
        self.assertFalse(system_info)

        os.unlink(release_file.name)
        del release_file

    def test_distro_override(self):
        fake_id = "manjaro"
        system_info = import_function("override_distro", (fake_id))
        self.assertTrue(system_info)
        self.assertTrue(fake_id in [system_info.id, system_info.original_id])
        self.assertFalse(system_info.version_id)

        fake_id = "manjaro:24"
        system_info = import_function("override_distro", (fake_id))
        self.assertTrue(system_info)
        self.assertTrue(fake_id.split(":")[0] in [system_info.id, system_info.original_id])
        self.assertTrue(system_info.version_id)

    def test_get_system_modaliases(self):
        """Test get_system_modaliases() using our fake hardware"""
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_1", None, ["modalias", legacy_gpu_modalias_1], []
        )
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_2", None, ["modalias", legacy_gpu_modalias_2], []
        )
        modaliases = import_function("get_system_modaliases", (self.umockdev.get_sys_dir()))
        self.assertIn(gpu_modalias_1, modaliases)
        self.assertIn(legacy_gpu_modalias_1, modaliases)
        self.assertIn(legacy_gpu_modalias_2, modaliases)

    def test_get_nvidia_devices(self):
        """Test get_nvidia_devices()"""
        json_file = get_json_file()
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_1", None, ["modalias", legacy_gpu_modalias_1], []
        )
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_2", None, ["modalias", legacy_gpu_modalias_2], []
        )
        devices = import_function("get_nvidia_devices", *[self.umockdev.get_sys_dir(), json_file])
        self.assertFalse(not devices)
        self.assertTrue(len(devices) == 3)

    def test_driver_assistant_1(self):
        """Test driver assistant scenario 1 (Manjaro)"""
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        stdout, stderr = self.run_driver_assistant("manjaro")
        self._diagnose_stderr(stderr)
        self.assertEqual(len(stderr), 0)

    def test_driver_assistant_branch(self):
        """Test driver assistant --branch argument"""
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])

        stdout, stderr = self.run_driver_assistant("manjaro", additional_args=["--branch", "530"])
        self.assertTrue(len(stderr) > 0)

        stdout, stderr = self.run_driver_assistant("manjaro", additional_args=["--branch", "r560"])
        self.assertTrue(len(stderr) > 0)

        stdout, stderr = self.run_driver_assistant("manjaro", additional_args=["--branch", "560"])
        self._diagnose_stderr(stderr)
        self.assertEqual(len(stderr), 0)

        stdout, stderr = self.run_driver_assistant("manjaro", additional_args=["--branch", "575"])
        self._diagnose_stderr(stderr)
        self.assertEqual(len(stderr), 0)

    def test_driver_assistant_module_flavor(self):
        """Test driver assistant --module-flavor argument"""
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--module-flavor", "Fopen"]
        )
        self.assertTrue(len(stderr) > 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--module-flavor", "closedo"]
        )
        self.assertTrue(len(stderr) > 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--module-flavor", "open"]
        )
        self._diagnose_stderr(stderr)
        self.assertEqual(len(stderr), 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--module-flavor", "oPEn"]
        )
        self.assertEqual(len(stderr), 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--module-flavor", "closed"]
        )
        self.assertEqual(len(stderr), 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--module-flavor", "CloSed"]
        )
        self.assertEqual(len(stderr), 0)

    def _unpack_recommend_driver(self, result):
        if isinstance(result, (tuple, list)) and len(result) == 4:
            return result[0], result[1], result[2], result[3]
        else:
            return result[0], result[1], result[2], None

    def test_recommend_driver(self):
        """Test recommended_driver() using vdpau support hints"""
        json_file = get_json_file()
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        result = import_function("recommend_driver", *[self.umockdev.get_sys_dir(), json_file])
        driver, legacy_branch, unsupported, _ = self._unpack_recommend_driver(result)
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_1", None, ["modalias", legacy_gpu_modalias_1], []
        )
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_2", None, ["modalias", legacy_gpu_modalias_2], []
        )
        result = import_function("recommend_driver", *[self.umockdev.get_sys_dir(), json_file])
        driver, legacy_branch, unsupported, _ = self._unpack_recommend_driver(result)
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

    def test_recommend_driver_mod(self):
        """Test recommended_driver() using json driver support hints"""
        json_file = get_json_file("supported-gpus-mod.json")
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        result = import_function(
            "recommend_driver", *[self.umockdev.get_sys_dir(), json_file]
        )
        driver, legacy_branch, unsupported, _ = self._unpack_recommend_driver(result)
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_1", None, ["modalias", legacy_gpu_modalias_1], []
        )
        self.umockdev.add_device(
            "pci", "legacy_gpu_modalias_2", None, ["modalias", legacy_gpu_modalias_2], []
        )
        result = import_function(
            "recommend_driver", *[self.umockdev.get_sys_dir(), json_file]
        )
        driver, legacy_branch, unsupported, _ = self._unpack_recommend_driver(result)
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

    def test_process_results(self):
        """Test instruction printing (Manjaro-only)"""
        json_file = get_json_file("supported-gpus-mod.json")
        self.umockdev.add_device("pci", "gpu_modalias_1", None, ["modalias", gpu_modalias_1], [])
        result = import_function(
            "recommend_driver", *[self.umockdev.get_sys_dir(), json_file]
        )
        driver, legacy_branch, unsupported, _ = self._unpack_recommend_driver(result)
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        results = import_function("process_results", *[driver, "manjaro", "25.0", None, None])
        self.assertTrue(results)

        results = import_function("process_results", *[driver, "manjaro", "25.0", "580", None])
        self.assertTrue(results)


if __name__ == "__main__":
    print("Please run as follows, instead of running this file directly:", file=sys.stderr)
    print("PYTHONPATH=. tests/run --suite %s" % (os.path.basename(__file__)), file=sys.stderr)
    exit(1)