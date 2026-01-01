

## CHANGELOG.md - Changes:



### Modified:
- **Device class extended** with architecture detection
- **Distribution detection** for Manjaro/Arch recognition
- **Driver recommendation logic** with architecture-based restrictions
- **Package installation commands** with Manjaro/Arch specific instructions

### Added variables and functions:
- `OPEN_UNSUPPORTED_ARCHS` - List of architectures not supporting Open kernel
- `manjaro_get_kernel_package()` - Extract kernel package name
- `manjaro_get_legacy_branch()` - Legacy branch detection
- Architecture detection methods in Device class

### Added installation instructions:
- `arch-closed`: `sudo pacman -S nvidia-dkms`
- `arch-open`: `sudo pacman -S nvidia-open-dkms`
- `manjaro-closed`: `sudo pacman -S KERNEL-nvidia`
- `manjaro-open`: `sudo pacman -S KERNEL-nvidia-open`

### Fixes:
- Proper identification of Manjaro among Arch-based systems
- Dynamic kernel placeholder replacement in Manjaro package names
















### Added
- **Enhanced GPU architecture detection**: 
  - Added `_get_architecture_from_chip_family()` method for detailed chip family analysis
  - Added `_get_architecture_from_device_name()` fallback method for architecture extraction from device names
  - Support for older architectures: Fermi, Kepler, Tesla 1.0/2.0, Curie, and pre-Curie
- **Platform module integration**: Added `import platform` for kernel release detection
- **Manjaro kernel package utilities**:
  - `manjaro_get_kernel_package()`: Extracts kernel package name from kernel release
  - `manjaro_get_legacy_branch()`: Determines legacy branch for Manjaro devices

### Changed
- **Arch and Manjaro distribution support enhancements**:
  - Improved kernel package name detection for Manjaro installations
  - Added legacy branch auto-detection for Manjaro systems
  - Enhanced warning and debug logging for kernel detection
- **Device class refactoring**:
  - Moved architecture detection into class methods
  - Added comprehensive logging for device detection details
  - Enhanced driver hint logic with architecture-based overrides
- **Driver recommendation logic**:
  - Modified `recommend_driver()` to return both driver and devices tuple
  - Added architecture-based override for open kernel module compatibility
  - Defined `OPEN_UNSUPPORTED_ARCHS` tuple for architectures incompatible with open drivers

### Fixed
- **Driver compatibility enforcement**: Open kernel module is now properly restricted to Turing and newer architectures
- **Legacy branch handling**: Improved error handling for legacy branch parsing
- **Code organization**: Moved helper functions to appropriate locations in the file
- **Log formatting**: Updated logging calls to use proper formatting syntax

### Technical Details
- Open Kernel Module now only supported for Turing, Ampere, Ada, and Hopper architectures
- Proprietary driver required for Maxwell, Pascal, Volta, Fermi, Kepler, Tesla, Curie, and older GPU generations
- Architecture detection uses both chip family codes and device name patterns for redundancy
- Manjaro installation commands now dynamically substitute kernel version (e.g., `linux618` for kernel 6.18)
