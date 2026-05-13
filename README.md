# nvidia-driver-assistant

This piece of software is meant to help users deciding on which NVIDIA graphics
driver to install, based on the detected system's hardware.

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
- `--mhwd` - MHWD compatibility mode (Manjaro Hardware Detection); prints only the module flavor (`open`/`closed`) for consumption by `mhwd`
- `--json` - Emit the recommendation as JSON, intended for installers and other automation
- `--verbose` - Verbose output

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
- On **Manjaro**, GPUs whose legacy branch is `>= 390` are still installable
  from the official repositories; GPUs whose legacy branch is `< 390` are
  flagged as ultra-legacy and the user is pointed at the matching
  `nvidia-<branch>xx-dkms` / `nvidia-<branch>xx-utils` packages in the
  AUR (with a note about enabling AUR support in Pamac).
- On **Arch Linux**, GPUs whose legacy branch is `>= 470` are still available
  through repository-supported community packages; GPUs whose legacy branch is
  `< 470` are flagged as ultra-legacy and the user is pointed at the matching
  `nvidia-<branch>xx-dkms` / `nvidia-<branch>xx-utils` packages in the AUR.
  Branch `580` itself is no longer in the official Arch repositories, so the
  tool explicitly redirects to `nvidia-580xx-dkms` / `nvidia-580xx-utils` in
  the AUR for that case.
- For all other supported distributions, unsupported legacy GPUs produce a
  descriptive error message advising a hardware upgrade.

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

## Test suite

To use the test suite `nvidia-driver-assistant` comes with, you are going to
need the following dependencies:

- `python3-gi`
- `umockdev` and `gir1.2-umockdev-1.0`

There are two test directories:

- `tests/` — the original/baseline test suite.
- `moretests/` — an extended test suite that additionally exercises legacy
  driver branch handling, Manjaro/Arch AUR fallbacks, the `--json` and
  `--mhwd` output modes, and the `supported-gpus-bad/` database fixtures
  (intentionally malformed input used to verify error handling).

The test suites can be run as follows:

```shell
$ PYTHONPATH=. tests/run --suite test_nvidia_driver_assistant.py
$ PYTHONPATH=. moretests/run --suite test_nvidia_driver_assistant.py
```

Note: no actual NVIDIA hardware is required for testing, since umockdev is
      used to simulate the presence of such devices. The `--simulate-gpu`
      flag can additionally be used to drive the tool itself against a
      simulated GPU from the command line.


## Authors and acknowledgment
- Alberto Milone &lt;amilone@nvidia.com&gt; — original author
- Manjaro Team — packaging adjustments and distribution-specific compatibility fixes
- Gábor Gyöngyösi &lt;megvadulthangya@gmail.com&gt; — refactoring and enhancements


## License
All the included code and assets are MIT licensed.
