"""Hardware detection functions for PCI devices."""

import os
import logging
import subprocess


def get_system_modaliases(sys_path=None):
    """Get a dictionary with modaliases and paths in the system"""
    modaliases = {}
    devices = "/sys/devices" if not sys_path else "%s/devices" % (sys_path)
    for path, dirs, files in os.walk(devices):
        modalias = None
        if "modalias" in files:
            try:
                with open(os.path.join(path, "modalias")) as file:
                    modalias = file.read().strip()
            except IOError as e:
                logging.debug("get_system_modaliases(): failed to read %s/modalias: %s", path, e)
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
    """Get PCI device information from sysfs path"""
    info = {}
    try:
        with open(os.path.join(dev_path, "vendor"), "r") as f:
            vendor = f.read().strip()
        with open(os.path.join(dev_path, "device"), "r") as f:
            device = f.read().strip()

        subsys_vendor_path = os.path.join(dev_path, "subsystem_vendor")
        subsys_device_path = os.path.join(dev_path, "subsystem_device")

        if os.path.exists(subsys_vendor_path):
            with open(subsys_vendor_path, "r") as f:
                subsys_vendor = f.read().strip()
            info["subsystem_vendor"] = subsys_vendor

        if os.path.exists(subsys_device_path):
            with open(subsys_device_path, "r") as f:
                subsys_device = f.read().strip()
            info["subsystem_device"] = subsys_device

        info["vendor"] = vendor
        info["device"] = device

    except Exception as e:
        logging.debug(f"get_pci_device_info(): Failed to read device info from {dev_path}: {e}")

    return info


def is_laptop_system():
    """Determine if the system is a laptop"""
    try:
        chassis_type_path = "/sys/class/dmi/id/chassis_type"
        if os.path.exists(chassis_type_path):
            with open(chassis_type_path, "r") as f:
                chassis_type = f.read().strip()
                if chassis_type in ["8", "9", "10", "11", "14"]:
                    return True

        if os.path.exists("/sys/class/power_supply/BAT0"):
            return True

        try:
            result = subprocess.run(
                ["dmidecode", "-s", "chassis-type"],
                capture_output=True,
                text=True,
                errors='replace',
                timeout=2
            )
            if result.returncode == 0:
                chassis_type = result.stdout.strip().lower()
                if any(word in chassis_type for word in ["laptop", "notebook", "portable", "hand"]):
                    return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    except Exception as e:
        logging.debug(f"is_laptop_system(): Could not determine system type: {e}")

    return False
