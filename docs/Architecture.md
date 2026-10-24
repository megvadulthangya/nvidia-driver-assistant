# Architecture

This document describes how `nvidia-driver-assistant` integrates with
`mhwd` on Manjaro. It documents the full chain from the command line
to the package that `pacman` installs, and it identifies which
component is responsible for each decision.

The chain has three independent pieces:

1. **`mhwd` (C++)** — parses the command line, walks the devices,
   calls `nvidia-driver-assistant --mhwd-config` (via the patch), and
   invokes the shell script.
2. **`scripts/mhwd` (bash)** — sources the selected `MHWDCONFIG`,
   resolves kernel module names, and calls `pacman`.
3. **`nvidia-driver-assistant` (Python)** — the decision engine. It is
   called twice: once for the config name (`--mhwd-config`), and once
   for the kernel module flavor (`--mhwd`).

The three pieces are described in the sections below, followed by a
step-by-step trace of a real installation and a list of known
limitations.

---

## 1. Entry point: `mhwd -a pci nonfree 0300`

The typical invocation on Manjaro is:

```shell
$ sudo mhwd -a pci nonfree 0300
```

This tells `mhwd` to auto-configure (`-a`) PCI devices (`pci`) with
a non-free driver (`nonfree`) whose class ID is `0300` (VGA
compatible controller).

`Mhwd::tryToParseCmdLineOptions()` in `src/Mhwd.cpp` parses this as:

| Variable | Value |
|---|---|
| `arguments_.AUTOCONFIGURE` | `true` |
| `operationType` | `"PCI"` |
| `autoConfigureNonFreeDriver` | `true` |
| `autoConfigureClassID` | `"0300"` |

`launch()` then enters the auto-configure block. It iterates over
`data_.PCIDevices` (all PCI devices), skips any device whose
`classID_` is not `"0300"`, and for each remaining device selects a
config.

---

## 2. Config selection: the `mhwd` patch

### 2.1 The patch

The `mhwd` package in this fork carries a single patch,
`0001-mhwd-nvidia-assistant-integration.patch`, which adds a method
`getNvidiaAssistantConfig()` to the `Mhwd` class and inserts a call
to it inside the auto-configure loop.

The method runs:

```cpp
FILE* fp = popen("nvidia-driver-assistant --mhwd-config 2>/dev/null", "r");
```

and reads one line (up to 256 bytes), strips trailing whitespace,
and caches the result for the rest of the `mhwd` invocation.

The call site in the auto-configure loop is:

```cpp
if (autoConfigureNonFreeDriver
        && "0300" == autoConfigureClassID
        && "10de" == device->vendorID_)
{
    std::string preferredConfig{getNvidiaAssistantConfig()};
    if (!preferredConfig.empty())
    {
        for (auto&& availableConfig : device->availableConfigs_)
        {
            if (availableConfig->name_ == preferredConfig)
            {
                config = availableConfig;
                break;
            }
        }
        if (nullptr == config)
        {
            consoleWriter_.printWarning(
                    "nvidia-driver-assistant recommended '"
                    + preferredConfig
                    + "' but it is not available for this device; "
                    "falling back to priority-based selection");
        }
    }
}
```

The patch only fires when **all three** conditions hold:

1. `autoConfigureNonFreeDriver` is true — i.e. the user passed
   `nonfree`, not `free`.
2. `autoConfigureClassID` is `"0300"`.
3. The device's `vendorID_` is `"10de"` (NVIDIA).

For free-driver invocations (`mhwd -a pci free 0300`), for
non-display class IDs, and for non-NVIDIA devices, the patch is
bypassed and the original priority loop runs.

### 2.2 Fallback: priority loop

If the patch does not fire, or if the config name returned by
`nvidia-driver-assistant --mhwd-config` is not present in the
device's `availableConfigs_`, `mhwd` falls back to the priority
loop:

```cpp
for (auto&& availableConfig : device->availableConfigs_)
{
    if (autoConfigureNonFreeDriver || availableConfig->freedriver_)
    {
        config = availableConfig;
        break;
    }
}
```

`availableConfigs_` is populated by `Data::setMatchingConfigs()` for
each config in `/var/lib/mhwd/db/pci/`, and sorted by
`Config::priority_` in descending order (higher priority first).
The loop takes the first matching entry.

