# NVIDIA Driver Assistant - Enhanced Version

## Overview

This patch enhances the official NVIDIA Driver Assistant (`nvidia-driver-assistant`) with advanced GPU detection, architecture-based driver compatibility checking, and improved safety features. The modifications focus on preventing incompatible driver installations while maintaining full backward compatibility.

## Key Features

### 1. **Architecture Detection & Compatibility Checking**
- **Automatic GPU Architecture Identification**: Detects GPU architecture (Turing, Pascal, Maxwell, etc.) from device names
- **Minimum Driver Requirements**: Enforces architecture-specific minimum driver versions
- **Compatibility Validation**: Checks if requested driver branches are compatible with the GPU's architecture

### 2. **Safety Enhancements**
- **Strict Compatibility Mode**: Prevents installation of drivers that don't support the GPU architecture
- **Auto-fallback Mechanism**: Automatically selects safe driver versions when incompatibility is detected
- **Confirmation Requirements**: Optional user confirmation for potentially incompatible drivers

### 3. **Improved GPU Detection**
- **Mobile vs Desktop Detection**: Better differentiation between laptop and desktop GPUs
- **Subsystem Matching**: Uses subsystem vendor/device IDs for more accurate GPU identification
- **Multiple Match Resolution**: Intelligently selects the best GPU match from multiple possibilities

### 4. **Workarounds & Bug Fixes**
- **580+ Legacy Branch Workaround**: Fixes incorrect legacy branch assignments in NVIDIA's database
- **Maxwell Architecture Correction**: Prevents Maxwell GPUs from using 580+ drivers
- **Backward Compatibility**: Maintains compatibility with existing configurations

## Full Source Code Access

For better understanding of the code changes and implementation details, I'm sharing the complete modified Python script. This allows developers and maintainers to examine the full implementation beyond just the patch file.

**Full script location**: [`MOD-NDA.py`](./MOD-NDA.py) (in repository root)

This complete script contains:
- All architecture detection logic
- Safety validation mechanisms
- GPU matching algorithms
- Distribution-specific override implementations
- Enhanced logging and debugging features

While the primary distribution method remains the patch file for packaging purposes, the full script is provided for transparency and to facilitate code review and understanding of the complete implementation.

## Usage

### Basic Usage
```bash
# Check for recommended driver (dry run)
nvidia-driver-assistant

# Install recommended driver
nvidia-driver-assistant --install

# Show verbose output
nvidia-driver-assistant --verbose

# Simulate with specific GPU for testing
nvidia-driver-assistant --simulate-gpu 4070 --verbose
```

### Advanced Options
```bash
# Specify driver branch
nvidia-driver-assistant --branch 545 --install

# Output JSON for automated tools
nvidia-driver-assistant --json

# MHWD mode (for Manjaro Hardware Detection)
nvidia-driver-assistant --mhwd

# Test with different distribution
nvidia-driver-assistant --distro ubuntu:22.04
```

### Distribution-Specific Override Variables
The script can be configured through these variables at the top of the script:

```python
# 1. Non-legacy cards (no legacybranch in JSON)
# Set to override default driver branch for modern GPUs
DISTRO_NON_LEGACY_DEFAULT_BRANCH = None  # e.g., "545", "550"

# 2. 580+ legacy branch cards
# Set to override 580+ legacy cards to older compatible branches
DISTRO_580_LEGACY_OVERRIDE_BRANCH = None  # e.g., "470", "390"

# 3. Old variable - backward compatibility (deprecated)
# Overrides ALL legacy cards regardless of architecture
DISTRO_LEGACY_OVERRIDE_BRANCH = None

# Safety features
ENABLE_STRICT_COMPATIBILITY = True
REQUIRE_CONFIRMATION = False
AUTO_FALLBACK = True
ENABLE_580_LEGACY_BUG_WORKAROUND = True
```

## Installation Instructions for Package Maintainers

### For Manjaro Package Building
Since this is a patch file, you should apply it to the original `nvidia-driver-assistant` script:

1. **Apply the patch**:
```bash
patch -p1 < nvidia-driver-assistant-enhanced.patch
```

2. **Package structure**:
```
/usr/bin/nvidia-driver-assistant
/usr/share/nvidia-driver-assistant/supported-gpus/supported-gpus.json
```

3. **Build the Manjaro package** using your standard packaging tools.

### No Additional Dependencies Required
The enhanced script maintains all original dependencies and adds no new ones.

## Adding Support for New GPU Architectures

