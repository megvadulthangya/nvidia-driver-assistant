# Configuration and NVIDIA device data

This document describes the configuration inputs used by the Manjaro fork. The current code loads three YAML policy files and five NVIDIA supportedchips HTML documents. There is no separate `architecture.yaml` registry in the current implementation; the older architecture-registry description has been retired.

## 1. Configuration files

| File | Purpose |
|---|---|
| `nvidia_driver_assistant/data/distro.yaml` | Distribution-specific legacy-branch and fallback policy. This fork currently contains Manjaro only. |
| `nvidia_driver_assistant/data/overrides.yaml` | General minimum supported legacy branch. |
| `nvidia_driver_assistant/data/instructions.yaml` | Manjaro installation command templates. |
| NVIDIA `supportedchips*.html` files | Vendor data parsed by `supported_chips.py`; downloaded and validated during package build. |
| `supported-gpus.json` | NVIDIA device names, feature flags and JSON legacy-branch data; extracted from the upstream DEB at package build time. |

`config.py` loads and validates the three YAML files when the package is imported. The HTML files are parsed by `supported_chips.py` and exposed as module-level maps/sets.

## 2. `distro.yaml`

### 2.1 Current Manjaro entry

The current Manjaro entry includes the following policy values:

```yaml
distro_registry:
  manjaro:
    min_official_branch: 340
    fallback_method: "aur"
    fallback_branches: []
    nouveau_hint_below: 580
    kernel_substitution: true
    branch_suffix: "xx"
    fallback_message: "These versions are no longer in official Manjaro repositories."
    fallback_device_header: "Ultra-legacy GPU(s) detected (branch < {min_branch}):"
    fallback_package_template: "nvidia-{branch}xx-dkms"
    fallback_utils_template: "nvidia-{branch}xx-utils"
    repo_available_note: >-
      Note: These legacy branches are still available in the
      Manjaro official repositories.

supported_distros:
  - manjaro
```

This is the current code configuration, not a statement that the maintainer's additional Debian-based 340xx/390xx package patches are official Manjaro packages. The `min_official_branch` field is consumed by the Assistant's distribution fallback logic; it must be reviewed whenever the actual Manjaro package/repository policy changes.

### 2.2 Fields

| Field | Purpose |
|---|---|
| `min_official_branch` | Threshold used by the CLI when deciding whether an initially unsupported legacy branch can be merged into the configured distribution branch path. |
| `fallback_method` | Behaviour for legacy branches below the configured threshold: `aur` or `error`. |
| `fallback_branches` | Explicit list of legacy branches handled as fallback-only branches. |
| `nouveau_hint_below` | Adds a Nouveau hint for sufficiently old legacy devices. |
| `kernel_substitution` | Enables replacement of the `KERNEL` command placeholder with the running Manjaro kernel package name. |
| `branch_suffix` | Suffix appended to a numeric branch in the `BRANCH` placeholder, currently `xx`. |
| `fallback_message` | Fallback message header. |
| `fallback_device_header` | Header for the unsupported/fallback device list; `{min_branch}` is substituted. |
| `fallback_package_template` | Package-name template for a fallback DKMS package. |
| `fallback_utils_template` | Package-name template for the matching userspace package. |
| `repo_available_note` | Note emitted when a legacy branch is handled by the configured distribution policy. |

The validator currently requires `fallback_method`, `kernel_substitution` and `branch_suffix`. The other fields are optional from the validator's perspective, but the CLI uses them when available.

### 2.3 Relationship to the global legacy threshold

`distro.yaml` is used after `check_legacy_devices()` has classified legacy devices against `min_supported_legacy_branch` from `overrides.yaml`.

With the current values:

- a branch below 580 is first placed in the unsupported-legacy set;
- the Manjaro distribution policy then applies `min_official_branch: 340` to determine whether that branch can be merged back into the configured legacy recommendation path;
- branches below the distribution threshold follow the configured fallback/error handling.

The two thresholds have different roles. Changing one without checking the other can alter which devices receive a normal branch recommendation versus a fallback message.

## 3. `overrides.yaml`

The current file contains:

```yaml
# Minimum legacy driver branch supported by the configured distributions.
# Legacy branches below this value are handled through the distribution's
# fallback policy. The 580 branch remains supported.
min_supported_legacy_branch: 580
```

`_validate_overrides()` requires this key to be a positive integer.

`check_legacy_devices()` uses it to separate legacy devices into:

- **supported legacy candidates:** numeric legacy branch greater than or equal to the threshold;
- **initially unsupported legacy devices:** numeric legacy branch below the threshold, or an invalid legacy-branch value.

The distribution-specific logic in `cli.py` may then merge a device back into the configured branch path if it meets the Manjaro `min_official_branch` policy. This is why the 580 threshold must be read together with `distro.yaml` rather than as a standalone package-availability statement.

## 4. `instructions.yaml`

The fork currently provides Manjaro-only install templates:

