# NVIDIA Driver Assistant - Changelog

## 2026.01.05.1-1
### Major Changes

#### 1. New Legacy Branch Open Kernel Restriction
- **Renamed switch**: `ENABLE_580_LEGACY_BUG_WORKAROUND` → `ENABLE_LEGACY_OPENKERNEL_RESTRICTION`
- **New logic**: All legacy branches (71.86.xx to 580.xx) cannot use open kernel modules
- **Exception**: Legacy branches above 580 are not restricted (for future compatibility)
- **Default**: `ENABLE_LEGACY_OPENKERNEL_RESTRICTION = True`

#### 2. Architecture-Based Check with Toggle
- **New switch**: `ENABLE_ARCHITECTURE_CHECK`
- **Option**: Enable/disable architecture-based open kernel checking
- **Default**: `ENABLE_ARCHITECTURE_CHECK = True`
- **Effect**: If `False`, does not check architectures for open kernel support

#### 3. Multiple Match Warning System
- **New feature**: Informative warning when multiple GPU models match the same device ID in database
- **Content**:
  - Device ID
  - Selected model name
  - All possible model names
  - Explanation that this does not affect compatibility
- **MHWD compatibility**: Warnings suppressed in MHWD mode and JSON output
- **English text**: Clear, user-friendly warning message

#### 4. Bug Fix - Supported Range Logic
- **Issue**: GTX 750 Ti (Maxwell) showed contradictory supported_max_driver (470) and legacy (580.xx)
- **Fix**: Removed Maxwell-specific correction in `_get_supported_range()` method
- **New logic**:
  - For legacy cards, maximum version always comes from JSON legacybranch
  - No architecture-based corrections
  - If JSON has "580.xx", supported_max_driver becomes "580"
- **Result**: Consistent JSON output

#### 5. Updated Priority Order
New driver selection priority order:
1. **Old variable** - Backward compatibility (`DISTRO_LEGACY_OVERRIDE_BRANCH`)
2. **Non-legacy default** - Modern cards override (`DISTRO_NON_LEGACY_DEFAULT_BRANCH`)
3. **580+ legacy override** - Safety net for 580+ legacy cards (`DISTRO_580_LEGACY_OVERRIDE_BRANCH`)
4. **New legacy restriction** - All legacy branches (71.86-580) cannot use open kernel (`ENABLE_LEGACY_OPENKERNEL_RESTRICTION`)
5. **Architecture-based check** - If enabled (`ENABLE_ARCHITECTURE_CHECK`)
6. **Normal JSON logic** - Based on JSON feature flags

#### 6. Enhanced JSON Output
- **New fields**:
  ```json
  "legacy_openkernel_restriction": true,
  "architecture_check_enabled": true
  ```
- **Preserved fields**: All existing fields remain unchanged

### Technical Improvements

#### 1. Parameter Expansion
- `select_best_gpu_match()`: New `suppress_warnings` parameter
- `get_nvidia_devices()`: New `suppress_warnings` parameter
- `recommend_driver()`: New `suppress_warnings` parameter

#### 2. Device Class Enhancements
- `_get_supported_range()`: Simplified, bug-free logic
- `_parse_features()`: Extended priority order
- Architecture detection remains functional but now optional

#### 3. New Helper Functions
- `show_multiple_match_warning()`: Multiple match warning display
- Improved `get_pci_device_info()`: More reliable device information collection

### Compatibility Notes

#### 1. MHWD Compatibility
- **Fully preserved**: MHWD still receives only "open" or "closed" string
- **No changes**: No warnings or extra output in MHWD mode

#### 2. Backward Compatibility
- **Old variables**: `DISTRO_LEGACY_OVERRIDE_BRANCH` still works (deprecated)
- **API unchanged**: External scripts and integrations continue to work
- **JSON output**: Extended but backward compatible

#### 3. Distribution Compatibility
- **All supported distributions**: Ubuntu, Debian, Fedora, RHEL, openSUSE, Arch, Manjaro, etc.
- **Installation instructions**: Unchanged
- **Branch-specific installation**: Still supported

### Developer Changes

#### 1. Configuration Variables
```python
# Old (renamed)
ENABLE_580_LEGACY_BUG_WORKAROUND = True

# New
ENABLE_LEGACY_OPENKERNEL_RESTRICTION = True
ENABLE_ARCHITECTURE_CHECK = True

# Distribution overrides (unchanged)
DISTRO_LEGACY_OVERRIDE_BRANCH = None
DISTRO_NON_LEGACY_DEFAULT_BRANCH = None
DISTRO_580_LEGACY_OVERRIDE_BRANCH = None
```

#### 2. Logging Enhancements
- **More detailed debug information**: GPU matching process
- **Architecture detection logging**: Automatic architecture determination
- **Legacy status logging**: Legacy branch handling

### Tested Configuration

#### 1. Simulated GPUs (in-code)
- **GeForce 545** (Fermi, legacy: 390)
- **GeForce 740A** (Kepler, legacy: 390)
- **GeForce 750** (Maxwell, legacy: 470)
- **GeForce 800A** (Fermi, custom subsystem)
- **GeForce RTX 4070** (Ada, non-legacy)
- **GeForce RTX 5070** (Blackwell, non-legacy)

#### 2. Real Hardware Test
- **✅ GTX 750 Ti**: Maxwell, legacy branch: 580.xx → supported_max_driver: 580
- **Test modes**: `--simulate-gpu`, `--json`, `--mhwd` partially tested
- **Installation test**: `--install` not yet tested in ISO environment

### Known Limitations

#### 1. Legacy Branch Data
- **JSON database**: If JSON contains incorrect legacy branch, program uses it
- **Architecture check**: If `ENABLE_ARCHITECTURE_CHECK = False`, architectures are not checked

#### 2. Multiple Matches
- **Automatic selection**: Program chooses, but not always perfect
- **Warning**: Only appears in interactive mode

### Future Development

#### 1. Suggested Features
- **GPU detection improvement**: More accurate model identification
- **Installation logging**: Track successful/failed installations
- **Auto-update**: Automatic JSON database updates

#### 2. Maintenance
- **Code cleanup**: Remove deprecated variables in future versions
- **Documentation**: Extend API documentation

---

**Developer**: Gábor Gyöngyösi (@megvadulthangya)  
**Testing**: Individual testing (GTX 750 Ti)  
**Version**: 2026.01.05.1-1
**Status**: Development version, partially tested  
**ISO Testing**: Not yet performed  
**Community Testing**: Not yet available  

**Note**: This version significantly improves legacy card handling and provides more comprehensive warnings to users while maintaining full backward compatibility. Further testing in various environments is recommended before production use.
