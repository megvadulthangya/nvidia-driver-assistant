"""Hardware detection functions for PCI devices."""

import os
import logging


def get_system_modaliases(sys_path=None):
    """Get the dictionary of system modaliases and their sysfs paths."""
    modaliases = {}
    devices = "/sys/devices" if not sys_path else "%s/devices" % sys_path

    for path, dirs, files in os.walk(devices):
        if "modalias" not in files:
            continue

        try:
            with open(os.path.join(path, "modalias")) as file:
                modalias = file.read().strip()
        except IOError as exc:
            logging.debug(
                "get_system_modaliases(): failed to read %s/modalias: %s",
                path,
                exc,
            )
            continue

        if not modalias:
            continue

        driver_path = os.path.join(path, "driver")
        module_path = os.path.join(driver_path, "module")

        if os.path.islink(driver_path) and not os.path.islink(module_path):
            continue

        modaliases[modalias] = path

    return modaliases


def get_pci_device_info(dev_path):
    """Get PCI device information from a sysfs path."""
    info = {}

    try:
        with open(os.path.join(dev_path, "vendor"), "r") as stream:
            vendor = stream.read().strip()

        with open(os.path.join(dev_path, "device"), "r") as stream:
            device = stream.read().strip()

        subsys_vendor_path = os.path.join(dev_path, "subsystem_vendor")
        subsys_device_path = os.path.join(dev_path, "subsystem_device")

        if os.path.exists(subsys_vendor_path):
            with open(subsys_vendor_path, "r") as stream:
                info["subsystem_vendor"] = stream.read().strip()

        if os.path.exists(subsys_device_path):
            with open(subsys_device_path, "r") as stream:
                info["subsystem_device"] = stream.read().strip()

        info["vendor"] = vendor
        info["device"] = device

    except Exception as exc:
        logging.debug(
            "get_pci_device_info(): Failed to read device info from %s: %s",
            dev_path,
            exc,
        )

    return info