When new NVIDIA GPU architectures are released (e.g., after Blackwell), follow these steps:

### Step 1: Update Architecture Definitions
In the `ARCHITECTURE_MIN_DRIVER` dictionary, add the new architecture:
```python
ARCHITECTURE_MIN_DRIVER = {
    "new_architecture": "550",  # Minimum driver version
    # ... existing architectures
}
```

### Step 2: Update Open/Closed Capability Lists
```python
OPEN_CAPABLE_ARCHS = ("turing", "ampere", "ada", "blackwell", "new_architecture")
OPEN_UNSUPPORTED_ARCHS = (
    "maxwell", "pascal", "volta", "fermi", "kepler", 
    "tesla2", "tesla1", "curie", "pre-curie", "unknown"
)
```

### Step 3: Update Architecture Detection
In the `_get_architecture_from_device_name` method, add patterns for the new architecture:
```python
arch_patterns = {
    "new_architecture": ["NEWARCH", "NA", "RTX 60", "6090", "6080"],
    # ... existing patterns
}
```

### Step 4: Add Simulated GPU Data (Optional, for testing)
```python
simulated_gpus = {
    "6090": {
        "modalias": "pci:v000010DEd00003A01sv000010DEsd000018FEbc03sc00i00",
        "expected_name": "GeForce RTX 6090",
        "expected_devid": "0x3A01",
        "expected_arch": "new_architecture",
        "expected_legacy": None
    },
    # ... existing simulations
}
```

### Step 5: Update NVIDIA's JSON Database
The script uses NVIDIA's `supported-gpus.json` database. When new GPUs are released:
1. NVIDIA will update their database
2. Update the `supported-gpus.json` file in the package
3. Test with simulated GPUs to ensure proper detection

## Safety Features Explained

### Compatibility Checking
The script validates that:
1. The driver version is ≥ the architecture's minimum requirement
2. The driver version is ≤ the maximum supported (for legacy cards)
3. Open kernel modules are only recommended for supported architectures

### 580+ Legacy Branch Bug Workaround
Some older GPUs in NVIDIA's database are incorrectly marked as supporting 580+ drivers. The workaround:
1. Detects when legacybranch ≥ 580
2. Checks if the architecture actually supports those drivers
3. Falls back to appropriate legacy branches (e.g., 470, 390)

### Auto-Fallback Mechanism
When incompatibility is detected:
1. Logs the error with detailed information
2. Automatically selects a safe driver version
3. Continues with installation using the safe version

## Troubleshooting

### Common Issues

1. **"Unknown architecture" warnings**
   - The GPU name couldn't be parsed
   - Check if the GPU is in `supported-gpus.json`
   - The script will still work with default "unknown" handling

2. **Compatibility errors during installation**
   - The requested driver doesn't support your GPU architecture
   - Enable verbose mode (`--verbose`) for details
   - Consider using the auto-fallback feature

3. **Mobile GPU detection issues**
   - Some desktop GPUs with "M" in the name might be misclassified
   - The script has exception lists for common desktop GPUs
   - Can be overridden via distribution-specific variables

### Debug Mode
For detailed debugging:
```bash
nvidia-driver-assistant --verbose --simulate-gpu <GPU_TYPE>
```
Replace `<GPU_TYPE>` with one of: `545`, `740A`, `750`, `800A`, `4070`, `5070`, `unknown`

## Contributing

When extending this script:

1. **Maintain backward compatibility** - don't break existing functionality
2. **Add thorough logging** - use `logging.debug()` for internal logic
3. **Update simulated GPU data** for testing new features
4. **Test with multiple distributions** - especially Manjaro and Arch
5. **Consider safety implications** - driver incompatibilities can break systems

## License

This project is based on NVIDIA tooling released under the MIT License.

Original work:
Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES

Downstream modifications were made by the Manjaro Team.
Further maintenance and enhancements by Gábor Gyöngyösi (@megvadulthangya).

See the `LICENSE` file and the script header for full license details.


## Credits

- Original Author: Alberto Milone (NVIDIA)
- Manjaro Team: Packaging and distribution adjustments
- Gábor Gyöngyösi (@megvadulthangya): Enhancements and maintenance

## Support

For issues with this enhanced version:
1. Check the troubleshooting section above
2. Enable verbose mode for detailed logs
3. Test with simulated GPUs to isolate issues
4. Contact the package maintainer for distribution-specific issues

---

**Note**: This enhanced version is designed to be a drop-in replacement for the original `nvidia-driver-assistant`. All original functionality is preserved while adding safety features and improved detection.
