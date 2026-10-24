# Building

This document describes how to build the components of this fork,
how to update them when a new upstream NVIDIA release appears, and
how to test them. It does not describe how to build the Manjaro live
ISOs; those are published separately (see Section 10).

---

## 1. Components

The fork is split across several repositories and packages. Each can
be built independently.

| Component | Repository | Package |
|---|---|---|
| Decision engine | `megvadulthangya/nvidia-driver-assistant` (branch `manjaro`) | `nvidia-driver-assistant` |
| Hardware detection with the patch | `code.manjaro.org/applications/mhwd` + `0001-mhwd-nvidia-assistant-integration.patch` | `mhwd` |
| Config database | `megvadulthangya/mhwd-db` (branch `develop`) | `mhwd-db` |
| Legacy 340 driver | `megvadulthangya/nvidia-340xx-utils` | `nvidia-340xx-utils` |
| Legacy 390 driver | `megvadulthangya/nvidia-390xx-utils` | `nvidia-390xx-utils` |
| Device ID lists | Produced by each `nvidia-*xx-utils` PKGBUILD | `mhwd-nvidia-340xx`, `mhwd-nvidia-390xx`, `mhwd-nvidia-470xx`, `mhwd-nvidia-580xx`, `mhwd-nvidia` |
| Driver wrapper | `show-driver` in `nvidia-driver-assistant` repo | `/usr/bin/nvidia-recommended-driver` |

The minimum set to get a working patched `mhwd` on a Manjaro system
is: `nvidia-driver-assistant`, `mhwd`, `mhwd-db`. The legacy driver
packages are needed only if you want 340 or 390 support.

---

## 2. Prerequisites

All builds use `makepkg`. The build tools for each package come from
its `makedepends`; install them with `pacman -S --needed ...` before
running `makepkg`. The relevant ones for the packages in this
document:

| Tool | Needed for |
|---|---|
| `base-devel` | `makepkg` itself |
| `git` | All source checkouts |
| `curl` | `nvidia-driver-assistant` downloads |
| `libarchive` | Extracting the upstream `.deb` |
| `gzip` | Extracting the upstream `.deb` |
| `cmake` | Building `mhwd` |
| `mpatch-git` | Applying the `mhwd` patch |
| `python` | Runtime for `nvidia-driver-assistant` |
| `python-pyyaml` | Runtime for `nvidia-driver-assistant` |
| `dkms` | Building the `nvidia-*xx-dkms` packages |

`mpatch-git` is a Manjaro package. It is not in the AUR under that
name; it is shipped by Manjaro's own repositories. If it is not
available, `patch -Np1` can be used instead, but the PKGBUILD in
this fork is written for `mpatch`.

---

## 3. Building `nvidia-driver-assistant`

### 3.1 Clone the package repository

The PKGBUILD and the source tree are in the same repository. Clone
the `manjaro` branch:

```shell
$ git clone --branch manjaro \
    https://github.com/megvadulthangya/nvidia-driver-assistant.git
$ cd nvidia-driver-assistant
```

### 3.2 Inspect the PKGBUILD

The PKGBUILD uses a two-stage version scheme. The `pkgver=` line at
the top is a placeholder; `pkgver()` (the function) overrides it at
build time.

The version has two parts:

- The **DEB version**, scraped from
  `developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/`
  by `_latest_deb_info()`;
- The **git hash** of the current commit.

For example, `0.62.71.10_1.g27411f2b34` means: upstream DEB version
`0.62.71.10-1`, git commit `27411f2b34`.

The `_nfb_version_override` variable controls which
`supportedchips.html` is downloaded. It is set to `"615.78.08"` in
the current PKGBUILD. If left empty, `_latest_nfb_version()` tries
to determine the New Feature Branch version automatically (see
Section 6).

### 3.3 Build

```shell
$ makepkg -si
```

The `-s` flag installs missing dependencies from the repositories;
the `-i` flag installs the resulting package after a successful
build.

`prepare()` downloads the latest DEB, extracts its `data.tar.*`
payload, and downloads `supportedchips.html`. `package()` installs:

