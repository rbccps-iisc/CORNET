# CORNET NS-3 Patch Bundle

This directory contains patches that extend NS-3 and the 5G-LENA NR module with
CORNET-specific schedulers and PDCP instrumentation.

> **Capability registry**: `CAPABILITY_MATRIX.yaml` in this directory is the
> authoritative source of what each patch provides, at what validation level,
> and which experiment domains it applies to. Consult it before deciding which
> patches to apply for a given experiment.

## Compatibility Matrix

| Patch set directory  | NS-3 version | NR version | Status        |
|----------------------|--------------|------------|---------------|
| `v2.4-ns3.38/`       | 3.38         | v2.4       | ✅ Validated  |
| `v4.2-ns3.47/`       | 3.47         | v4.2       | ⏳ Patches rebased — awaiting runtime validation (`make validate-v47`) |

## v2.4-ns3.38 — Patch Descriptions

### `ns3_lte_pdcp.patch`
**Type**: `infrastructure` | Applies to the **NS-3 source directory** (`$NS3_DIR`).

Instruments `LtePdcp` to expose per-PDU timestamps for Age-of-Information (AoI)
measurement. Also threads a CORNET callback into `LteHelper` and `LteNetDevice`
for co-simulation handoff.

**Scope**: Useful for ANY CORNET experiment that measures packet age — not limited
to AoI/EDF scheduler experiments. Also enables the TUN/TAP virtual-port
contract (`cornet_tap_bridge_contract`).

| File modified | Change |
|---|---|
| `src/lte/helper/lte-helper.cc` | CORNET callback registration at UE attach |
| `src/lte/model/lte-net-device.cc` | Forward RX events to CORNET dispatcher |
| `src/lte/model/lte-net-device.h` | Add dispatcher hook declaration |
| `src/lte/model/lte-pdcp.cc` | Timestamp injection + AoI callback |
| `src/lte/model/lte-pdcp.h` | Add AoI callback type and member |

### `originals/nr_edf_scheduler.patch` (DO NOT apply directly — use `nr_schedulers.patch`)
Adds an Earliest-Deadline-First (EDF) MAC scheduler to the NR module. This patch
conflicts with `nr_aoi_mac_scheduler.patch` on `CMakeLists.txt`. Use the combined
`nr_schedulers.patch` instead.

Kept in `originals/` for provenance / archaeology.

### `originals/nr_aoi_mac_scheduler.patch` (DO NOT apply directly — use `nr_schedulers.patch`)
Adds an Age-of-Information (AoI)-aware MAC scheduler to the NR module. Its
`CMakeLists.txt` hunk adds BOTH EDF and AoI entries, conflicting with the
standalone EDF patch. Also contains an absolute-path `scratch/remote_robot_control.cc`
diff from the original developer machine — not a NR module file.

Kept in `originals/` for provenance / archaeology.

### `nr_schedulers.patch` ← **USE THIS ONE**
**Type**: `research-feature` | **Domain**: AoI-measurement, deadline-scheduling |
Applies to the **NR contrib directory** (`$NS3_DIR/contrib/nr`).

Combined, conflict-free patch that registers both the EDF and AoI schedulers.
Generated from the fully-patched CORNET3.0 NR v2.4 working tree.

> **Domain scoping**: This patch is relevant to AoI-measurement and deadline-
> scheduling experiments. For CSI-RS, MIMO, beamforming, or fronthaul
> experiments, this code is **inert** — it will be compiled in but has no effect
> unless `schedulerType=edf` or `schedulerType=aoi` is explicitly set.

`nr_edf_only.patch` and `nr_aoi_only.patch` register each scheduler at a
different `CMakeLists.txt` anchor, so each applies on a clean v2.4 tree and
the two also apply together in either order. AoI still subclasses EDF, so a
build that includes AoI must apply `nr_edf_only.patch` as well (the
`aoi-measurement` profile does that). `nr_schedulers.patch` remains the
combined patch used by the default `full` profile.

The files under `originals/` are not those patches. They still share one
`CMakeLists.txt` context and must not be applied.

| File modified/added | Patch type | Change |
|---|---|---|
| `CMakeLists.txt` | combined | Registers EDF + AoI `.cc`/`.h` files in build |
| `model/nr-mac-scheduler-lcg.h` | EDF | EDF LCG scheduler extension |
| `model/nr-mac-scheduler-ns3.cc` | EDF | EDF scheduler wiring |
| `model/nr-mac-scheduler-ns3.h` | EDF | EDF scheduler declaration |
| `model/nr-mac-scheduler-ofdma-edf.cc` | EDF | New: EDF OFDMA scheduler implementation |
| `model/nr-mac-scheduler-ofdma-edf.h` | EDF | New: EDF OFDMA scheduler header |
| `model/nr-mac-scheduler-ue-info-edf.cc` | EDF | New: EDF UE info implementation |
| `model/nr-mac-scheduler-ue-info-edf.h` | EDF | New: EDF UE info header |
| `model/nr-mac-scheduler-ofdma-aoi.cc` | AoI | New: AoI OFDMA scheduler implementation |
| `model/nr-mac-scheduler-ofdma-aoi.h` | AoI | New: AoI OFDMA scheduler header |
| `model/nr-mac-scheduler-ue-info-aoi.cc` | AoI | New: AoI UE info implementation |
| `model/nr-mac-scheduler-ue-info-aoi.h` | AoI | New: AoI UE info header |

## Validated Application Order

For a clean NR v2.4 + NS-3 3.38 checkout:

```bash
# Step 1: Apply LTE PDCP patch (to NS-3 root)
cd $NS3_DIR
git apply scripts/patches/ns3/v2.4-ns3.38/ns3_lte_pdcp.patch

# Step 2: Apply combined NR schedulers patch (to NR contrib dir)
cd $NS3_DIR/contrib/nr
git apply ../../scripts/patches/ns3/v2.4-ns3.38/nr_schedulers.patch
```

> **Why not apply the files in `originals/`?**
> `originals/nr_edf_scheduler.patch` and `originals/nr_aoi_mac_scheduler.patch`
> both start from the same `CMakeLists.txt` context. Applying one changes that
> context and the other produces a `.rej`. Use `nr_edf_only.patch` and
> `nr_aoi_only.patch`, or the combined `nr_schedulers.patch`.

## Automated Install

The install script handles all of the above automatically:

```bash
make install-ns3
# or
bash scripts/install/install_ns3.sh
```
