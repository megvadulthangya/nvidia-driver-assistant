# Recommendation safeguards and data-source boundaries

This document explains how the Manjaro-targeted fork combines NVIDIA's JSON database and NVIDIA's own supported-device HTML documents, and what the resulting safeguards do—and do not—guarantee.

The central rule is straightforward: **a GPU classified as legacy 580 or older must not be assigned the open NVIDIA kernel module.** The Assistant enforces that rule in its device-classification code before it uses the ordinary JSON feature fallback.

## 1. Why the safeguard exists

The `supported-gpus.json` database includes feature flags used to distinguish the kernel-module flavours. A `kernelopen` flag is not, by itself, sufficient evidence that an older legacy GPU can use the open kernel module.

The fork therefore applies an explicit legacy rule: if a device has a legacy branch of 580 or lower, its module hint is forced to `proprietary_required`, even when the JSON record contains `kernelopen`.

The rule covers legacy 580, 470, 390 and 340 devices. It is not limited to a particular model such as the GTX 750 Ti.

## 2. The inputs are not interchangeable

The program consumes two groups of upstream NVIDIA data.

### 2.1 `supported-gpus.json`

This JSON file is extracted from the latest NVIDIA `nvidia-driver-assistant` DEB during the package build. It supplies GPU names, PCI identifiers, optional subsystem identifiers, feature flags and the `legacybranch` field.

When a JSON record explicitly contains `legacybranch`, the Assistant retains it as the primary legacy classification. The HTML parser does not silently replace a conflicting JSON branch. A disagreement is logged as a warning.

### 2.2 NVIDIA `supportedchips.html` documents

The five HTML documents have separate roles:

| Document | Use in recommendation / MHWD logic |
|---|---|
| Latest `supportedchips.html` | Provides a Device ID-to-legacy/current map. It can fill in a legacy branch when JSON has no `legacybranch`; it is also the source for the per-device `--mhwd-branch` query. |
| `supportedchips580.html` | Provides the 580 Current set used by the special 580 + latest-6xx mixed-GPU compatibility check. |
| `supportedchips470.html` | Provides the 470xx list for MHWD ID generation and audit. |
| `supportedchips390.html` | Provides the 390xx list for MHWD ID generation and audit. |
| `supportedchips340.html` | Provides the 340xx list for MHWD ID generation and audit. |

The 470, 390 and 340 documents are not used as an independent override of a conflicting JSON legacy branch. Their direct operational role is generating and auditing the respective MHWD ID lists.

## 3. Device classification and module-flavour rule

`Device` in `device.py` applies the following sequence:

1. Normalize the detected PCI Device ID.
2. Retain the JSON `legacybranch` value if one is present.
3. If JSON has no legacy branch, consult the latest supportedchips map. If the device appears under a numeric legacy section, use that branch as the missing legacy classification.
4. If both sources provide a value but disagree, log the disagreement and keep the JSON legacy branch.
5. Determine whether the device is in the latest document's `Current` list with no JSON legacy branch (`supports_latest_6xx`).
6. Independently determine whether the device is in the `Current` list of `supportedchips580.html` (`supports_580`).
7. Resolve its kernel-module hint.

The module-flavour rule is:

- Any legacy branch up to and including 580 is forced to `proprietary_required`.
- A device listed in the latest 6xx `Current` list, with no legacy assignment, is treated as requiring the open kernel module.
- Other devices use the relevant feature flags from `supported-gpus.json` as the fallback.

This is a targeted safeguard, not a claim that the entire recommendation is independent of JSON. JSON remains the primary source for an explicit legacy assignment and remains a fallback source for devices not conclusively classified as latest Current by the NVIDIA document.

## 4. Multi-GPU decisions

The module flavour is computed from all detected NVIDIA GPUs. The Assistant does not simply choose the flavour of one arbitrary device.

### 4.1 Legacy 580 plus latest 6xx

This combination receives a dedicated common-driver check:

- Identify the legacy-580 GPU(s) and the latest-6xx Current GPU(s).
- Check every detected GPU against the Current list in `supportedchips580.html`.
- If every GPU is in that list, select branch 580 with the closed module.
- If at least one GPU is absent from the 580 Current list, the complete system cannot use a common 580 driver. The Assistant prioritises the latest 6xx driver for the newer GPU(s) and marks the legacy-580 device(s) as incompatible with that choice.