- the Python package (`nvidia_driver_assistant/`) into
  `site-packages`;
- the `nvidia-driver-assistant` wrapper into `/usr/bin/`;
- the `show-driver` wrapper as `/usr/bin/nvidia-recommended-driver`;
- `supportedchips.html` into
  `site-packages/nvidia_driver_assistant/data/`;
- `supported-gpus.json` and the NVIDIA EULA from the DEB into
  `/usr/share/nvidia-driver-assistant/`;
- documentation (`README.md`, `docs/Configuration.md`, `COPYING`)
  into `/usr/share/doc/nvidia-driver-assistant/` and
  `/usr/share/licenses/nvidia-driver-assistant/`.

### 3.4 Verify

```shell
$ nvidia-driver-assistant --list-supported-distros
The following are the currently accepted distribution aliases:
  manjaro

$ nvidia-driver-assistant --simulate-gpu 750 --mhwd
closed

$ nvidia-driver-assistant --simulate-gpu 4070 --mhwd
open
```

The first command should print only `manjaro`. The second should
print `closed` for the simulated GTX 750 Ti, regardless of what the
current `supported-gpus.json` says about `0x1380`. The third should
print `open` for the simulated RTX 4070.

To confirm that `supportedchips.html` is installed:

```shell
$ python -c 'from nvidia_driver_assistant.supported_chips import SUPPORTED_CHIPS; print(len(SUPPORTED_CHIPS))'
```

This should print a number in the thousands (the exact number
depends on the NFB version). A `None` result means the file was not
installed or failed to parse; the tool still runs, but Layer 2 of
the defense (see `docs/Defense.md`) is inactive.

---

## 4. Building the patched `mhwd`

### 4.1 The patch

The `mhwd` patch is `0001-mhwd-nvidia-assistant-integration.patch`.
It adds a `getNvidiaAssistantConfig()` method to `Mhwd` and inserts
a call to it inside the auto-configure loop. `docs/Architecture.md`
Section 2 describes what the patch does.

The patch is small: `src/Mhwd.cpp` gains ~64 lines, `src/Mhwd.hpp`
gains 6 lines (the method declaration and two member fields).

### 4.2 Clone the package repository

The patched `mhwd` PKGBUILD is in the `mhwd` fork, not in the
upstream `mhwd` repository. Clone the package directory:

```shell
$ git clone <URL-to-your-mhwd-package-repo> mhwd
$ cd mhwd
```

The directory contains three files:

- `PKGBUILD`
- `0001-mhwd-nvidia-assistant-integration.patch`
- `mhwd.install`

### 4.3 Inspect the PKGBUILD

The PKGBUILD pins the upstream `mhwd` to a specific commit:

```bash
_commit=6ddcc6072c28a067ecebe6d38245dd0748f59c0f
source=(
  "git+https://code.manjaro.org/applications/mhwd.git#commit=${_commit}"
  "0001-mhwd-nvidia-assistant-integration.patch"
)
```

The `commit=` pin is deliberate. `mhwd` is developed on
`code.manjaro.org` and the C++ source changes between commits; the
patch is written against this specific commit. Re-pinning to a newer
commit requires rebasing the patch.

`makedepends` includes `mpatch-git`. The PKGBUILD uses `mpatch` with
`--atomic` and `--fuzz-factor 0.7`:

```bash
_mpatch_opts=(
    --atomic
    --fuzz-factor 0.7
)
```

`--atomic` applies the patch as a single unit; if any hunk fails,
no changes are written. `--fuzz-factor 0.7` allows the patch to
apply with a larger offset than `patch` would accept by default.
The patch is applied at line 254 of `Mhwd.cpp` and line 1252 of
`Mhwd.cpp`. If `mpatch` reports a fuzz-match on a different line,
the code still compiles and runs; the exact line number is not
significant for C++ member functions.

### 4.4 Build

```shell
$ makepkg -si
```

`prepare()` applies the patch. `build()` runs:

```shell
$ cmake -B build -S "$pkgname" \
    -DCMAKE_BUILD_TYPE='RelWithDebInfo' \
    -DCMAKE_INSTALL_PREFIX='/usr' \
    -DCMAKE_POLICY_VERSION_MINIMUM='3.5'
$ cmake --build build
```

`package()` installs the binary and creates the empty
`/var/lib/mhwd/db/pci`, `/var/lib/mhwd/db/usb`,
`/var/lib/mhwd/local/pci`, `/var/lib/mhwd/local/usb` directories.

The `-DCMAKE_POLICY_VERSION_MINIMUM='3.5'` flag is required because
`mhwd`'s `CMakeLists.txt` declares `cmake_minimum_required (VERSION 2.6)`,
which current CMake versions reject by default. Setting the policy
minimum to `3.5` makes CMake accept the project.

### 4.5 The `post_install` script

`mhwd.install` runs `mhwd-gpu --check` in `post_install()`,
`post_upgrade()`, and `post_remove()`. This is the same behaviour as
upstream `mhwd`. It removes a stale
`/etc/X11/xorg.conf.d/90-mhwd.conf` symlink if its target no longer
exists.

### 4.6 Verify

```shell
$ which mhwd
/usr/bin/mhwd

$ strings /usr/bin/mhwd | grep -E 'nvidia-driver-assistant|recommendation'
nvidia-driver-assistant --mhwd-config 2>/dev/null
Using nvidia-driver-assistant recommendation: 
```

The two strings confirm that the patch is present in the binary.

To exercise it end-to-end, run:

```shell
$ sudo mhwd -a pci nonfree 0300
```

On a system with a single NVIDIA GPU, `mhwd` should print a line of
the form:

```
> Using nvidia-driver-assistant recommendation: video-nvidia-580xx
```

and proceed with the install.

---

## 5. Building the `mhwd-db` fork

### 5.1 Clone the package repository

```shell
$ git clone <URL-to-your-mhwd-db-package-repo> mhwd-db
$ cd mhwd-db
```

The directory contains `PKGBUILD`, `mhwd-db.install`, and a `pci/`
subdirectory (the config database).

### 5.2 Inspect the PKGBUILD

The PKGBUILD pulls the database from GitHub:

```bash
_commit=""  # empty = latest from the develop branch

if [[ -n "$_commit" ]]; then
  source=("git+https://github.com/megvadulthangya/mhwd-db.git#commit=$_commit")
else
  source=("git+https://github.com/megvadulthangya/mhwd-db.git#branch=develop")
fi
```

Leaving `_commit` empty tracks the `develop` branch. Setting it to a
specific hash pins the build. For a reproducible build, pin to the
hash that has been tested.

The version is date-based:

```bash
pkgver() {
  cd "$pkgname"
  printf "$(git show -s --format=%cd --date=format:%Y%m%d HEAD)"
}
```

A build on 2026-08-23 produces `pkgver=20260823`, regardless of what
the top-of-file `pkgver=` says.

### 5.3 Build

```shell
$ makepkg -si
```

`package()` copies the `pci/` directory to
`/var/lib/mhwd/db/pci/` and creates `/etc/X11/mhwd.d/`. The
`mhwd-db.install` script's `post_upgrade()` then iterates over every
`MHWDCONFIG` in `db/pci/` and copies it to
`/var/lib/mhwd/local/pci/` if the `VERSION` field differs from the
local copy. See `docs/Architecture.md` Section 7 for details.

### 5.4 Verify

```shell
$ ls /var/lib/mhwd/db/pci/graphic_drivers/
video-hybrid-amd-nvidia-470xx-prime
video-hybrid-amd-nvidia-580xx-prime
video-hybrid-amd-nvidia-prime
video-hybrid-intel-nvidia-340xx-bumblebee
video-hybrid-intel-nvidia-390xx-bumblebee
video-hybrid-intel-nvidia-470xx-prime
video-hybrid-intel-nvidia-580xx-prime
video-hybrid-intel-nvidia-prime
video-linux
video-modesetting
video-nvidia
video-nvidia-340xx
video-nvidia-390xx
video-nvidia-470xx
video-nvidia-580xx
video-virtualmachine

$ ls /var/lib/mhwd/ids/pci/
nvidia.ids
nvidia-340xx.ids
nvidia-390xx.ids
nvidia-470xx.ids
nvidia-580xx.ids
```