The priorities in the `mhwd-db` fork (as of the current package
version) are:

| Config | Priority | Freedriver |
|---|---|---|
| `video-hybrid-intel-nvidia-prime` | 12 | false |
| `video-hybrid-amd-nvidia-prime` | 12 | false |
| `video-hybrid-intel-nvidia-580xx-prime` | 10 | false |
| `video-hybrid-amd-nvidia-580xx-prime` | 10 | false |
| `video-hybrid-intel-nvidia-470xx-prime` | 9 | false |
| `video-hybrid-amd-nvidia-470xx-prime` | 9 | false |
| `video-hybrid-intel-nvidia-390xx-bumblebee` | 8 | false |
| `video-hybrid-intel-nvidia-340xx-bumblebee` | 8 | false |
| `video-nvidia` | 7 | false |
| `video-nvidia-580xx` | 5 | false |
| `video-nvidia-470xx` | 4 | false |
| `video-nvidia-390xx` | 3 | false |
| `video-nvidia-340xx` | 2 | false |
| `video-virtualmachine` | 2 | true |
| `video-linux` | 2 | true |
| `video-modesetting` | 1 | true |
| `video-vesa` | 0 | true |

For a system with a single GPU, the priority loop and the patch
typically agree, because only one config matches the device. The
patch matters when several configs could apply (e.g. hybrid
systems); see Section 9.

---

## 3. `nvidia-driver-assistant --mhwd-config`

`_resolve_mhwd_config()` in `cli.py` maps the detected branch to a
config name:

```python
def _resolve_mhwd_config(legacy_branch, branch_locked):
    branch = branch_locked or legacy_branch
    if branch:
        branch_str = str(branch).split(".")[0]
        if branch_str and branch_str != "latest":
            return "video-nvidia-%sxx" % branch_str
    return "video-nvidia"
```

The mapping:

| Detected branch | Config name |
|---|---|
| `None` (modern GPU) | `video-nvidia` |
| `"580"` | `video-nvidia-580xx` |
| `"470"` | `video-nvidia-470xx` |
| `"390"` | `video-nvidia-390xx` |
| `"340"` | `video-nvidia-340xx` |

The branch is determined by `check_legacy_devices()` inside
`recommend_driver()`. It reads the `legacybranch` field of the
matched JSON entry, subject to the defense layers described in
`docs/Defense.md`.

`--mhwd-config` is called from `mhwd` only. It is not used by any
other consumer.

---

## 4. The `MHWDCONFIG` file format

An `MHWDCONFIG` file is a shell-sourced file that describes a
graphics driver configuration. It is located at
`/var/lib/mhwd/db/pci/graphic_drivers/<config>/MHWDCONFIG` (in the
`mhwd-db` package) and is copied to
`/var/lib/mhwd/local/pci/<config>/MHWDCONFIG` when installed.

### 4.1 Configuration fields

| Field | Example | Purpose |
|---|---|---|
| `NAME` | `video-nvidia-580xx` | The config name; must match the directory name |
| `INFO` | `Closed source NVIDIA 580xx drivers for linux.` | Description shown by `mhwd -la` |
| `VERSION` | `2026.03.05` | Used by `mhwd-db.install` to decide whether to update the local copy |
| `FREEDRIVER` | `false` | `true` for open-source drivers |
| `PRIORITY` | `5` | Higher numbers are tried first |
| `CLASSIDS` | `0300 0302` | PCI class IDs matched |
| `VENDORIDS` | `10de` | PCI vendor IDs matched, or `*` |
| `DEVICEIDS` | `>/var/lib/mhwd/ids/pci/nvidia-580xx.ids` | Space-separated list, or `>file` to read from a file |
| `BLACKLISTEDCLASSIDS` | | Optional exclusion list |
| `BLACKLISTEDVENDORIDS` | | Optional exclusion list |
| `BLACKLISTEDDEVICEIDS` | | Optional exclusion list |
| `CONFLICTS` / `CONFLICTS_32` / `CONFLICTS_64` | | Package names that must be removed first |
| `CONKMOD` | `nvidia-390xx nvidia-470xx nvidia` | Kernel modules that must be removed |
| `CONFLDD` / `CONFLDD_64` | | Directories that must be removed |
| `MHWDCONFLICTS` | `video*nvidia*` | Other mhwd configs that conflict |
| `MHWDDEPENDS` | `video-linux` | Other mhwd configs that must be installed first |
| `DEPENDS` / `DEPENDS_32` / `DEPENDS_64` | `nvidia-580xx-utils nvidia-580xx-settings libxnvctrl-580xx` | Package dependencies |
| `DEPKMOD` | `nvidia-580xx` | Kernel module package(s); the kernel name is prepended at runtime |
| `OPTREMDEPENDS` / `OPTREMDEPENDS_32` / `OPTREMDEPENDS_64` | | Optional dependencies to demote on removal |

