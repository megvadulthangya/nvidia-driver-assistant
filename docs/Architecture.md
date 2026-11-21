# Architecture

This document describes how the Manjaro fork classifies NVIDIA GPUs, selects a driver recommendation and integrates with MHWD. It covers the current implementation in the maintainer's `manjaro` branch.

## 1. Components and data flow

The recommendation path has four main parts:

1. **Hardware discovery** — the tool reads the system's PCI information and identifies NVIDIA display devices.
2. **Device classification** — `database.py`, `device.py` and `supported_chips.py` combine `supported-gpus.json` with NVIDIA's supportedchips documents.
3. **Recommendation logic** — `recommendation.py` and `cli.py` resolve the module flavour, legacy branch and mixed-GPU policy.
4. **Output and integration** — `output.py` prints or executes Manjaro installation instructions; MHWD can consume the dedicated CLI output modes.

The Assistant does not replace MHWD or the package manager. MHWD still resolves the installed configuration, removes conflicts, installs the packages and runs the configuration's hooks.

## 2. NVIDIA data sources

The fork uses two kinds of NVIDIA vendor data.

### 2.1 `supported-gpus.json`

The package build extracts `supported-gpus.json` and the NVIDIA EULA from NVIDIA's published `nvidia-driver-assistant` DEB. The JSON provides GPU names, feature flags and a `legacybranch` value when one is present.

The JSON remains the primary source for an explicitly populated `legacybranch`. The supportedchips parser can fill a missing legacy-branch value, but it does not silently replace an existing JSON value when the two sources disagree.

### 2.2 The five supportedchips documents

The package build downloads and validates five NVIDIA documents:

| Document installed in package data | Used for |
|---|---|
| `supportedchips.html` | Latest 6xx New Feature Branch mapping, including legacy section anchors and the latest `Current` device list |
| `supportedchips580.html` | Devices in the 580 branch's `Current` table |
| `supportedchips470.html` | The 470xx branch's own supported-device table |
| `supportedchips390.html` | The 390xx branch's own supported-device table |
| `supportedchips340.html` | The 340xx branch's own supported-device table |

The parser has two formats to handle:

- The latest and 580 documents use section anchors and `devidXXXX` table-row IDs. The first four hexadecimal digits are the PCI Device ID; any subsystem suffix in the row ID is not written to the MHWD list.
- The older 470/390/340 documents use ordinary HTML tables with a `Device PCI ID` column. The parser reads the first PCI ID in that column and ignores additional subsystem vendor/device IDs. It stops at the document's own legacy-list boundary so later, older driver lists are not accidentally included.

All five documents are validated during packaging. A missing, empty or unparseable document causes the build-time validation to fail instead of silently producing an incomplete package.

## 3. Per-device classification and module flavour

The current implementation is in `Device` (`device.py`). The relevant sequence is:

1. Read the JSON `legacybranch`, if present.
2. Look up the four-digit PCI Device ID in the latest supportedchips map.
3. If JSON does not provide a legacy branch and the latest supportedchips map identifies a legacy section, use that branch as the missing legacy classification.
4. If JSON already provides a legacy branch but the supportedchips map disagrees, log a warning and retain the JSON branch.
5. Determine whether the device appears in the 580 `Current` list and whether it appears in the latest 6xx `Current` list.
6. Resolve the module flavour.

The module-flavour rules in `_parse_features()` are deliberately simple and ordered:

- An explicit legacy branch of 580 or lower requires the proprietary (`closed`) kernel module. A `kernelopen` flag in JSON cannot override this.
- A device in the latest 6xx `Current` list, with no JSON legacy branch, is treated as a current GPU and requires the open kernel module.
- Remaining devices use the supported module-feature flags from `supported-gpus.json`.

The 580 `Current` membership is not itself a general open/closed decision. It is used by the mixed-GPU resolver to determine whether the whole detected set can use a common 580 driver.

## 4. Legacy branch selection

`recommendation.py` evaluates all detected NVIDIA devices and identifies the highest supported legacy branch and any unsupported legacy devices. The configured `min_supported_legacy_branch` is currently `580` in `data/overrides.yaml`.