The `.ids` files come from the `mhwd-nvidia-*` packages, which are
produced by the corresponding `nvidia-*xx-utils` PKGBUILDs. If they
are missing, the configs that depend on them will not match any
device.

---

## 6. How `supportedchips.html` is obtained

### 6.1 The three strategies

`_latest_nfb_version()` tries to determine the New Feature Branch
version of the NVIDIA driver. This is the version from which
`supportedchips.html` is downloaded. Three strategies are tried in
order.

**Strategy 1 — `_nfb_version_override`.** If the PKGBUILD's
`_nfb_version_override` variable is non-empty, it is used directly:

```bash
_nfb_version_override="615.78.08"
```

This is the current setting. To use a different version, edit the
variable.

**Strategy 2 — scrape the unix driver page.** If
`_nfb_version_override` is empty, the PKGBUILD fetches
`https://www.nvidia.com/en-us/drivers/unix/` and searches for the
string `"Latest New Feature Branch Version: X.Y.Z"`. The version is
extracted from the text.

**Strategy 3 — directory listing.** If both of the above fail, the
PKGBUILD parses the directory listing at
`https://download.nvidia.com/XFree86/Linux-x86_64/` and takes the
highest version. As a last resort, it reads
`https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt`
(which points to the production branch) and uses that.

### 6.2 When to update `_nfb_version_override`

The override exists so that a packaging build does not depend on
NVIDIA's HTML layout. If the unix driver page or the directory
listing changes, the automatic detection breaks, but the override
keeps the build working.

Update the override when a new New Feature Branch is released. If
the override is stale, `supportedchips.html` is downloaded from an
older branch; the parser still works, but the branch map may not
include GPUs that were added to the newer branch. For the legacy
`<= 580` range this is not a problem (those GPUs are in every
version of `supportedchips.html`), but for newer cards it matters.

### 6.3 What happens if the download fails

`prepare()` aborts if `supportedchips.html` cannot be downloaded or
fails the sanity check. The build does not produce a package. This is
deliberate; a package without `supportedchips.html` would be missing
Layer 2 of the defense (see `docs/Defense.md` Section 3).

If the build is failing because of the download, set
`_nfb_version_override` to a version that is known to work, or
download the file manually and place it in the build directory. The
PKGBUILD's `prepare()` always overwrites the file, so a manual
placement only helps if the download step is also skipped or
modified.

---

## 7. Updating for a new upstream release

### 7.1 The Python code does not change

The Python code in this fork is based on upstream `0.51`. New
upstream releases do not require changes to the Python code, because
the code does not track upstream's newer additions. The fork's
decision logic and CLI are stable.

The JSON, however, is updated on every release. This is why the
PKGBUILD downloads it from the latest DEB automatically.

### 7.2 The step-by-step procedure

When a new `nvidia-driver-assistant_X.Y.Z.deb` appears on
`developer.nvidia.com`:

1. **No manual edit to the PKGBUILD is required.** The `pkgver()`
   function calls `_latest_deb_info()` at build time and picks up
   the new DEB.
2. **No manual edit to the JSON is required.** `prepare()` extracts
   `supported-gpus.json` from the new DEB and installs it.
3. **`_nfb_version_override` may need an update.** If the new
   release introduces a new New Feature Branch, update the override
   (or leave it empty to use automatic detection).
4. **Rebuild and reinstall:**

   ```shell
   $ cd nvidia-driver-assistant
   $ makepkg -si
   ```

5. **Verify** with the commands from Section 3.4.

### 7.3 The GitHub Actions workflow

The repository contains a GitHub Actions workflow that builds the
package on every push to the `manjaro` branch. The workflow:

1. Checks out the branch.
2. Runs `makepkg` in an Arch container.
3. Uploads the resulting package as an artifact.