In addition to the fields, an `MHWDCONFIG` file may define shell
functions:

- `pre_install()` — run before package operations
- `post_install()` — run after package operations
- `pre_remove()` — run before package removal
- `post_remove()` — run after package removal

The fields are parsed by `Config::readConfigFile()` in
`src/Config.cpp`.

### 4.2 Multiple hardware ID groups

A single config can match several hardware IDs by repeating the
`CLASSIDS` / `VENDORIDS` / `DEVICEIDS` triple:

```
# NVIDIA cards
CLASSIDS="0300 0302"
VENDORIDS="10de"
DEVICEIDS=">/var/lib/mhwd/ids/pci/nvidia-580xx.ids"

# Intel cards
CLASSIDS="0300"
VENDORIDS="8086"
DEVICEIDS="*"
BLACKLISTEDDEVICEIDS="0be1 8108"
```

`Config::readConfigFile()` pushes a new `HardwareID` group onto
`hwdIDs_` each time a `CLASSIDS` field is seen after the previous
group already has a non-empty `classIDs` list.

`Data::getAllDevicesOfConfig()` then requires **every** group to
match at least one device. If any group matches no device, the
entire config is discarded for that device list. This is how the
hybrid configs require both an NVIDIA and an Intel (or AMD) device
to be present.

### 4.3 The `>file` syntax for `DEVICEIDS`

When a `DEVICEIDS` value begins with `>`, `readConfigFile()` reads
the file whose path follows the `>` and uses its whitespace-separated
contents as the device ID list.

For the NVIDIA configs, these files live in
`/var/lib/mhwd/ids/pci/` and are generated by the `mhwd-nvidia`
helper script from two files extracted from the NVIDIA `.run`
installer:

- `README.txt` — NVIDIA's own list of supported GPUs;
- `kernel/nvidia/nv-kernel-amd64.o_binary` — the compiled kernel
  module binary, used to extract the actual device IDs.

The result is a single line of space-separated hex device IDs, e.g.:

```
1b06 1d81 1380 1381 ...
```

The PKGBUILD for `nvidia-390xx-utils` shows the generation step:

```bash
sh -e ${srcdir}/mhwd-nvidia \
    ${srcdir}/${_pkg}/README.txt \
    ${srcdir}/${_pkg}/kernel/nvidia/nv-kernel-amd64.o_binary \
    > ${pkgdir}/var/lib/mhwd/ids/pci/nvidia-390xx.ids
```

This is important for `docs/Defense.md`: the device-to-config
matching uses `.ids` files generated from NVIDIA's own binary, not
from `supported-gpus.json`. A JSON manipulation cannot change which
config a given PCI device matches.

### 4.4 The `nvidia-recommended-driver` call inside `MHWDCONFIG`

Several configs (notably `video-nvidia`, `video-nvidia-580xx`,
`video-nvidia-470xx`, `video-nvidia-390xx`, `video-nvidia-340xx`,
and the hybrid variants) contain a line of the form:

```bash
DEPKMOD="nvidia-580xx"
[[ "$(nvidia-recommended-driver)" == "open" ]] && DEPKMOD="nvidia-580xx-open"
```

`nvidia-recommended-driver` is a small shell wrapper (`show-driver`
in the repository):

```bash
#!/bin/bash
driver=$(nvidia-driver-assistant --mhwd)
echo $driver
```

