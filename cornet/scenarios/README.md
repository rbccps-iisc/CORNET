# CORNET Scenario Templates

This directory contains built-in NS-3 script templates selected by
`network.scenario.profile`.

Profiles:

- `5g_nr_urllc`: CTTC NR, numerology 3, 120 kHz SCS, low-latency defaults
- `5g_nr_embb`: CTTC NR, numerology 1, sub-6 GHz eMBB defaults
- `5g_nr_mmtc`: CTTC NR, numerology 0, narrowband IoT-style defaults
- `6g_thz`: ns3-thz experimental profile, 300 GHz default carrier

Each template accepts `--tunX=<ifname>,<ip>` arguments for TapBridge wiring.