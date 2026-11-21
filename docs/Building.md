# Building and testing

This document covers the maintainer's Manjaro fork: the Assistant package, NVIDIA supported-device data, MHWD ID packages, the two MHWD integration patches and the related legacy driver packaging work.

## 1. Components

The work is split into independently buildable components.

| Component | Purpose |
|---|---|
| `nvidia-driver-assistant` | Detects NVIDIA GPUs, recommends driver branch/module flavour, provides MHWD CLI modes and generates/audits `.ids` lists. |
| NVIDIA `*-utils` PKGBUILDs | Build the userspace/DKMS driver packages and the MHWD split package containing the relevant `.ids` file. |
| `mhwd` | Applies the selected MHWD integration patch and performs the actual config selection/installation. |
| `mhwd-db` | Supplies the MHWD graphics-driver configs, including the matching NVIDIA and hybrid profiles. |
| 340xx/390xx driver package projects | Separate maintainer-managed legacy driver packaging and patch work based on Debian's driver packaging/patch branches. |

The Assistant can generate ID lists, but it does not compile the NVIDIA kernel module. MHWD's split package names remain in use because the config database still consumes those packages and their `.ids` files.

## 2. Prerequisites

Use `makepkg` and install the build tools listed in each PKGBUILD's `makedepends`. The Assistant package build currently needs Git, curl, libarchive and gzip in addition to the normal Arch/Manjaro build environment. Runtime dependencies include Python 3 and PyYAML.

The MHWD development workflow in this fork uses `mpatch` (provided by the `mpatch-git` build dependency in the development packaging). The Manjaro downstream packaging adaptation uses the standard GNU `patch` utility instead; that downstream packaging choice does not replace `mpatch` in this branch's own development workflow.

## 3. Building `nvidia-driver-assistant`

Clone the maintainer's branch and build the package:

```shell
git clone --branch manjaro \
  https://github.com/megvadulthangya/nvidia-driver-assistant.git
cd nvidia-driver-assistant
makepkg -si
```

The PKGBUILD handles the vendor data as part of the build.

### 3.1 Upstream JSON and EULA

The build locates the latest NVIDIA `nvidia-driver-assistant` DEB in the configured NVIDIA CUDA repository, downloads it and extracts the `supported-gpus.json` data and NVIDIA EULA. The Python implementation in this fork is packaged alongside those vendor assets.

### 3.2 The five supportedchips documents

The build resolves a version for each supported NVIDIA branch and downloads:

- latest 6xx New Feature Branch: `supportedchips.html`
- 580: `supportedchips580.html`
- 470: `supportedchips470.html`
- 390: `supportedchips390.html`
- 340: `supportedchips340.html`

The current PKGBUILD exposes per-branch version override variables:

```bash
_6xx_version_override=""
_580_version_override=""
_470_version_override=""
_390_version_override=""
_340_version_override=""
```

An empty value enables automatic version discovery. A non-empty value pins the corresponding NVIDIA document version for deliberate testing or a controlled rebuild.

After downloading, `prepare()` copies the documents into the Python package data directory and runs `validate_all_documents()` from the parser that will be shipped. The build fails if any required document cannot be parsed and validated. This prevents an apparently successful package build with incomplete ID-generation or branch-classification data.

### 3.3 Installed files

The package installs:

- the `nvidia-driver-assistant` command;
- the `nvidia_driver_assistant` Python modules and YAML data;
- all five supportedchips HTML files in the package data directory;
- `supported-gpus.json` and the NVIDIA EULA from the upstream DEB;
- `show-driver` as the compatibility command `nvidia-recommended-driver`;
- `README.md` and `docs/Configuration.md` under `/usr/share/doc/nvidia-driver-assistant/`;
- `COPYING` and the NVIDIA EULA under `/usr/share/licenses/nvidia-driver-assistant/`.

The other maintainer documents (`Architecture.md`, `Building.md` and `Defense.md`) remain in the source repository for development and packaging reference; the current PKGBUILD does not install those three files into the runtime documentation directory.