So the config runs `nvidia-driver-assistant --mhwd` a **second
time** during installation. The output is `open` or `closed`, and it
selects between the closed and open variants of the kernel module
package.

The two `nvidia-driver-assistant` calls serve different purposes:

| Call | When | Returns | Consumer |
|---|---|---|---|
| `--mhwd-config` | Before install, from `mhwd` C++ | Config name (e.g. `video-nvidia-580xx`) | `mhwd` patch |
| `--mhwd` | During install, from the config's `post_install()` | `open` or `closed` | `nvidia-recommended-driver` |

The two calls are independent. Both use the same underlying
recommendation logic and both are protected by the layers described
in `docs/Defense.md`.

---

## 5. The shell script: `scripts/mhwd`

`Mhwd::runScript()` builds a command line of the form:

```shell
exec /var/lib/mhwd/scripts/mhwd --install --sync \
     --cachedir /var/cache/pacman/pkg \
     --pmconfig /etc/pacman.conf \
     --pmroot / \
     --config /var/lib/mhwd/local/pci/video-nvidia-580xx/MHWDCONFIG \
     --device "0300|10de|1380|1:0:0" \
     2>&1
```

and runs it via `popen()`, forwarding the output to `mhwd`'s stdout
with a green colour marker.

`scripts/mhwd` parses these arguments, sets up some globals, and
sources the config. The relevant globals and steps:

### 5.1 Globals

- `ARCH=$(uname -m)` — used to decide whether to install 32-bit
  packages.
- `KERNELS=$(pacman -Qqs "^linux[0-9][0-9]?([0-9])$")` — list of
  installed kernel packages (e.g. `linux618 linux61`).
- `MHWD64_IS_LIB32` — whether 32-bit packages should be installed,
  read from `/etc/mhwd-x86_64.conf` or defaulting to `true`.

### 5.2 Sourcing the config

```bash
. "${CONFIGPATH}"
```

Then, for each class ID in `$CLASSIDS`, the corresponding include
file in `/var/lib/mhwd/scripts/include/` is sourced. The `0300`
include provides helper functions such as
`MHWD_ADD_DEVICE_SECTION`, `MHWD_ADD_DRI`, `MHWD_ADD_COMPOSITING`,
and `MHWD_ADD_BACKSPACE`, used by many configs' `post_install()`.

### 5.3 The install flow

When `INSTALL=true`, the script runs the following steps in order.

**1. `pre_install()`** — if the config defines it.

**2. Remove conflicting directories** (`CONFLDD`, `CONFLDD_64`).

**3. `MHWD_CHECK_KMODS()`** — for each installed kernel, and for
each module in `CONKMOD` and `DEPKMOD`, build the fully qualified
module names. For example:

| Config value | Installed kernel | Result |
|---|---|---|
| `CONKMOD="nvidia-390xx nvidia-470xx nvidia"` | `linux618` | `CONKMODS="linux618-nvidia-390xx linux618-nvidia-470xx linux618-nvidia"` |
| `DEPKMOD="nvidia-580xx"` | `linux618` | `DEPKMODS="linux618-nvidia-580xx"` |
| `DEPKMOD="nvidia-580xx-open"` (from the open branch) | `linux618` | `DEPKMODS="linux618-nvidia-580xx-open"` |

**4. Remove conflicting packages** (`CONFLICTS`, `CONFLICTS_32`,
`CONFLICTS_64`, `CONKMODS`) via `pacman -Rs`.

**5. Install dependencies** (`DEPENDS`, `DEPENDS_32`, `DEPENDS_64`,
`DEPKMODS`) via:

```bash
pacman --needed -S${SYNC} ${PACKAGES}
pacman -D --asexplicit ${PACKAGES}
```

`-S${SYNC}` is `-Sy` if `--sync` was passed to the script.

Note that `DEPENDS` (the userspace packages, e.g.
`nvidia-580xx-utils`) is separate from `DEPKMODS` (the kernel module
package, e.g. `linux618-nvidia-580xx`). Both are installed in the
same `pacman` invocation.

**6. `post_install()`** — if the config defines it. This is where
the Xorg configuration is created, the `nvidia_drm.modeset=1` option
is written, and `mhwd-gpu` is called.

### 5.4 The Xorg configuration step

