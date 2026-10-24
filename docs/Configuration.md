# Configuration

All driver policy in this fork is driven by four YAML files in
`nvidia_driver_assistant/data/`:

| File | Purpose |
|---|---|
| `architecture.yaml` | GPU architecture registry: open-capable flag, minimum driver branch, name patterns |
| `distro.yaml` | Manjaro-specific legacy branch policy and fallback behaviour |
| `overrides.yaml` | Global switches that affect `_parse_features()` and the recommendation |
| `instructions.yaml` | Installation command templates |

This fork is Manjaro-only. `distro.yaml` contains a single entry
(`manjaro`); `instructions.yaml` contains only the `manjaro-closed`
and `manjaro-open` keys. The multi-distro configuration of the
upstream tool has been removed; see `docs/Defense.md` Section 5 for
the rationale.

A fifth input, `supportedchips.html`, is not a YAML file but is
downloaded by the PKGBUILD and read by the tool at import time. It is
described in Section 6.

The files are loaded and validated once, at package import time, by
`nvidia_driver_assistant/config.py`. A syntax error or a missing
required key raises `FileNotFoundError` or `ValueError` at startup;
the tool does not run with a partially valid configuration.

---

## 1. `architecture.yaml`

### 1.1 Purpose

Maps each GPU architecture to:

- `is_open_capable` — whether the open kernel module can bind to
  hardware of this architecture;
- `min_driver` — the minimum NVIDIA driver branch that supports the
  architecture;
- `patterns` — regex patterns used by
  `Device._get_architecture_from_device_name()` to classify a GPU
  from its name.

The registry is the single source of truth for architecture
classification. Derived constants (`OPEN_CAPABLE_ARCHS`,
`OPEN_UNSUPPORTED_ARCHS`, `ARCHITECTURE_MIN_DRIVER`) are computed
from it at load time, so adding an architecture only requires editing
this file.

### 1.2 Entry format

Each top-level key is an architecture name. The value is a mapping
with three required fields:

```yaml
ada:
  is_open_capable: true
  min_driver: 525
  patterns:
    - '\bADA\b'
    - '\bAD\d|\bAD\b'
    - '\bRTX 40\d'
    - '\b4090\b'
    - '\b4080\b'
    - '\b4070\b'
    - '\b4060\b'
    - '\b4050\b'
```

| Field | Type | Description |
|---|---|---|
| `is_open_capable` | bool | `true` if the open kernel module is supported by this architecture |
| `min_driver` | int | Minimum NVIDIA driver major version (e.g. `525` for Ada) |
| `patterns` | list of str | Case-insensitive regexes matched against the uppercased device name |

The validation in `config.py` (`_validate_architecture()`) rejects an
entry if any of the three keys is missing, if `is_open_capable` is
not a `bool`, if `min_driver` is not an `int`, or if `patterns` is
not a `list`.

### 1.3 Ordering

Dictionary order matters. `_get_architecture_from_device_name()`
iterates over `ARCHITECTURE_REGISTRY` in insertion order and returns
on the first match. Two rules follow:

1. **Specific architectures must come before generic ones.** For
   example, `blackwell` (which matches `\bRTX 50\d`) must come before
   `modern-generic` (which matches `\bRTX [6-9]\d`). The current
   order is newest-first: `blackwell`, `ada`, `ampere`, `turing`,
   `volta`, `pascal`, `maxwell`, `kepler`, `fermi`, `tesla2`,
   `tesla1`, `curie`, `pre-curie`, `modern-generic`, `unknown`.

2. **`modern-generic` must come after every explicit architecture.**
   It is the catch-all for GPUs that are newer than the currently
   listed ones (RTX 60xx and beyond). Its `is_open_capable` is
   `true`, and its `min_driver` is `550`. Because the pattern is
   `\bRTX [6-9]\d`, it cannot match any legacy GPU (which never has
   an "RTX 6xxx" name).

3. **`unknown` must come last.** It has an empty `patterns` list, so
   it cannot match anything; it exists so that
   `ARCHITECTURE_REGISTRY.get(self.architecture, "390")` has a
   fallback entry with `is_open_capable: false`.