### 3.4 Basic verification

Examples:

```shell
nvidia-driver-assistant --simulate-gpu 750 --mhwd
# Expected: closed

nvidia-driver-assistant --simulate-gpu 4070 --mhwd
# Expected: open

python -c 'from nvidia_driver_assistant.supported_chips import validate_all_documents; print("supportedchips parser imported")'
```

The last command checks that the parser can be imported. The package build performs the full five-document validation.

## 4. Generating MHWD `.ids` files

The old `mhwd-nvidia` shell-script generator has been retired from the 390xx, 470xx, 580xx and latest NVIDIA utils package builds. The replacement is part of `nvidia-driver-assistant`:

```shell
nvidia-driver-assistant --generate-ids <branch>
```

Supported branch names are `latest`, `6xx`, `580`, `470`, `390` and `340`.

Examples:

```shell
nvidia-driver-assistant --generate-ids latest > nvidia.ids
nvidia-driver-assistant --generate-ids 580 > nvidia-580xx.ids
nvidia-driver-assistant --generate-ids 470 > nvidia-470xx.ids
nvidia-driver-assistant --generate-ids 390 > nvidia-390xx.ids
nvidia-driver-assistant --generate-ids 340 > nvidia-340xx.ids
```

The command writes to standard output. The relevant `package_mhwd-nvidia*()` function redirects that output to the package staging path, for example:

```bash
nvidia-driver-assistant --generate-ids 390 \
  > "${pkgdir}/var/lib/mhwd/ids/pci/nvidia-390xx.ids"
```

### 4.1 What the generated file contains

The generator writes:

1. A comment header (`# List generated by mhwd. Do not edit manually.`).
2. A sorted, unique list of four-digit PCI **Device IDs**.

Subsystem Vendor IDs and Subsystem Device IDs are intentionally not written. For the latest/580 document format, the parser takes the four-digit ID from the `devidXXXX` row identifier. For older 470/390/340 formats, it reads the first PCI Device ID in the `Device PCI ID` column and ignores any additional subsystem identifiers in that cell.

The result is the hardware ID list consumed by MHWD. It is not a list of NVIDIA kernel-module names and does not determine whether the module should be open or closed.

### 4.2 Auditing installed `.ids` files

`--check-ids` compares existing target files with the matching NVIDIA documents. It is read-only:

```shell
sudo nvidia-driver-assistant --check-ids
```

The default directory is `/var/lib/mhwd/ids/pci`. To check a staging directory:

```shell
nvidia-driver-assistant --check-ids --ids-dir ./staged-ids
```

For each file found, the report includes missing IDs, IDs not found in the document, duplicates and malformed tokens. Missing branch files are optional and are skipped. A reported difference is a review item; the audit does not rewrite the file. A missing ID in a current vendor document does not, by itself, prove that the driver binary cannot support that device.

## 5. Building the patched MHWD package

The MHWD package contains two alternative patches. The selected patch is controlled by:

```bash
NVIDIA_ASSISTANT_MODE="corrective"
```

Use exactly one of the following values:

| Value | Patch | Behaviour |
|---|---|---|
| `authority` | `0001-mhwd-nvidia-assistant-integration.patch` | Uses `--mhwd-config` as the authority for the NVIDIA branch/profile. |
| `corrective` | `0002-mhwd-nvidia-assistant-corrective.patch` | Retains MHWD's priority selection unless per-device supportedchips data requires correction. |

The patches are alternatives. Do not apply both to the same MHWD source tree. See [Architecture.md](Architecture.md) for the exact control flow and the differences between the modes.

### 5.1 Patch application in this branch's development workflow

The maintainer's development PKGBUILD uses `mpatch` for patch application. The configuration uses atomic application and the configured fuzz factor:

```bash
_mpatch_opts=(
  --atomic
  --fuzz-factor 0.7
)
```

The development helper also creates an mpatch diagnostic report when application fails. This is retained for the maintainer's development and debugging workflow.

