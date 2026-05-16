"""GPU database loading, validation, and device matching."""

import os
import re
import json
import logging
import sys

from .config import default
from .device import Device
from .hardware import get_system_modaliases, get_pci_device_info, is_laptop_system


# Enhanced simulated GPU data with more detailed information
simulated_gpus = {
    "545": {
        "modalias": "pci:v000010DEd00001241sv000010DEsd000018FEbc03sc00i00",
        "expected_name": "GeForce 545",
        "expected_devid": "0x1241"
    },
    "nvs290": {
        "modalias": "pci:v000010DEd0000042Fsv000010DEsd00000000bc03sc00i00",
        "expected_name": "Quadro NVS 290",
        "expected_devid": "0x042F"
    },
    "7150m": {
        "modalias": "pci:v000010DEd00000531sv000010DEsd00000000bc03sc00i00",
        "expected_name": "GeForce 7150M / nForce 630M",
        "expected_devid": "0x0531"
    },
    "740A": {
        "modalias": "pci:v000010DEd00001292sv000010DEsd000018FEbc03sc00i00",
        "expected_name": "GeForce 740A",
        "expected_devid": "0x1292"
    },
    "750": {
        "modalias": "pci:v000010DEd00001380sv000010DEsd000018FEbc03sc00i00",
        "expected_name": "NVIDIA GeForce GTX 750 Ti",
        "expected_devid": "0x1380"
    },
    "800A": {
        "modalias": "pci:v000010DEd00001058sv000017AAsd00003682bc03sc00i00",
        "expected_name": "GeForce 800A",
        "expected_devid": "0x1058",
        "expected_subsys_vendor": "0x17AA",
        "expected_subsys_device": "0x3682"
    },
    "4070": {
        "modalias": "pci:v000010DEd00002783sv000010DEsd000018FEbc03sc00i00",
        "expected_name": "GeForce RTX 4070",
        "expected_devid": "0x2783"
    },
    "5070": {
        "modalias": "pci:v000010DEd00002D18sv000017AAsd00003E31bc03sc00i00",
        "expected_name": "GeForce RTX 5070",
        "expected_devid": "0x2D18"
    },
    "unknown": {
        "modalias": "pci:v000010DEd000022BCsv000010DEsd000018FEbc04sc03i00",
        "expected_name": "unknown",
        "expected_devid": "0x22BC"
    },
    "mixed": [
        {
            "modalias": "pci:v000010DEd00001380sv000010DEsd000018FEbc03sc00i00",
            "expected_name": "NVIDIA GeForce GTX 750 Ti",
            "expected_devid": "0x1380"
        },
        {
            "modalias": "pci:v000010DEd00002D18sv000017AAsd00003E31bc03sc00i00",
            "expected_name": "GeForce RTX 5070",
            "expected_devid": "0x2D18"
        },
    ],
    "badmix": [
        {
            "modalias": "pci:v000010DEd00001292sv000010DEsd000018FEbc03sc00i00",
            "expected_name": "GeForce 740A",
            "expected_devid": "0x1292"
        },
        {
            "modalias": "pci:v000010DEd00002D18sv000017AAsd00003E31bc03sc00i00",
            "expected_name": "GeForce RTX 5070",
            "expected_devid": "0x2D18"
        },
    ],
}


