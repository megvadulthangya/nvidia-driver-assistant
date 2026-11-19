import pathlib
import tempfile
import unittest
from unittest.mock import patch

import nvidia_driver_assistant.device as device_module
import nvidia_driver_assistant.recommendation as recommendation_module

from nvidia_driver_assistant.device import Device
from nvidia_driver_assistant import supported_chips


LATEST_HTML = """\
<p><a name="Current" id="Current"></a></p>
<h3>Current NVIDIA GPUs</h3>
<table>
  <tr id="devid2D98"><td>GeForce RTX example</td></tr>
  <tr id="devid1340"><td>GeForce legacy overlap example</td></tr>
</table>
<p><a name="legacy_580.xx" id="legacy_580.xx"></a></p>
<table><tr id="devid1340"><td>GeForce 830M</td></tr></table>
<p><a name="legacy_470.xx" id="legacy_470.xx"></a></p>
<table><tr id="devid0FC6"><td>GeForce GTX 650</td></tr></table>
<p><a name="legacy_173.14.xx" id="legacy_173.14.xx"></a></p>
<table><tr id="devid00C2"><td>Legacy GPU</td></tr></table>
"""


SUPPORTED_580_HTML = """\
<p><a name="Current" id="Current"></a></p>
<h3>Current NVIDIA GPUs</h3>
<table>
  <tr id="devid1340"><td>GeForce 830M</td></tr>
  <tr id="devid2D98_17AA_3E31"><td>GeForce RTX example subsystem variant</td></tr>
</table>
<p><a name="legacy_470.xx" id="legacy_470.xx"></a></p>
<table><tr id="devid1340"><td>Unrelated old-driver section</td></tr></table>
"""


class SupportedChipsParserTests(unittest.TestCase):

    def _write_temp(self, directory, filename, content):
        path = pathlib.Path(directory) / filename
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_latest_document_maps_current_and_legacy_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_temp(
                tmpdir,
                "supportedchips.html",
                LATEST_HTML,
            )
            branch_map = supported_chips.parse(path)

        self.assertEqual(branch_map["2d98"], "current")
        self.assertEqual(branch_map["1340"], "580")
        self.assertEqual(branch_map["0fc6"], "470")
        self.assertEqual(branch_map["00c2"], "173")

    def test_580_current_only_ignores_later_legacy_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_temp(
                tmpdir,
                "supportedchips580.html",
                SUPPORTED_580_HTML,
            )
            current_ids = supported_chips.parse_current(path)

        self.assertEqual(current_ids, {"1340", "2d98"})

    def test_subsystem_variants_reduce_to_base_device_id(self):
        rows = supported_chips.parse_html(SUPPORTED_580_HTML)

        self.assertIn(
            "2d98",
            {row["device_id"] for row in rows},
        )

    def test_legacy_entry_wins_over_duplicate_current_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_temp(
                tmpdir,
                "supportedchips.html",
                LATEST_HTML,
            )
            branch_map = supported_chips.parse(path)

        self.assertEqual(branch_map["1340"], "580")

    def test_build_validation_requires_both_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            latest_path = self._write_temp(
                tmpdir,
                "supportedchips.html",
                LATEST_HTML,
            )
            chips580_path = self._write_temp(
                tmpdir,
                "supportedchips580.html",
                SUPPORTED_580_HTML,
            )

            latest, current580 = supported_chips.validate_documents(
                latest_path,
                chips580_path,
            )

        self.assertEqual(latest["1340"], "580")
        self.assertEqual(latest["2d98"], "current")
        self.assertEqual(current580, {"1340", "2d98"})

    def test_empty_or_unrecognized_html_is_rejected(self):
        self.assertIsNone(
            supported_chips.parse_html(
                "<html><body>not an NVIDIA list</body></html>"
            )
        )


