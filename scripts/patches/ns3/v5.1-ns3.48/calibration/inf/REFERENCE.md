# InF reference note

Source of the formulas: 3GPP TR 38.901 (Release 16 and later), Tables 7.2-4, 7.4.1-1, 7.4.2-1, 7.5-6 Part-3, 7.5-11, and 7.8-7.

Ramos et al., "Implementation and Calibration of the 3GPP Industrial Channel Model for ns-3", WNS3 2022, published a whole-file replacement of ns-3's `channel-condition-model`, `three-gpp-propagation-loss-model`, `three-gpp-channel-model`, and the NR helpers, plus `three-gpp-industrial-channel-example.cc` (180 UEs; SINR, RSSI, coupling loss, positions). That drop-in is not used here. The numbers below are the specification tables that replacement encoded. Credit: Andrea Ramos, Yanet Estrada, Miguel Cantero, Jaime Romero, David Martín-Sacristán, Saúl Inca, Manuel Fuentes, Jose F. Monserrat (iTEAM / Fivecomm). Repository: `https://gitlab.com/andre.ramosp/ns-3-inf-channel-modeling`.

## Scenarios (Table 7.2-4)

| | InF-SL | InF-DL | InF-SH | InF-DH |
|---|---|---|---|---|
| Clutter | sparse, low BS | dense, low BS | sparse, high BS | dense, high BS |
| Typical `d_clutter` | 10 m | 2 m | 10 m | 2 m |
| Density `r` | < 40% | ≥ 40% | < 40% | ≥ 40% |
| BS height | below clutter | below clutter | above clutter | above clutter |

`fc` is in GHz. Distances are in metres. `d_3D` validity for the path-loss formulas is `1 ≤ d_3D ≤ 600`.

## Path loss (Table 7.4.1-1)

LOS, all four sub-scenarios:

```
PL_LOS = 31.84 + 21.50 log10(d_3D) + 19.00 log10(fc)
σ_SF = 4.3
```

NLOS, then `PL_NLOS = max(PL, PL_LOS)` except InF-DL, which is `max(PL, PL_LOS, PL_InF-SL)`:

| Sub-scenario | PL | σ_SF |
|---|---|---|
| InF-SL | `33 + 25.5 log10(d_3D) + 20 log10(fc)` | 5.7 |
| InF-DL | `18.6 + 35.7 log10(d_3D) + 20 log10(fc)` | 7.2 |
| InF-SH | `32.4 + 23.0 log10(d_3D) + 20 log10(fc)` | 5.9 |
| InF-DH | `33.63 + 21.9 log10(d_3D) + 20 log10(fc)` | 4.0 |

## LOS probability (Table 7.4.2-1)

```
Pr_LOS(d_2D) = exp(-d_2D / k)
k = -d_clutter / ln(1 - r)                                 # InF-SL, InF-DL
k = -d_clutter / ln(1 - r) * (h_BS - h_UT) / (h_c - h_UT)  # InF-SH, InF-DH
```

`h_c` is the effective clutter height. The high-BS form needs `h_c > h_UT`. Clutter density, height, and size are attributes on the channel-condition model.

Calibration defaults from Table 7.8-7, used when a scenario is selected through NR's channel helper:

| | sparse (SL, SH) | dense (DL, DH) |
|---|---|---|
| `r` | 0.20 | 0.60 |
| `h_c` | 2 m | 6 m |
| `d_clutter` | 10 m | 2 m |
| BS height | 1.5 m (SL, DL) | 8 m (SH, DH) |
| Hall | SL and DH: 120 × 60 × 10 m | DL and SH: 300 × 150 × 10 m |

Volume and surface (walls + floor + ceiling) for the delay-spread formula:

- Small hall: `V = 72000 m³`, `S = 18000 m²`
- Big hall: `V = 450000 m³`, `S = 99000 m²`

## Fast fading (Table 7.5-6 Part-3 and Table 7.5-11)

`V/S` is hall volume over surface area. `fc` is in GHz.

| Parameter | LOS | NLOS |
|---|---|---|
| `μ_lgDS` | `log10(26(V/S)+14) - 9.35` | `log10(30(V/S)+32) - 9.44` |
| `σ_lgDS` | 0.15 | 0.19 |
| `μ_lgASD` / `σ_lgASD` | 1.56 / 0.25 | 1.57 / 0.20 |
| `μ_lgASA` / `σ_lgASA` | `-0.18 log10(1+fc)+1.78` / `0.12 log10(1+fc)+0.2` | 1.72 / 0.30 |
| `μ_lgZSA` / `σ_lgZSA` | `-0.2 log10(1+fc)+1.5` / 0.35 | `-0.13 log10(1+fc)+1.45` / 0.45 |
| `μ_lgZSD` / `σ_lgZSD` (Table 7.5-11) | 1.35 / 0.35 | 1.2 / 0.55 |
| ZOD offset | 0 | 0 |
| K-factor `μ` / `σ` | 7 / 8 | N/A |
| Delay scaling `r_τ` | 2.7 | 3 |
| XPR `μ` / `σ` | 12 / 6 | 11 / 6 |
| Clusters / rays | 25 / 20 | 25 / 20 |
| Cluster ASD / ASA / ZSA (deg) | 5 / 8 / 9 | 5 / 8 / 9 |
| Cluster DS | N/A (ns-3 uses 3.91 ns) | N/A (3.91 ns) |
| Per-cluster shadowing std (dB) | 4 | 3 |
| LSP correlation distance (m) | 10 | 10 |

Non-zero LOS cross-correlations, order `[SF, K, DS, ASD, ASA, ZSD, ZSA]`: `K–DS = -0.7`, `K–ASD = -0.5`. NLOS cross-correlations in the table are 0, so the factor is the identity (K omitted).

Table 7.6.3.1-2 lists the InF cluster-and-ray spatial-consistency distance as 10 m. LOS-state correlation distance is `d_clutter / 2`.