Most `post_install()` functions end with:

```bash
mhwd-gpu --setmod nvidia --setxorg "${XORGFILE}"
```

`mhwd-gpu` (a shell script in `scripts/mhwd-gpu`) then:

- Writes `/etc/modprobe.d/mhwd-gpu.conf` with blacklist entries for
  `nouveau`, `ttm`, `drm_kms_helper`, and `drm`.
- Writes `/etc/modules-load.d/mhwd-gpu.conf` with `nvidia` (or
  `nvidia_drm`, depending on the config).
- Symlinks `/etc/X11/xorg.conf.d/90-mhwd.conf` to `$XORGFILE`.

For `video-nvidia-580xx`, the config additionally appends:

```bash
echo "options nvidia_drm modeset=1" >> "${MHWDGPU_MODOPTNVIDIA}"
```

to `/etc/modprobe.d/mhwd-gpu.conf`.

### 5.5 The removal flow

Symmetric to install:

1. `pre_remove()` — if defined.
2. `MHWD_CHECK_KMODS()` — rebuild `CONKMODS` and `DEPKMODS`.
3. `pacman -Rs` on the union of `DEPENDS`, `DEPKMODS`,
   `CONKMODS`.
4. `pacman -D --asdeps` on `OPTREMDEPENDS*`.
5. `post_remove()` — removes the Xorg symlink and modprobe entries.

The `post_remove()` of every standard config ends with
`mhwd-gpu --check`, which removes `/etc/X11/xorg.conf.d/90-mhwd.conf`
if its target no longer exists.

---

## 6. End-to-end trace: GTX 750 Ti on Manjaro

This section walks through `sudo mhwd -a pci nonfree 0300` on a
system with a single GTX 750 Ti.

### 6.1 `mhwd` — parse and discover

`Mhwd::launch()` reads `PCIDevices`. The GTX 750 Ti has
`classID_ = "0300"`, `vendorID_ = "10de"`, `deviceID_ = "1380"`.

### 6.2 `mhwd` — call `nvidia-driver-assistant --mhwd-config`

The patch condition holds (`nonfree`, `0300`, `10de`). `mhwd` runs:

```shell
$ nvidia-driver-assistant --mhwd-config
```

The Python tool:

1. `get_nvidia_devices()` finds device `0x1380`.
2. `_parse_features()` runs the layered checks:
   - Step 0: `supportedchips.html` parser maps `1380` to legacy
     branch `580`, so `driver_hint = proprietary_required`,
     `original_legacy_branch = "580"`.
   - Step 3 would have done the same even without step 0, because
     the JSON says `legacybranch: "580.xx"`.
3. `check_legacy_devices()` returns `("580", [])`.
4. `_resolve_mhwd_config("580", None)` returns
   `"video-nvidia-580xx"`.
5. `--mhwd-config` prints `video-nvidia-580xx` to stdout and exits
   `0`.

`mhwd` receives the string `video-nvidia-580xx`.

### 6.3 `mhwd` — pick the config

The patch looks for `video-nvidia-580xx` in
`device->availableConfigs_`. The GTX 750 Ti is in
`nvidia-580xx.ids` (generated by the `nvidia-580xx-utils` PKGBUILD
from `README.txt` and `nv-kernel-amd64.o_binary`), so
`video-nvidia-580xx` is present. `config = video-nvidia-580xx`.

If the config were not present, `mhwd` would fall back to the
priority loop.

### 6.4 `mhwd` — install

`performTransaction(config, INSTALL)` calls `runScript(config,
INSTALL)`, which builds:

```shell
exec /var/lib/mhwd/scripts/mhwd --install --sync \
     --cachedir /var/cache/pacman/pkg \
     --pmconfig /etc/pacman.conf \
     --pmroot / \
     --config /var/lib/mhwd/local/pci/video-nvidia-580xx/MHWDCONFIG \
     --device "0300|10de|1380|1:0:0"
```

### 6.5 `scripts/mhwd` — source and resolve

The script sources the config. The config defines:

```bash
DEPKMOD="nvidia-580xx"
[[ "$(nvidia-recommended-driver)" == "open" ]] && DEPKMOD="nvidia-580xx-open"
```