The Manjaro-specific distribution policy is then applied by `cli.py` using `data/distro.yaml`. The current policy entry sets `min_official_branch: 340`; this value controls how the Assistant handles branches that were initially classified below its general supported-legacy threshold. It is a policy value in this fork and must be kept aligned with the actual package/repository policy. It is not a statement that the maintainer's custom Debian-based driver package work is official Manjaro packaging.

For a branch that is available through the configured policy, the Assistant merges the device back into the branch recommendation. For a branch below that policy threshold, the configured fallback behaviour is used.

## 5. Mixed-GPU policy

Mixed hardware needs more than a simple highest-branch comparison.

### 5.1 580 legacy plus latest 6xx

When at least one device is classified as legacy 580 and at least one device appears in the latest 6xx `Current` list, the tool checks whether **every detected NVIDIA device** is also present in the 580 `Current` list:

- If all devices are listed, the system can use branch 580 with the proprietary module.
- If any device is absent, there is no common 580 driver for the complete set. The recommendation prioritises the latest 6xx driver for the newer GPU and passes the incompatible 580 legacy device(s) to the existing unsupported-device handling.

This test uses the 580 document specifically. It does not assume that support in one legacy document implies support in another.

### 5.2 Other unsupported legacy hardware alongside a modern GPU

If the recommendation includes an open-capable modern GPU while another detected device requires a legacy branch below the configured supported threshold, the CLI's mixed-device handling prioritises the modern GPU. It reports that the incompatible legacy device will not work with the selected driver rather than claiming that one driver can serve both.

### 5.3 Simulations

`--simulate-mixed` covers the GTX 750 Ti (legacy 580) plus an RTX 5070. `--simulate-badmix` covers an older legacy 470 device plus an RTX 5070. These cases exercise the decision logic; they do not replace testing with physical hardware.

## 6. MHWD CLI interfaces

The Assistant exposes three MHWD-oriented output modes. They have distinct purposes.

| Command | Output | Scope | Used by |
|---|---|---|---|
| `nvidia-driver-assistant --mhwd` | `open` or `closed` | Overall module-flavour recommendation | MHWD config hooks / `nvidia-recommended-driver` |
| `nvidia-driver-assistant --mhwd-config` | Config name such as `video-nvidia-580xx` | Overall recommended branch | MHWD `authority` mode |
| `nvidia-driver-assistant --mhwd-branch --mhwd-device-id ID` | `current` or a numeric NVIDIA branch | One PCI Device ID | MHWD `corrective` mode |

These modes intentionally print only the requested value to standard output so that MHWD shell/C++ code can consume it safely.

### 6.1 `--mhwd-config`

`_resolve_mhwd_config()` maps the overall selected branch to the corresponding config name:

| Selected branch | Config name |
|---|---|
| No legacy branch / latest | `video-nvidia` |
| `580` | `video-nvidia-580xx` |
| `470` | `video-nvidia-470xx` |
| `390` | `video-nvidia-390xx` |
| `340` | `video-nvidia-340xx` |

The final config must also exist in the MHWD database and match the hardware according to its `DEVICEIDS` rules.

### 6.2 `--mhwd-branch --mhwd-device-id`

This is a per-device query. It normalises the supplied PCI Device ID and looks it up in the latest supportedchips mapping. It returns `current` or a numeric legacy branch. It deliberately does not run the global multi-GPU recommendation algorithm.

An unknown or invalid PCI ID returns a failure status. MHWD must not interpret a failed lookup as an arbitrary branch.

## 7. The two alternative MHWD integration modes

The MHWD package carries two alternative patches. Only one is selected for a given package build. They change how MHWD chooses the config; they do not change the Assistant's Python recommendation logic.

### 7.1 Authority mode

The authority patch calls `nvidia-driver-assistant --mhwd-config` before NVIDIA config selection. It extracts the branch from the returned config name and looks for an available MHWD profile for that branch.