The workflow does not publish to a package repository. The artifact
is the build output, and the package is installed manually.

The exact contents of the workflow file are not described here.
Inspect `.github/workflows/` in the repository for the authoritative
version.

---

## 8. Building the legacy `nvidia-*xx-utils` packages

This section describes the legacy driver packages that the fork uses
for 340xx and 390xx support. It is optional: the patched `mhwd` and
`mhwd-db` work without them (they only affect systems with those
GPUs).

### 8.1 The 390xx PKGBUILD in outline

The `nvidia-390xx-utils` PKGBUILD is large (over 70 Debian patches
plus several Manjaro follow-up patches). The structure:

- `source=()` includes the NVIDIA `.run` installer, several
  Manjaro-specific files, and a `series.resolved` file that lists
  the Debian patches in order.
- `prepare()` extracts the `.run` installer and applies every patch
  from `series.resolved` in order, then applies a small DKMS
  workaround.
- `package_*()` functions build the four split packages:
  `nvidia-390xx-utils`, `opencl-nvidia-390xx`,
  `nvidia-390xx-dkms`, and `mhwd-nvidia-390xx`.

The `series.resolved` file is the source of truth for patch order.
It is maintained alongside the PKGBUILD and must be kept in sync
with the patches.

### 8.2 The Debian patchset

Both 340xx and 390xx are built on top of the Debian patchset
(`salsa.debian.org/nvidia-graphics-driver`, branches `340xx/main`
and `390xx/main`, maintained by Andreas Beckmann). The Debian
patchset backports the driver to newer kernels. The Manjaro
follow-up patches (in the fork) add support for kernels beyond what
Debian has patched, plus the mhwd integration.

For 340xx, the thread at
`forum.manjaro.org/t/nvidia-340-108-390-157-legacy-drivers-...`
documents the kernel support range (6.1 through 7.3-rc) and the
follow-up patches (`kernel-6.18-workqueue-flush.patch`,
`kernel-7.0-screen_info.patch`, `kernel-7.2.patch`,
`kernel-7.3-acpi.patch`, `vma-lock-7.0-plus.patch`,
`fixup-warnings.patch`).

For 390xx, the PKGBUILD's `_debian_patches` list is the
authoritative source. It includes patches for kernel 6.18 and 7.3.

### 8.3 The `.ids` file generation

The `package_mhwd-nvidia-390xx()` function produces the device ID
list that `mhwd` uses for config matching:

```bash
sh -e ${srcdir}/mhwd-nvidia \
    ${srcdir}/${_pkg}/README.txt \
    ${srcdir}/${_pkg}/kernel/nvidia/nv-kernel-amd64.o_binary \
    > ${pkgdir}/var/lib/mhwd/ids/pci/nvidia-390xx.ids
```

The `mhwd-nvidia` helper script reads the `README.txt` and the
compiled kernel module binary and emits a space-separated list of
hex device IDs. A post-processing `sed` fixes a known missing ID
(`1b82` for the GTX 1070 Ti, which the script does not emit).

The corresponding `.ids` files for 340xx, 470xx, 580xx, and latest
are produced by their own PKGBUILDs the same way. They are installed
to `/var/lib/mhwd/ids/pci/`.

### 8.4 Kernel support

The 390xx PKGBUILD adds a DKMS workaround at the top of
`kernel/Makefile`:

```makefile
ifeq ($(M),)
  override KERNELRELEASE :=
endif
```

This prevents the kernel build system from setting `KERNELRELEASE`
before the top-level `make` call, which would otherwise cause the
DKMS build to fail on kernels 6.18 and later.

The `dkms.conf` is prepared with four modules:

```
BUILT_MODULE_NAME[0]="nvidia"
DEST_MODULE_LOCATION[0]="/kernel/drivers/video"
BUILT_MODULE_NAME[1]="nvidia-uvm"
DEST_MODULE_LOCATION[1]="/kernel/drivers/video"
BUILT_MODULE_NAME[2]="nvidia-modeset"
DEST_MODULE_LOCATION[2]="/kernel/drivers/video"
BUILT_MODULE_NAME[3]="nvidia-drm"
DEST_MODULE_LOCATION[3]="/kernel/drivers/video"
```

