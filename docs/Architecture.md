# Architecture

This document describes how the Manjaro-targeted `nvidia-driver-assistant` works, how it evaluates NVIDIA devices, and how its command-line interfaces are consumed by MHWD.

The design has three cooperating parts:

1. **NVIDIA data** — `supported-gpus.json` and five NVIDIA `supportedchips.html` documents provide device and driver-branch information.
2. **The Assistant (Python)** — detects GPUs, classifies their supported driver branches, selects the kernel-module flavour and exposes machine-readable interfaces.
3. **Manjaro's MHWD packages** — use the Assistant's result when selecting an NVIDIA profile and installing the corresponding packages.

The Assistant does not replace MHWD or `pacman`. It supplies recommendations and device-branch data that the Manjaro installation path consumes.

## 1. Detection and data inputs

### 1.1 GPU discovery

`hardware.py` collects PCI modalias information from sysfs. `database.py` uses the NVIDIA vendor/device information to match the detected device against the loaded `supported-gpus.json` database. Subsystem vendor and device IDs are also considered when the JSON contains subsystem-specific entries.

The selected JSON record is used to construct a `Device` object containing the PCI Device ID, name, subsystem IDs, feature flags and any `legacybranch` value.

### 1.2 NVIDIA supported-device documents

The package build retrieves five NVIDIA documents:

| File | Driver generation | Main role in the Assistant |
|---|---|---|
| `supportedchips.html` | Latest 6xx / New Feature Branch | Maps Device IDs to `current` or a legacy branch; used by device classification and `--mhwd-branch`. |
| `supportedchips580.html` | 580 | Its `Current` list is used to check whether all detected devices can share the 580 driver in a 580 + latest-6xx combination. |
| `supportedchips470.html` | 470 | Source for generating and auditing 470xx MHWD IDs. |
| `supportedchips390.html` | 390 | Source for generating and auditing 390xx MHWD IDs. |
| `supportedchips340.html` | 340 | Source for generating and auditing 340xx MHWD IDs. |

The parser in `supported_chips.py` supports two document layouts:

- Latest and 580 documents use named sections and table-row IDs such as `devid1380` or `devid2D18_17AA_3E31`.
- Older 470, 390 and 340 documents use HTML tables with a `Device PCI ID` column. The parser identifies that column in each table and reads the first PCI Device ID token from it. Subsystem Vendor IDs and Subsystem Device IDs are not added to the generated base Device ID list.

The older parser stops at the document's legacy-section introduction. This prevents it from accidentally treating an appended list for a different, older driver series as part of the document's own supported-device table.

The PKGBUILD validates all five documents before packaging. A missing, empty or unparseable required document causes the build to fail.

## 2. Device classification

`Device` in `device.py` combines information from the selected JSON record and the latest NVIDIA `supportedchips.html` map.

The order is important:

1. The JSON `legacybranch` is retained as the primary legacy classification when it is present.
2. If JSON does not provide a legacy branch, the latest NVIDIA supportedchips map can supply one when the Device ID appears in a legacy section.
3. If both sources provide a classification but disagree, the code logs a warning and keeps the JSON legacy branch. The HTML value does not silently overwrite an explicit JSON legacy assignment.
4. A device is treated as supporting the latest 6xx line only when it appears in the latest document's `Current` section and JSON does not assign it a legacy branch.
5. `supports_580` is set independently by checking the Device ID against the `Current` entries in `supportedchips580.html`.

The distinction between `supports_latest_6xx` and `supports_580` is used by the mixed-GPU logic. The latter is not inferred from a GPU name or from the latest document.

## 3. Kernel-module flavour selection

The Assistant returns either `open` or `closed`.

The core safety rule in `Device._parse_features()` is:

> A device assigned to a legacy branch up to and including 580 must use the proprietary (`closed`) kernel module, regardless of an `kernelopen` feature flag in `supported-gpus.json`.

The implementation then handles current devices and the JSON feature fallback:

1. If the device has a legacy branch and its numeric branch is 580 or lower, or the legacy branch cannot be parsed, its hint is `proprietary_required`.
2. If the device is listed in the latest NVIDIA `Current` section and has no legacy assignment, its hint is `open_required`.
3. For other devices, the feature flags from `supported-gpus.json` are used. The code recognizes `kernelopen` and `gsp_proprietary_supported` and resolves the hint accordingly.

`recommendation.py` aggregates the per-device hints into one system-level flavour. The recommendation is system-wide; it is not simply the result for the first detected GPU.

This code path deliberately avoids treating the `kernelopen` flag as sufficient for a GPU that is already classified as legacy 580 or older.

## 4. Legacy-branch and Manjaro package policy

Two configuration values serve different purposes:

