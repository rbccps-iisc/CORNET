# TR 36.777 aerial cross-check

The CORNET model implements TR 36.777 V15.0.0 Annex B Tables B-1 (LOS probability), B-2 (path loss), and B-3 (shadow-fading standard deviation). Fast fading is unchanged. Scope: **aerial path loss only**.

Golden numbers come from running `A2gChannelTr36777::PathLossDb` and `LosProbability` in `Muhammaduazir69/ntn-sagin` `model/a2g-channel-tr36777.cc` (fetched 2026-09-28). The calculator was compiled outside this tree. Its source is not copied here.

Geometry for the path-loss rows: `d_2D = 500 m`, `f_c = 2 GHz`, BS height 25 m (UMa-AV), 10 m (UMi-AV), or 35 m (RMa-AV). `comparison.csv` is `TR 36.777 − calculator`.

| Point | Within 0.1 dB | Why |
|---|---|---|
| UMa-AV LOS, 100 m | yes (0.00 dB) | Both use `28 + 22 log10(d_3D) + 20 log10(f_c)`. This is the specification breakpoint. |
| UMa-AV NLOS, 50 m | yes (0.002 dB) | The calculator folds `20 log10(40 π / 3)` into the constant 14.94. |
| UMi-AV NLOS, 100 m | yes | The height term `43.2 − 7.6 log10(100)` is 28 in both. |
| RMa-AV NLOS, 50 m | yes (0.002 dB) | Same free-space reduction as UMa-AV NLOS. |
| UMi-AV LOS, 100 m | no (−2.71 dB) | The calculator uses slope 22.25 and drops the `−0.5 log10(h_UT)` term and the free-space floor. |
| RMa-AV LOS, 50 m | no (+4.44 dB) | The calculator uses intercept 28. Table B-2 uses `max(23.9 − 1.8 log10(h_UT), 20) log10(d_3D) + 20 log10(40 π f_c / 3)`. |

LOS probability at the same breakpoints:

| Case | TR 36.777 | ntn-sagin |
|---|---|---|
| UMa-AV, 50 m, 1000 m | 0.7720518705 | 0.3664516939 |
| UMa-AV, 150 m | 1 | 1 |
| UMi-AV, 30 m, 500 m | 0.2619728828 | 0.1292911317 |
| RMa-AV, 20 m, 2000 m | 0.5976747604 | 0.4244636170 |
| RMa-AV, 80 m | 1 | 1 |

The calculator raises LOS linearly with height. Table B-1 uses the `d_1`, `p_1` piecewise formula, and is 100% only above 100 m (UMa-AV) or 40 m (RMa-AV). UMi-AV has no 100% ceiling. The unit test checks the table values. The model is not changed to follow the calculator where the two disagree.

`three-gpp-aerial-propagation-loss-model` passed on `~/ns-3-dev-v51`: UMa-AV at 100 m and 500 m is within 0.1 dB of Table B-2, and a UT at 350 m matches the 300 m result after a height-clamp warning.
