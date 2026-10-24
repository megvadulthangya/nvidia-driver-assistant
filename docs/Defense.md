# Why This Fork Exists

## The defense against `supported-gpus.json` manipulation

This document explains **why** `nvidia-driver-assistant` in this fork
contains logic that looks redundant at first glance — and why removing
any of it would re-open the attack surface that a November 2025 NVIDIA
release exposed.

The audience is:

- the **future maintainer** of this fork, who will look at
  `_parse_features()` and wonder whether steps 0–4 can be collapsed
  into "just trust the JSON";
- the **Manjaro packagers** who currently patch the JSON by hand and
  may want to know how the fork avoids that;
- anyone reviewing this project and asking "why so many layers for a
  driver-selection tool?"

The short answer: **the JSON is untrusted input**. The tool does not
use it to decide whether a legacy GPU can run open kernel modules,
because NVIDIA has published a JSON that says the opposite of what
the hardware can do.

---

## 1. The November 2025 regression

### What happened

In November 2025, NVIDIA released `nvidia-driver-assistant` version
`0.23.44.01-1` (2025-11-25), followed by `0.23.48.01-1` (2025-12-17).
Both versions shipped a `supported-gpus.json` in which every legacy
580 GPU — Maxwell (GTX 750 Ti, GTX 980 Ti), Pascal (GTX 1080 Ti,
GTX 1060), Volta (TITAN V, Quadro GV100), and dozens of others — was
given both a legacy branch (`580.xx`) and the `kernelopen` feature
flag.

The JSON for `0x1380` (GTX 750 Ti) changed from:

```json
{"devid":"0x1380","name":"NVIDIA GeForce GTX 750 Ti",
 "features":["hdmi4k","vdpaufeaturesetE"]}
```

to:

```json
{"devid":"0x1380","name":"NVIDIA GeForce GTX 750 Ti",
 "legacybranch":"580.xx","features":["kernelopen"]}
```

The `kernelopen` feature flag tells the tool that the GPU can run the
open kernel module. For Maxwell, Pascal, and Volta hardware this is
not the case: the open module requires GSP firmware and an
architecture that these GPUs were not designed for. Loading
`nvidia-open-580` on a GTX 750 Ti does not produce a working driver.

The practical effect: users with a legacy 580 GPU who ran
`nvidia-driver-assistant` (or `mhwd`, which consumes it on Manjaro)
were directed to install the open driver.

The change was documented by Philip Müller (Manjaro team) on the
NVIDIA developer forum in January 2026, with verbose output from both
the old and the new version. His report shows that `0.22.105.08-1`
returned `closed` for the GTX 750 Ti, and `0.23.48.01-1` returned
`open` for the same hardware.

### Where the bug is today

As of `nvidia-driver-assistant` version `0.62.71.10-1` (2026-09-24,
the most recent release at the time of writing), the bug is still
present.

**In the JSON**: the file still contains the `kernelopen` flag on
every legacy 580 GPU:

```json
{"devid":"0x1380","name":"NVIDIA GeForce GTX 750 Ti",
 "legacybranch":"580.xx","features":["kernelopen"]}
{"devid":"0x1B06","name":"NVIDIA GeForce GTX 1080 Ti",
 "legacybranch":"580.xx","features":["kernelopen"]}
{"devid":"0x1D81","name":"NVIDIA TITAN V",
 "legacybranch":"580.xx","features":["kernelopen"]}
```

**In the code**: the module-flavor decision still trusts the
`kernelopen` flag. `Device._parse_features()` sets
`driver_hint = "open_required"` when `kernelopen` is present and the
device has no conflicting flag. The legacy-branch detection function
(`check_legacy_devices()`) is present — it selects a branch, and
`main()` sets `branch_locked` from it — but it does **not** override
the module flavor. The GTX 750 Ti on a stock `0.62.71.10` still
resolves to `nvidia-open-580`.

The fix that would make this work — a hardcoded rule that forces
`closed` for every legacy branch `<= 580` — is not in the upstream
code. It is in this fork.

---

## 2. The core principle: JSON is untrusted input

This fork's design rule is:

> **Physics first, vendor metadata last.**