- `min_supported_legacy_branch` in `overrides.yaml` is the Assistant's threshold for treating a legacy branch as directly supported by the common recommendation path. Its current value is 580.
- `min_official_branch` in `distro.yaml` is the lowest legacy branch currently available in the Manjaro package set. Its current value is 390.

As a result, 390xx and 470xx are initially classified as legacy devices below the Assistant's common 580 threshold, then handled by the Manjaro repository policy as available legacy branches. A 340xx device is recognized by the Assistant, but is below Manjaro's current repository minimum and follows the configured fallback path.

This is a distribution-availability distinction, not a limitation of the parser or ID generator. The Assistant retains 340xx support for detection, branch classification and MHWD ID operations.

For a device requiring 340xx, `--mhwd-branch --mhwd-device-id ID` can still return `340`. However, `--mhwd-config` does not advertise a Manjaro profile for a branch outside the configured repository availability. MHWD cannot install a 340xx profile that is not present in its available configuration database.

## 5. Multi-GPU handling

### 5.1 General rule

`recommend_driver()` evaluates all detected NVIDIA GPUs. It collects legacy devices, computes the module-flavour hints and identifies unsupported combinations. The CLI then applies the Manjaro branch-availability policy.

If a system contains an open-capable GPU alongside a legacy GPU that cannot use the same selected driver, the CLI prioritises the newer GPU and reports that the incompatible legacy device will not work with the selected driver. If all relevant legacy devices are available through the Manjaro package policy, their branch can instead be merged into the selected legacy recommendation.

### 5.2 Legacy 580 plus latest 6xx

This combination receives a specific compatibility check:

- If at least one GPU requires legacy 580 and at least one GPU is listed in the latest 6xx `Current` list, the Assistant checks every detected device against the 580 `Current` list.
- If every detected device is present in that 580 list, a common 580 driver is selected with the closed kernel module.
- If any device is absent from the 580 `Current` list, there is no common 580 driver for the complete system. The latest 6xx driver is prioritised for the newer GPU, and the legacy-580 GPU is reported as incompatible with that selection.

The special case does not infer compatibility for 470xx, 390xx or 340xx from the 580 document.

## 6. MHWD interfaces

The Assistant exposes three separate CLI interfaces to MHWD.

| Command | Output | Purpose |
|---|---|---|
| `nvidia-driver-assistant --mhwd-config` | MHWD config name, such as `video-nvidia-580xx` | System-level NVIDIA profile recommendation. |
| `nvidia-driver-assistant --mhwd-branch --mhwd-device-id ID` | Numeric legacy branch or `current` | Per-device branch classification for one NVIDIA PCI Device ID. |
| `nvidia-driver-assistant --mhwd` | `open` or `closed` | System-level kernel-module flavour for the selected MHWD config. |

`--mhwd-branch` bypasses system-wide multi-GPU recommendation and asks only about the supplied Device ID. If the ID is not present in the latest supportedchips map, it exits with an error status instead of guessing.

`--mhwd-config` maps the resolved branch to a profile name:

| Resolved branch | Profile name |
|---|---|
| No legacy branch / latest driver | `video-nvidia` |
| `580` | `video-nvidia-580xx` |
| `470` | `video-nvidia-470xx` |
| `390` | `video-nvidia-390xx` |
| `340` | `video-nvidia-340xx` in the generic mapping, but the Manjaro availability policy prevents advertising an unavailable 340xx package/profile |

The final point is important: branch recognition does not create a profile or installable package. The Manjaro policy has a minimum official branch of 390.

## 7. MHWD integration modes

The `mhwd` PKGBUILD in the associated PKGBUILDs repository contains two alternative patches. `NVIDIA_ASSISTANT_MODE` selects exactly one. The patches target the MHWD auto-configure path for non-free NVIDIA display devices.

### 7.1 Authority mode

Patch: `0001-mhwd-nvidia-assistant-integration.patch`

1. MHWD calls `nvidia-driver-assistant --mhwd-config` to obtain the system-level NVIDIA profile recommendation.
2. MHWD parses the branch represented by that profile name.
3. When processing NVIDIA devices, MHWD searches the available profiles for the Assistant's selected branch.
4. Hybrid profiles are considered using the same NVIDIA branch information.
5. If the Assistant does not return a valid config/branch, or the matching profile is unavailable, MHWD does not select an NVIDIA profile through its normal priority fallback.

This mode gives the Assistant authority over the NVIDIA branch decision.

### 7.2 Corrective mode

Patch: `0002-mhwd-nvidia-assistant-corrective.patch`