Because the GTX 750 Ti is legacy 580, `nvidia-recommended-driver`
runs `nvidia-driver-assistant --mhwd`, which returns `closed`
(step 3 of `_parse_features()`). So `DEPKMOD` stays
`nvidia-580xx`.

`MHWD_CHECK_KMODS()` converts `DEPKMOD="nvidia-580xx"` and the
installed kernel `linux618` into `DEPKMODS="linux618-nvidia-580xx"`.

### 6.6 `scripts/mhwd` — call pacman

The final `pacman` invocation installs the userspace packages and
the kernel module:

```shell
$ pacman --needed -Sy \
    nvidia-580xx-utils nvidia-580xx-settings libxnvctrl-580xx \
    linux618-nvidia-580xx
```

### 6.7 `post_install()`

The `video-nvidia-580xx` `post_install()`:

- creates `/etc/X11/mhwd.d/nvidia.conf` via `nvidia-xconfig`;
- adds a `Section "ServerFlags"` block (for compatibility);
- runs `mhwd-gpu --setmod nvidia --setxorg ...`, which blacklists
  `nouveau`/`ttm`/`drm` and symlinks `90-mhwd.conf`;
- loads `nvidia_drm`;
- appends `options nvidia_drm modeset=1` to
  `/etc/modprobe.d/mhwd-gpu.conf`.

After the script returns, `mhwd` copies the config directory from
`/var/lib/mhwd/db/pci/graphic_drivers/video-nvidia-580xx/` to
`/var/lib/mhwd/local/pci/video-nvidia-580xx/` and updates its
installed-config cache.

---

## 7. The `mhwd-db` package

The `mhwd-db` package provides the contents of
`/var/lib/mhwd/db/pci/graphic_drivers/` and
`/var/lib/mhwd/db/pci/network_drivers/`. Its PKGBUILD (`mhwd-db`)
installs the whole `pci/` tree from the fork of the `mhwd-db`
repository.

The `mhwd-db.install` script's `post_upgrade()` iterates over every
config in `graphic_drivers/` and `network_drivers/` and compares its
`VERSION` field against the version of the corresponding file in
`/var/lib/mhwd/local/pci/`. If the versions differ, the new
`MHWDCONFIG` is copied to the local directory. This is how a
`pacman -Syu` propagates updated config files to already-installed
systems.

The `mhwd-db` package in this fork depends on:

- `mhwd-nvidia-340xx`, `mhwd-nvidia-390xx`, `mhwd-nvidia-470xx`,
  `mhwd-nvidia-580xx`, `mhwd-nvidia` — the packages that ship the
  `.ids` files;
- `nvidia-driver-assistant` — the Python decision engine that the
  `MHWDCONFIG` files call.

The `mhwd-nvidia-*` packages are produced by the corresponding
`nvidia-*xx-utils` PKGBUILDs (see Section 4.3).

---

## 8. The `nvidia-recommended-driver` wrapper

`show-driver` (installed as `/usr/bin/nvidia-recommended-driver`) is
a three-line shell wrapper:

```bash
#!/bin/bash
driver=$(nvidia-driver-assistant --mhwd)
echo $driver
```

Its purpose is to let the `MHWDCONFIG` files ask the Python engine
for the kernel module flavor without hardcoding the answer. All
NVIDIA configs in the `mhwd-db` fork use it.

The wrapper has a comment saying it is deprecated, in favour of
calling `nvidia-driver-assistant --mhwd` directly from the config.
The existing configs still use the wrapper; a future cleanup could
inline it.

---

## 9. Known limitations and edge cases

The current implementation has several behaviours that are worth
documenting, because they are not obvious from the code.

### 9.1 The patch only fires for `classID == "0300"`

If a user runs `mhwd -a pci nonfree 0302` (a 3D controller, sometimes
used by discrete laptop GPUs), the patch does not fire
(`"0300" == autoConfigureClassID` is false). The priority loop
handles the selection instead.

In practice, most configs match both `0300` and `0302` via their
`CLASSIDS` field, so the outcome is usually the same. But the patch
is not involved in that case.

### 9.2 The patch and the priority loop disagree on hybrid systems

