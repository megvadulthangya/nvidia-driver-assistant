"""nvidia-driver-assistant – modular package."""

from .config import (
    ARCHITECTURE_REGISTRY,
    OPEN_CAPABLE_ARCHS,
    OPEN_UNSUPPORTED_ARCHS,
    ARCHITECTURE_MIN_DRIVER,
    DISTRO_REGISTRY,
    MANJARO_MIN_OFFICIAL_LEGACY_BRANCH,
    ARCH_MIN_REPO_LEGACY_BRANCH,
    ARCH_AUR_ONLY_BRANCHES,
    supported_distros,
    DISTRO_NON_LEGACY_DEFAULT_BRANCH,
    DISTRO_580_LEGACY_OVERRIDE_BRANCH,
    ENABLE_LEGACY_OPENKERNEL_RESTRICTION,
    ENABLE_ARCHITECTURE_CHECK,
    AUTO_FALLBACK,
    min_supported_legacy_branch,
    instructions,
    branch_instructions,
    proprietary_required,
    proprietary_supported,
    default,
    open_supported,
    support_flags,
)
from .hardware import get_system_modaliases, get_pci_device_info, is_laptop_system
from .system import SystemInfo, get_distro, override_distro
from .database import simulated_gpus, select_best_gpu_match, get_nvidia_devices
from .device import Device
from .recommendation import (
    get_driver_from_json_hints,
    check_legacy_devices,
    recommend_driver,
    merge_unsupported_into_legacy,
    ubuntu_get_latest_driver_branch,
    manjaro_get_kernel_package,
    manjaro_get_legacy_branch,
)
from .output import (
    print_pretty_gpu_summary,
    show_multiple_match_warning,
    print_fallback_instructions,
    print_aur_instructions,
    get_conditional_instructions,
    process_results,
    install_driver,
    print_instructions,
)
from .cli import main
