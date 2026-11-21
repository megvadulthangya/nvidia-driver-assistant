# NVIDIA Driver Assistant — Manjaro integration

A Manjaro-focused fork of NVIDIA's `nvidia-driver-assistant`. It detects NVIDIA GPUs, determines a suitable NVIDIA driver branch and kernel-module flavour, and exposes a command-line interface for both users and Manjaro's `mhwd` tooling.

The project also provides the NVIDIA PCI Device ID data used by MHWD. It can generate and audit the `.ids` files consumed by MHWD's NVIDIA profiles.

> **Scope:** This branch documents the Manjaro-targeted integration. It describes the capabilities of this program separately from the driver packages currently available in Manjaro's repositories.

## Main capabilities

- Detect NVIDIA display devices from PCI information in sysfs.
- Match detected PCI Device IDs against NVIDIA's `supported-gpus.json` data.
- Use NVIDIA's `supportedchips.html` documents to classify legacy branches and determine Current-device support.
- Recommend the `open` or `closed` NVIDIA kernel-module flavour.
- Handle supported legacy branches and report when a detected GPU needs a driver outside the current Manjaro repository set.
- Evaluate multi-GPU configurations, including mixed legacy-580 and latest-6xx systems.
- Provide machine-readable output with `--json`.
- Integrate with MHWD through dedicated command-line interfaces.
- Generate MHWD `.ids` lists for 6xx/latest, 580, 470, 390 and 340.
- Audit existing MHWD `.ids` files without changing them.

## Driver branches and distribution availability

The Assistant understands five NVIDIA driver generations for its data-processing and MHWD-ID functions:

| Branch | Assistant capability | Current Manjaro package availability |
|---|---|---|
| Latest 6xx | Full support | Current driver line |
| 580xx | Full support | Legacy driver line |
| 470xx | Full support | Legacy driver line |
| 390xx | Full support | Oldest legacy branch currently available in the Manjaro package set |
| 340xx | Full support in the Assistant | Not currently provided by the Manjaro repositories |

**The 340xx capability is intentionally retained.** The program can classify 340xx hardware, read and validate NVIDIA's 340 supported-device document, generate a 340xx MHWD ID list, and audit an existing 340xx `.ids` file. The current Manjaro distribution policy starts repository availability at 390xx, so recognizing a 340xx GPU does not mean that Manjaro's repositories provide a 340xx driver or MHWD profile.

The two boundaries are configured separately:

- `min_supported_legacy_branch` controls the Assistant's legacy-branch recommendation handling.
- `min_official_branch` in `distro.yaml` describes the lowest legacy branch currently available in Manjaro's repositories (390).

See [Configuration](docs/Configuration.md) for details.

## How the data is used

The build retrieves two kinds of NVIDIA data:

1. **`supported-gpus.json` and the NVIDIA EULA** are extracted from NVIDIA's latest published `nvidia-driver-assistant` DEB.
2. **Five NVIDIA `supportedchips.html` documents** are downloaded for the latest 6xx, 580, 470, 390 and 340 driver generations.

The parser handles both the modern anchor/row-ID format used by the latest and 580 documents and the older table format used by 470, 390 and 340. The PKGBUILD validates all five documents before packaging.

The documents have different roles. The latest document provides the per-device legacy/current classification used by the recommendation and MHWD branch-query paths. The 580 Current list is used to check whether all devices in a mixed 580/6xx system have a common 580 driver. The 470, 390 and 340 documents are also used to generate and audit their respective MHWD ID lists.

## Installation and build

The package is built with `makepkg` from this branch:

```shell
git clone --branch manjaro-upstream \
  https://github.com/megvadulthangya/nvidia-driver-assistant.git
cd nvidia-driver-assistant
makepkg -si
```

The package has Python and PyYAML runtime dependencies. The PKGBUILD installs the command-line program, its Python modules and data, the compatibility wrapper `nvidia-recommended-driver`, `supported-gpus.json`, the NVIDIA EULA, and the packaged documentation.

The MHWD application and the MHWD database are separate Manjaro packages. The patches and their build configuration are maintained in the associated PKGBUILDs repository. See [Building](docs/Building.md).

## Command-line reference

```text
nvidia-driver-assistant [options]
```