### 1.4 Current architectures

The fork currently defines fifteen entries:

| Name | Open-capable | min_driver | Notes |
|---|---|---|---|
| `blackwell` | yes | 550 | RTX 50xx, GB chips |
| `ada` | yes | 525 | RTX 40xx, AD chips |
| `ampere` | yes | 470 | RTX 30xx, GA chips |
| `turing` | yes | 418 | RTX 20xx, GTX 16xx, TU chips |
| `volta` | no | 418 | TITAN V, GV chips |
| `pascal` | no | 390 | GTX 10xx, GP chips |
| `maxwell` | no | 390 | GTX 9xx, GTX 750, GM chips |
| `kepler` | no | 390 | GTX 6xx/7xx, GK chips |
| `fermi` | no | 390 | GTX 5xx, GF chips |
| `tesla2` | no | 340 | GTX 200, GT200 chips |
| `tesla1` | no | 304 | 8xxx/9xxx, G80/G9x chips |
| `curie` | no | 96 | GeForce 7xxx, G7x chips |
| `pre-curie` | no | 71 | GeForce 6xxx and older |
| `modern-generic` | yes | 550 | Catch-all for RTX 60xx and newer |
| `unknown` | no | 390 | Fallback for unrecognized names |

The `min_driver` values are used by `_check_driver_compatibility()`
to reject a branch that is too old (or too new) for a given
architecture. For example, a `maxwell` GPU cannot use a branch below
`390`, and a `turing` GPU cannot use a branch below `418`.

### 1.5 How `min_driver` interacts with `_check_driver_compatibility()`

When `DISTRO_NON_LEGACY_DEFAULT_BRANCH` or
`DISTRO_580_LEGACY_OVERRIDE_BRANCH` is set (see Section 3), the
override branch is checked against `min_driver`. If the override is
below the architecture's minimum, `_check_driver_compatibility()`
returns `(False, message)`, and `_parse_features()` either applies a
safe fallback (`AUTO_FALLBACK: true`) or rejects the override
(`AUTO_FALLBACK: false`).

The `max_supported` value returned by `_get_supported_range()` is
the GPU's own legacy branch if present, or `"999"` for non-legacy
GPUs. A branch above `max_supported` is also rejected.

---

## 2. `distro.yaml`

### 2.1 Purpose

Defines the Manjaro-specific legacy branch policy: which branches
are available in the official repositories, what happens when a GPU
needs a branch that is not, and what messages to show.

### 2.2 Entry format

The file has two top-level keys:

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

### 2.3 Fields

| Field | Type | Description |
|---|---|---|
| `min_official_branch` | int | Minimum legacy branch available in the official Manjaro repositories |
| `fallback_method` | `"aur"` or `"error"` | Behaviour when a GPU needs a branch below `min_official_branch` |
| `fallback_branches` | list of int | Branches that the tool knows about but that are not in the official repositories |
| `nouveau_hint_below` | int or null | GPUs on a branch below this value get a Nouveau hint |
| `kernel_substitution` | bool | Whether install commands use a `KERNEL` placeholder |
| `branch_suffix` | str | Suffix appended to branch numbers in install commands |
| `fallback_message` | str | Header printed before AUR fallback instructions |
| `fallback_device_header` | str | Header printed before the per-device legacy listing; `{min_branch}` is substituted |
| `fallback_package_template` | str | Package name pattern for the fallback (e.g. `nvidia-{branch}xx-dkms`) |
| `fallback_utils_template` | str | Package name pattern for the utils fallback |
| `repo_available_note` | str | Note printed when legacy branches are still available in the official repos |

The validation in `config.py` (`_validate_distro_registry()`) only
requires `fallback_method`, `kernel_substitution`, and
`branch_suffix`. The other fields are optional but have defaults
used by the code if absent.

### 2.4 How the values are used

**`min_official_branch`** partitions the unsupported devices into two
groups in `cli.py`:

- devices whose `legacy_int >= min_official_branch` are served from
  the official repositories (they are "repo devices");