The 580 document is used for this explicit 580 compatibility decision only. It is not used to infer support for 470, 390 or 340.

### 4.2 Other mixed configurations

The general recommendation logic identifies legacy devices that fall below the Assistant's common legacy threshold. The CLI then reconciles them with the Manjaro policy:

- Legacy branches at or above the Manjaro repository minimum (currently 390) can be merged into the selected repository-supported legacy branch.
- Branches below the Manjaro repository minimum follow the configured fallback path.
- When a newer open-capable device is prioritised over an incompatible older device, the CLI reports that the older device will not function with the selected driver.

A successful simulated result does not prove that every combination of physical GPUs, kernels and MHWD profiles is supported.

## 5. Why the `.ids` data is separate

MHWD uses PCI Device ID lists to determine which profiles match the detected hardware. The Assistant generates those lists from NVIDIA's supportedchips documents, not from `supported-gpus.json`.

This provides a useful separation:

- JSON is used by the Assistant's detection and recommendation path.
- NVIDIA supportedchips data is used to build the MHWD ID lists.
- MHWD consumes the installed `.ids` files when matching profiles.

The generated IDs are four-character base PCI Device IDs. When an older NVIDIA HTML cell contains a base Device ID followed by subsystem values, the parser uses only the first ID token.

The `mhwd-nvidia*` split package names remain part of the packaging interface because the MHWD database expects those packages to provide the ID files. The generation implementation has moved into `nvidia-driver-assistant --generate-ids`; the split package interface has not been removed.

## 6. Manjaro package availability is a separate policy

The Assistant can process the 340xx branch. This includes:

- branch recognition through NVIDIA's latest supportedchips mapping where the device is listed;
- the legacy closed-module rule;
- the 340 supportedchips parser;
- `--mhwd-branch` classification;
- `--generate-ids 340`;
- `--check-ids` validation of an existing `nvidia-340xx.ids` file.

The current Manjaro policy in `distro.yaml` sets `min_official_branch: 390`. Therefore 340xx is not currently available from the Manjaro repositories. The Assistant follows the configured fallback path for a 340xx device, and `--mhwd-config` does not claim that a missing Manjaro 340xx profile can be installed.

This distinction is intentional. The software's ability to understand a driver branch is not the same thing as the distribution's current package availability.

## 7. What these safeguards do not guarantee

The code should not be described as completely immune to changes or manipulation of NVIDIA's JSON data. The actual guarantees are narrower:

- An explicit JSON legacy branch remains the primary legacy classification when present.
- The latest NVIDIA supportedchips document can fill in a missing legacy branch.
- A conflict between an explicit JSON branch and the latest HTML classification is logged; the JSON value is retained.
- Legacy branches up to 580 are forced to the closed kernel module.
- Latest 6xx Current membership is used as the current-generation indicator.
- The 580 Current list is used for the specific 580/6xx mixed-GPU compatibility decision.

The recommendation can still be affected by changes to NVIDIA's published data, parser assumptions, PCI Device ID matching, the Manjaro package policy or the available MHWD profiles. The package build validates the five downloaded documents to detect format changes and missing data early, but successful parsing alone does not prove the correctness of every vendor classification.

## 8. Validation and testing

The build validates all five source documents with `validate_all_documents()`. The test suite includes:

- latest/current and legacy section parsing;
- 580 Current-only parsing;
- 470/390/340 legacy table parsing and boundary detection;
- base Device ID extraction when subsystem IDs are present;
- MHWD ID generation for each supported branch;
- read-only `.ids` auditing;
- GPU simulation and recommendation tests.

Run the parser and ID tests with:

```shell
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_supported_chips_parser.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_mhwd_ids.py' -v
```

Then run the original and extended suites as described in [Building](Building.md).

## 9. Further reading

- [Architecture](Architecture.md) — recommendation flow and MHWD integration.
- [Configuration](Configuration.md) — the policy thresholds and five NVIDIA documents.
- [Building](Building.md) — retrieval, validation, packaging and test procedures.
