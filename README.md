# nvidia-driver-assistant (Manjaro fork)

A fork of NVIDIA's `nvidia-driver-assistant`, reduced to Manjaro-only
and extended with a defense against `supported-gpus.json`
manipulation.

The tool detects NVIDIA GPUs, recommends the optimal driver (open or
proprietary kernel modules) and legacy branch, handles multi-GPU and
legacy hardware scenarios, and provides Manjaro-specific installation
instructions. It integrates with `mhwd` through a small patch to the
`mhwd` binary and a fork of the `mhwd-db` configuration database.

---

## Why this fork exists

In November 2025, NVIDIA released a `supported-gpus.json` that marked
every legacy 580 GPU (`GTX 750 Ti`, `GTX 1080 Ti`, `TITAN V`, …) as
`kernelopen`, even though the open kernel module cannot bind to
Maxwell, Pascal, or Volta hardware. The upstream tool followed the
JSON and recommended `nvidia-open-580` for those cards, which does
not produce a working driver.

The same JSON is still shipped in the most recent upstream release
(`0.62.71.10`, 2026-09-24). The upstream Python code still trusts
the `kernelopen` flag for the module-flavor decision. A system with a
stock `nvidia-driver-assistant` still resolves the GTX 750 Ti to
`nvidia-open-580`.

This fork does not patch the JSON. It uses the JSON as one input
among many, and it does not use the JSON for the decision that the
JSON has historically gotten wrong. The hardcoded rules in
`overrides.yaml` and `architecture.yaml` produce the same output
regardless of what the JSON says.

The full rationale, the code paths, and the maintenance comparison
with the patch-based approach are in
[docs/Defense.md](docs/Defense.md). Read that document before
modifying `_parse_features()` or `overrides.yaml`.

---

## What this fork is, and is not

**Is:**

- A drop-in replacement for `nvidia-driver-assistant` on Manjaro.
- A defense against a specific class of JSON manipulation.
- A packaging layer that takes `supported-gpus.json` and the NVIDIA
  EULA from the latest upstream DEB automatically.
- An `mhwd` integration with a `--mhwd-config` flag and a patched
  `mhwd` binary.
- A fork of `mhwd-db` with the 340xx and 580xx configs, and with
  `DEPKMOD` selected by `nvidia-recommended-driver`.

**Is not:**

- A multi-distribution tool. The 13 distro entries of the upstream
  have been removed. `supported_distros` contains only `manjaro`.
- A patched JSON. The JSON is downloaded verbatim from the upstream
  DEB. The defense is in the code.
- A replacement for `mhwd`. `mhwd` still does the installation; the
  fork only chooses the config and the module flavor.

---

## Project structure

The core logic is in the `nvidia_driver_assistant/` Python package:

```
nvidia_driver_assistant/
├── __init__.py          # Re-exports all public symbols
├── cli.py               # argparse setup, main() entry point
├── config.py            # YAML loader, validator, derived constants
├── hardware.py          # PCI modalias collection, chassis detection
├── system.py            # SystemInfo, distro detection
├── database.py          # GPU JSON loading, device matching, simulation data
├── device.py            # Device class, architecture detection, _parse_features()
├── recommendation.py    # Driver recommendation, legacy branch logic
├── output.py            # Instruction display, driver installation
├── supported_chips.py   # Parser for supportedchips.html
└── data/
    ├── architecture.yaml   # GPU architectures (regex patterns, open-capable flag, min_driver)
    ├── distro.yaml         # Manjaro legacy branch policy
    ├── overrides.yaml      # Control variables (min_supported_legacy_branch, etc.)
    └── instructions.yaml   # Manjaro × driver installation templates
```

The top-level `nvidia-driver-assistant` script is a thin wrapper that
imports from the package. It exists for backward compatibility with
the CLI interface and the test harness.

The `supportedchips.html` file is not in the repository. It is
downloaded by the PKGBUILD at build time and installed into the
package's `data/` directory. See [docs/Building.md](docs/Building.md)
Section 6.

### Dependencies

- Python 3
- `pyyaml` — for loading the YAML configuration files

There is no `gi` dependency: hardware detection uses sysfs, not
`hwinfo`.

---

## Installation

The package is built with `makepkg`:

```shell
$ git clone --branch manjaro \
    https://github.com/megvadulthangya/nvidia-driver-assistant.git
$ cd nvidia-driver-assistant
$ makepkg -si
```