- devices whose `legacy_int < min_official_branch` (or whose
  `legacy_int` is `-1`) are "fallback devices".

With `min_official_branch: 340`, a GTX 480 (branch `390`) is a repo
device, and a GeForce 6800 (branch `304`) is a fallback device.

**`fallback_method: "aur"`** means that fallback devices trigger the
AUR message path in `print_fallback_instructions()`:

```
These versions are no longer in official Manjaro repositories.
You can find them in the AUR (Arch User Repository) as:
  - nvidia-304xx-dkms
  - nvidia-304xx-utils
```

The package names come from `fallback_package_template` and
`fallback_utils_template`, with `{branch}` replaced by the device's
branch.

**`nouveau_hint_below: 580`** adds a Nouveau hint for GPUs on
branches below `580` when they reach the AUR fallback path. A GTX
480 (branch `390`) gets the hint; a GTX 750 Ti (branch `580`) does
not.

**`kernel_substitution: true`** tells `process_results()` to replace
`KERNEL` in the instruction template with the running kernel package
name (e.g. `linux618`). The kernel name is computed by
`manjaro_get_kernel_package()` from `platform.release()`.

**`branch_suffix: "xx"`** is appended to branch numbers in the
`BRANCH` placeholder. A branch `580` becomes `580xx` in the
generated command, producing `linux618-nvidia-580xx`.

**`repo_available_note`** is printed when a device is moved from the
unsupported list back into the legacy branch selection because its
branch is available in the repos.

### 2.5 Adding a distribution

This fork is Manjaro-only. The upstream tool supported thirteen
distributions; the fork has removed twelve. To add a distribution
back:

1. Add a `distro_registry` entry to `distro.yaml` with at least
   `fallback_method`, `kernel_substitution`, and `branch_suffix`.
2. Add the distribution's `os-release` ID to the `supported_distros`
   list in the same file.
3. Add `instructions` and `branch_instructions` entries to
   `instructions.yaml` with keys of the form `<distro>-closed` and
   `<distro>-open`.
4. If the distribution has distro-specific aliases (e.g.
   `opensuse-leap` → `opensuse`), add them to
   `SystemInfo.update_info()` in `system.py`.

The `_validate_distro_registry()` check will reject the new entry if
the three required fields are missing. The `_validate_instructions()`
check will reject `instructions.yaml` if either top-level key
(`instructions` or `branch_instructions`) is missing, but it does not
check individual distro entries; a missing entry will surface as a
runtime error when `process_results()` tries to look it up.

---

## 3. `overrides.yaml`

### 3.1 Purpose

Global switches that affect `_parse_features()` and the
recommendation. Unlike `distro.yaml`, these are **not**
distro-conditional: they apply to every detected GPU regardless of
which distribution is running.

### 3.2 Fields

```yaml
DISTRO_NON_LEGACY_DEFAULT_BRANCH: null
DISTRO_580_LEGACY_OVERRIDE_BRANCH: null
ENABLE_LEGACY_OPENKERNEL_RESTRICTION: true
ENABLE_ARCHITECTURE_CHECK: true
AUTO_FALLBACK: true
min_supported_legacy_branch: 580
```

| Field | Type | Default | Description |
|---|---|---|---|
| `DISTRO_NON_LEGACY_DEFAULT_BRANCH` | str or null | `null` | If set, forces every non-legacy GPU to this branch and forces the proprietary module |
| `DISTRO_580_LEGACY_OVERRIDE_BRANCH` | str or null | `null` | If set, overrides the JSON legacy branch of every 580+ legacy GPU |
| `ENABLE_LEGACY_OPENKERNEL_RESTRICTION` | bool | `true` | Forces the proprietary module for every legacy branch `<= 580` |
| `ENABLE_ARCHITECTURE_CHECK` | bool | `true` | Forces the proprietary module for any architecture in `OPEN_UNSUPPORTED_ARCHS` |
| `AUTO_FALLBACK` | bool | `true` | When an override is incompatible with the GPU, fall back to a safe branch instead of rejecting it |
| `min_supported_legacy_branch` | int | `580` | Below this branch, a legacy GPU is classified as unsupported |