1. MHWD first performs its normal priority-based profile selection.
2. Hybrid NVIDIA profiles attached to the integrated GPU are deferred so that the NVIDIA device can drive the branch validation.
3. For each NVIDIA PCI Device ID, MHWD calls `nvidia-driver-assistant --mhwd-branch --mhwd-device-id ID`.
4. MHWD extracts the branch from its selected profile and compares it with the Assistant's supportedchips result.
5. If the branches differ, MHWD searches for a profile with the required branch while retaining the original profile's hybrid/non-hybrid type.
6. If an alternative profile exists, MHWD corrects the selection. If none exists, it skips that NVIDIA device rather than installing a mismatched profile.
7. If the Assistant cannot determine a branch, MHWD retains its original priority-based selection.

This mode keeps MHWD's native priority order as the starting point and uses the Assistant as a per-device correction layer.

### 7.3 Mode selection and patch application

The two patches implement alternative behaviours for the same MHWD code path and must never be applied together. The PKGBUILD selects one by setting:

```bash
NVIDIA_ASSISTANT_MODE="authority"
# or
NVIDIA_ASSISTANT_MODE="corrective"
```

The Manjaro-targeted PKGBUILD uses the standard GNU `patch` utility to apply the selected patch. See [Building](Building.md).

## 8. MHWDCONFIG and package installation

MHWD profiles are stored under `/var/lib/mhwd/db/pci/graphic_drivers/` and contain an `MHWDCONFIG` file. When installed, the selected profile is copied to the local MHWD configuration directory.

The configuration contains package dependencies, conflicting packages/modules, and optional shell hooks. MHWD's shell script sources the selected file, resolves the installed kernel package names and calls `pacman` to remove conflicting packages and install the requested userspace and kernel-module packages.

For profiles that support open/closed module selection, the `DEPKMOD` value is selected from the Assistant's `--mhwd` output. The compatibility wrapper installed as `/usr/bin/nvidia-recommended-driver` calls that interface. It is retained because the current MHWD configuration files use it; the wrapper is marked deprecated in its own source comment in favour of calling `nvidia-driver-assistant --mhwd` directly.

The Assistant does not execute MHWD's package transaction itself. The final installation remains the responsibility of MHWD and `pacman`.

## 9. MHWD PCI ID lists

MHWD profile `DEVICEIDS` values can reference a file under `/var/lib/mhwd/ids/pci/`. The NVIDIA split packages continue to provide these files through their `mhwd-nvidia*` package outputs.

The Assistant can generate each list:

| Assistant argument | MHWD filename |
|---|---|
| `latest` or `6xx` | `nvidia.ids` |
| `580` | `nvidia-580xx.ids` |
| `470` | `nvidia-470xx.ids` |
| `390` | `nvidia-390xx.ids` |
| `340` | `nvidia-340xx.ids` |

`--generate-ids` writes a header and sorted four-digit PCI Device IDs to standard output. The calling PKGBUILD redirects this output into the package staging directory. It does not alter the live MHWD database.

`--check-ids` compares any existing target `.ids` files with the corresponding NVIDIA supported-device document. It is read-only and reports missing, undocumented, duplicate and malformed entries. It does not require all five files to exist.

## 10. End-to-end examples

### 10.1 GTX 750 Ti (legacy 580)

For a GTX 750 Ti with Device ID `1380`:

1. The hardware detector obtains the NVIDIA PCI identity from sysfs.
2. `database.py` matches the device in `supported-gpus.json`.
3. `Device` retains the JSON legacy branch when it is present. The latest NVIDIA supportedchips map supplies supporting classification and `supports_580` is checked against the 580 Current list.
4. The legacy-580 safety rule chooses the closed kernel-module flavour.
5. The Manjaro repository policy accepts 580 as a repository branch.
6. `--mhwd-config` can return `video-nvidia-580xx`; `--mhwd` returns `closed`.
7. MHWD selects the corresponding profile and installs the packages named by its `MHWDCONFIG`.

Useful checks:

```shell
nvidia-driver-assistant --simulate-gpu 750 --json
nvidia-driver-assistant --simulate-gpu 750 --mhwd
```

### 10.2 A 340xx GPU

For a Device ID classified by NVIDIA as legacy 340:

1. The Assistant can identify the legacy branch from the latest supportedchips data or JSON legacy field.
2. The legacy closed-module rule applies.
3. The Manjaro policy sees that 340 is below `min_official_branch: 390`.
4. The normal CLI recommendation path reports the 340xx requirement and follows its configured fallback instructions.
5. `--mhwd-branch --mhwd-device-id ID` can still report `340`.
6. `--generate-ids 340` and `--check-ids` retain their functionality.
7. `--mhwd-config` does not claim that an unavailable Manjaro 340xx profile can be installed.

This is the intended separation between Assistant capability and current Manjaro package availability.
