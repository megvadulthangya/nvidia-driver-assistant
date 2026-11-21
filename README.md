# nvidia-driver-assistant — Manjaro fork

[![Compatibility Validation](https://github.com/megvadulthangya/nvidia-driver-assistant/actions/workflows/compatibility-validation.yml/badge.svg?branch=manjaro)](https://github.com/megvadulthangya/nvidia-driver-assistant/actions/workflows/compatibility-validation.yml)

A Manjaro-focused fork of NVIDIA's `nvidia-driver-assistant`. It detects NVIDIA GPUs, recommends a compatible driver branch and kernel-module flavour, provides Manjaro-specific installation instructions, and integrates with MHWD.

This README describes the maintainer's own `manjaro` branch and its expanded scope, including the 340xx and 390xx legacy-driver work. It does **not** describe official Manjaro packaging or imply that the maintainer's additional driver patches are part of the official Manjaro repositories.

---

## What this fork provides

- **NVIDIA GPU detection and recommendations** — detects NVIDIA devices through the system's PCI information and recommends the driver branch and `open` or `closed` kernel-module flavour.
- **Legacy driver classification** — uses NVIDIA's `supported-gpus.json` together with NVIDIA's `supportedchips.html` documents. The supported document set covers the latest 6xx branch and the 580, 470, 390 and 340 legacy branches.
- **Legacy kernel-module safety** — a GPU explicitly assigned to a legacy branch up to and including 580 is always directed to the proprietary (`closed`) kernel module, regardless of a contradictory `kernelopen` feature flag in the JSON.
- **Mixed-GPU handling** — considers whether the detected GPUs can share a common driver, including the special case of 580 legacy hardware combined with a latest 6xx GPU.
- **Two MHWD integration modes** — `authority` and `corrective`, described in [docs/Architecture.md](docs/Architecture.md).
- **MHWD PCI ID generation** — produces the `.ids` lists consumed by MHWD from NVIDIA's supported-device documentation.
- **MHWD PCI ID auditing** — compares installed `.ids` files with the relevant NVIDIA documents without modifying them.

The Assistant makes recommendations and provides integration data. It does not build the NVIDIA kernel modules itself. Driver packages and MHWD's configuration database remain separate components.

---

## Why this fork exists

NVIDIA's `supported-gpus.json` has previously marked legacy 580 GPUs, including the GTX 750 Ti, as `kernelopen`. The open kernel module does not support Maxwell, Pascal or Volta hardware, so blindly following that feature flag can produce an unusable recommendation.

This fork applies an explicit rule before relying on that flag: **a device with a detected legacy branch of 580 or lower requires the proprietary kernel module**. For GPUs identified as members of the latest 6xx `Current` list, the tool selects the open kernel module. Other cases use the feature information from `supported-gpus.json` as a fallback.

The relationship between the JSON and NVIDIA's supported-device documents is documented in [docs/Defense.md](docs/Defense.md). The code does not claim that every possible incorrect or manipulated JSON entry is automatically corrected; in particular, an existing JSON `legacybranch` is retained when it conflicts with the latest supportedchips mapping, and the discrepancy is logged.

---

## Scope and project structure

This is a **Manjaro-only** fork. The distribution registry currently contains Manjaro, and the installation templates are Manjaro-specific. It is not a multi-distribution replacement for NVIDIA's upstream tool.

The main Python package is `nvidia_driver_assistant/`:

```text
nvidia_driver_assistant/
├── cli.py               # CLI options and command dispatch
├── config.py            # Loads and validates the YAML policy files
├── hardware.py          # Hardware discovery
├── system.py            # Distribution detection
├── database.py          # supported-gpus.json loading and test devices
├── device.py            # Per-GPU classification and module-flavour rules
├── recommendation.py    # Driver and mixed-GPU recommendation logic
├── output.py            # Instructions and installation handling
├── supported_chips.py   # Parsers for NVIDIA supportedchips documents
├── mhwd_ids.py          # MHWD .ids generation and audit functions
└── data/
    ├── distro.yaml
    ├── overrides.yaml
    ├── instructions.yaml
    └── supportedchips*.html  # Added to the package during the build
```

The supportedchips HTML files are downloaded and validated by the package build; they are not maintained as static vendor documents in the Git repository. The upstream `supported-gpus.json` and NVIDIA EULA are extracted from NVIDIA's published DEB during packaging.

Runtime dependencies are Python 3 and PyYAML. The package build additionally uses the tools declared by its PKGBUILD, including Git, curl and libarchive.

---

## Installation

Build the package from this branch using `makepkg`:

```shell
git clone --branch manjaro \
  https://github.com/megvadulthangya/nvidia-driver-assistant.git
cd nvidia-driver-assistant
makepkg -si
```

`makepkg` downloads the upstream JSON/EULA payload and the five NVIDIA supportedchips documents, validates the documents with the fork's parser, and packages them with the Python code. See [docs/Building.md](docs/Building.md) for the complete process and the related MHWD packages.

---

## Command-line interface

```text
nvidia-driver-assistant [options]
```

With no special output mode, the tool detects the installed NVIDIA GPU or GPUs, prints the recommendation and displays the applicable Manjaro installation instructions. `--install` executes the generated installation commands.

### Detection and recommendation

| Option | Purpose |
|---|---|
| `--install` | Execute the recommended installation commands. |
| `--branch BRANCH` | Lock the recommendation to a numeric branch of 560 or newer. |
| `--supported-gpus PATH` | Use a specific `supported-gpus.json` file. |
| `--sys-path PATH` | Use an alternate sysfs root; useful for testing. |
| `--os-release-path PATH` | Use an alternate `os-release` file; useful for testing. |
| `--distro DISTRO[:VERSION]` | Override distribution detection; useful for testing. |
| `--module-flavor open\|closed` | Override the module flavour; useful for testing. |
| `--json` | Emit the recommendation and per-device classification as JSON. |
| `--verbose` | Enable verbose diagnostic logging. |

### MHWD integration

| Option | Purpose |
|---|---|
| `--mhwd` | Print only `open` or `closed`. Used by MHWD configuration scripts to select the kernel-module package. |
| `--mhwd-config` | Print the MHWD config name for the overall recommendation, such as `video-nvidia-580xx`. Used by the `authority` integration mode. |
| `--mhwd-branch --mhwd-device-id ID` | Print the NVIDIA supportedchips branch for one PCI Device ID (`current`, `580`, `470`, `390`, `340`, etc.). Used by the `corrective` integration mode. |

`--mhwd-branch` requires `--mhwd-device-id`. The device ID may be supplied with or without the `0x` prefix. An unknown or unclassifiable ID causes this command to fail rather than inventing a branch.

### MHWD `.ids` tools

| Option | Purpose |
|---|---|
| `--generate-ids BRANCH` | Generate an MHWD `.ids` list to standard output. Accepted values: `latest`, `6xx`, `580`, `470`, `390`, `340`. |
| `--check-ids` | Audit existing NVIDIA `.ids` files. Does not modify them. |
| `--ids-dir DIR` | Use a non-default directory for `--check-ids`; default is `/var/lib/mhwd/ids/pci`. |

The generation and audit options are standalone operations and cannot be combined with driver detection or installation options.

### Simulation options

| Option | Purpose |
|---|---|
| `--simulate-gpu KEY` | Simulate one GPU defined in the test database. |
| `--simulate-mixed` | Simulate a GTX 750 Ti (legacy 580) together with an RTX 5070. |
| `--simulate-badmix` | Simulate a GT 740A (legacy 470) together with an RTX 5070. |

The simulation options are mutually exclusive. They are useful for exercising decision paths without the corresponding physical GPUs; they do not replace hardware testing.

### JSON output

`--json` returns one object with the overall recommendation and a `devices` array. The current top-level fields are:

| Field | Meaning |
|---|---|
| `driver` | Driver family (`nvidia`). |
| `module_flavor` | Recommended module flavour: `open` or `closed`. |
| `branch` | Selected driver branch, or `null` when no explicit legacy branch is locked. |
| `legacy_closed_kernel_enforced` | Indicates that the legacy closed-module rule is enabled. |
| `min_supported_legacy_branch` | Current general legacy threshold from `overrides.yaml`. |
| `manjaro_min_official_legacy_branch` | Manjaro distribution-policy threshold from `distro.yaml`. |
| `arch_min_repo_legacy_branch` | Retained compatibility field; normally `null` in this Manjaro-only registry. |
| `arch_aur_only_branches` | Retained compatibility field; normally empty for this Manjaro-only registry. |
| `devices` | Per-GPU PCI ID, name, legacy state, subsystem IDs and supportedchips classifications. |

Each `devices[]` entry currently includes `pci_id`, `name`, `is_legacy`, `subsystem_vendor`, `subsystem_device`, `legacy`, `nvidia_supported_branch`, `supports_latest_6xx` and `supports_580`. The JSON output is intended for scripts and diagnostics; the CLI output is the user-facing recommendation.

### Examples

```shell
# Show the recommendation for detected hardware
nvidia-driver-assistant

# Return only the module flavour for MHWD
nvidia-driver-assistant --simulate-gpu 750 --mhwd
# Expected: closed

# A modern open-kernel-capable example
nvidia-driver-assistant --simulate-gpu 4070 --mhwd
# Expected: open

# Ask for the branch assigned to one NVIDIA PCI Device ID
nvidia-driver-assistant --mhwd-branch --mhwd-device-id 1380

# Generate a list for the 390xx MHWD package
nvidia-driver-assistant --generate-ids 390 > nvidia-390xx.ids

# Audit the system's installed MHWD NVIDIA lists (read-only)
sudo nvidia-driver-assistant --check-ids

# Audit a staging directory instead
nvidia-driver-assistant --check-ids --ids-dir ./staged-ids
```

`--generate-ids` writes to standard output; the caller decides where the output is saved. It does not write to `/var/lib/mhwd/ids/pci/` itself.

---

## How the recommendation works

The tool combines two NVIDIA data sources:

1. **`supported-gpus.json`** — provides device names, feature flags and the JSON `legacybranch` classification.
2. **NVIDIA `supportedchips.html` documents** — provide a device-to-driver-branch mapping and the per-branch device lists used by MHWD.

The current per-device kernel-module rules are:

- If a device has a legacy branch of 580 or lower, it requires the proprietary (`closed`) kernel module. A contradictory `kernelopen` flag does not override this rule.
- If a device is listed in the latest 6xx document's `Current` section and has no JSON legacy branch, it is treated as a current GPU and uses the open kernel module.
- Other devices use the supported feature flags from `supported-gpus.json` as the fallback.

The latest supportedchips document fills in a legacy branch only when the JSON does not provide one. If the JSON and the document disagree while the JSON already contains a legacy branch, the Assistant logs a warning and retains the JSON value.

For mixed systems, the tool checks whether a 580 legacy GPU can share the 580 driver with every other detected GPU. If all devices are present in the 580 `Current` list, branch 580 can be used with the closed module. Otherwise the recommendation prioritises the latest 6xx driver for the newer GPU and marks the incompatible legacy device for the existing unsupported-device handling. Legacy branches below the configured minimum are also subject to the Manjaro distribution policy in `distro.yaml`.

See [docs/Architecture.md](docs/Architecture.md), [docs/Configuration.md](docs/Configuration.md) and [docs/Defense.md](docs/Defense.md) for the exact decision paths and configuration fields.

---

## MHWD integration

The fork supports two alternative patches for MHWD. Select one mode when building the MHWD package:

- **`authority`** — the Assistant supplies the overall NVIDIA config branch through `--mhwd-config`. MHWD selects a matching available config and does not silently fall back to NVIDIA priority selection when the Assistant's result is invalid or unavailable.
- **`corrective`** — MHWD makes its normal priority-based selection first. The Assistant then checks the individual NVIDIA PCI Device ID through `--mhwd-branch --mhwd-device-id`; MHWD corrects the selected profile if its branch differs and a matching profile exists.

The modes are alternatives, not two patches to apply together. They are implemented in the MHWD packaging, not by changing the Assistant's decision engine. Detailed behaviour and limitations are described in [docs/Architecture.md](docs/Architecture.md).

---

## Related 340xx and 390xx legacy-driver maintenance

This branch documents the maintainer's related 340xx and 390xx driver work because it is part of the wider Manjaro legacy-NVIDIA effort.

The 340xx and 390xx package work is based on the corresponding Debian NVIDIA packaging/patch branches (`340xx/main` and `390xx/main`) and includes maintainer-provided follow-up work for Manjaro packaging, newer kernel compatibility and related fixes. These are the maintainer's own downstream package and patch-maintenance efforts; they are **not official Manjaro-maintained patches or packages**.

The NVIDIA Driver Assistant is a separate component. It classifies the hardware, recommends the available branch and can generate MHWD ID lists; it does not compile or maintain the 340xx/390xx kernel modules. See [docs/Building.md](docs/Building.md) for the relationship between the components.

---

## Testing and limitations

The repository contains the original test suite and an extended suite. They use `umockdev` to simulate hardware and do not require a physical NVIDIA GPU for the simulated cases:

```shell
PYTHONPATH=. python3 tests/run --suite test_nvidia_driver_assistant.py
PYTHONPATH=. python3 moretests/run --suite test_nvidia_driver_assistant.py
```

Passing simulated tests does not prove that an open kernel module works on every Turing-or-newer physical GPU, nor that every hybrid graphics configuration installs and operates correctly. Real-hardware testing is still valuable, especially for the `open` path and hybrid MHWD profiles.

The `.ids` audit is read-only. A difference between an installed ID list and NVIDIA's current document is reported for review; it does not automatically modify the list or prove that the driver itself cannot support the device.

---

## Documentation

- [Architecture](docs/Architecture.md) — recommendation flow, MHWD patches and installation chain.
- [Building](docs/Building.md) — package builds, NVIDIA source documents, `.ids` generation, MHWD patch modes and legacy driver package work.
- [Configuration](docs/Configuration.md) — YAML policy files and NVIDIA supportedchips data.
- [Defense](docs/Defense.md) — safeguards, trust boundaries and known limitations of the data sources.

## Acknowledgements

- Alberto Milone — original NVIDIA `nvidia-driver-assistant` project.
- Manjaro contributors — Manjaro's MHWD and distribution integration components on which this work builds.
- Gábor Gyöngyösi — maintainer of this fork and its additional Manjaro-focused functionality.

## License

The Python code and packaging files are MIT-licensed. NVIDIA's EULA is distributed separately from the upstream NVIDIA package payload.