The validation in `config.py` (`_validate_overrides()`) requires
`ENABLE_LEGACY_OPENKERNEL_RESTRICTION`,
`ENABLE_ARCHITECTURE_CHECK`, `AUTO_FALLBACK`, and
`min_supported_legacy_branch`. It does not require the two
`DISTRO_*_BRANCH` fields.

### 3.3 How the fields are used

The two `DISTRO_*_BRANCH` overrides are read in
`_parse_features()` steps 1 and 2. The two `ENABLE_*` switches are
read in steps 3 and 4. `min_supported_legacy_branch` is used by
`check_legacy_devices()` in `recommendation.py`.

The interaction with `_parse_features()`:

| Step | Condition | Effect |
|---|---|---|
| 0 | `supportedchips.html` present | Forces `proprietary_required` for legacy devices |
| 1 | `DISTRO_NON_LEGACY_DEFAULT_BRANCH` set and GPU is non-legacy | Forces the specified branch and `proprietary_required` |
| 2 | `DISTRO_580_LEGACY_OVERRIDE_BRANCH` set and GPU is 580+ legacy | Forces the specified branch and `proprietary_required` |
| 3 | `ENABLE_LEGACY_OPENKERNEL_RESTRICTION` and GPU is legacy `<= 580` | Forces `proprietary_required` |
| 4 | `ENABLE_ARCHITECTURE_CHECK` and GPU is in `OPEN_UNSUPPORTED_ARCHS` | Forces `proprietary_required` |
| 5 | No earlier step fired | Reads the JSON `features` flags |

Steps 3 and 4 are the primary defense. Steps 0, 1 and 2 are
additional layers. Step 5 is the upstream behaviour, which the
fork retains only as a last resort. `docs/Defense.md` describes
each layer's role in detail.

### 3.4 Use cases for the `DISTRO_*_BRANCH` overrides

Both default to `null`, which disables them. They are intended for
distributions that want to lock a subset of GPUs to a specific
branch. This fork is Manjaro-only and uses the defaults; the
overrides exist because the code paths are shared with upstream.

A distribution that wants to lock every modern GPU to `550` would
set:

```yaml
DISTRO_NON_LEGACY_DEFAULT_BRANCH: "550"
```

A distribution that wants to downgrade every 580+ legacy card to
`575` would set:

```yaml
DISTRO_580_LEGACY_OVERRIDE_BRANCH: "575"
```

Neither is used by this fork.

### 3.5 `AUTO_FALLBACK` and incompatible overrides

If an override branch is below the GPU's `min_driver`, or above the
GPU's `max_supported`, `_check_driver_compatibility()` returns
`False`. The behaviour then depends on `AUTO_FALLBACK`:

- `true` — `_parse_features()` computes a safe branch via
  `_get_safe_fallback_branch()` and uses it;
- `false` — the override is logged as an error and the branch is
  left unset.

`docs/Defense.md` Section 4 discusses why `AUTO_FALLBACK: true` is
the safer default.

---

## 4. `instructions.yaml`

### 4.1 Purpose

Installation command templates. The fork contains only the
`manjaro-closed` and `manjaro-open` entries.

### 4.2 Format

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

Each entry is a list of shell commands. Placeholders:

| Placeholder | Replaced with | When |
|---|---|---|
| `KERNEL` | The running kernel package name (e.g. `linux618`) | If the distro's `kernel_substitution` is `true` |
| `BRANCH` | The effective branch, with the distro's `branch_suffix` appended (e.g. `580xx`) | If `branch_id` is set |

The substitution order in `process_results()`:

1. `KERNEL` is replaced first, using `manjaro_get_kernel_package()`.
2. `BRANCH` is replaced second, using `branch_id + branch_suffix`.

The `manjaro_open` templates use `-open` to select the open module;
the `manjaro_closed` templates do not.

### 4.3 How the templates are selected

`process_results()` picks a template based on three inputs:

- `distro_id` — the Manjaro `os-release` ID (always `"manjaro"`);
- `driver` — `"open"` or `"closed"`, from `_parse_features()`;
- `branch_id` — `None` for the default branch, a branch string
  (e.g. `"580"`) for an explicit branch.