class DeviceClassificationTests(unittest.TestCase):

    def _make_device(
        self,
        device_id,
        name,
        features,
        legacy_branch,
        latest_map,
        current580,
    ):
        with patch.object(
            device_module,
            "SUPPORTED_CHIPS",
            latest_map,
        ):
            with patch.object(
                device_module,
                "SUPPORTED_CHIPS_580",
                current580,
            ):
                return Device(
                    device_id,
                    name,
                    features,
                    legacy_branch,
                )

    def test_legacy_580_forces_closed_despite_kernelopen_json_flag(self):
        dev = self._make_device(
            "0x1380",
            "GeForce GTX 750 Ti",
            ["kernelopen"],
            "580.xx",
            {"1380": "580"},
            {"1380"},
        )

        self.assertEqual(dev.original_legacy_branch, "580.xx")
        self.assertEqual(dev.legacy_int, 580)
        self.assertEqual(dev.driver_hint, "proprietary_required")
        self.assertFalse(dev.supports_latest_6xx)
        self.assertTrue(dev.supports_580)

    def test_json_legacybranch_remains_authoritative(self):
        dev = self._make_device(
            "0x1340",
            "GeForce 830M",
            ["kernelopen"],
            "580.xx",
            {"1340": "current"},
            {"1340"},
        )

        self.assertEqual(dev.original_legacy_branch, "580.xx")
        self.assertEqual(dev.legacy_int, 580)
        self.assertFalse(dev.supports_latest_6xx)
        self.assertEqual(dev.driver_hint, "proprietary_required")

    def test_html_legacy_branch_fills_missing_json_legacybranch(self):
        dev = self._make_device(
            "0x0fc6",
            "GeForce GTX 650",
            [],
            None,
            {"0fc6": "470"},
            set(),
        )

        self.assertEqual(dev.original_legacy_branch, "470.xx")
        self.assertEqual(dev.legacy_int, 470)
        self.assertEqual(dev.driver_hint, "proprietary_required")

    def test_latest_current_gpu_requires_open_kernel_module(self):
        dev = self._make_device(
            "0x2d98",
            "GeForce RTX example",
            [],
            None,
            {"2d98": "current"},
            set(),
        )

        self.assertTrue(dev.supports_latest_6xx)
        self.assertFalse(dev.supports_580)
        self.assertEqual(dev.driver_hint, "open_required")

    def test_580_compatibility_is_based_only_on_580_current_membership(self):
        dev = self._make_device(
            "0x2d98",
            "GeForce RTX example",
            ["kernelopen"],
            None,
            {"2d98": "current"},
            {"2d98"},
        )

        self.assertTrue(dev.supports_latest_6xx)
        self.assertTrue(dev.supports_580)


class Mixed580And6xxRecommendationTests(unittest.TestCase):

    def _make_devices(self, current580):
        latest_map = {
            "1380": "580",
            "2d18": "current",
        }

        legacy_gpu = Device(
            "0x1380",
            "GeForce GTX 750 Ti",
            ["kernelopen"],
            "580.xx",
        )
        modern_gpu = Device(
            "0x2d18",
            "GeForce RTX 5070",
            ["kernelopen"],
            None,
        )

        with patch.object(
            device_module,
            "SUPPORTED_CHIPS",
            latest_map,
        ):
            with patch.object(
                device_module,
                "SUPPORTED_CHIPS_580",
                current580,
            ):
                legacy_gpu = Device(
                    "0x1380",
                    "GeForce GTX 750 Ti",
                    ["kernelopen"],
                    "580.xx",
                )
                modern_gpu = Device(
                    "0x2d18",
                    "GeForce RTX 5070",
                    ["kernelopen"],
                    None,
                )

        return {
            "0x1380": legacy_gpu,
            "0x2d18": modern_gpu,
        }, legacy_gpu

    def test_common_580_driver_selected_when_every_gpu_is_580_current(self):
        devices, legacy_gpu = self._make_devices(
            {"1380", "2d18"}
        )

        with patch.object(
            recommendation_module,
            "get_nvidia_devices",
            return_value=devices,
        ):
            driver, branch, unsupported, detected = (
                recommendation_module.recommend_driver(
                    supported_gpus="unused",
                    suppress_warnings=True,
                )
            )

        self.assertEqual(driver, "closed")
        self.assertEqual(branch, "580")
        self.assertEqual(unsupported, [])
        self.assertIs(detected["0x1380"], legacy_gpu)

    def test_latest_6xx_prioritised_when_gpu_is_not_580_current(self):
        devices, legacy_gpu = self._make_devices(
            {"1380"}
        )

        with patch.object(
            recommendation_module,
            "get_nvidia_devices",
            return_value=devices,
        ):
            driver, branch, unsupported, detected = (
                recommendation_module.recommend_driver(
                    supported_gpus="unused",
                    suppress_warnings=True,
                )
            )

        self.assertEqual(driver, "open")
        self.assertIsNone(branch)
        self.assertIn(legacy_gpu, unsupported)
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(
            detected["0x2d18"].nvidia_supported_branch,
            "current",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