On a system with an Intel iGPU and an NVIDIA GPU, the priority loop
for the Intel device selects `video-hybrid-intel-nvidia-prime`
(priority 12). The patch for the NVIDIA device selects
`video-nvidia` (or `video-nvidia-580xx`), because
`nvidia-driver-assistant --mhwd-config` only sees NVIDIA devices
and does not know that a hybrid configuration is appropriate.

The two selections conflict. In the loop over `configs_`,
`mhwd` will install the hybrid config first, then fail on the second
config because `MHWDCONFLICTS="video*nvidia*"` matches the
already-installed hybrid config.

This is a known behaviour of the current patch. Fixing it would
require either:

- extending `--mhwd-config` to detect the presence of a hybrid
  partner (Intel or AMD GPU) and return the hybrid config name, or
- making the patch skip when a hybrid config is available for the
  same device.

Neither is implemented.

### 9.3 Mixed legacy and modern NVIDIA GPUs

On a system with both a legacy GPU (e.g. GTX 750 Ti) and a modern
GPU (e.g. RTX 4070), the priority loop queues two configs
(`video-nvidia-580xx` for the 750 Ti, `video-nvidia` for the 4070).
The two configs conflict via `MHWDCONFLICTS="video*nvidia*"`, so the
second install fails.

This is not specific to the patch; the same failure happens with
the priority loop alone.

### 9.4 Unknown GPUs

If a device is not listed in any `nvidia-*.ids` file (e.g. a
newly-released GPU before `nvidia-utils` is updated), no config is
in `availableConfigs_`. The patch's `--mhwd-config` returns
`video-nvidia`, `mhwd` prints a warning ("recommended ... but it is
not available for this device"), the priority loop finds nothing,
and `mhwd` reports "No config found for device".

The Python tool, independently, classifies the unknown device as
`open_required` (via `_parse_features()` step 5 fallback). This is
not used by `mhwd` in that path.

---

## 10. Files and directories

| Path | Purpose |
|---|---|
| `/usr/bin/nvidia-driver-assistant` | Python entry point (from `nvidia-driver-assistant` package) |
| `/usr/bin/nvidia-recommended-driver` | `show-driver` wrapper (from `nvidia-driver-assistant` package) |
| `/usr/share/nvidia-driver-assistant/supported-gpus/supported-gpus.json` | Upstream JSON, extracted from the DEB |
| `.../nvidia_driver_assistant/data/supportedchips.html` | Parser input, downloaded by the PKGBUILD |
| `/usr/bin/mhwd` | The C++ `mhwd` binary |
| `/var/lib/mhwd/scripts/mhwd` | The bash script sourced by `runScript()` |
| `/var/lib/mhwd/scripts/include/<classid>` | Per-class helper functions |
| `/var/lib/mhwd/db/pci/graphic_drivers/<config>/MHWDCONFIG` | Config database (from `mhwd-db`) |
| `/var/lib/mhwd/db/pci/network_drivers/<config>/MHWDCONFIG` | Network config database (from `mhwd-db`) |
| `/var/lib/mhwd/local/pci/<config>/MHWDCONFIG` | Installed configs (copied by `installConfig`) |
| `/var/lib/mhwd/ids/pci/nvidia-*.ids` | Device ID lists (from `mhwd-nvidia-*` packages) |
| `/etc/mhwd-x86_64.conf` | Optional lib32 override |
| `/etc/X11/xorg.conf.d/90-mhwd.conf` | Symlink to the active Xorg config |
| `/etc/modprobe.d/mhwd-gpu.conf` | Blacklist and modprobe options |
| `/etc/modules-load.d/mhwd-gpu.conf` | Modules to load at boot |
| `/etc/modules-load.d/mhwd-gpu.conf` | Modules to load at boot |
| `/etc/X11/mhwd.d/nvidia.conf` | Generated Xorg config for the NVIDIA driver |

---

## 11. See also

- `docs/Defense.md` — why the Python decision logic has multiple
  hardcoded layers, and how they interact with `supported-gpus.json`.
- `docs/Configuration.md` — the YAML configuration files that drive
  the Python engine.
- `docs/Building.md` — how to build the fork, the patched `mhwd`,
  and the `mhwd-db` fork locally.
```

---