The lookup key is `"%s-%s" % (distro_id, driver)`, e.g.
`"manjaro-closed"`. If `branch_id` is set, `branch_instructions` is
used; otherwise `instructions`.

If no template is found, `process_results()` prints an error and
returns `False`. This cannot happen with the current
`instructions.yaml` (both keys are present for both drivers), but it
would happen if a future edit removed one.

### 4.4 The `--install` flag

When `nvidia-driver-assistant --install` is passed, the generated
commands are executed with `os.system()` instead of printed. The
function prints the EULA notice first (see `install_driver()` in
`output.py`). The EULA text is extracted from the upstream DEB at
package build time and installed to
`/usr/share/nvidia-driver-assistant/driver_eula/LICENSE`.

---

## 5. `config.py` — loading and validation

### 5.1 Loading

`load_config()` reads all four YAML files from
`nvidia_driver_assistant/data/`, validates them, and returns a dict.
The dict is unpacked into module-level variables at import time, so
every other module imports the constants directly from
`nvidia_driver_assistant.config`.

If a file is missing, `_load_yaml()` raises `FileNotFoundError`. If
a file is empty, it raises `ValueError`. If validation fails, it
raises `ValueError` with a message naming the offending file and
field.

### 5.2 Validation

Each file has its own validator:

- `_validate_architecture()` — every entry must have
  `is_open_capable`, `min_driver`, `patterns` with correct types;
- `_validate_distro_registry()` — every entry must have
  `fallback_method`, `kernel_substitution`, `branch_suffix`;
- `_validate_overrides()` — the four required keys must be present;
- `_validate_instructions()` — the `instructions` and
  `branch_instructions` top-level keys must be present.

The validators do not check semantic correctness (e.g. that
`min_driver` values are in ascending order, or that `min_official_branch`
is a valid branch). Those are the maintainer's responsibility.

### 5.3 Derived constants

`config.py` also computes:

- `OPEN_CAPABLE_ARCHS` — tuple of architecture names where
  `is_open_capable` is `true`;
- `OPEN_UNSUPPORTED_ARCHS` — tuple of names where it is `false`;
- `ARCHITECTURE_MIN_DRIVER` — dict mapping architecture name to
  `str(min_driver)` (the string form is used by
  `_check_driver_compatibility()`);
- `DISTRO_REGISTRY` — the `distro_registry` mapping with
  `fallback_branches` converted to a tuple;
- `MANJARO_MIN_OFFICIAL_LEGACY_BRANCH`, `ARCH_MIN_REPO_LEGACY_BRANCH`,
  `ARCH_AUR_ONLY_BRANCHES` — Manjaro- and Arch-specific convenience
  constants (Arch is not used by this fork but the constants exist
  for symmetry with upstream).

---

## 6. `supportedchips.html`

### 6.1 Purpose

`supportedchips.html` is NVIDIA's own authoritative list of GPUs and
the driver branch that supports each one, published on
`download.nvidia.com`. The fork parses it and uses the resulting
`{devid → branch}` map as an additional check against
`supported-gpus.json` manipulation.

`docs/Defense.md` Section 3 explains why this layer exists. This
section documents how the file is obtained and parsed.

### 6.2 How the file is obtained

The PKGBUILD downloads it in `prepare()`, at build time, from:

```
https://us.download.nvidia.com/XFree86/Linux-x86_64/<version>/README/supportedchips.html
```

The `<version>` is determined by `_latest_nfb_version()`, which:

1. Uses `_nfb_version_override` if set (currently `"615.78.08"`);
2. Otherwise scrapes `https://www.nvidia.com/en-us/drivers/unix/`
   for the "Latest New Feature Branch Version";
3. Otherwise falls back to the directory listing of
   `https://download.nvidia.com/XFree86/Linux-x86_64/`;
4. Otherwise falls back to the production branch from `latest.txt`.

