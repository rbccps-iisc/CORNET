## ADDED Requirements

### Requirement: ScenarioConfig selects a pre-built NS-3 script template
The system SHALL add `ScenarioConfig` to `cornet/config/schema.py` with fields: `profile: str`, `numerology: int | None`, `bandwidth_mhz: float | None`, `scheduler: str | None`. A `profile` value SHALL select a script template from `cornet/scenarios/<profile>/run.py`. Valid profiles SHALL be: `5g_nr_urllc`, `5g_nr_embb`, `5g_nr_mmtc`, `6g_thz`. An invalid profile value SHALL raise `ConfigValidationError` at load time.

#### Scenario: Profile selects correct NS-3 template
- **WHEN** `scenario.profile: 5g_nr_urllc` is set in config
- **THEN** `Ns3Plugin` SHALL launch `cornet/scenarios/5g_nr_urllc/run.py` as the NS-3 script
- **THEN** the script SHALL use the CTTC `nr` module with numerology 3, 120kHz subcarrier spacing

#### Scenario: Unknown profile raises error at load time
- **WHEN** `scenario.profile: unknown_standard` is in the config
- **THEN** `load_unified()` SHALL raise `ConfigValidationError` listing the valid profile names
- **THEN** no NS-3 subprocess SHALL be launched

#### Scenario: No scenario section uses default NS-3 script path
- **WHEN** the config has no `scenario` section
- **THEN** `Ns3Plugin` SHALL use `network.script` (existing behavior) to find the NS-3 script
- **THEN** all existing NS-3 task configs SHALL work unchanged

### Requirement: 5G NR URLLC template (numerology 3, 120 kHz)
The `5g_nr_urllc` NS-3 script template SHALL configure NS-3 with the CTTC `nr` module using: numerology μ=3 (120 kHz subcarrier spacing), configurable bandwidth (default 100 MHz), `NrMacSchedulerTdmaRR` scheduler, and `TapBridge` connecting to CORNET TUN interfaces. The template SHALL accept `--bandwidth-mhz`, `--num-ue`, `--num-gnb`, and `--tunX=<ifname>,<ip>` CLI arguments.

#### Scenario: URLLC template runs without error
- **WHEN** the template is launched with `--num-ue=1 --num-gnb=1 --tun0=tun0,10.0.0.1 --tun1=tun1,10.0.0.2`
- **THEN** the NS-3 simulation SHALL start without error
- **THEN** a `TapBridge` SHALL attach to each named TUN interface
- **THEN** traffic sent on `tun0` SHALL appear as packets from `10.0.0.1` in NS-3

### Requirement: 5G NR eMBB template (numerology 1, 30 kHz)
The `5g_nr_embb` NS-3 script template SHALL configure NS-3 with numerology μ=1 (30 kHz subcarrier spacing), configurable bandwidth (default 100 MHz), and MIMO antenna configuration. The same CLI interface as URLLC SHALL be supported.

#### Scenario: eMBB template uses numerology 1
- **WHEN** the `5g_nr_embb` template is launched
- **THEN** the NS-3 `NrHelper` SHALL be configured with `SetPathlossAttribute("Frequency", ...)` consistent with sub-6GHz eMBB
- **THEN** numerology SHALL be set to μ=1

### Requirement: 5G NR mMTC template (numerology 0, 15 kHz)
The `5g_nr_mmtc` NS-3 script template SHALL configure NS-3 with numerology μ=0 (15 kHz subcarrier spacing), narrow bandwidth (default 20 MHz), supporting up to 32 UEs, for IoT/sensor device scenarios.

#### Scenario: mMTC template supports many UEs
- **WHEN** the template is launched with `--num-ue=16`
- **THEN** 16 NS-3 UE nodes SHALL be created and attached to the gNB
- **THEN** 16 TUN interfaces SHALL be mapped (tun0 through tun15)

### Requirement: 6G THz template (ns3-thz module, experimental)
The `6g_thz` NS-3 script template SHALL configure NS-3 using the NIST `ns3-thz` module at a configurable center frequency (default 300 GHz) and bandwidth (default 2 GHz). When the `ns3-thz` module is not available at NS-3 build time, `Ns3Plugin` SHALL log a WARNING: `"6g_thz profile requires ns3-thz module. See docs/INSTALL.md#ns3-thz."` and raise `PluginConfigError`. The `6g_thz` profile SHALL be marked `experimental: true` in `ScenarioConfig`.

#### Scenario: 6G THz template raises clear error when module missing
- **WHEN** `scenario.profile: 6g_thz` and ns3-thz is not installed
- **THEN** `Ns3Plugin.configure()` SHALL raise `PluginConfigError` with a message referencing `INSTALL.md#ns3-thz`
- **THEN** the error message SHALL NOT be a raw Python `ImportError` or `FileNotFoundError`

#### Scenario: Experimental flag logs warning at load time
- **WHEN** `scenario.profile: 6g_thz` is loaded
- **THEN** a WARNING SHALL be logged: `"Scenario profile 6g_thz is experimental. Behavior may change."`
