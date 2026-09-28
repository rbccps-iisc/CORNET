# Migration Status: NS-3 3.48 + NR v5.1

## v4.2 stepping-stone gate

Reconciliation tasks 4.1–4.3 are complete:

- `~/ns-3-dev-v47/.cornet-built` and `contrib/nr/.cornet-patched-v4.2` exist.
- `make validate-v47` wrote `pendulum_nr_control@ns3-v47` with status SUCCESS.
- `tasks/pendulum_nr_control/results/analysis/aoi_statistics.json` is non-empty: sensor flow `mean` 7.34113 ms, `rx_packets` 5930.

That file is the flow-monitor Age of Information of the internal sensor probe. It is not an NR PDCP trace. NR bearer repetitions come from `nr_pdcp_aoi.patch` on v4.2; `ns3_lte_pdcp.patch` does not affect those bearers.

## Unpatched baseline

`make install-ns3-v51` built `~/ns-3-dev-v51` at the pinned commits with CMake 4.4.3. No CORNET patches were applied for this check.

- Handover: `./ns3 run "test-runner --suite=nr-handover-metrics-guards --stop-on-failure"` passed (`nr-handover-metrics-guards`, 4.100 s).
- Wrap-around: `cttc-nr-3gpp-calibration-user --enableWraparound=true --numRings=0 --ueNumPergNb=1 --trafficScenario=2 --technology=NR --appGenerationTime=+1500ms --appStopWindow=+100ms` exited 0. The log shows the hexagonal grid, three cells, and `End simulation` after 33 s wall clock. A shorter window aborts in the example's percentile code because UDP apps start at 400 ms while the stop time ignores that offset.

## Patches

`make install-ns3-v51` applied `ns3_lte_pdcp.patch`, `nr_pdcp_aoi.patch`, `nr_schedulers.patch`, and `ns3_channel_inf.patch`, then rebuilt. Both sentinels are present. `three-gpp-propagation-loss-model` passed in 1.783 s. `handover_smoke` printed one `HandoverTotalTime` record and exited 0.

`pendulum_nr_control@ns3-v51` is SUCCESS with metric 16.5911. `analysis/aoi_statistics.json` has sensor `mean` 16.5911 ms and `rx_packets` 5929. The run printed `timing_ok is false; violated lag_budget_ms`.

`ns3_channel_aerial_36777.patch` is applied on `~/ns-3-dev-v51`. `three-gpp-aerial-propagation-loss-model` passed. The scope recorded for `channel_aerial_36777` is aerial path loss only. The ntn-sagin cross-check is in `calibration/aerial/VERDICT.md`. The capability stays `cornet-integrated` until a leaderboard run exercises an aerial scenario.