```yaml
instructions:
  manjaro-closed:
    - "sudo pacman -S KERNEL-nvidia"
  manjaro-open:
    - "sudo pacman -S KERNEL-nvidia-open"

branch_instructions:
  manjaro-closed:
    - "sudo pacman -S KERNEL-nvidia-BRANCH"
  manjaro-open:
    - "sudo pacman -S KERNEL-nvidia-BRANCH-open"
```

### 4.1 Placeholders

| Placeholder | Replacement |
|---|---|
| `KERNEL` | Running Manjaro kernel package name, for example `linux618`, when `kernel_substitution` is enabled. |
| `BRANCH` | Numeric branch plus the configured suffix, for example `580xx`. |

The `closed` templates select the proprietary kernel module. The `open` templates select the open kernel module. When `--install` is used, `output.py` executes the generated commands instead of only printing them; the NVIDIA EULA notice is displayed as part of that flow.

## 5. NVIDIA supportedchips documents

The parser in `supported_chips.py` handles five documents, each with a specific purpose:

| Branch/document | Parser path | Data exposed |
|---|---|---|
| Latest 6xx | `supportedchips.html` | Device-to-branch map and latest `Current` ID set |
| 580 | `supportedchips580.html` | 580 `Current` ID set |
| 470 | `supportedchips470.html` | 470 supported Device ID set |
| 390 | `supportedchips390.html` | 390 supported Device ID set |
| 340 | `supportedchips340.html` | 340 supported Device ID set |

### 5.1 Latest 6xx document

The latest document uses section anchors such as `Current` and `legacy_580.xx`, together with table rows whose IDs begin with `devidXXXX`. The parser builds a map from a four-digit PCI Device ID to `current` or a numeric legacy branch.

If a device appears in both a `Current` and a legacy section, the explicit legacy entry wins in the map. The `Device` class uses this data to fill in a missing JSON legacy branch. If JSON already provides a legacy branch and the HTML mapping disagrees, the code logs a warning and keeps the JSON value.

The `--mhwd-branch --mhwd-device-id` command uses this map for an individual-device branch query.

### 5.2 The 580 document

The 580 document is parsed separately. Only IDs in its `Current` section are exposed through `SUPPORTED_CHIPS_580`. This set is used by the mixed-GPU compatibility check for a legacy 580 device combined with a latest 6xx device.

### 5.3 The 470/390/340 documents

These older documents use ordinary HTML tables. The parser identifies the `Device PCI ID` column in each repeated table header and reads the first PCI Device ID token from that column. It stops when NVIDIA's own legacy-list introduction is reached, preventing later lists of older devices from being counted as supported by the document's target branch.

When the cell includes subsystem identifiers as well as the Device ID, only the first four-digit PCI Device ID is used. Subsystem Vendor IDs and Subsystem Device IDs are intentionally ignored for MHWD `.ids` generation.

## 6. MHWD `.ids` generation and audit

`mhwd_ids.py` exposes two standalone CLI operations.

### 6.1 Generate

```shell
nvidia-driver-assistant --generate-ids latest
nvidia-driver-assistant --generate-ids 580
nvidia-driver-assistant --generate-ids 470
nvidia-driver-assistant --generate-ids 390
nvidia-driver-assistant --generate-ids 340
```

The output is a header plus sorted, unique, four-digit PCI Device IDs. It is written to stdout; the caller, normally the relevant NVIDIA utils PKGBUILD, chooses the package staging destination.

### 6.2 Audit

```shell
nvidia-driver-assistant --check-ids
nvidia-driver-assistant --check-ids --ids-dir /path/to/ids
```

The audit is read-only. For each existing branch file it compares the listed IDs against the corresponding NVIDIA document and reports:

- IDs present in the document but missing from the file;
- IDs listed in the file but absent from the document;
- duplicate IDs;
- malformed tokens.

Only files that exist are checked. A missing optional branch file is skipped. A reported difference is a review item; the command does not repair the file automatically.

## 7. Configuration maintenance notes

- When the Manjaro legacy package policy changes, review `min_official_branch`, `fallback_branches` and `min_supported_legacy_branch` together.
- When adding or changing a driver branch, ensure the corresponding NVIDIA supportedchips document is downloaded and validated, the parser handles its format, and the relevant MHWD split package/config exists.
- Do not add subsystem IDs to the generated `.ids` output unless the MHWD config semantics are deliberately changed as well.
- Do not reintroduce an `architecture.yaml` dependency without updating `config.py`, `device.py`, the tests and this documentation. The current implementation does not load such a file.

## 8. Related documentation

- [Architecture.md](Architecture.md) — how the YAML settings and vendor documents feed the recommendation and MHWD integration.
- [Building.md](Building.md) — how the PKGBUILD obtains and validates the JSON, EULA and five supportedchips files, and how `.ids` files are generated.
- [Defense.md](Defense.md) — the security and correctness boundaries of the JSON/vendor-document decision path.
