# Recommendation safeguards and data-source boundaries

This document explains the safeguards used by the Manjaro fork when NVIDIA vendor data contains conflicting or incomplete information. It describes what the current code does and, just as importantly, what it does not guarantee.

## 1. The problem addressed

The NVIDIA `supported-gpus.json` database has previously marked legacy 580 GPUs as `kernelopen`. That feature flag can suggest the open kernel module even though Maxwell, Pascal and Volta devices in the affected legacy group cannot use it.

This fork therefore does not let a `kernelopen` flag override an explicit legacy-branch restriction. The rule is implemented in `Device._parse_features()` and is independent of the feature list in JSON.

## 2. Current sources of information

The tool uses two vendor data sources with different responsibilities.

### `supported-gpus.json`

This is extracted from NVIDIA's published DEB during package build. It provides device names, feature flags and the optional `legacybranch` field.

When the JSON already has a `legacybranch`, the current code retains it as the primary legacy classification.

### NVIDIA `supportedchips.html`

The latest New Feature Branch document provides a PCI Device ID to branch mapping. It is used to supplement a missing JSON legacy branch and to answer the per-device `--mhwd-branch` query.

The parser also loads separate 580, 470, 390 and 340 documents. Their per-branch Device ID lists are used for MHWD `.ids` generation. The 580 `Current` set has an additional role in mixed-GPU compatibility checking.

These documents are independent vendor inputs; they are not generated from `supported-gpus.json`.

## 3. The legacy kernel-module restriction

The most important rule is:

> A device with a detected legacy branch of 580 or lower requires the proprietary (`closed`) kernel module.

The code checks the legacy branch before relying on JSON feature flags. Therefore, a contradictory `kernelopen` flag cannot turn an explicitly identified 340, 390, 470 or 580 legacy GPU into an open-module recommendation.

The latest 6xx `Current` list is handled separately. A device listed there and having no JSON legacy branch is classified as a current GPU and uses the open kernel module. Devices that do not match either of those rules fall back to the supported module-feature flags in JSON.

This is a targeted safety rule for the legacy/open-module conflict. It should not be described as a universal guarantee that every possible incorrect JSON field is detected or corrected.

## 4. What happens when JSON and supportedchips disagree

The current `Device` implementation follows these rules:

1. If JSON has a `legacybranch`, that value remains the primary branch classification.
2. If JSON has no `legacybranch`, the latest supportedchips map can fill in a legacy branch for the PCI Device ID.
3. If both sources provide a classification but disagree, the tool logs a warning and retains the JSON legacy branch.
4. The separate latest `Current` membership is used for the current 6xx path only when the device has no JSON legacy branch.

This is a deliberate source-precedence decision. The parser is a supplement for missing legacy data and a separate source for MHWD ID lists; it is not currently a blanket override for every JSON value.

Consequently, the tool does **not** claim to be immune to every incorrect or deliberately manipulated JSON entry. For example, an incorrect but non-empty JSON legacy branch is retained after a discrepancy warning. Maintainers should review such warnings and update the source data or policy deliberately rather than assume the tool silently repairs the classification.

## 5. Mixed-GPU safeguard for 580 and latest 6xx

A legacy 580 GPU and a latest 6xx GPU do not automatically share a driver merely because both are present in the same system.

The mixed-GPU resolver checks every detected NVIDIA device against the separate 580 `Current` list:

- If every detected device is present in that list, branch 580 with the closed module is a common option.
- If any detected device is absent, the system has no common 580 driver according to that document. The tool prioritises the latest 6xx driver for the modern GPU and sends the incompatible legacy 580 device(s) through the unsupported-device handling.

This avoids assuming that a device supported by the latest branch is necessarily supported by 580.

## 6. MHWD ID lists are a separate data path

MHWD uses PCI ID lists from files under `/var/lib/mhwd/ids/pci/` to decide which hardware matches a config. The maintained `.ids` files are now generated from NVIDIA's supportedchips documentation:

```shell
nvidia-driver-assistant --generate-ids <branch>
```

This generation path does not read `supported-gpus.json`. It parses the document for the selected NVIDIA driver branch and writes the four-digit PCI Device IDs used by MHWD. The generated lists are sorted and de-duplicated, and subsystem IDs are intentionally ignored.

This means a JSON feature-flag change does not itself change the contents of an `.ids` file. Conversely, a correct `.ids` file only controls MHWD hardware/config matching; it does not decide the open/closed module flavour.

`--check-ids` provides a read-only comparison of installed files with the corresponding NVIDIA documents. It reports differences for review and does not rewrite the files.

## 7. MHWD integration provides two different controls

The two MHWD patches apply the Assistant's data at different points.

### Authority mode

The authority patch uses `--mhwd-config` to obtain the overall recommended NVIDIA config branch. It then requires MHWD to find an available profile for that branch. If the Assistant result is invalid or no matching profile exists, the patch does not silently fall back to a different NVIDIA config selected only by priority.

### Corrective mode

The corrective patch lets MHWD make its normal priority-based choice first. It then calls `--mhwd-branch --mhwd-device-id` for the NVIDIA device and compares the supportedchips branch with the branch encoded in the selected profile. It corrects a mismatch if a matching profile is available. If the branch cannot be determined, the original MHWD selection is retained; if the required corrected profile is absent, the NVIDIA device is skipped rather than assigned a known-wrong branch.

The modes are alternatives. Authority is an overall recommendation path; corrective is a per-device branch-validation path. See [Architecture.md](Architecture.md) for the detailed flow.

## 8. Build-time data validation

The Assistant package build downloads and validates all five supportedchips documents: latest 6xx, 580, 470, 390 and 340. It uses the same parser module that is packaged for runtime. If the HTML cannot be parsed or a required branch list is empty, the build fails.

This catches a changed NVIDIA HTML structure before publishing a package with missing or incomplete MHWD ID data. It cannot guarantee that NVIDIA's source document is itself free of errors, nor that a future document will retain the same format indefinitely.

## 9. What these safeguards do not prove

- They do not prove that every GPU marked `open` in metadata has been tested on physical hardware.
- They do not make an incompatible legacy and modern GPU share a driver.
- They do not create a missing MHWD database profile or install a missing `.ids` package.
- They do not repair stale or incorrect JSON legacy-branch values automatically.
- They do not validate all hybrid graphics combinations without the corresponding hardware and MHWD profiles.
- They do not make the maintainer's additional 340xx/390xx Debian-based driver patch work part of official Manjaro packaging.

The decision logic, vendor-data precedence and MHWD behaviour should be reviewed together whenever one of the NVIDIA source formats, the driver branch set or the MHWD database changes.