The patched `mhwd` and the `mhwd-db` fork are separate packages.
See [docs/Building.md](docs/Building.md) for the build order.

---

## Command line interface

```
nvidia-driver-assistant [options]
```

By default, the tool prints the detected GPU(s) and the commands to
install the recommended driver. With `--install`, it executes the
commands instead.

### Options

| Flag | Description |
|---|---|
| `--install` | Install the recommended driver |
| `--branch <BRANCH>` | Lock the branch to a specific value (must be ≥ 560) |
| `--supported-gpus <PATH>` | Use a different `supported-gpus.json` |
| `--sys-path <PATH>` | Use a different `/sys` path (testing) |
| `--os-release-path <PATH>` | Use a different `os-release` file (testing) |
| `--distro <DISTRO[:VERSION]>` | Override the detected distro (testing) |
| `--module-flavor <open\|closed>` | Override the module flavor (testing) |
| `--mhwd` | Print `open` or `closed` only. Used by the `mhwd-db` configs via `nvidia-recommended-driver` |
| `--mhwd-config` | Print the mhwd config name only (e.g. `video-nvidia-580xx`). Called by the patched `mhwd` |
| `--json` | Emit the recommendation as JSON (see below) |
| `--simulate-gpu <KEY>` | Simulate a single GPU. See [docs/Building.md](docs/Building.md) Section 9.2 for the list of keys |
| `--simulate-mixed` | Simulate GTX 750 Ti (legacy 580) + RTX 5070 (modern) |
| `--simulate-badmix` | Simulate GT 740A (legacy 470) + RTX 5070 (modern) |
| `--verbose` | Verbose output |

`--simulate-gpu`, `--simulate-mixed`, and `--simulate-badmix` are
mutually exclusive.

### Examples

```shell
# Detected GPU, print installation instructions
$ nvidia-driver-assistant

# Detected GPU, install directly
$ sudo nvidia-driver-assistant --install

# Simulated GTX 750 Ti (legacy 580)
$ nvidia-driver-assistant --simulate-gpu 750 --verbose
...
Legacy GPU detected. Using driver branch 580.

Please copy and paste the following command to install the legacy
kernel module flavour:
  sudo pacman -S linux618-nvidia-580xx

# Simulated RTX 4070 (modern, open-capable)
$ nvidia-driver-assistant --simulate-gpu 4070 --mhwd
open

# Config name, for mhwd
$ nvidia-driver-assistant --mhwd-config
video-nvidia-580xx
```

---

## JSON output format

With `--json`, the tool prints a single JSON object on stdout:

```json
{
  "driver": "nvidia",
  "module_flavor": "open" | "closed",
  "branch": "<branch or null>",
  "distro_non_legacy_default": "<branch or null>",
  "distro_580_legacy_override": "<branch or null>",
  "legacy_openkernel_restriction": true,
  "architecture_check_enabled": true,
  "manjaro_min_official_legacy_branch": 340,
  "arch_min_repo_legacy_branch": null,
  "arch_aur_only_branches": [580],
  "devices": [
    {
      "pci_id": "0x1380",
      "name": "NVIDIA GeForce GTX 750 Ti",
      "architecture": "maxwell",
      "type": "desktop",
      "is_laptop": false,
      "is_legacy": true,
      "subsystem_vendor": "0x10DE",
      "subsystem_device": "0x18FE",
      "supported_min_driver": "390",
      "supported_max_driver": "580",
      "legacy": "580"
    }
  ]
}
```

`manjaro_min_official_legacy_branch` and
`arch_min_repo_legacy_branch` are read from the loaded
`DISTRO_REGISTRY`. The Arch fields are retained from upstream for
compatibility with the shared `_check_driver_compatibility()` code
path; they are not used by the Manjaro-only `distro_registry`.

The format is stable and intended for installers and automation.

---

## How the recommendation is made

The decision logic is in `Device._parse_features()`. It runs these
steps in order and returns on the first that applies:

| Step | Condition | Effect |
|---|---|---|
| 0 | `supportedchips.html` maps the device to a legacy branch | Force `proprietary_required` |
| 1 | `DISTRO_NON_LEGACY_DEFAULT_BRANCH` is set and the device is non-legacy | Force the branch and `proprietary_required` |
| 2 | `DISTRO_580_LEGACY_OVERRIDE_BRANCH` is set and the device is 580+ legacy | Force the branch and `proprietary_required` |
| 3 | `ENABLE_LEGACY_OPENKERNEL_RESTRICTION` and the device is legacy ≤ 580 | Force `proprietary_required` |
| 4 | `ENABLE_ARCHITECTURE_CHECK` and the device's arch is in `OPEN_UNSUPPORTED_ARCHS` | Force `proprietary_required` |
| 5 | No earlier step fired | Read the JSON `features` flags |

