#!/usr/bin/env python3

"""Tests for the per-device MHWD NVIDIA branch lookup."""

import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from nvidia_driver_assistant.cli import _resolve_mhwd_branch, main


class MhwdBranchSelectionTests(unittest.TestCase):

    def test_legacy_branch_lookup(self):
        supported_chips = {
            "0dc4": "390",
            "1380": "580",
        }

        with patch(
            "nvidia_driver_assistant.supported_chips.SUPPORTED_CHIPS",
            supported_chips,
        ):
            self.assertEqual(_resolve_mhwd_branch("0dc4"), "390")
            self.assertEqual(_resolve_mhwd_branch("0DC4"), "390")
            self.assertEqual(_resolve_mhwd_branch("0x0dc4"), "390")
            self.assertEqual(_resolve_mhwd_branch("1380"), "580")

    def test_current_branch_lookup(self):
        with patch(
            "nvidia_driver_assistant.supported_chips.SUPPORTED_CHIPS",
            {"2783": "current"},
        ):
            self.assertEqual(_resolve_mhwd_branch("2783"), "current")

    def test_unknown_or_invalid_device_id(self):
        with patch(
            "nvidia_driver_assistant.supported_chips.SUPPORTED_CHIPS",
            {"0dc4": "390"},
        ):
            self.assertIsNone(_resolve_mhwd_branch("1234"))
            self.assertIsNone(_resolve_mhwd_branch("not-a-pci-id"))
            self.assertIsNone(_resolve_mhwd_branch("0x123456"))
            self.assertIsNone(_resolve_mhwd_branch(""))

    def test_missing_supportedchips_data(self):
        with patch(
            "nvidia_driver_assistant.supported_chips.SUPPORTED_CHIPS",
            None,
        ):
            self.assertIsNone(_resolve_mhwd_branch("0dc4"))

    def test_mhwd_branch_cli_output(self):
        output = StringIO()

        with patch(
            "nvidia_driver_assistant.supported_chips.SUPPORTED_CHIPS",
            {"0dc4": "390"},
        ):
            with patch.object(
                sys,
                "argv",
                [
                    "nvidia-driver-assistant",
                    "--mhwd-branch",
                    "--mhwd-device-id",
                    "0dc4",
                ],
            ):
                with redirect_stdout(output):
                    with self.assertRaises(SystemExit) as result:
                        main()

        self.assertEqual(result.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "390")

    def test_mhwd_branch_cli_unknown_device(self):
        output = StringIO()

        with patch(
            "nvidia_driver_assistant.supported_chips.SUPPORTED_CHIPS",
            {"0dc4": "390"},
        ):
            with patch.object(
                sys,
                "argv",
                [
                    "nvidia-driver-assistant",
                    "--mhwd-branch",
                    "--mhwd-device-id",
                    "1234",
                ],
            ):
                with redirect_stdout(output):
                    with self.assertRaises(SystemExit) as result:
                        main()

        self.assertEqual(result.exception.code, 1)
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