With no special output mode, the program detects the available NVIDIA GPUs, prints a summary, and displays the recommended driver instructions. `--install` executes the generated installation command instead of only displaying it.

### Detection and recommendation

| Option | Description |
|---|---|
| `--install` | Execute the recommended installation command. |
| `--branch BRANCH` | Lock the requested driver branch. Values below 560 are rejected by this option. |
| `--supported-gpus PATH` | Use a specified `supported-gpus.json` file. |
| `--sys-path PATH` | Use an alternate sysfs root; intended for testing. |
| `--os-release-path PATH` | Use an alternate `os-release` file; intended for testing. |
| `--distro DISTRO[:VERSION]` | Override detected distribution information; intended for testing. |
| `--module-flavor open\|closed` | Override the selected module flavour for testing. |
| `--json` | Print the recommendation and per-device details as JSON. |
| `--verbose` | Enable verbose diagnostic logging. |

### Simulated hardware

| Option | Simulated device or scenario |
|---|---|
| `--simulate-gpu 545` | GeForce 545 |
| `--simulate-gpu nvs290` | Quadro NVS 290 |
| `--simulate-gpu 7150m` | GeForce 7150M / nForce 630M |
| `--simulate-gpu 740A` | GeForce 740A |
| `--simulate-gpu 750` | GeForce GTX 750 Ti |
| `--simulate-gpu 800A` | GeForce 800A |
| `--simulate-gpu 4070` | GeForce RTX 4070 |
| `--simulate-gpu 5070` | GeForce RTX 5070 Laptop |
| `--simulate-gpu unknown` | Unknown NVIDIA device entry |
| `--simulate-mixed` | GTX 750 Ti (legacy 580) + RTX 5070 (latest 6xx) |
| `--simulate-badmix` | GeForce 740A (legacy 470) + RTX 5070 (latest 6xx) |

The three simulation options are mutually exclusive. Simulation is useful for exercising the recommendation logic without the corresponding physical GPUs; it does not replace real-hardware validation.

### MHWD integration interfaces

| Option | Description |
|---|---|
| `--mhwd` | Print only `open` or `closed` for MHWD's kernel-module selection. |
| `--mhwd-config` | Print the MHWD NVIDIA config name for the current system recommendation. |
| `--mhwd-branch --mhwd-device-id ID` | Print the NVIDIA supported branch for one PCI Device ID. The result is a numeric legacy branch or `current`. |

Examples:

```shell
# Kernel-module flavour for the detected system
nvidia-driver-assistant --mhwd

# Recommended MHWD config name
nvidia-driver-assistant --mhwd-config

# Classify one PCI Device ID (0x prefix is optional)
nvidia-driver-assistant --mhwd-branch --mhwd-device-id 1380
```

`--mhwd-branch` deliberately evaluates one Device ID at a time. It does not run the system-wide multi-GPU recommendation. An unknown ID or an unavailable classification returns a non-zero exit status.

`--mhwd-config` is subject to the Manjaro package-availability policy. If the detected GPU requires a branch that Manjaro cannot install through its available MHWD profiles (currently including 340xx), the command exits unsuccessfully rather than inventing an available profile.

### MHWD ID generation and audit

| Option | Description |
|---|---|
| `--generate-ids BRANCH` | Generate one MHWD `.ids` list on standard output. Accepted values: `latest`, `6xx`, `580`, `470`, `390`, `340`. |
| `--check-ids` | Audit any recognized NVIDIA `.ids` files found in the target directory. This mode does not modify files. |
| `--ids-dir DIR` | Directory to audit with `--check-ids`; default: `/var/lib/mhwd/ids/pci`. |

Examples:

```shell
# Generate ID lists; the caller chooses the output file
nvidia-driver-assistant --generate-ids latest > nvidia.ids
nvidia-driver-assistant --generate-ids 580 > nvidia-580xx.ids
nvidia-driver-assistant --generate-ids 470 > nvidia-470xx.ids
nvidia-driver-assistant --generate-ids 390 > nvidia-390xx.ids
nvidia-driver-assistant --generate-ids 340 > nvidia-340xx.ids

# Audit the live MHWD ID directory without changing it
nvidia-driver-assistant --check-ids

# Audit a staging directory
nvidia-driver-assistant --check-ids --ids-dir ./staged-ids
```