def select_best_gpu_match(matching_gpus, pci_info=None, suppress_warnings=False):
    """Select the best GPU match from multiple possibilities

    Selection logic (in order of priority):
    1. Match by subsystem vendor and device ID (most specific)
    2. Match by subsystem vendor only
    3. If simulating, try to match by expected name
    4. Match laptop GPU with laptop system, desktop GPU with desktop system
    5. Has legacybranch field (more specific)
    6. Has more features (more detailed information)
    7. Name contains fewer "unknown" or generic terms
    8. Original order (fallback)
    """
    if len(matching_gpus) == 1:
        return matching_gpus[0]

    logging.debug(f"select_best_gpu_match(): Found {len(matching_gpus)} matching GPUs")
    all_matching_names = [gpu["name"] for gpu in matching_gpus]
    selected_gpu = None

    # 1. Match by exact subsystem vendor and device
    if pci_info and 'subsystem_vendor' in pci_info and 'subsystem_device' in pci_info:
        subsys_vendor_hex = pci_info.get('subsystem_vendor')
        subsys_device_hex = pci_info.get('subsystem_device')
        for gpu in matching_gpus:
            gpu_subsys_vendor = gpu.get("subvendorid")
            gpu_subsys_device = gpu.get("subdevid")
            if gpu_subsys_vendor and gpu_subsys_device:
                gpu_vendor_norm = gpu_subsys_vendor.lower().replace("0x", "")
                gpu_device_norm = gpu_subsys_device.lower().replace("0x", "")
                pci_vendor_norm = subsys_vendor_hex.lower().replace("0x", "")
                pci_device_norm = subsys_device_hex.lower().replace("0x", "")
                if gpu_vendor_norm == pci_vendor_norm and gpu_device_norm == pci_device_norm:
                    logging.debug(f"select_best_gpu_match(): Exact subsystem match: {gpu['name']}")
                    selected_gpu = gpu
                    break

    # 2. Match by subsystem vendor only
    if not selected_gpu and pci_info and 'subsystem_vendor' in pci_info:
        subsys_vendor_hex = pci_info.get('subsystem_vendor')
        for gpu in matching_gpus:
            gpu_subsys_vendor = gpu.get("subvendorid")
            if gpu_subsys_vendor:
                gpu_vendor_norm = gpu_subsys_vendor.lower().replace("0x", "")
                pci_vendor_norm = subsys_vendor_hex.lower().replace("0x", "")
                if gpu_vendor_norm == pci_vendor_norm:
                    logging.debug(f"select_best_gpu_match(): Subsystem vendor match: {gpu['name']}")
                    selected_gpu = gpu
                    break

    # 3. Simulated name match
    if not selected_gpu:
        simulate_gpu = pci_info.get('simulate_gpu') if pci_info else None
        if simulate_gpu and simulate_gpu in simulated_gpus:
            expected_name = simulated_gpus[simulate_gpu]["expected_name"]
            for gpu in matching_gpus:
                if expected_name.lower() in gpu["name"].lower():
                    logging.debug(f"select_best_gpu_match(): Simulated name match: '{expected_name}' -> '{gpu['name']}'")
                    selected_gpu = gpu
                    break

    # 4. Laptop vs desktop system matching
    if not selected_gpu:
        is_laptop_system_val = is_laptop_system()
        mobile_gpus = []
        desktop_gpus = []
        for gpu in matching_gpus:
            temp_device = Device(gpu["devid"], gpu["name"], gpu.get("features", []),
                                 gpu.get("legacybranch"), gpu.get("subvendorid"), gpu.get("subdevid"))
            if temp_device.is_laptop_gpu:
                mobile_gpus.append(gpu)
            else:
                desktop_gpus.append(gpu)

        if is_laptop_system_val and mobile_gpus:
            matching_gpus = mobile_gpus[:]
            logging.debug("select_best_gpu_match(): Laptop system detected, prioritizing mobile GPUs")
        elif not is_laptop_system_val and desktop_gpus:
            matching_gpus = desktop_gpus[:]
            logging.debug("select_best_gpu_match(): Desktop system detected, prioritizing desktop GPUs")

        if len(matching_gpus) == 1:
            selected_gpu = matching_gpus[0]

    # 5. Prefer entries with legacybranch (more specific)
    if not selected_gpu:
        with_legacy = [g for g in matching_gpus if g.get("legacybranch")]
        if with_legacy:
            matching_gpus = with_legacy
            if len(matching_gpus) == 1:
                selected_gpu = matching_gpus[0]

    # 6. Prefer entries with more features
    if not selected_gpu:
        max_features = max(len(g.get("features", [])) for g in matching_gpus)
        with_max_features = [g for g in matching_gpus if len(g.get("features", [])) == max_features]
        if len(with_max_features) == 1:
            selected_gpu = with_max_features[0]
        else:
            # 7. Name specificity score
            def name_specificity_score(name):
                name_lower = name.lower()
                score = 100
                if "unknown" in name_lower:
                    score -= 50
                if "generic" in name_lower:
                    score -= 40
                if "nvidia" in name_lower and len(name_lower.split()) < 3:
                    score -= 30
                if re.search(r'(gtx|rtx|quadro|tesla|titan)\s+\d+', name_lower):
                    score += 30
                if re.search(r'\d{4}', name_lower):
                    score += 20
                if "ti" in name_lower:
                    score += 10
                return score

            best_score = max(name_specificity_score(g["name"]) for g in with_max_features)
            best_matches = [g for g in with_max_features if name_specificity_score(g["name"]) == best_score]
            selected_gpu = best_matches[0]

    # Emit warning once based on the final selection
    if not suppress_warnings and len(all_matching_names) > 1:
        from .output import show_multiple_match_warning
        show_multiple_match_warning(
            pci_info.get('device') if pci_info else None,
            selected_gpu["name"], all_matching_names
        )
    return selected_gpu


