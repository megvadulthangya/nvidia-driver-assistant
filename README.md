# nvidia-driver-assistant

[![Compatibility Validation](https://github.com/megvadulthangya/nvidia-driver-assistant/actions/workflows/compatibility-validation.yml/badge.svg?branch=refactor)](https://github.com/megvadulthangya/nvidia-driver-assistant/actions/workflows/compatibility-validation.yml?branch=refactor)

Detects NVIDIA GPUs, recommends the optimal driver (open/proprietary kernel
modules) and legacy branch, handles multi-GPU and legacy hardware scenarios,
and provides distribution-aware installation instructions across 13 Linux
distributions.

## Project structure

The core logic lives in the `nvidia_driver_assistant/` Python package:

```
nvidia_driver_assistant/
├── __init__.py          # Re-exports all public symbols (backward compat)
├── cli.py               # argparse setup, main() entry point coordination
├── config.py            # YAML loader, validator, configuration exports
├── hardware.py          # PCI modalias collection, chassis detection
├── system.py            # SystemInfo class, distro detection, alias mapping
├── database.py          # GPU JSON loading, device matching, simulation data
├── device.py            # Device class, architecture detection, _parse_features()
├── recommendation.py    # Driver recommendation, legacy branch logic
├── output.py            # Instruction display, formatting, driver installation
└── data/
    ├── architecture.yaml   # 14 GPU architectures (regex patterns, open-capable flags, min_driver)
    ├── distro.yaml         # 13 distro definitions + supported_distros list
    ├── overrides.yaml      # Control variables (min_supported_legacy_branch, etc.)
    ├── instructions.yaml   # All distro × driver installation instruction templates
    └── supported-gpus.json # Symlink to supported-gpus/supported-gpus.json
```

The top-level `nvidia-driver-assistant` script is a thin wrapper (~55 lines) that
imports from the package, preserving backward compatibility with the existing CLI
interface and the test harness's `importlib`-based import mechanism.

### Dependencies

- Python 3 with `gi` (GObject Introspection) for hardware detection
- `pyyaml` — for loading the YAML configuration files

## Command line interface

By default, the `nvidia-driver-assistant` command line tool will show the driver
packages suitable for the hardware, and print the instructions relevant to
the current Linux distribution (see the list of supported Linux
distributions in the next section).

Optionally, `nvidia-driver-assistant --install`, can also install the driver
automatically.

Additional supported arguments:
- `--branch [BRANCH]` - Specify the desired NVIDIA driver branch
- `--list-supported-distros` - Print out the list of the supported Linux distributions and exit
- `--supported-gpus [SUPPORTED_GPUS]` - Use a different version of the `supported-gpus.json` file
- `--sys-path [SYS_PATH]` - Use a different /sys path. Useful for testing
- `--os-release-path [OS_RELEASE_PATH]` - Use a different path for the os-release file. Useful for testing
- `--distro [DISTRO]` - Specify a Linux distro using the `"DISTRO:VERSION"` or `"DISTRO"` pattern. Useful for testing
- `--module-flavor [MODULE_FLAVOR]` - Specify a kernel module flavor (`open` or `closed`). Useful for testing
- `--simulate-gpu [GPU]` - Simulate a GPU for testing without real hardware. Accepted values: `545`, `nvs290`, `7150m`, `740A`, `750`, `800A`, `4070`, `5070`, `unknown`
- `--simulate-mixed` - Simulate a mixed-GPU system (GTX 750 Ti [legacy 580] + RTX 5070 [modern]). Useful for testing mixed-GPU policy
- `--simulate-badmix` - Simulate a mixed-GPU system (GT 740A [legacy 470] + RTX 5070 [modern]). Useful for testing unsupported legacy + modern GPU policy
- `--mhwd` - MHWD compatibility mode (Manjaro Hardware Detection); prints only the module flavor (`open`/`closed`) for consumption by `mhwd`
- `--json` - Emit the recommendation as JSON, intended for installers and other automation
- `--verbose` - Verbose output

Note: `--simulate-gpu`, `--simulate-mixed`, and `--simulate-badmix` are mutually
exclusive — only one may be specified at a time.

Please see `nvidia-driver-assistant --help` for further details.

## Supported Linux distributions

The following Linux distributions are currently supported:

- Amazon Linux 2023
- Arch Linux
- CBL-Mariner (Azure Linux)
- Debian
- Fedora
- Kylin
- Manjaro
- openSUSE
- Oracle Linux
- Red Hat Enterprise Linux (RHEL)
- Rocky Linux
- SUSE Linux Enterprise Server (SLES)
- Ubuntu

The exact set of accepted distribution aliases can also be queried at runtime
with `nvidia-driver-assistant --list-supported-distros`.

## Supported GPU architectures

The hardware database and architecture-based logic cover the following NVIDIA
GPU architectures (newest to oldest):

- `blackwell`
- `ada`
- `ampere`
- `turing`
- `volta`
- `pascal`
- `maxwell`
- `kepler`
- `fermi`
- `tesla2`
- `tesla1`
- `curie`
- `pre-curie`

Architectures `turing`, `ampere`, `ada` and `blackwell` are eligible for the
open kernel modules; older architectures require the proprietary modules. Each
architecture is also mapped to a minimum compatible driver branch, which is
used to pick a working legacy driver when no current driver supports the GPU.

## Legacy driver support

`nvidia-driver-assistant` performs distribution-aware legacy driver handling
based on the `legacybranch` field in `supported-gpus.json`:

- The currently accepted minimum legacy driver branch is **580** (anything
  below that is considered no longer supported by current NVIDIA drivers).
- For non-legacy GPUs the recommended branch falls out of the device entries
  and the system's package manager defaults.
- Distribution-specific legacy driver policies (e.g., which branches are
  available in official repositories vs. AUR, fallback behavior) are configured
  in `data/distro.yaml`. See [docs/Configuration.md](docs/Configuration.md) for
  detailed documentation on per-distro configuration and current policies.

## JSON output format

When invoked with `--json`, the tool prints a single JSON object on stdout
describing the recommendation. The shape is:

```json
{
  "driver": "nvidia",
  "module_flavor": "open" | "closed",
  "branch": "<branch or null>",
  "distro_non_legacy_default": "<branch or null>",
  "distro_580_legacy_override": "<branch or null>",
  "legacy_openkernel_restriction": true,
  "architecture_check_enabled": true,
  "devices": [
    {
      "pci_id": "10DE:XXXX",
      "name": "GeForce ...",
      "architecture": "ada",
      "type": "desktop" | "mobile",
      "is_laptop": false,
      "is_legacy": false,
      "subsystem_vendor": "10DE",
      "subsystem_device": "XXXX",
      "supported_min_driver": "<branch or null>",
      "supported_max_driver": "<branch or null>",
      "legacy": "<branch or null>"
    }
  ]
}
```

This format is intended to be consumed by installers and scripts that need to
choose the right NVIDIA driver package without parsing human-readable output.

## Mixed-GPU policy

When a system contains multiple NVIDIA GPUs from different generations, the
tool applies special logic to determine the best recommendation:

### Supported legacy (580) + modern GPU (`--simulate-mixed`)

Example: GTX 750 Ti (legacy 580) + RTX 5070 (modern, open-capable).

Both GPUs are supported (580 is the minimum supported legacy branch). The
recommendation engine initially selects `open` for the modern GPU, but the
CLI safety-net detects that the legacy 580 branch is active and that GPUs on
this branch are **not capable** of using open kernel modules. The final
recommendation is overridden to `closed` with the branch locked to `580`.

### Unsupported legacy (<580) + modern GPU (`--simulate-badmix`)

Example: GT 740A (legacy 470) + RTX 5070 (modern, open-capable).

The 740A is on legacy branch 470, which is below `min_supported_legacy_branch`
(580) and therefore unsupported. The CLI detects the presence of an
open-capable modern GPU and discards the unsupported legacy device. The final
recommendation is `open` with no branch lock. The legacy GPU will **not** work
with the recommended driver.

## Test suite

To use the test suite `nvidia-driver-assistant` comes with, you are going to
need the following dependencies:

- `python3-gi`
- `pyyaml`
- `umockdev` and `gir1.2-umockdev-1.0`

There are two test directories:

- `tests/` — the original/baseline test suite (11 tests). Covers distro
  detection, modalias collection, device matching, CLI argument validation,
  driver recommendation, and instruction generation.
- `moretests/` — an extended test suite (16 tests) that additionally exercises
  legacy driver branch handling, mixed-GPU policy (`--simulate-mixed`,
  `--simulate-badmix`), Manjaro/Arch AUR fallbacks, the `--json` and `--mhwd`
  output modes, and the `supported-gpus-bad/` database fixtures (intentionally
  malformed input used to verify error handling). The mixed-GPU tests run
  across multiple distros (fedora, manjaro, debian, ubuntu) and print verbose
  reports explaining the policy, expected vs actual results, and PASS/FAIL
  for each assertion.

The test suites can be run as follows:

```shell
$ PYTHONPATH=. python3 tests/run --suite test_nvidia_driver_assistant.py
$ PYTHONPATH=. python3 moretests/run --suite test_nvidia_driver_assistant.py
```

Note: no actual NVIDIA hardware is required for testing, since umockdev is
      used to simulate the presence of such devices. The `--simulate-gpu`,
      `--simulate-mixed`, and `--simulate-badmix` flags can additionally be
      used to drive the tool itself against simulated GPUs from the command
      line:

```shell
# Single modern GPU on Ubuntu 24.04
$ PYTHONPATH=. ./nvidia-driver-assistant --simulate-gpu ada --distro ubuntu:24.04

# Mixed-GPU scenarios (JSON output)
$ PYTHONPATH=. ./nvidia-driver-assistant --simulate-mixed --distro fedora --json
$ PYTHONPATH=. ./nvidia-driver-assistant --simulate-badmix --distro manjaro --json
```


## For distribution maintainers and packagers

For detailed documentation on configuration, per-distro legacy branch policies,
and how to add support for new distributions, see [docs/Configuration.md](docs/Configuration.md).

## Authors and acknowledgment
- Alberto Milone &lt;amilone@nvidia.com&gt; — original author
- Manjaro Team — packaging adjustments and distribution-specific compatibility fixes
- Gábor Gyöngyösi &lt;megvadulthangya@gmail.com&gt; — refactoring and enhancements


## License
All the included code and assets are MIT licensed.