The physical capabilities of a GPU are determined by:

- its **architecture** (Maxwell, Pascal, Volta, Turing, Ampere, Ada,
  Blackwell, …), which decides whether the open kernel module can
  bind;
- its **legacy branch** (71.86, 96.43, 173.14, 304, 340, 390, 470,
  580), which decides which closed driver series is the newest one
  that still supports it.

Both are **hardcoded** in this fork (see `architecture.yaml`,
`overrides.yaml`). The JSON is consulted only as a **last resort**,
after the hardcoded rules have had a chance to fire.

The result: if the JSON is manipulated, the tool still returns the
correct closed-kernel-module recommendation for every legacy ≤ 580
GPU. If the JSON is correct, the tool returns the same answer. **The
JSON cannot change the outcome for the devices that matter.**

---

## 3. The defense layers

The decision logic lives in `nvidia_driver_assistant/device.py`,
method `_parse_features()`. It runs in this order:

### Layer 1 (primary, hardcoded): legacy restriction + architecture check

This is the **original** defense, present in this fork from the
beginning. It does not depend on `supported-gpus.json` for the
decision it makes, and it is the layer that fixes the November 2025
regression.

```python
# 3. Legacy branch openkernel restriction
if self.original_legacy_branch and ENABLE_LEGACY_OPENKERNEL_RESTRICTION:
    legacy_major_int = self.legacy_int
    if legacy_major_int >= 0 and legacy_major_int <= 580:
        self.driver_hint = proprietary_required
        return

# 4. Architecture-based check
if ENABLE_ARCHITECTURE_CHECK:
    if self.architecture in OPEN_CAPABLE_ARCHS:
        if open_supported in flags:
            self.driver_hint = default
        else:
            self.driver_hint = proprietary_required
    else:
        self.driver_hint = proprietary_required
    return
```

**Step 3** fires if the JSON says the GPU has a `legacybranch` of
`≤ 580`. The branch itself is taken from the JSON — but note that in
the November regression the branch was *correct* (`"580.xx"`). The
regression was in the `features` list, which step 3 never reads: it
returns immediately.

**Step 4** fires if step 3 did not. It checks the GPU's architecture
against `OPEN_CAPABLE_ARCHS` (Turing, Ampere, Ada, Blackwell,
`modern-generic`) and `OPEN_UNSUPPORTED_ARCHS` (everything else,
including `unknown`). The architecture is derived from the GPU's
**name** (see `architecture.yaml` patterns), which is harder to
manipulate accidentally than a feature flag.

**Result**: a legacy 580 GPU is forced to `proprietary_required` by
step 3, regardless of what the JSON says in `features`. A modern GPU
is evaluated by step 4, which requires the JSON to *also* flag
`kernelopen` — but the architecture gate has already filtered out
every GPU that cannot physically run it.

### Layer 1b (secondary safety net in `main()`)

In addition to the two `_parse_features()` steps, `cli.py` contains a
final safety net after the recommendation is computed:

```python
if driver == "open" and branch_locked:
    effective_branch = _safe_branch_int(str(branch_locked))
    if effective_branch >= 0 and effective_branch <= 580:
        driver = "closed"
```

