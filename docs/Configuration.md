# Configuration and NVIDIA device data

The Manjaro-targeted fork uses three YAML files in `nvidia_driver_assistant/data/`:

| File | Purpose |
|---|---|
| `distro.yaml` | Distribution-specific legacy package availability and fallback behaviour. |
| `overrides.yaml` | The Assistant's minimum supported legacy branch. |
| `instructions.yaml` | Installation command templates for open and closed NVIDIA kernel modules. |

There is no `architecture.yaml` in the current implementation. GPU classification is based on PCI Device IDs, `supported-gpus.json`, and NVIDIA's supportedchips documents, not on a separate GPU-name architecture registry.

The YAML files are loaded and validated by `config.py` when the package is imported. A missing, empty or invalid required configuration prevents the application from loading.

## 1. Distribution policy: `distro.yaml`

The current configuration contains the Manjaro entry:

```yaml
distro_registry:
  manjaro:
    min_official_branch: 390
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

### 1.1 Fields

| Field | Meaning |
|---|---|
| `min_official_branch` | Lowest legacy driver branch currently available in the Manjaro package set. The current value is 390. |
| `fallback_method` | Action for a legacy branch below the repository threshold. `aur` prints the configured AUR fallback instructions. |
| `fallback_branches` | Additional branch numbers handled as explicit fallback-only branches. The current list is empty. |
| `nouveau_hint_below` | Adds a Nouveau hint for fallback branches below this number. |
| `kernel_substitution` | Enables replacement of the `KERNEL` placeholder in installation templates. |
| `branch_suffix` | Text appended to the numeric driver branch for package names, currently `xx`. |
| `fallback_message` | Configured fallback message header. |
| `fallback_device_header` | Per-device fallback header; `{min_branch}` is substituted with the configured minimum. |
| `fallback_package_template` | Package name template for the DKMS fallback package. |
| `fallback_utils_template` | Package name template for the userspace utilities fallback package. |
| `repo_available_note` | Message shown when a legacy branch is available in the Manjaro package set. |

`supported_distros` currently contains only `manjaro`.

### 1.2 The two legacy thresholds are different

Do not confuse `min_official_branch` with `min_supported_legacy_branch`:

- `min_official_branch: 390` is a statement about the current Manjaro package set. It means that 390xx is the lowest legacy branch currently available there.
- `min_supported_legacy_branch: 580` is the Assistant's own recommendation threshold. Branches below 580 are initially processed through the unsupported-legacy path and then reconciled with the selected distribution's repository/fallback policy.

This allows the Assistant to support the 390xx and 470xx repository branches even though they are below its common legacy threshold. It also allows the Assistant to recognize 340xx while reporting that the current Manjaro repository set does not provide that branch.

### 1.3 340xx capability versus repository availability

The value `390` in `min_official_branch` does not disable 340xx support in the program. The 340 parser, PCI ID list generation, ID audit, PCI Device ID branch lookup and legacy closed-module handling remain present.

For a 340xx device, the normal Manjaro recommendation path reaches the configured fallback handling because 340 is below 390. This is expected. It is not a parser failure and does not mean the Assistant has lost 340xx support.

## 2. Assistant legacy threshold: `overrides.yaml`

The current file contains:

```yaml
# Minimum legacy driver branch supported by the configured distributions.
# Legacy branches below this value are handled through the distribution's
# fallback policy. The 580 branch remains supported.
min_supported_legacy_branch: 580
```

The value is read by `recommendation.py` and used when `check_legacy_devices()` separates legacy devices into the common supported set and the distribution-policy path.

With the current values:

| Legacy branch | Assistant handling | Manjaro package-policy result |
|---|---|---|
| 580 | At/above the Assistant threshold | Available in the Manjaro package set |
| 470 | Below the Assistant threshold | Reconciled as a repository branch because it is at/above 390 |
| 390 | Below the Assistant threshold | Reconciled as a repository branch because it meets the 390 minimum |
| 340 | Below the Assistant threshold | Below the Manjaro repository minimum; fallback handling is used |

Changing this value changes the Assistant's legacy classification path. It does not install packages or create MHWD profiles.

## 3. Installation templates: `instructions.yaml`

The current Manjaro templates are:

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

### 3.1 Placeholders

| Placeholder | Replacement | Example |
|---|---|---|
| `KERNEL` | Running Manjaro kernel package name | `linux618` |
| `BRANCH` | Numeric branch plus `branch_suffix` | `580xx` |

For a 580xx closed-module recommendation, the branch template produces a command similar to:

```shell
sudo pacman -S linux618-nvidia-580xx
```

For a latest driver recommendation with the open module, the non-branch template produces:

```shell
sudo pacman -S linux618-nvidia-open
```

The `--install` option executes the generated command after showing the NVIDIA EULA notice. Without `--install`, the command is displayed for the user.

## 4. NVIDIA source documents

The Assistant package build downloads and validates five documents:

| File | Branch | Parser | What it supplies |
|---|---|---|---|
| `supportedchips.html` | Latest 6xx | Modern row/section parser | Full Device ID-to-current/legacy map. |
| `supportedchips580.html` | 580 | Modern row/section parser | 580 Current Device ID set. |
| `supportedchips470.html` | 470 | Legacy table parser | 470-supported base Device IDs. |
| `supportedchips390.html` | 390 | Legacy table parser | 390-supported base Device IDs. |
| `supportedchips340.html` | 340 | Legacy table parser | 340-supported base Device IDs. |

The files are fetched at package build time from NVIDIA's driver documentation tree:

```text
https://us.download.nvidia.com/XFree86/Linux-x86_64/<version>/README/supportedchips.html
```

The actual `<version>` is discovered separately for each driver generation by the PKGBUILD. The five files are copied into `nvidia_driver_assistant/data/` for validation and then installed into the Python package data directory.

### 4.1 Latest and 580 parser behaviour

The latest and 580 documents use sections marked by anchors such as `Current` or `legacy_580.xx`, and table rows with IDs such as:

```html
<tr id="devid1380"> ... </tr>
<tr id="devid2D18_17AA_3E31"> ... </tr>
```

The parser extracts the four-character NVIDIA Device ID. For rows that include subsystem identifiers, it uses the base Device ID; subsystem IDs are not separate MHWD device entries.

The latest document produces a map whose values are `current` or a numeric legacy branch. If an ID occurs in Current and a legacy section, the explicit legacy classification wins.

The 580 parser can return only the `Current` list. Later legacy sections appended to that document are not included in the set.

### 4.2 470, 390 and 340 parser behaviour

Older documents use tables with a `Device PCI ID` column. The parser identifies the column from each table header rather than assuming a fixed column index. It reads the first PCI ID token from the cell. If the cell contains a base Device ID and subsystem IDs, only the first value is used.

The parser requires NVIDIA's legacy-section boundary to be present. If that boundary cannot be found, it refuses to guess where the supported-products tables end. This causes validation to fail instead of silently generating an incomplete list.

## 5. MHWD ID generation and audit

`mhwd_ids.py` maps branches to filenames:

| Argument | Filename |
|---|---|
| `latest` or `6xx` | `nvidia.ids` |
| `580` | `nvidia-580xx.ids` |
| `470` | `nvidia-470xx.ids` |
| `390` | `nvidia-390xx.ids` |
| `340` | `nvidia-340xx.ids` |

Generation is read-only with respect to the system. `generate_ids()` returns text; the CLI writes it to stdout and the calling PKGBUILD redirects it into the package staging directory.

```shell
nvidia-driver-assistant --generate-ids 340 > nvidia-340xx.ids
```

The generated file contains a comment header followed by sorted four-character PCI Device IDs. The generator validates each token and rejects an empty or invalid source list.

The audit mode reads only the files that exist in the selected directory. It reports:

- Device IDs present in NVIDIA's document but missing from the `.ids` file;
- IDs in the `.ids` file that are not present in the corresponding document;
- duplicate IDs;
- malformed tokens.

The audit never edits the checked file. A missing branch file is optional and does not itself make the audit fail, provided at least one target NVIDIA `.ids` file exists.

## 6. Configuration loading and validation

`config.py` loads the three YAML files and exposes the runtime values to the other modules. It validates the required fields and converts `fallback_branches` to a tuple for internal use.

The current configuration does not include the old multi-distribution registry or separate architecture pattern database. This branch is configured for Manjaro.

## 7. Changing policy safely

Before changing either threshold, identify which behaviour is intended:

- Change `min_supported_legacy_branch` only when changing the Assistant's own legacy recommendation handling.
- Change `min_official_branch` only when the Manjaro package set changes.
- Change `fallback_method` and its templates when the desired handling for branches below the Manjaro minimum changes.
- Change `instructions.yaml` only when the actual package naming or installation command changes.

Do not raise or lower one threshold merely to imitate the other. They describe different layers of the system.

## 8. Related documents

- [README](../README.md) — command-line reference and project overview.
- [Architecture](Architecture.md) — how device classification and MHWD integration work.
- [Building](Building.md) — how the five documents are obtained, validated and packaged.
- [Defense](Defense.md) — the module-flavour safety rule and data-source limitations.
