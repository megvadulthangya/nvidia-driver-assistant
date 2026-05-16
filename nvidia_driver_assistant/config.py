"""YAML configuration loader and validator for nvidia-driver-assistant."""

import os
import logging
import yaml


# Package-level paths
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")

# Driver type flags (constants)
proprietary_required = "proprietary_required"
proprietary_supported = "gsp_proprietary_supported"
default = "open_required"
open_supported = "kernelopen"
support_flags = (open_supported, proprietary_supported)


def _load_yaml(filename):
    """Load a YAML file from the data directory."""
    path = os.path.join(_DATA_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError("Configuration file not found: %s" % path)
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError("Configuration file is empty: %s" % path)
    return data


def _validate_architecture(registry):
    """Validate the architecture registry."""
    required_keys = {"is_open_capable", "min_driver", "patterns"}
    for arch, info in registry.items():
        if not isinstance(info, dict):
            raise ValueError("Architecture '%s' must be a dict, got %s" % (arch, type(info).__name__))
        missing = required_keys - set(info.keys())
        if missing:
            raise ValueError("Architecture '%s' missing required keys: %s" % (arch, missing))
        if not isinstance(info["is_open_capable"], bool):
            raise ValueError("Architecture '%s': is_open_capable must be bool" % arch)
        if not isinstance(info["min_driver"], int):
            raise ValueError("Architecture '%s': min_driver must be int" % arch)
        if not isinstance(info["patterns"], list):
            raise ValueError("Architecture '%s': patterns must be a list" % arch)


def _validate_distro_registry(registry):
    """Validate the distro registry."""
    required_keys = {"aur_supported", "kernel_substitution", "branch_suffix"}
    for distro, info in registry.items():
        if not isinstance(info, dict):
            raise ValueError("Distro '%s' must be a dict, got %s" % (distro, type(info).__name__))
        missing = required_keys - set(info.keys())
        if missing:
            raise ValueError("Distro '%s' missing required keys: %s" % (distro, missing))


def _validate_overrides(overrides):
    """Validate override configuration."""
    required_keys = {
        "ENABLE_LEGACY_OPENKERNEL_RESTRICTION",
        "ENABLE_ARCHITECTURE_CHECK",
        "AUTO_FALLBACK",
        "min_supported_legacy_branch",
    }
    missing = required_keys - set(overrides.keys())
    if missing:
        raise ValueError("Overrides config missing required keys: %s" % missing)


def _validate_instructions(data):
    """Validate instruction configuration."""
    if "instructions" not in data:
        raise ValueError("Instructions config missing 'instructions' key")
    if "branch_instructions" not in data:
        raise ValueError("Instructions config missing 'branch_instructions' key")


def _convert_instruction_dicts(raw):
    """Convert version-keyed instruction dicts to use numeric keys."""
    result = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            converted = {}
            for ver_key, ver_val in value.items():
                converted[int(ver_key) if not isinstance(ver_key, int) else ver_key] = ver_val
            result[key] = converted
        else:
            result[key] = value
    return result


def load_config():
    """Load and validate all YAML configuration files.

    Returns a dict with all configuration data, ready to be unpacked
    into module-level variables.
    """
    # Load YAML files
    arch_data = _load_yaml("architecture.yaml")
    distro_data = _load_yaml("distro.yaml")
    overrides_data = _load_yaml("overrides.yaml")
    instructions_data = _load_yaml("instructions.yaml")

    # Validate
    _validate_architecture(arch_data)
    _validate_distro_registry(distro_data.get("distro_registry", {}))
    _validate_overrides(overrides_data)
    _validate_instructions(instructions_data)

    # Build ARCHITECTURE_REGISTRY
    ARCHITECTURE_REGISTRY = arch_data

    # Derived constants from architecture registry
    OPEN_CAPABLE_ARCHS = tuple(
        arch for arch, info in ARCHITECTURE_REGISTRY.items() if info["is_open_capable"]
    )
    OPEN_UNSUPPORTED_ARCHS = tuple(
        arch for arch, info in ARCHITECTURE_REGISTRY.items() if not info["is_open_capable"]
    )
    ARCHITECTURE_MIN_DRIVER = {
        arch: str(info["min_driver"]) for arch, info in ARCHITECTURE_REGISTRY.items()
    }

    # Build DISTRO_REGISTRY with proper tuple conversions
    raw_distro_registry = distro_data.get("distro_registry", {})
    DISTRO_REGISTRY = {}
    for distro_name, info in raw_distro_registry.items():
        entry = dict(info)
        # Convert aur_branches list to tuple
        entry["aur_branches"] = tuple(entry.get("aur_branches", []) or [])
        DISTRO_REGISTRY[distro_name] = entry

    # Derived constants for backward compatibility
    manjaro_info = DISTRO_REGISTRY.get("manjaro", {})
    arch_info = DISTRO_REGISTRY.get("arch", {})
    MANJARO_MIN_OFFICIAL_LEGACY_BRANCH = manjaro_info.get("min_official_branch")
    ARCH_MIN_REPO_LEGACY_BRANCH = arch_info.get("min_official_branch")
    ARCH_AUR_ONLY_BRANCHES = arch_info.get("aur_branches", ())

    # Supported distros
    supported_distros = distro_data.get("supported_distros", [])

    # Overrides
    DISTRO_NON_LEGACY_DEFAULT_BRANCH = overrides_data.get("DISTRO_NON_LEGACY_DEFAULT_BRANCH")
    DISTRO_580_LEGACY_OVERRIDE_BRANCH = overrides_data.get("DISTRO_580_LEGACY_OVERRIDE_BRANCH")
    ENABLE_LEGACY_OPENKERNEL_RESTRICTION = overrides_data["ENABLE_LEGACY_OPENKERNEL_RESTRICTION"]
    ENABLE_ARCHITECTURE_CHECK = overrides_data["ENABLE_ARCHITECTURE_CHECK"]
    AUTO_FALLBACK = overrides_data["AUTO_FALLBACK"]
    min_supported_legacy_branch = overrides_data["min_supported_legacy_branch"]

    # Instructions
    instructions = _convert_instruction_dicts(instructions_data["instructions"])
    branch_instructions = _convert_instruction_dicts(instructions_data["branch_instructions"])

    return {
        "ARCHITECTURE_REGISTRY": ARCHITECTURE_REGISTRY,
        "OPEN_CAPABLE_ARCHS": OPEN_CAPABLE_ARCHS,
        "OPEN_UNSUPPORTED_ARCHS": OPEN_UNSUPPORTED_ARCHS,
        "ARCHITECTURE_MIN_DRIVER": ARCHITECTURE_MIN_DRIVER,
        "DISTRO_REGISTRY": DISTRO_REGISTRY,
        "MANJARO_MIN_OFFICIAL_LEGACY_BRANCH": MANJARO_MIN_OFFICIAL_LEGACY_BRANCH,
        "ARCH_MIN_REPO_LEGACY_BRANCH": ARCH_MIN_REPO_LEGACY_BRANCH,
        "ARCH_AUR_ONLY_BRANCHES": ARCH_AUR_ONLY_BRANCHES,
        "supported_distros": supported_distros,
        "DISTRO_NON_LEGACY_DEFAULT_BRANCH": DISTRO_NON_LEGACY_DEFAULT_BRANCH,
        "DISTRO_580_LEGACY_OVERRIDE_BRANCH": DISTRO_580_LEGACY_OVERRIDE_BRANCH,
        "ENABLE_LEGACY_OPENKERNEL_RESTRICTION": ENABLE_LEGACY_OPENKERNEL_RESTRICTION,
        "ENABLE_ARCHITECTURE_CHECK": ENABLE_ARCHITECTURE_CHECK,
        "AUTO_FALLBACK": AUTO_FALLBACK,
        "min_supported_legacy_branch": min_supported_legacy_branch,
        "instructions": instructions,
        "branch_instructions": branch_instructions,
        "proprietary_required": proprietary_required,
        "proprietary_supported": proprietary_supported,
        "default": default,
        "open_supported": open_supported,
        "support_flags": support_flags,
    }


# ── Module-level configuration ──────────────────────────────────────
# Load once at import time; every other module reads from here.

_cfg = load_config()

ARCHITECTURE_REGISTRY = _cfg["ARCHITECTURE_REGISTRY"]
OPEN_CAPABLE_ARCHS = _cfg["OPEN_CAPABLE_ARCHS"]
OPEN_UNSUPPORTED_ARCHS = _cfg["OPEN_UNSUPPORTED_ARCHS"]
ARCHITECTURE_MIN_DRIVER = _cfg["ARCHITECTURE_MIN_DRIVER"]
DISTRO_REGISTRY = _cfg["DISTRO_REGISTRY"]
MANJARO_MIN_OFFICIAL_LEGACY_BRANCH = _cfg["MANJARO_MIN_OFFICIAL_LEGACY_BRANCH"]
ARCH_MIN_REPO_LEGACY_BRANCH = _cfg["ARCH_MIN_REPO_LEGACY_BRANCH"]
ARCH_AUR_ONLY_BRANCHES = _cfg["ARCH_AUR_ONLY_BRANCHES"]
supported_distros = _cfg["supported_distros"]
DISTRO_NON_LEGACY_DEFAULT_BRANCH = _cfg["DISTRO_NON_LEGACY_DEFAULT_BRANCH"]
DISTRO_580_LEGACY_OVERRIDE_BRANCH = _cfg["DISTRO_580_LEGACY_OVERRIDE_BRANCH"]
ENABLE_LEGACY_OPENKERNEL_RESTRICTION = _cfg["ENABLE_LEGACY_OPENKERNEL_RESTRICTION"]
ENABLE_ARCHITECTURE_CHECK = _cfg["ENABLE_ARCHITECTURE_CHECK"]
AUTO_FALLBACK = _cfg["AUTO_FALLBACK"]
min_supported_legacy_branch = _cfg["min_supported_legacy_branch"]
instructions = _cfg["instructions"]
branch_instructions = _cfg["branch_instructions"]