A separate Manjaro downstream packaging adaptation uses GNU `patch` instead of `mpatch`, because that is the packaging target's selected dependency. This is a downstream packaging difference; it does **not** mean that this branch has migrated its development workflow away from mpatch.

### 5.2 Build and verify

Build with the tools required by the selected PKGBUILD:

```shell
makepkg -si
```

After installation, verify that the binary includes the Assistant integration and test the selected mode on hardware or a suitable test system. A successful `prepare()` only proves that the selected patch applied; it does not prove that MHWD selected or installed the correct driver on every hardware configuration.

## 6. MHWD database and ordering

The MHWD database must contain the matching NVIDIA config names for the branches that the Assistant can recommend. Those configs reference the `.ids` files installed under `/var/lib/mhwd/ids/pci/`.

A practical build/install order for a test system is:

1. Build and install `nvidia-driver-assistant`.
2. Build and install the NVIDIA utils packages that provide the required MHWD `.ids` split packages.
3. Build and install the matching `mhwd-db` configuration database.
4. Build and install `mhwd` with exactly one selected integration patch.
5. Test the chosen MHWD mode with the actual target hardware and the installed configs.

The required set depends on which NVIDIA branches and hybrid profiles are being tested.

## 7. Related 340xx and 390xx legacy-driver work

The 340xx and 390xx driver packages are separate from the Assistant. This fork documents them because the branch-selection and MHWD ID functionality is intended to work with this wider legacy-driver effort.

The maintainer's 340xx and 390xx package work is based on the corresponding Debian NVIDIA packaging/patch branches (`340xx/main` and `390xx/main`). The downstream work includes Manjaro-specific packaging and follow-up changes for kernel compatibility and related fixes. This work is maintained by the fork maintainer; it is not official Manjaro-maintained patch work.

The Assistant can classify these GPUs and generate their MHWD `.ids` files. It does not build, patch or install the corresponding kernel modules. Those responsibilities stay with the relevant driver PKGBUILDs and their patch series.

## 8. Test suites

The repository contains the baseline suite in `tests/` and an extended suite in `moretests/`. They use `umockdev` to simulate system hardware.

```shell
PYTHONPATH=. python3 tests/run --suite test_nvidia_driver_assistant.py
PYTHONPATH=. python3 moretests/run --suite test_nvidia_driver_assistant.py
```

The GitHub Actions workflow also runs dedicated parser and MHWD ID tests:

```shell
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_supported_chips_parser.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_mhwd_ids.py' -v
```

The suites cover hardware discovery, device matching, argument validation, recommendations, output modes, supportedchips parsing, `.ids` generation/auditing and extended legacy/mixed-GPU cases. The exact assertions should be read from the current test files; this document intentionally does not freeze a test count.

Simulated tests are useful for deterministic decision-path checks. They do not replace real hardware tests for the open-module recommendation, hybrid systems or actual MHWD package installation.

## 9. Build troubleshooting notes

- **Supportedchips validation fails:** confirm that the relevant NVIDIA document version exists and that the downloaded HTML is complete. Do not bypass validation to produce a package with missing device data.
- **An `.ids` audit reports differences:** inspect the exact missing/extra/duplicate/malformed values and the document version used by the installed Assistant. The audit is read-only.
- **MHWD cannot find a matching profile:** verify that the corresponding config exists in `mhwd-db`, that the correct `.ids` split package is installed, and that its file contains the PCI Device ID.
- **Authority mode skips an NVIDIA device:** verify the `--mhwd-config` output and whether a profile for that branch is available for the device.
- **Corrective mode retains the MHWD choice:** check the output of `--mhwd-branch --mhwd-device-id <ID>`. An unclassified ID intentionally does not trigger a guessed correction.
- **mPatch fails in the development workflow:** inspect its diagnostic output/report before changing patch context or fuzz settings. The Manjaro GNU `patch` packaging variant is a separate downstream packaging path.
