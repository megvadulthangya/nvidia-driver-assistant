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

# ---------------------------------------------------------------------------
# GPU modalias constants used throughout the tests
#   gpu_a  0x2783  RTX 4070 SUPER          ada        modern, open-capable
#   gpu_b  0x1D81  TITAN V                 volta      580.xx legacy
#   gpu_c  0x00C2  GeForce 6800 LE         pre-curie  304.xx unsupported
#   gpu_d  0x0FC6  GeForce GTX 650         kepler     470.xx unsupported
#   gpu_e  0x06C0  GeForce GTX 480         fermi      390.xx unsupported
#   gpu_f  0x1B06  GeForce GTX 1080 Ti     pascal     580.xx legacy
#   gpu_g  0x1DBA  Quadro GV100            volta      580.xx legacy
#   gpu_h  0x1380  GeForce GTX 750 Ti      maxwell    580.xx legacy
# ---------------------------------------------------------------------------
gpu_a = "pci:v000010DEd00002783sv000010DEsd000018FEbc03sc00i00"
gpu_b = "pci:v000010DEd00001D81sv000010DEsd000018FEbc03sc00i00"
gpu_c = "pci:v000010DEd000000C2sv000010DEsd000018FEbc03sc00i00"
gpu_d = "pci:v000010DEd00000FC6sv000010DEsd000018FEbc03sc00i00"
gpu_e = "pci:v000010DEd000006C0sv000010DEsd000018FEbc03sc00i00"
gpu_f = "pci:v000010DEd00001B06sv000010DEsd000018FEbc03sc00i00"
gpu_g = "pci:v000010DEd00001DBAsv000010DEsd000018FEbc03sc00i00"
gpu_h = "pci:v000010DEd00001380sv000010DEsd000018FEbc03sc00i00"


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
        "pci", "black", None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"], [],
    )
    testbed.add_device(
        "pci", "white", None,
        ["modalias", "pci:v00001022d000014E3sv00000000sd00000000bc06sc00i00"], [],
    )
    testbed.add_device(
        "pci", "red", None,
        ["modalias", "pci:v0000144Dd0000A808sv0000144Dsd0000A801bc01sc08i02"], [],
    )
    testbed.add_device(
        "pci", "blue", None,
        ["modalias", "pci:v00001022d000014E1sv00000000sd00000000bc06sc00i00"], [],
    )
    testbed.add_device(
        "pci", "magenta", None,
        ["modalias", "pci:v00001022d000014DAsv00000000sd00000000bc06sc00i00"], [],
    )
    testbed.add_device(
        "pci", "navy", None,
        ["modalias", "pci:v00001022d0000790Esv00001462sd00007E26bc06sc01i00"], [],
    )
    testbed.add_device("pci", "pink", None, ["modalias", "acpi:PNP0800:"], [])
    testbed.add_device(
        "pci", "olive", None,
        ["modalias", "pci:v000010DEd000022BCsv000010DEsd000018FEbc04sc03i00"], [],
    )
    testbed.add_device(
        "usb", "usb_dev_1", None,
        ["modalias", "usb:v0E8Dp0616d0100dcEFdsc02dp01icE0isc01ip01in02"], [],
    )
    testbed.add_device(
        "hdaudio", "audio_dev_1", None,
        ["modalias", "hdaudio:v10EC0897r00100500a01"], []
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
        self.umockdev = generate_fake_hardware()

    def run_driver_assistant(self, distro_id, json_file=None, additional_args=[], testbed=None):
        if testbed is None:
            testbed = self.umockdev
        os_release = generate_os_release(distro_id)
        command = [
            "%s/nvidia-driver-assistant" % root_dir,
            "--supported-gpus", get_json_file(json_file),
            "--sys-path", testbed.get_sys_dir(),
            "--os-release-path", os_release.name,
        ]
        if additional_args:
            command.extend(additional_args)
        assistant = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return assistant.communicate()

    def _load_main_module(self):
        filename = "nvidia-driver-assistant.py"
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, filename))
        spec = importlib.util.spec_from_file_location("nvidia_driver_assistant", script_path)
        nda = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nda)
        return nda

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
        self.umockdev.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        self.umockdev.add_device("pci", "gpu_c", None, ["modalias", gpu_c], [])
        self.umockdev.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])
        modaliases = import_function("get_system_modaliases", (self.umockdev.get_sys_dir()))
        self.assertIn(gpu_a, modaliases)
        self.assertIn(gpu_c, modaliases)
        self.assertIn(gpu_d, modaliases)

    def test_get_nvidia_devices(self):
        """Test get_nvidia_devices()"""
        testbed = generate_fake_hardware()
        json_file = get_json_file()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        testbed.add_device("pci", "gpu_c", None, ["modalias", gpu_c], [])
        testbed.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])
        devices = import_function("get_nvidia_devices", *[testbed.get_sys_dir(), json_file])
        self.assertFalse(not devices)
        self.assertTrue(len(devices) == 3)

    def test_driver_assistant_1(self):
        """Test driver assistant scenario 1 (Manjaro)"""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        stdout, stderr = self.run_driver_assistant("manjaro", testbed=testbed)
        self.assertEqual(len(stderr), 0)

    def test_driver_assistant_branch(self):
        """Test driver assistant --branch argument"""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--branch", "530"], testbed=testbed
        )
        self.assertTrue(len(stderr) > 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--branch", "r560"], testbed=testbed
        )
        self.assertTrue(len(stderr) > 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--branch", "560"], testbed=testbed
        )
        self.assertEqual(len(stderr), 0)

        stdout, stderr = self.run_driver_assistant(
            "manjaro", additional_args=["--branch", "575"], testbed=testbed
        )
        self.assertEqual(len(stderr), 0)

    def _check_module_flavor(self, distro_id):
        """Shared helper: validates --module-flavor accept/reject on a given distro."""
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        for bad in ("Fopen", "closedo"):
            stdout, stderr = self.run_driver_assistant(
                distro_id, additional_args=["--module-flavor", bad], testbed=testbed
            )
            self.assertTrue(len(stderr) > 0,
                            f"--module-flavor {bad!r} should be rejected on {distro_id}")
        for good in ("open", "oPEn", "closed", "CloSed"):
            stdout, stderr = self.run_driver_assistant(
                distro_id, additional_args=["--module-flavor", good], testbed=testbed
            )
            self.assertEqual(len(stderr), 0,
                             f"--module-flavor {good!r} should be accepted on {distro_id}")

    def test_driver_assistant_module_flavor(self):
        """Test --module-flavor accept/reject on manjaro"""
        self._check_module_flavor("manjaro")

    # -----------------------------------------------------------------
    # Mixed-GPU CLI tests
    # -----------------------------------------------------------------

    def _extract_json(self, raw_stdout):
        text = raw_stdout.decode("utf-8", errors="replace")
        json_start = text.index("{")
        json_end = text.rindex("}") + 1
        return json.loads(text[json_start:json_end])

    def test_simulate_mixed(self):
        """CLI end-to-end: --simulate-mixed (manjaro only)"""
        test_distros = ["manjaro"]

        for distro in test_distros:
            with self.subTest(distro=distro):
                command = [
                    "%s/nvidia-driver-assistant" % root_dir,
                    "--supported-gpus", get_json_file(),
                    "--distro", distro,
                    "--simulate-mixed", "--json",
                ]
                proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate()
                self.assertEqual(len(stderr), 0, f"stderr not empty on {distro}: {stderr}")
                result = self._extract_json(stdout)

                self.assertEqual(
                    result["module_flavor"], "closed",
                    f"[{distro}] Mixed 580+modern must recommend 'closed'. Got: {result['module_flavor']!r}"
                )
                self.assertEqual(
                    result["branch"], "580",
                    f"[{distro}] Branch must be locked to '580'. Got: {result['branch']!r}"
                )
                self.assertEqual(
                    len(result["devices"]), 2,
                    f"[{distro}] Both GPUs must be present. Got: {len(result['devices'])}"
                )

    def test_simulate_badmix(self):
        """CLI end-to-end: --simulate-badmix (manjaro only)"""
        test_distros = ["manjaro"]

        for distro in test_distros:
            with self.subTest(distro=distro):
                command = [
                    "%s/nvidia-driver-assistant" % root_dir,
                    "--supported-gpus", get_json_file(),
                    "--distro", distro,
                    "--simulate-badmix", "--json",
                ]
                proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate()
                self.assertEqual(len(stderr), 0, f"stderr not empty on {distro}: {stderr}")
                result = self._extract_json(stdout)

                self.assertEqual(
                    result["module_flavor"], "open",
                    f"[{distro}] Badmix must recommend 'open'. Got: {result['module_flavor']!r}"
                )
                self.assertIsNone(
                    result["branch"],
                    f"[{distro}] No branch lock expected. Got: {result['branch']!r}"
                )
                self.assertEqual(
                    len(result["devices"]), 2,
                    f"[{distro}] Both GPUs must be listed. Got: {len(result['devices'])}"
                )

    # -----------------------------------------------------------------
    # recommend_driver() API-level tests
    # -----------------------------------------------------------------

    def test_recommend_driver(self):
        """API test: recommend_driver() with modern GPU alone, then with sub-580 legacy GPUs"""
        nda = self._load_main_module()
        json_file = get_json_file()
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        testbed.add_device("pci", "gpu_c", None, ["modalias", gpu_c], [])
        testbed.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])
        result2 = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result2) == 4:
            driver2, legacy_branch2, unsupported2, open_kernel2 = result2
        else:
            driver2, legacy_branch2, unsupported2 = result2
        self.assertTrue(driver2)
        self.assertEqual(driver2, "open")

    def test_recommend_driver_mod(self):
        """API test: recommend_driver() with supported-gpus-mod.json"""
        json_file = get_json_file("supported-gpus-mod.json")
        if not os.path.isfile(json_file):
            self.skipTest("supported-gpus-mod.json not found")

        nda = self._load_main_module()
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_a", None, ["modalias", gpu_a], [])
        result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
        self.assertTrue(driver)
        self.assertEqual(driver, "open")

        testbed.add_device("pci", "gpu_b", None, ["modalias", gpu_b], [])
        result2 = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result2) == 4:
            driver2, legacy_branch2, unsupported2, open_kernel2 = result2
        else:
            driver2, legacy_branch2, unsupported2 = result2
        self.assertTrue(driver2)
        self.assertEqual(driver2, "open")

    def test_recommend_driver_legacy_580(self):
        """API test: recommend_driver() with three 580.xx legacy GPUs"""
        nda = self._load_main_module()
        json_file = get_json_file()
        testbed = generate_fake_hardware()
        testbed.add_device("pci", "gpu_f", None, ["modalias", gpu_f], [])
        testbed.add_device("pci", "gpu_g", None, ["modalias", gpu_g], [])
        testbed.add_device("pci", "gpu_h", None, ["modalias", gpu_h], [])
        result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
        if len(result) == 4:
            driver, legacy_branch, unsupported, open_kernel = result
        else:
            driver, legacy_branch, unsupported = result
        self.assertTrue(driver)
        if legacy_branch is not None:
            self.assertIn(legacy_branch, ["580", "580.xx"])

    def test_malformed_json_legacy_open_kernel(self):
        """Resilience test: malformed JSON (single quotes, trailing commas)"""
        nda = self._load_main_module()
        testbed = generate_fake_hardware()
        bad_json_file = os.path.join(root_dir, "supported-gpus-bad", "supported-gpus.json")
        testbed.add_device("pci", "gpu_d", None, ["modalias", gpu_d], [])
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
        """Matrix test: process_results() for every GPU × manjaro"""
        json_file = get_json_file("supported-gpus-mod.json")
        if not os.path.isfile(json_file):
            self.skipTest("supported-gpus-mod.json not found")

        nda = self._load_main_module()
        gpu_list = [gpu_a, gpu_b, gpu_c, gpu_d, gpu_e, gpu_f, gpu_g, gpu_h]

        with patch('nvidia_driver_assistant.recommendation.ubuntu_get_latest_driver_branch', return_value='575'):
            for gpu_mod in gpu_list:
                testbed = generate_fake_hardware()
                testbed.add_device("pci", "gpu_under_test", None, ["modalias", gpu_mod], [])
                result = nda.recommend_driver(testbed.get_sys_dir(), json_file)
                driver = result[0] if result else None
                self.assertIsNotNone(driver, f"No driver recommended for GPU {gpu_mod}")

                for distro_key in os_release_files:
                    with self.subTest(gpu=gpu_mod, distro=distro_key):
                        release_file = generate_os_release(distro_key)
                        system_info = nda.get_distro(release_file.name)
                        if not system_info:
                            os.unlink(release_file.name)
                            continue
                        version = system_info.version_id if system_info.version_id else "10.0"
                        for branch in (None, "580"):
                            results = nda.process_results(driver, system_info.id, version, branch, None)
                            self.assertTrue(results,
                                            f"process_results failed for GPU {gpu_mod} "
                                            f"on {distro_key} version {version} branch {branch}")
                        os.unlink(release_file.name)


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