Steps 3 and 4 are the primary defense. Step 0 is a defense-in-depth
addition that closes a narrower gap. Steps 1 and 2 are
distribution-level overrides that default to `null`. Step 5 is the
upstream behavior, used only as a last resort.

The full explanation, including why each step is load-bearing, is in
[docs/Defense.md](docs/Defense.md). The YAML fields are described in
[docs/Configuration.md](docs/Configuration.md).

The branch selection (`check_legacy_devices()`) reads the
`legacybranch` field of the matched JSON entry, subject to the same
layers. In `cli.py`, a final safety net flips `open` to `closed` if
the branch is locked to `≤ 580` and the computed flavor is still
`open`.

---

## Mixed-GPU policy

When a system has multiple NVIDIA GPUs, the recommendation depends on
which GPUs are present.

### Legacy 580 + modern (`--simulate-mixed`)

Example: GTX 750 Ti (legacy 580) + RTX 5070 (modern).

Both GPUs are individually supported. The engine computes `open` for
the RTX 5070, and the branch lock from `check_legacy_devices()` is
`580`. The final safety net in `cli.py` detects the legacy branch and
flips the flavor to `closed`. Result: `module_flavor: "closed"`,
`branch: "580"`.

### Unsupported legacy (< 580) + modern (`--simulate-badmix`)

Example: GT 740A (legacy 470) + RTX 5070 (modern).

The 740A is below `min_supported_legacy_branch` (580). The CLI
detects the open-capable modern GPU and discards the unsupported
legacy device. Result: `module_flavor: "open"`, `branch: null`. The
legacy GPU will not work with the recommended driver.

### Legacy 580 + legacy 580

If both GPUs are on the same legacy branch, the branch is used
directly. If they are on different legacy branches (e.g. one 580,
one 470), `check_legacy_devices()` picks the higher supported branch
and marks the other as unsupported. The recommendation is driven by
the supported branch.

### Limitations

The mixed-GPU handling described here is for the JSON-level
recommendation. The `mhwd` integration (see below) has known
limitations for hybrid systems; see [docs/Architecture.md](docs/Architecture.md)
Section 9.

---

## mhwd integration

On Manjaro, the fork plugs into `mhwd` through two calls:

| Call | Trigger | Output | Consumer |
|---|---|---|---|
| `nvidia-driver-assistant --mhwd-config` | Before install, from the `mhwd` C++ patch | Config name (e.g. `video-nvidia-580xx`) | `mhwd` |
| `nvidia-driver-assistant --mhwd` | During install, from the `MHWDCONFIG` `post_install()` | `open` or `closed` | `nvidia-recommended-driver` |

The two calls serve different purposes and both are protected by the
layers described above. The full chain is documented in
[docs/Architecture.md](docs/Architecture.md).

The patched `mhwd` binary is a separate package. Its patch is
`0001-mhwd-nvidia-assistant-integration.patch`, which adds a
`getNvidiaAssistantConfig()` method to `Mhwd` and inserts a call to
it in the auto-configure loop. The patch fires only when
`mhwd -a pci nonfree 0300` is invoked for an NVIDIA display device.

The `mhwd-db` fork ships the `video-nvidia-340xx` and `video-nvidia-580xx`
configs and the hybrid variants, and it changes `DEPKMOD` for the
580 and latest configs to call `nvidia-recommended-driver`:

```bash
DEPKMOD="nvidia-580xx"
[[ "$(nvidia-recommended-driver)" == "open" ]] && DEPKMOD="nvidia-580xx-open"
```

---

## Legacy 340xx and 390xx

The `nvidia-340xx-utils` and `nvidia-390xx-utils` PKGBUILDs in the
fork are built on top of the Debian patchset
(`salsa.debian.org/nvidia-graphics-driver`, branches `340xx/main` and
`390xx/main`, maintained by Andreas Beckmann) plus Manjaro-specific
follow-up patches for kernels beyond what Debian has patched. They
are separate packages from `nvidia-driver-assistant`; the tool
recommends them by branch, but does not install them.