If the branch has been locked to a value `<= 580` (by
`check_legacy_devices()` or by the user's `--branch`), and the
computed flavor is still `open`, this flips it to `closed`. It is
redundant with step 3 for the November regression, but it catches
other code paths (for example, when the legacy branch is set by
`DISTRO_580_LEGACY_OVERRIDE_BRANCH` in a way that bypasses step 3).

### Layer 2 (defense-in-depth): `supportedchips.html` parser

This layer was added later, after Layer 1, as additional protection
against a **different** class of manipulation: the JSON setting
`legacybranch: null` on a device that is actually legacy. Step 3
cannot fire in that case (there is no legacy branch to compare), and
step 4 would only fire if the device name still identifies the
correct architecture. If the JSON manipulates both `legacybranch`
and `name`, Layer 1 alone would produce the wrong answer.

`nvidia_driver_assistant/supported_chips.py` parses NVIDIA's own
`supportedchips.html` (the authoritative list published on
`download.nvidia.com`) and builds a `{devid → branch}` map. This map
is consulted at step 0:

```python
# 0. supportedchips.html authoritative override (if available)
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

The parser currently extracts over 1100 unique device IDs from the
published `supportedchips.html`, with spot-check coverage:

| Device ID | GPU              | Expected branch |
|-----------|------------------|-----------------|
| `1380`    | GTX 750 Ti       | 580             |
| `1b06`    | GTX 1080 Ti      | 580             |
| `1d81`    | TITAN V          | 580             |
| `0fc6`    | GTX 650          | 470             |
| `06c0`    | GTX 480          | 390             |
| `00c2`    | GeForce 6800 LE  | 304             |
| `2783`    | RTX 4070 SUPER   | current         |
| `2d18`    | RTX 5070 Laptop  | current         |

**Layer 2 is optional by design.** If `supportedchips.html` is
missing — because the packaging step was interrupted, because a
downstream user renamed the file, or because the parser failed to
parse a future HTML layout — `SUPPORTED_CHIPS` is `None`, step 0 is
skipped, and the tool falls back to Layer 1. **The application still
runs.** For the November regression, Layer 1 is sufficient: step 3
still catches the legacy branch, and the output is still `closed`.
For an attack that manipulates both `legacybranch` and `name`, Layer
2 is required.

This asymmetry is intentional. Layer 2 is not load-bearing for the
primary attack; it is a defense-in-depth addition that closes a
narrower gap. Removing it (or its input) does not break the tool. It
does, however, remove the only defense against a combined
name-and-branch manipulation.

### Layer 3 (independent): mhwd config selection

On Manjaro, the fork integrates with `mhwd` via the `--mhwd-config`
flag. `mhwd` calls this flag **before** it decides which config to
install:

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
    }
}
```

`--mhwd-config` returns a **config name** (`video-nvidia-580xx`,
`video-nvidia`, `video-nvidia-340xx`, …), not a kernel module flavor.
The config name is derived from the branch, which is derived from the
hardcoded rules above. The device-to-config matching itself is
handled by `mhwd` using `nvidia-*.ids` files, which are **generated
from `README.txt` + `nv-kernel-amd64.o_binary`** in the
`nvidia-*xx-utils` PKGBUILD — not from `supported-gpus.json`.

This layer is independent of the JSON in two ways:

1. The config name is computed from the branch, which comes from the
   hardcoded layers.
2. The device-to-config binding is `.ids`-based, not JSON-based.

The kernel module flavor (`open` vs `closed`) is decided **inside**
the config, by the `MHWDCONFIG` `DEPKMOD` variable. For the 580 and
latest configs in the `mhwd-db` fork, `DEPKMOD` is set by a second
call to `nvidia-driver-assistant --mhwd`, which returns `open` or
`closed` based on the same hardcoded rules:

```bash
DEPKMOD="nvidia-580xx"
[[ "$(nvidia-recommended-driver)" == "open" ]] && DEPKMOD="nvidia-580xx-open"
```

The `.ids` files are not involved in this decision.

**Result:** the entire mhwd integration chain is independent of the
`supported-gpus.json` file. The JSON only influences the second
`--mhwd` call, which is protected by layers 1 and 2.

---

## 4. Why it cannot be "simplified"

A future maintainer may look at `_parse_features()` and ask: "Why
not just read the JSON? It has everything we need." Here is what
happens if each layer is removed.

### Removing step 3 (legacy restriction)

The November regression returns. `0x1380` with
`legacybranch: "580.xx"`, `features: ["kernelopen"]` evaluates to
`open`. The GPU is directed to a driver that does not bind to it.

### Removing step 4 (architecture check)

A JSON edit that sets `legacybranch: null` on a Maxwell GPU (or
removes the field) causes step 3 to not fire. Without step 4, the
tool would then read the `kernelopen` flag and return `open`.

### Removing the `main()` safety net

The safety net is redundant with step 3 for the November regression,
but it catches cases where the branch is set by an override
(`DISTRO_580_LEGACY_OVERRIDE_BRANCH`) without the corresponding
`_parse_features()` step. Removing it removes the second line of
defense against a branch/flavor mismatch.

### Removing step 0 (`supportedchips.html`)

The tool still runs, and Layer 1 still catches the November
regression. But the fork loses its defense against a combined
manipulation: `legacybranch` set to `null` **and** `name` changed to
something that matches an open-capable architecture pattern. Step 4
would then pass, step 5 would read the `kernelopen` flag, and the
output would be `open` for hardware that cannot run it. Step 0
catches this because the device ID (from the PCI modalias, not from
the JSON) still maps to a legacy branch in `supportedchips.html`.

### Removing the mhwd integration (`--mhwd-config`)

`mhwd` falls back to its priority-based config selection. On a system
with multiple NVIDIA GPUs, or on a system where the JSON has been
manipulated to suggest `open`, `mhwd` would install the wrong config.
The `DEPKMOD` in the selected config would then call
`nvidia-driver-assistant --mhwd`, which is protected by layers 1 and
2 — but if the *config itself* was wrong (e.g. `video-nvidia` selected
for a 750 Ti instead of `video-nvidia-580xx`), the wrong package set
is installed regardless of what `--mhwd` returns.

Each layer defends against a **different attack vector**. None is
redundant. This is why this document exists: without it, the next
maintainer may remove "the redundant checks" and the fork will be
vulnerable again.

---

## 5. Comparison with other approaches

There are three active responses to the November regression.

### NVIDIA upstream (`0.62.71.10`)

The JSON still contains `kernelopen` on every legacy 580 GPU. The
module-flavor decision still trusts the flag. The
`check_legacy_devices()` function selects a branch, and `main()` sets
`branch_locked` from it, but the flavor is not overridden. The GTX
750 Ti resolves to `nvidia-open-580`.

### Manjaro PKGBUILD (`0.23.48.01-7`)

Manjaro's current `nvidia-driver-assistant` PKGBUILD is at
`pkgver=0.23.48.01`, `pkgrel=7`. It applies three patches:

- `manjaro.patch` — adds Manjaro/Arch distribution support;
- `fix-db.patch` — rewrites the JSON entries for legacy 580 GPUs
  from `"features": ["kernelopen"]` back to
  `"features": ["hdmi4k", "vdpaufeaturesetE"]`;
- `change-db-to-580xx.patch` — path fix.

`fix-db.patch` **works**. It corrects the JSON. The result is that
the tool, running against the patched JSON, produces `closed` for the
GTX 750 Ti. This is a valid response.

The trade-off is maintenance: `fix-db.patch` is a diff against a
specific upstream JSON file. Every time NVIDIA ships a new JSON
(every release), the patch must be rebased. The `pkgrel` counter
tracks the number of rebases: it is currently at 7. If a future
upstream release re-introduces the bug (or introduces a new variant),
the counter will grow again.

### This fork

The Python code in this fork is based on upstream `0.51`. Since then,
upstream has moved on (to `0.62.71.10` at the time of writing), but
the fork has not re-merged those changes. The hardcoded defense logic
in `_parse_features()` and the CLI plumbing are the fork's own, and
they do not need anything the newer upstream versions added.

The `supported-gpus.json` and the NVIDIA EULA, on the other hand, are
taken from the latest official `nvidia-driver-assistant` DEB published
in the CUDA repository for Ubuntu 24.04
(`developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64`).
This is why the PKGBUILD version string contains the latest upstream
version (currently `0.62.71.10`), even though the Python code in the
package is based on `0.51`: the version string tracks the DEB from
which the JSON was taken, not the code.

The fork does not patch the JSON. It uses the JSON as one input
among many, and it does not use the JSON for the decision that the
November regression got wrong. The hardcoded rules in
`overrides.yaml` and `architecture.yaml` produce the same output
regardless of what the JSON says.

### Maintenance cost comparison

| Approach | What has to change when NVIDIA ships a new JSON |
|---|---|
| **NVIDIA upstream** | Nothing. The bug stays. |
| **Manjaro PKGBUILD** | Rebase `fix-db.patch` against the new JSON. `pkgrel` counter grows. |
| **This fork** | Nothing. The hardcoded rules do not read the JSON for the legacy-branch decision. |

The maintenance workflow for this fork is:

1. A new `nvidia-driver-assistant_X.Y.Z.deb` appears on
   `developer.nvidia.com` (in the Ubuntu 24.04 CUDA repository).
2. The fork's package directory is replaced with a fresh checkout
   (or the old package directory is removed).
3. The GitHub Actions builder runs. The PKGBUILD's `pkgver()`
   function detects the latest DEB automatically by scraping the
   NVIDIA repository directory listing
   (`_latest_deb_info()` in the PKGBUILD). It then:
   - downloads the new DEB and extracts `supported-gpus.json` and
     the NVIDIA EULA from it;
   - downloads `supportedchips.html` from the configured New Feature
     Branch version;
   - packages the fork's Python code (based on `0.51`) together with
     the new JSON.
4. The new package is published.

There is no version string to edit manually, no patch to rebase, and
no JSON diff to review. The fork's Python code does not change
between upstream releases; only the JSON input (downloaded
automatically) changes.

This is not a claim that the fork is universally "better". It is a
claim that the fork is **architecturally different**: it treats the
JSON as one input among many, not as the authoritative source of
truth for a decision that the JSON has historically gotten wrong.

---

## 6. How to contribute

### The most valuable contribution: open-kernel-capable hardware testing

This fork's author does not have access to Turing, Ampere, Ada, or
Blackwell hardware. The `--mhwd` → `open` path is verified through:

- `--simulate-gpu` with the simulated GPUs in `database.py`;
- the `supported-gpus.json` logic (which is the *last* layer of the
  defense, but still the first one that runs for modern GPUs);
- the CI test suite (`tests/` and `moretests/`).

None of these replaces real hardware. In particular, the fork has
**no way to verify** that:

- a real Turing or newer GPU is correctly classified as open-capable
  by step 4;
- the `--mhwd` output matches what `mhwd` actually installs on real
  Manjaro hardware;
- the `DEPKMOD` substitution in the `MHWDCONFIG` produces a working
  driver install.

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
4. Does the driver installation actually work (kernel module loads,
   `nvidia-smi` reports the GPU, OpenGL uses the NVIDIA renderer)?

Open an issue on GitHub or post in the Manjaro forum topic. Negative
results (the fork gave the wrong answer) are **more valuable** than
positive ones — they are the data points that cannot be generated
without real hardware.

### Other ways to contribute

- **Legacy GPU testing** (Maxwell, Pascal, Volta): confirm that
  `nvidia-driver-assistant --mhwd` returns `closed` for your GPU even
  when the JSON has the `kernelopen` flag. This is the November
  regression scenario, and it is the easiest to test: use the
  `supported-gpus.json` from a version that has the regression (e.g.
  `0.62.71.10`), and verify the fork still returns `closed`.
- **Manjaro packagers**: see `docs/Building.md` for how to build the
  patched `mhwd` and the `mhwd-db` fork locally, and
  `docs/Architecture.md` for how the integration works end to end.
- **Upstream contributors**: the `supportedchips.html` parser is
  self-contained. It can be submitted as a small PR to upstream
  `nvidia-driver-assistant` without touching anything else. See
  `docs/Building.md` for the procedure.

---

## 7. See also

- `docs/Architecture.md` — the full mhwd → `--mhwd-config` →
  `MHWDCONFIG` → `nvidia-recommended-driver` → `DEPKMOD` → `pacman`
  chain.
- `docs/Configuration.md` — the YAML configuration files, including
  `ENABLE_LEGACY_OPENKERNEL_RESTRICTION` and
  `ENABLE_ARCHITECTURE_CHECK`.
- `docs/Building.md` — how to build and test the fork, the patched
  `mhwd`, and the `mhwd-db` fork.
- The original NVIDIA developer forum thread (Philip Müller,
  January 2026): *"Nvidia-driver-assistant 0.23.44.01-1 and later
  suggests wrong drivers"*.
- The Manjaro forum topic (May 2026): *"Updated
  nvidia-driver-assistant (v51 rebase + Manjaro legacy support)"*.
```

---