The 340xx branch has a different module set (nvidia, nvidia-uvm; no
modeset, no drm in the same form).

### 8.5 Kernel module binary rename

Before the patches are applied, the PKGBUILD renames the precompiled
kernel module blobs:

```bash
mv -f nvidia/nv-kernel.o_binary nvidia/nv-kernel-amd64.o_binary
mv -f nvidia-modeset/nv-modeset-kernel.o_binary \
      nvidia-modeset/nv-modeset-kernel-amd64.o_binary
```

This is needed because the `use-ARCH.o_binary` patches expect the
`-amd64` suffix and create a `.cmd` file that `modpost` needs. For
340xx, only one blob exists.

---

## 9. Testing

### 9.1 The Python test suite

The fork has two test directories:

- `tests/` — the original/baseline suite. Covers distro detection,
  modalias collection, device matching, CLI argument validation,
  driver recommendation, and instruction generation.
- `moretests/` — an extended suite. Adds legacy branch handling,
  mixed-GPU policy, `--simulate-mixed`/`--simulate-badmix`, AUR
  fallback, `--json`/`--mhwd` output modes, and malformed JSON
  handling.

Both use `umockdev` to simulate hardware and do not require actual
NVIDIA GPUs. Run them with:

```shell
$ PYTHONPATH=. python3 tests/run --suite test_nvidia_driver_assistant.py
$ PYTHONPATH=. python3 moretests/run --suite test_nvidia_driver_assistant.py
```

The `run` wrapper execs `umockdev-wrapper` automatically. The
`--suite` argument selects a specific file; without it, all test
files in the directory are run.

The GitHub Actions workflow runs the tests on every push. The
current suite is 12 tests in `tests/` and 16 in `moretests/`.

### 9.2 Simulated GPUs

The `database.py` module defines simulated GPUs that can be used
without real hardware:

| Key | Device | Branch |
|---|---|---|
| `545` | GeForce GT 545 | legacy 390 |
| `nvs290` | Quadro NVS 290 | legacy 340 |
| `7150m` | GeForce 7150M | legacy 304 |
| `740A` | GeForce 740A | legacy 470 |
| `750` | GeForce GTX 750 Ti | legacy 580 |
| `800A` | GeForce 800A | legacy 390 |
| `4070` | GeForce RTX 4070 SUPER | modern |
| `5070` | GeForce RTX 5070 Laptop | modern |
| `unknown` | Unknown non-NVIDIA device | — |

Use `--simulate-gpu <key>` to drive the tool against one of these.
The mixed-GPU scenarios (`--simulate-mixed`, `--simulate-badmix`)
combine a legacy GPU with a modern one.

Example:

```shell
$ nvidia-driver-assistant --simulate-gpu 750 --json
```

The output is a JSON object with `module_flavor: "closed"` and
`branch: "580"`. This confirms that the hardcoded legacy restriction
fires even when the JSON says `kernelopen`.

### 9.3 The mixed-GPU policy test

The `--simulate-mixed` and `--simulate-badmix` flags correspond to
two test cases in `moretests/`:

- `test_simulate_mixed` — GTX 750 Ti (legacy 580) + RTX 5070
  (modern). Expected: `closed`, branch `580`.
- `test_simulate_badmix` — GT 740A (legacy 470) + RTX 5070
  (modern). Expected: `open`, no branch lock, both devices listed.

These are checked on every push. See `docs/Architecture.md`
Section 9.3 for the limitation these tests encode.

### 9.4 Real-hardware testing

The simulated GPUs and the JSON tests do not replace real hardware.
A build that passes the test suite has not been verified on actual
Turing, Ampere, Ada, or Blackwell hardware. `docs/Defense.md`
Section 6 lists the data points that require real hardware to
verify. If you have access to one of those GPUs, please test and
report back.

---

## 10. Legacy ISOs