Generation writes only to standard output. It does not write into `/var/lib/mhwd`; package build functions redirect the output into their own staging directories. The audit reports missing, undocumented, duplicate and malformed IDs. It checks only the files that are present; it does not require every branch-specific file to exist.

`--generate-ids` and `--check-ids` are standalone operations and cannot be combined with hardware-detection or installation options. `--ids-dir` is valid only with `--check-ids`.

### Example recommendations

```shell
# Simulated legacy-580 GPU: proprietary module
nvidia-driver-assistant --simulate-gpu 750 --mhwd
# closed

# Simulated latest-6xx GPU: open module
nvidia-driver-assistant --simulate-gpu 4070 --mhwd
# open
```

## JSON output

`--json` emits a single JSON object containing:

- `driver`, `module_flavor` and the effective `branch`;
- `legacy_closed_kernel_enforced` and `min_supported_legacy_branch`;
- the Manjaro and retained Arch compatibility policy fields;
- one record per detected device, including PCI ID, device name, subsystem IDs, the resolved legacy branch, the latest NVIDIA-document classification, and the `supports_latest_6xx` / `supports_580` flags.

The exact schema is defined by the current `cli.py`. Consumers should treat it as a machine interface and validate fields they depend on.

## MHWD integration

The Assistant exposes three distinct interfaces for the MHWD integration:

- `--mhwd-config` supplies a system-level profile name.
- `--mhwd-branch --mhwd-device-id ID` supplies a per-device branch classification.
- `--mhwd` supplies the `open` or `closed` kernel-module flavour used by MHWD configuration scripts.

The MHWD package offers two alternative integration modes, selected by `NVIDIA_ASSISTANT_MODE` in its PKGBUILD:

- **authority:** the Assistant's system-level config recommendation drives NVIDIA profile selection.
- **corrective:** MHWD makes its normal priority-based selection first; the Assistant checks each NVIDIA PCI Device ID and corrects a mismatched branch when a matching profile is available.

Only one patch is applied in a build. The Manjaro-targeted MHWD PKGBUILD uses the standard GNU `patch` utility. The full call chain and mode differences are described in [Architecture](docs/Architecture.md).

## 340xx capability and Manjaro availability

The Assistant intentionally retains 340xx support in its code and data-processing interfaces. This includes:

- reading and parsing `supportedchips340.html`;
- using the latest `supportedchips.html` mapping to classify a device where that document provides a legacy branch;
- recognizing a 340xx legacy branch and applying the legacy closed-kernel-module rule;
- generating `nvidia-340xx.ids` with `--generate-ids 340`;
- auditing an existing `nvidia-340xx.ids` file with `--check-ids`.

The Manjaro distribution configuration sets `min_official_branch: 390`. Therefore, 340xx is outside the currently available Manjaro repository driver set. For a 340xx GPU, the normal recommendation path reports the unavailable legacy branch and follows the configured fallback instructions. The Assistant's retained technical capability must not be mistaken for a 340xx package or MHWD profile being present in Manjaro's repositories.

## Tests

The repository includes parser tests, MHWD ID-generation/audit tests, and the original and extended hardware/recommendation suites. Run them from the repository root:

```shell
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_supported_chips_parser.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_mhwd_ids.py' -v
PYTHONPATH=. python3 tests/run --suite test_nvidia_driver_assistant.py
PYTHONPATH=. python3 moretests/run --suite test_nvidia_driver_assistant.py
```

The compatibility-validation GitHub Actions workflow downloads and validates all five NVIDIA documents, runs the parser and ID tests, and executes the original and extended test suites. A successful simulated test does not prove operation on every physical GPU, kernel or hybrid-GPU configuration.

## Documentation

- [Architecture](docs/Architecture.md) — decision flow and MHWD integration.
- [Building](docs/Building.md) — package build, NVIDIA data retrieval, MHWD packaging and tests.
- [Configuration](docs/Configuration.md) — YAML policy and NVIDIA supported-device documents.
- [Defense](docs/Defense.md) — module-flavour safeguards, data-source boundaries and limitations.

## Credits and licence

This project is based on NVIDIA's `nvidia-driver-assistant`. The fork contains Manjaro-focused packaging and integration changes. See `COPYING` for the source licence. NVIDIA's driver EULA is distributed separately from the upstream DEB in the package's licence directory.
