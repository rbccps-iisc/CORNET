# v5.1-ns3.48

Explicit lane. The plain `make install-ns3` default stays `v2.4-ns3.38`.

| Component | Tag | Pinned commit |
|---|---|---|
| NS-3 | `ns-3.48` | `d2add90b452d600cfb4859baed8e9ea633519447` |
| 5G-LENA | `v5.1` | `cedceadda17392c90587fb9400eb9b1f8c236713` |

`make install-ns3-v51` clones those tags and rejects a HEAD that does not match the pinned commit.

## Research reason for rebasing `nr_schedulers.patch`

Auto-research scheduler experiments (EDF and AoI) need the same MAC schedulers on the lane that also has NR handover and wrap-around. That is why the research-feature scheduler patch is ported here, not only the infrastructure patches.

## InF channel patch

`ns3_channel_inf.patch` adds TR 38.901 Indoor Factory path loss, LOS probability, and fast-fading parameters to NS-3 3.48 and registers `InF-SL`, `InF-DL`, `InF-SH`, and `InF-DH` on NR's channel helper. It does not replace the upstream channel files with the Ramos et al. drop-in. The formulas, clutter defaults, and calibration hall sizes are in `calibration/inf/REFERENCE.md`.

Credit: Andrea Ramos, Yanet Estrada, Miguel Cantero, Jaime Romero, David Martín-Sacristán, Saúl Inca, Manuel Fuentes, and Jose F. Monserrat, "Implementation and Calibration of the 3GPP Industrial Channel Model for ns-3", WNS3 2022. Repository: https://gitlab.com/andre.ramosp/ns-3-inf-channel-modeling.

## Wrap-around channel matrix

`ns3_wraparound_channel_matrix.patch` rebuilds the 3GPP channel matrix and the cached long-term component when wrap-around replaces the channel parameters at simulation time 0. Upstream compares timestamps with `>`, so a replacement at time 0 kept the previous cluster count and aborted in `CalcBeamformingGain`. Apply it after `ns3_channel_inf.patch`.

## Aerial channel patch

`ns3_channel_aerial_36777.patch` adds TR 36.777 V15.0.0 Annex B path loss and LOS probability for `UMa-AV`, `UMi-AV`, and `RMa-AV`. The scope is aerial path loss only: fast fading is unchanged. Heights outside 1.5 m to 300 m are clamped and a warning is logged. Below the scenario threshold the terrestrial UMa, UMi-Street Canyon, or RMa model is used. The cross-check against `ntn-sagin`'s calculator is in `calibration/aerial/VERDICT.md`. That calculator was run for numbers only and its source is not in this tree.