The 340xx and 390xx branches have live ISOs published outside this
project. They are not built by this project and are not described
here. The current ISO links are posted on the project's Facebook
page:

```
https://www.facebook.com/manjaroawesome
```

The thread at `forum.manjaro.org/t/nvidia-340-108-390-157-legacy-drivers-...`
documents the ISO split: two stacks are published, one with the
340xx branch only (which requires a legacy-ABI XLibre) and one with
390/470/580/latest. The ISO split is a consequence of the XLibre
ABI difference, not of anything in this fork.

If you are building your own ISO, the components described in this
document are sufficient. The ISO builder is outside the scope of
this repository.

---

## 11. Known issues and gotchas

### 11.1 `mpatch` fuzz factor

The `mhwd` PKGBUILD uses `--fuzz-factor 0.7`. This is larger than
`patch`'s default. It means the patch can apply at a different line
offset than the one recorded in the patch file. The C++ member
functions remain functionally correct, but the reported line numbers
in `git diff --stat` may not match the ones in the patch file. This
is expected.

If the patch fails entirely under `mpatch`, `_mpatch_debug_on_failure`
in the PKGBUILD generates a debug report at
`${srcdir}/mpatch-debug/`. Check that directory for the reason.

### 11.2 Kernel package name detection

`manjaro_get_kernel_package()` in `recommendation.py` computes the
kernel package name from `platform.release()`. It assumes the
format `X.Y.Z-...-MANJARO` and produces `linuxXY`. This works for
the standard Manjaro kernels (`linux61`, `linux66`, `linux612`,
`linux618`, …) but may not work for real-time kernels or
custom-built kernels. For `-rt` kernels the package name is
`linuxXY-rt`, not `linuxXY`, and the substitution would produce an
invalid package name. This is a known limitation; the configs that
need `-rt` support would need a different substitution.

### 11.3 The `_nfb_version_override` staleness

As noted in Section 6.2, the override is not automatically updated
when a new New Feature Branch is released. A stale override produces
a `supportedchips.html` from an older NFB. For legacy GPUs (`<= 580`)
this is fine; for newer GPUs it may miss entries. The parser's
fallback (skipping unknown device IDs) handles this gracefully: an
unknown device falls through to steps 3 and 4.

### 11.4 The `pkginfo` cache

`makepkg` caches build artifacts in `src/` and `pkg/`. If a build
fails and you want to start clean:

```shell
$ makepkg -C  # clean the build directories
$ makepkg -si
```

The `-C` flag removes `src/` and `pkg/` but keeps the downloaded
sources. To remove sources as well, delete `PKGBUILD`-adjacent
`.tar.*` and `.deb` files manually.

### 11.5 The GitHub Actions builder

The Actions workflow builds in a container. If the container image
has an older `cmake` that rejects the `cmake_minimum_required (VERSION 2.6)`
declaration, the build fails. The PKGBUILD's
`-DCMAKE_POLICY_VERSION_MINIMUM='3.5'` flag addresses this for local
builds; the Actions container should use a matching version.

### 11.6 The `show-driver` deprecation

`show-driver` (installed as `/usr/bin/nvidia-recommended-driver`)
carries a deprecation notice:

```bash
#!/bin/bash
# This script is depreciated. Use 'nvidia-driver-assistant --mhwd' in MHWDCONFIG directly
driver=$(nvidia-driver-assistant --mhwd)
echo $driver
```

The `MHWDCONFIG` files in `mhwd-db` still use the wrapper. Inlining
the call would remove one process spawn per install. This is a
future cleanup, not a bug.

---

## 12. See also

- `docs/Defense.md` — the layered defense that these builds package,
  and why each layer is load-bearing.
- `docs/Architecture.md` — how the Python tool integrates with
  `mhwd`, and the full decision chain.
- `docs/Configuration.md` — the YAML files that drive the Python
  engine, including `architecture.yaml`, `distro.yaml`,
  `overrides.yaml`, and `instructions.yaml`.
- `README.md` — the project overview, CLI reference, and JSON output
  format.
```

---