- If the Assistant returns a valid result, MHWD selects an available profile with the matching NVIDIA branch.
- If the Assistant cannot return a valid config/branch, MHWD does not choose an NVIDIA driver by its usual priority order.
- If no matching profile exists for the NVIDIA device, that device is skipped with a warning instead of silently selecting a different NVIDIA branch.

This mode makes the Assistant's whole-system branch decision authoritative for NVIDIA selection. Non-NVIDIA handling remains within MHWD's existing logic.

### 7.2 Corrective mode

The corrective patch preserves MHWD's native priority-based selection as the starting point. It then checks each NVIDIA device using:

```shell
nvidia-driver-assistant --mhwd-branch --mhwd-device-id <PCI_DEVICE_ID>
```

The patch compares the returned branch with the branch encoded in the selected MHWD config:

- If the branches match, the original MHWD selection is retained.
- If the Assistant cannot determine a branch for that device, the original MHWD selection is retained.
- If the branches differ, MHWD searches for a config with the supported branch while retaining whether the original selection was a hybrid or non-hybrid profile.
- If no matching config exists, MHWD skips that device and reports the reason instead of installing the wrong branch.

This mode corrects MHWD's initial choice only when the per-device supportedchips information proves that another branch is required.

### 7.3 Selecting a mode

The MHWD PKGBUILD selects one patch through `NVIDIA_ASSISTANT_MODE`:

- `authority` selects `0001-mhwd-nvidia-assistant-integration.patch`.
- `corrective` selects `0002-mhwd-nvidia-assistant-corrective.patch`.

Do not apply both patches to the same MHWD source tree. The exact packaging details and patch application method are covered in [Building.md](Building.md).

## 8. MHWD config database and `.ids` files

MHWD config files use `DEVICEIDS` entries that can reference files under:

```text
/var/lib/mhwd/ids/pci/
```

The NVIDIA split packages continue to provide the `mhwd-nvidia*` package names because MHWD and the config database still depend on those package names and their `.ids` payloads. What has been retired in the relevant 390xx, 470xx, 580xx and latest package builds is the old `mhwd-nvidia` shell-script **generator**, not the MHWD split packages.

The current generator is:

```shell
nvidia-driver-assistant --generate-ids <branch>
```

It writes a comment header and a sorted, unique list of four-digit PCI Device IDs to standard output. It does not write to the live MHWD database itself. Package build functions redirect the output into the appropriate package staging directory.

To audit installed files without changing them:

```shell
sudo nvidia-driver-assistant --check-ids
```

The audit checks missing, undocumented, duplicate and malformed IDs against the corresponding NVIDIA supportedchips document. See [Building.md](Building.md) for examples.

## 9. Kernel-module package selection

The MHWD config database can use `nvidia-recommended-driver` (the `show-driver` compatibility wrapper) to invoke `nvidia-driver-assistant --mhwd`. This wrapper is retained for compatibility and is marked deprecated in the source script; new `MHWDCONFIG` code can call `nvidia-driver-assistant --mhwd` directly. The resulting `open` or `closed` value selects the matching kernel-module package in the config's `DEPKMOD` logic.

This is separate from selecting the MHWD config name. In short:

- `--mhwd-config` selects the branch-specific MHWD profile.
- `--mhwd` selects the open or proprietary module flavour within the profile.

The Assistant reports the decision; the MHWD script and pacman perform the installation.

## 10. Boundaries and limitations

- The two MHWD modes are alternatives and have different decision scopes: whole-system authority versus per-device correction.
- Both modes require the Assistant executable, the relevant MHWD configs and their `.ids` data to be installed.
- A branch can be correctly identified by the Assistant but still be unavailable if the MHWD database does not contain a matching profile.
- The corrective mode retains MHWD's native selection when a per-device lookup fails; this is deliberate fallback behaviour, not proof that the priority choice is correct.
- The authority mode does not silently fall back to NVIDIA priority selection when its branch cannot be resolved or matched.
- Mixed-GPU behaviour must be validated against the actual hardware and the exact set of installed MHWD hybrid profiles.
