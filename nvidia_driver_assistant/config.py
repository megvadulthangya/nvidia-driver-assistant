"""YAML configuration loader and validator for nvidia-driver-assistant."""

import os
import yaml


# Package-level paths.
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PACKAGE_DIR, "data")

# Driver type flags.
proprietary_required = "proprietary_required"
proprietary_supported = "gsp_proprietary_supported"
default = "open_required"
open_supported = "kernelopen"
support_flags = (open_supported, proprietary_supported)


def _load_yaml(filename):
    """Load a YAML file from the data directory."""
    path = os.path.join(_DATA_DIR, filename)

    if not os.path.isfile(path):
        raise FileNotFoundError(
            "Configuration file not found: %s" % path
        )

    with open(path, "r") as stream:
        data = yaml.safe_load(stream)

    if data is None:
        raise ValueError(
            "Configuration file is empty: %s" % path
        )

    return data


def _validate_distro_registry(registry):
    """Validate the distribution registry."""
    required_keys = {
        "fallback_method",
        "kernel_substitution",
        "branch_suffix",
    }

    for distro, info in registry.items():
        if not isinstance(info, dict):
            raise ValueError(
                "Distro '%s' must be a dict, got %s"
                % (distro, type(info).__name__)
            )

        missing = required_keys - set(info.keys())

        if missing:
            raise ValueError(
                "Distro '%s' missing required keys: %s"
                % (distro, missing)
            )


def _validate_overrides(overrides):
    """Validate the remaining legacy-branch configuration."""
    if not isinstance(overrides, dict):
        raise ValueError("Overrides configuration must be a dict")

    if "min_supported_legacy_branch" not in overrides:
        raise ValueError(
            "Overrides config missing 'min_supported_legacy_branch'"
        )

    minimum = overrides["min_supported_legacy_branch"]

    if not isinstance(minimum, int) or minimum <= 0:
        raise ValueError(
            "min_supported_legacy_branch must be a positive integer"
        )


def _validate_instructions(data):
    """Validate installation instructions."""
    if "instructions" not in data:
        raise ValueError(
            "Instructions config missing 'instructions' key"
        )

    if "branch_instructions" not in data:
        raise ValueError(
            "Instructions config missing 'branch_instructions' key"
        )


def _convert_instruction_dicts(raw):
    """Convert version-keyed instruction dictionaries to numeric keys."""
    result = {}

    for key, value in raw.items():
        if isinstance(value, dict):
            converted = {}

            for version_key, version_value in value.items():
                numeric_key = (
                    version_key
                    if isinstance(version_key, int)
                    else int(version_key)
                )
                converted[numeric_key] = version_value

            result[key] = converted

        else:
            result[key] = value

    return result


def load_config():
    """Load and validate the distribution, legacy and instruction settings."""
    distro_data = _load_yaml("distro.yaml")
    overrides_data = _load_yaml("overrides.yaml")
    instructions_data = _load_yaml("instructions.yaml")

    _validate_distro_registry(
        distro_data.get("distro_registry", {})
    )
    _validate_overrides(overrides_data)
    _validate_instructions(instructions_data)

    # Build the distribution registry with tuple conversions.
    raw_distro_registry = distro_data.get("distro_registry", {})
    distro_registry = {}

    for distro_name, info in raw_distro_registry.items():
        entry = dict(info)
        entry["fallback_branches"] = tuple(
            entry.get("fallback_branches", []) or []
        )
        # Preserve the historical alias.
        entry["aur_branches"] = entry["fallback_branches"]
        distro_registry[distro_name] = entry

    manjaro_info = distro_registry.get("manjaro", {})
    arch_info = distro_registry.get("arch", {})

    manjaro_min_official_legacy_branch = manjaro_info.get(
        "min_official_branch"
    )
    arch_min_repo_legacy_branch = arch_info.get(
        "min_official_branch"
    )
    arch_aur_only_branches = arch_info.get(
        "fallback_branches",
        (),
    )

    supported_distros = distro_data.get("supported_distros", [])

    min_legacy_branch = overrides_data["min_supported_legacy_branch"]

    instructions = _convert_instruction_dicts(
        instructions_data["instructions"]
    )
    branch_instructions = _convert_instruction_dicts(
        instructions_data["branch_instructions"]
    )

    return {
        "DISTRO_REGISTRY": distro_registry,
        "MANJARO_MIN_OFFICIAL_LEGACY_BRANCH": (
            manjaro_min_official_legacy_branch
        ),
        "ARCH_MIN_REPO_LEGACY_BRANCH": arch_min_repo_legacy_branch,
        "ARCH_AUR_ONLY_BRANCHES": arch_aur_only_branches,
        "supported_distros": supported_distros,
        "min_supported_legacy_branch": min_legacy_branch,
        "instructions": instructions,
        "branch_instructions": branch_instructions,
    }


# Load configuration once at module import.
_cfg = load_config()

DISTRO_REGISTRY = _cfg["DISTRO_REGISTRY"]
MANJARO_MIN_OFFICIAL_LEGACY_BRANCH = (
    _cfg["MANJARO_MIN_OFFICIAL_LEGACY_BRANCH"]
)
ARCH_MIN_REPO_LEGACY_BRANCH = _cfg["ARCH_MIN_REPO_LEGACY_BRANCH"]
ARCH_AUR_ONLY_BRANCHES = _cfg["ARCH_AUR_ONLY_BRANCHES"]
supported_distros = _cfg["supported_distros"]
min_supported_legacy_branch = _cfg["min_supported_legacy_branch"]
instructions = _cfg["instructions"]
branch_instructions = _cfg["branch_instructions"]