The downloaded file is sanity-checked (`grep -qE 'CURRENT NVIDIA
GPUS|Current NVIDIA GPUs|[0-9]+\.xx driver supports'`) and installed
to `/usr/share/nvidia-driver-assistant/.../data/supportedchips.html`
inside the package.

### 6.3 How the file is parsed

`nvidia_driver_assistant/supported_chips.py` parses it at import
time. The parser:

- splits the HTML at `<a name="Current">` and
  `<a name="legacy_<branch>.xx">` anchors;
- collects `<tr id="devidXXXX">` rows under each anchor;
- assigns each row the branch of the nearest preceding anchor;
- resolves the "current vs legacy" conflict by preferring the
  legacy entry.

The result is exposed as `SUPPORTED_CHIPS`, a dict mapping the
lowercase hex device ID (without the `0x` prefix) to a branch
string (`"current"`, `"580"`, `"470"`, …) or `None` if the file is
missing or unparseable.

### 6.4 How the tool uses it

`Device._parse_features()` step 0:

```python
if SUPPORTED_CHIPS:
    readme_key = self.id.lower().replace("0x", "")
    readme_branch = SUPPORTED_CHIPS.get(readme_key)
    if readme_branch and readme_branch != "current":
        self.legacy_branch = readme_branch
        self.original_legacy_branch = readme_branch
        self.legacy_int = _safe_branch_int(readme_branch)
        self.driver_hint = proprietary_required
        return
```

If `SUPPORTED_CHIPS` is `None` (file missing or parser failed), the
step is skipped and the tool falls back to steps 3 and 4. The
application still runs; see `docs/Defense.md` Section 3 for the
implications.

### 6.5 Why the file is not in `data/` of this repository

The file is NVIDIA-published content. The PKGBUILD downloads it at
build time so that the packaged version always corresponds to a
specific NVIDIA release. The fork does not vendor the HTML in its
git tree, and the file is not in `nvidia_driver_assistant/data/` in
the repository; the packaging step places it there in the installed
package.

If the download fails at build time, the PKGBUILD aborts (the sanity
check runs before `package()`). A build failure is preferable to a
package whose primary defense layer is silently missing.

---

## 7. Adding a new architecture

The typical reason to edit `architecture.yaml` is a new NVIDIA
generation. The procedure:

1. Add a new top-level entry **before** `modern-generic`. The name
   is free-form but should match the architecture's marketing name
   (e.g. `rubin` if NVIDIA calls it that).
2. Set `is_open_capable` and `min_driver` based on NVIDIA's
   published support.
3. Add patterns that match the new card names. Include specific
   model numbers (`\b5090\b`) and the generic series pattern
   (`\bRTX 50\d`) so that both named and unnamed cards are caught.
4. Do not change `modern-generic`'s position; it must stay last.

If the new architecture is open-capable but the specific cards are
not yet known, the `modern-generic` catch-all will classify them
correctly (as open-capable), and adding an explicit entry later is a
refinement, not a fix.

If the new architecture is **not** open-capable, it must be added
explicitly before `modern-generic`, because `modern-generic`
assumes open-capability.

---

## 8. Modifying the Manjaro policy

The typical reasons to edit `distro.yaml` are:

- A legacy branch is removed from the official repositories. Lower
  `min_official_branch` and add the branch to `fallback_branches`.
  Update `fallback_package_template` if the package naming changed.
- A new legacy branch is added. Raise `min_official_branch`.
- The Nouveau hint should apply to a different branch range. Update
  `nouveau_hint_below`.
- The kernel package name format changes. Update
  `manjaro_get_kernel_package()` in `recommendation.py` (this is
  Python code, not YAML).

None of these changes require touching the Python decision logic.
The YAML files are the single source of truth for policy.

---

## 9. See also

- `docs/Defense.md` — the layered defense that these configurations
  drive, and why each layer is load-bearing.
- `docs/Architecture.md` — how the Python tool integrates with
  `mhwd`, and how the two `nvidia-driver-assistant` calls (`--mhwd`
  and `--mhwd-config`) consume these configurations.
- `docs/Building.md` — how to build and test the package, and how
  the PKGBUILD obtains `supportedchips.html`.
```
