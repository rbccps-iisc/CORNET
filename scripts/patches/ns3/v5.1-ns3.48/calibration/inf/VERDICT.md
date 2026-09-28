# InF calibration verdict

Layout: TR 38.901 Table 7.8-7, 3.5 GHz, isotropic antennas, serving cell by minimum path loss. Shadowing is on for the CDFs.

Formula anchor, InF-SL LOS, shadowing off, d3D = 10 m: 63.6773 dB (Table 7.4.1-1 reference 63.6773 dB). Within 0.1 dB.

TR 38.901 section 7.8.4 points the serving-cell coupling-loss curves at R1-1909704. Those numeric medians are not in this tree, so no sub-scenario is within a checked 1 dB of that reference.

Verdict: uncalibrated. Failing sub-scenarios: InF-SL, InF-DL, InF-SH, InF-DH.

| Scenario | Sites | UEs | Median (dB) | 5% | 95% |
|---|---:|---:|---:|---:|---:|
| InF-SL | 18 | 180 | 60.8406 | 49.9757 | 67.1784 |
| InF-DL | 18 | 180 | 74.3768 | 59.4952 | 84.7104 |
| InF-SH | 18 | 180 | 68.63 | 62.1194 | 74.8681 |
| InF-DH | 18 | 180 | 64.8749 | 58.0396 | 70.775 |