The 340xx branch is community-maintained and not in the official
Manjaro repositories. The 390xx branch is still in the official
repositories, and the fork provides an alternative Debian-based
build.

The kernel support range, the follow-up patches, and the CVE
backports are documented in the forum thread at
`forum.manjaro.org/t/nvidia-340-108-390-157-legacy-drivers-...`.
See [docs/Building.md](docs/Building.md) Section 8 for the build
procedure.

---

## Live ISOs

Live ISOs with the 340xx and 390xx branches, built from this fork,
are published outside this project. The current links are on the
project's Facebook page:

```
https://www.facebook.com/manjaroawesome
```

The ISOs are split into two stacks because the 340.108 driver
requires a legacy-ABI XLibre. This is not a property of this fork;
it is a consequence of the 340 driver's X ABI. See the forum thread
for details.

---

## We need your feedback

This fork is maintained by one person. It has been tested on legacy
hardware (Maxwell, Pascal, Volta, and a GeForce 210 on the 340xx
branch), but **not** on open-kernel-capable hardware (Turing,
Ampere, Ada, Blackwell). The `--mhwd` → `open` path is verified
through `--simulate-gpu` and the JSON logic, but not on real cards.

If you own any of the following, please test the fork and report
back:

- Turing: RTX 20xx, GTX 16xx
- Ampere: RTX 30xx
- Ada: RTX 40xx
- Blackwell: RTX 50xx
- Any `modern-generic` device (RTX 60xx or newer, if you have one)

What to report:

1. `nvidia-driver-assistant --mhwd` → does it return `open`?
2. `nvidia-driver-assistant --json` → does `module_flavor` match, and
   does `branch` match what the driver actually uses?
3. `mhwd -a pci nonfree 0300` → which config is selected? Does it
   match `nvidia-driver-assistant --mhwd-config`?
4. Does the driver installation work (kernel module loads,
   `nvidia-smi` reports the GPU, OpenGL uses the NVIDIA renderer)?

Negative results — the fork gave the wrong answer — are more
valuable than positive ones. Open an issue on GitHub or post in the
Manjaro forum topic. Every data point helps.

---

## Test suite

The fork has two test directories:

- `tests/` — the original/baseline suite. 12 tests covering distro
  detection, modalias collection, device matching, CLI argument
  validation, driver recommendation, and instruction generation.
- `moretests/` — an extended suite. 16 tests. Adds legacy branch
  handling, mixed-GPU policy (`--simulate-mixed`,
  `--simulate-badmix`), `--json`/`--mhwd` output modes, and
  malformed JSON handling.

Both use `umockdev` to simulate hardware. No actual NVIDIA GPU is
required. Dependencies:

- `python3`
- `pyyaml`
- `umockdev`
- `gir1.2-umockdev-1.0`

Run them with:

```shell
$ PYTHONPATH=. python3 tests/run --suite test_nvidia_driver_assistant.py
$ PYTHONPATH=. python3 moretests/run --suite test_nvidia_driver_assistant.py
```

The GitHub Actions workflow runs the tests on every push.

---

## For Manjaro packagers and distribution maintainers

- [docs/Defense.md](docs/Defense.md) — the layered defense, why each
  layer is load-bearing, and how the fork compares to the patch-based
  approach.
- [docs/Architecture.md](docs/Architecture.md) — the full `mhwd` →
  `--mhwd-config` → `MHWDCONFIG` → `nvidia-recommended-driver` →
  `DEPKMOD` → `pacman` chain.
- [docs/Configuration.md](docs/Configuration.md) — the YAML files,
  including `architecture.yaml`, `distro.yaml`, `overrides.yaml`,
  and `instructions.yaml`. How to add a new architecture, modify the
  Manjaro policy, or add a distribution.
- [docs/Building.md](docs/Building.md) — how to build the fork, the
  patched `mhwd`, and the `mhwd-db` fork. The maintenance workflow
  for new upstream releases.

---

## Authors and acknowledgment

- Alberto Milone `<amilone@nvidia.com>` — original
  `nvidia-driver-assistant` author
- Manjaro Team — packaging adjustments and distribution-specific
  compatibility fixes
- Gábor Gyöngyösi `<megvadulthangya@gmail.com>` — fork maintainer,
  refactoring and enhancements

---

## License

The Python code and the packaging files are MIT-licensed. The
NVIDIA EULA is installed separately as
`/usr/share/licenses/nvidia-driver-assistant/NVIDIA-EULA` and is
extracted from the upstream DEB.
```

---