def get_nvidia_devices(sys_path, supported_gpus, simulate_gpu=None, simulate_multi=None, suppress_warnings=False):
    """Get a dictionary with all the NVIDIA graphics devices

    Returns {str PCI_ID: Device object, etc.}
    """
    pci_class_display = "03"

    if simulate_multi:
        multi_gpus = simulated_gpus[simulate_multi]
        modaliases = {}
        for idx, gpu_data in enumerate(multi_gpus):
            modalias = gpu_data["modalias"]
            modaliases[modalias] = f'/sys/devices/pci0000:00/0000:00:0{idx + 1}.0/0000:0{idx + 1}:00.0'
    elif simulate_gpu:
        if simulate_gpu in simulated_gpus:
            gpu_data = simulated_gpus[simulate_gpu]
            modalias = gpu_data["modalias"]
            modaliases = {modalias: '/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0'}
        else:
            logging.error(f"Unknown simulated GPU: {simulate_gpu}")
            return None
    else:
        modaliases = get_system_modaliases(sys_path)

    json_path = supported_gpus
    if json_path is None:
        logging.error("supported_gpus path is None")
        return None

    try:
        file_size = os.path.getsize(json_path)
        if file_size > 10 * 1024 * 1024:  # 10 MB limit
            logging.error("supported_gpus JSON file too large: %d bytes (limit 10MB)", file_size)
            return None
    except OSError as e:
        logging.error("failed to get size of %s: %s", json_path, e)
        return None

    devices = {}

    try:
        with open(json_path, "r") as stream:
            try:
                gpus = list(json.load(stream)["chips"])
            except Exception as e:
                logging.error("failed to load %s: %s" % (json_path, e))
                return None

            # Build lookup by device ID
            gpu_map = {}
            for gpu in gpus:
                devid = gpu.get("devid")
                if not devid:
                    logging.warning("Skipping GPU entry missing 'devid' key or empty: %s" % (json.dumps(gpu) if gpu else "None"))
                    continue
                if devid not in gpu_map:
                    gpu_map[devid] = []
                gpu_entry = gpu.copy()
                if "subvendorid" in gpu_entry and not gpu_entry["subvendorid"].startswith("0x"):
                    gpu_entry["subvendorid"] = f"0x{gpu_entry['subvendorid']}"
                if "subdevid" in gpu_entry and not gpu_entry["subdevid"].startswith("0x"):
                    gpu_entry["subdevid"] = f"0x{gpu_entry['subdevid']}"
                gpu_map[devid].append(gpu_entry)

            for alias, syspath in modaliases.items():
                modalias_pattern = re.compile("(.+):v(.+)d(.+)sv(.+)sd(.+)bc(.+)sc(.+)i.*")
                details = modalias_pattern.match(alias)
                if details:
                    if details.group(1) == "pci":
                        vendor = details.group(2)[4:]
                        devid = "0x%s" % details.group(3)[4:]
                        subsys_vendor = "0x%s" % details.group(4)[4:]
                        subsys_device = "0x%s" % details.group(5)[4:]
                        classid = details.group(6)

                        if vendor.lower() == "10de" and classid == pci_class_display:
                            logging.debug(
                                "get_nvidia_devices(): Processing Vendor: %s, Device ID: %s, Subsystem: %s:%s, class %s"
                                % (vendor, devid, subsys_vendor, subsys_device,
                                   "0x%s%s" % (details.group(6), details.group(7)))
                            )

                            pci_info = get_pci_device_info(syspath) if not simulate_gpu and not simulate_multi else None
                            pci_match_info = {
                                "subsystem_vendor": subsys_vendor,
                                "subsystem_device": subsys_device,
                                "device": devid
                            }
                            if pci_info:
                                pci_match_info.update(pci_info)
                            if simulate_gpu:
                                pci_match_info["simulate_gpu"] = simulate_gpu
                            if simulate_multi:
                                pci_match_info["simulate_multi"] = simulate_multi

                            if devid in gpu_map:
                                matching_gpus = gpu_map[devid]
                                if len(matching_gpus) == 1:
                                    gpu = matching_gpus[0]
                                    device = Device(
                                        devid, gpu["name"], gpu["features"],
                                        gpu.get("legacybranch"),
                                        gpu.get("subvendorid"),
                                        gpu.get("subdevid")
                                    )
                                    devices[devid] = device
                                else:
                                    best_gpu = select_best_gpu_match(matching_gpus, pci_match_info, suppress_warnings)
                                    device = Device(
                                        devid, best_gpu["name"], best_gpu["features"],
                                        best_gpu.get("legacybranch"),
                                        best_gpu.get("subvendorid"),
                                        best_gpu.get("subdevid")
                                    )
                                    devices[devid] = device
                                    logging.debug(f"get_nvidia_devices(): Multiple matches for {devid}, selected {best_gpu['name']}")
                            else:
                                dev = Device(devid, "unknown", [], "", None, None)
                                dev.driver_hint = default
                                devices[devid] = dev
                                logging.info("get_nvidia_devices(): Unknown GPU ID %s" % devid)

    except (IOError, FileNotFoundError, PermissionError) as e:
        logging.error("failed to read %s: %s" % (json_path, e))
        return None

    logging.debug("get_nvidia_devices(): Created %d Device objects" % len(devices))
    return devices
