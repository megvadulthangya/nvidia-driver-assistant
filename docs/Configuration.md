# Configuration Guide for Distribution Maintainers

All driver policy, legacy branch thresholds, and distro-specific behavior
are driven by YAML configuration files in `nvidia_driver_assistant/data/`.
This means most customizations can be done by editing YAML — no Python code
changes required.

## Per-distro legacy branch policy (`data/distro.yaml`)

Every supported distribution has its own entry in the `distro_registry`
section with the following configurable fields:

| Field | Type | Description |
|---|---|---|
| `min_official_branch` | `int` or `null` | Minimum legacy branch available in the distro's official repositories. GPUs requiring a branch >= this value are served from the repos. Set to `null` if no legacy branches exist in the repos. |
| `fallback_method` | `"aur"` or `"error"` | What happens when a GPU's branch is below `min_official_branch`: `"aur"` directs users to AUR packages; `"error"` prints an unsupported-hardware message. |
| `fallback_branches` | `list[int]` | Branches that are supported by the tool but NOT in the official repos (e.g. Arch's 580 branch is AUR-only). |
| `nouveau_hint_below` | `int` or `null` | GPUs on a branch below this threshold get a hint about the open-source Nouveau driver. Set to `null` to disable. |
| `fallback_message` | `str` or `null` | Header text printed before fallback package listing. |
| `fallback_device_header` | `str` or `null` | Header printed before the per-device listing. Supports `{min_branch}` placeholder. |
| `fallback_package_template` | `str` or `null` | Package name pattern for the main fallback package (typically -dkms). Use `{branch}` as placeholder (e.g. `"nvidia-{branch}xx-dkms"`). |
| `fallback_utils_template` | `str` or `null` | Package name pattern for the utils fallback package. Use `{branch}` as placeholder (e.g. `"nvidia-{branch}xx-utils"`). |
| `repo_available_note` | `str` or `null` | Note printed when legacy branches are still available in official repos. |
| `kernel_substitution` | `bool` | Whether install commands use a KERNEL placeholder (Manjaro). |
| `branch_suffix` | `str` | Suffix appended to branch numbers in install commands (e.g. `"xx"`). |

### Example — adding legacy branch support to a Fedora fork:

```yaml
# Before (default): all legacy GPUs → "unsupported, upgrade hardware"
fedora:
  min_official_branch: null
  fallback_method: "error"

# After: 470+ available in repo, below 470 → error + Nouveau hint
fedora:
  min_official_branch: 470
  fallback_method: "error"
  nouveau_hint_below: 340
```

No Python code changes needed — the tool will automatically serve the 470+
branches from the repo and show the error fallback only for GPUs below 470.

### Current distribution-specific configurations

Based on the current `data/distro.yaml`:

**Arch Linux:**
- `min_official_branch: null` — No legacy branches in official repositories
- `fallback_method: "aur"` — All legacy GPUs directed to AUR packages
- `fallback_branches: [580]` — The 580 branch is AUR-only
- Legacy GPUs are directed to `nvidia-{branch}xx-dkms` / `nvidia-{branch}xx-utils` packages in the AUR

**Manjaro:**
- `min_official_branch: 390` — Legacy branches >= 390 available in official repositories
- `fallback_method: "aur"` — GPUs below 390 directed to AUR packages
- `fallback_branches: []` — No AUR-only branches
- GPUs with legacy branch >= 390 are served from official repos; GPUs below 390 are directed to AUR packages

**All other supported distributions:**
- `min_official_branch: null` — No legacy branches in official repositories
- `fallback_method: "error"` — Unsupported legacy GPUs produce an error message advising hardware upgrade

## Global overrides (`data/overrides.yaml`)

| Variable | Description |
|---|---|
| `min_supported_legacy_branch` | Below this branch, a GPU is classified as unsupported (currently `580`). |
| `DISTRO_NON_LEGACY_DEFAULT_BRANCH` | Default branch override for non-legacy devices. |
| `DISTRO_580_LEGACY_OVERRIDE_BRANCH` | Override branch for 580 legacy devices. |
| `ENABLE_LEGACY_OPENKERNEL_RESTRICTION` | Whether to restrict open kernel modules for legacy GPUs. |
| `ENABLE_ARCHITECTURE_CHECK` | Enable/disable GPU architecture validation. |
| `AUTO_FALLBACK` | Auto-fallback when no exact driver match is found. |

## Adding a new distribution

To add support for a new Linux distribution:

1. Add an entry in `data/distro.yaml` under `distro_registry` with the fields above
2. Add the distro alias to the `supported_distros` list in the same file
3. Add installation instruction templates in `data/instructions.yaml`
