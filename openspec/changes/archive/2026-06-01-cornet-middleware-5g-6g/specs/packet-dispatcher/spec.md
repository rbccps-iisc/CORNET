## ADDED Requirements

### Requirement: PacketDispatcher priority queue with physics-time release
The system SHALL implement `PacketDispatcher` in `cornet/middleware/dispatcher.py` using a min-heap priority queue keyed on `(release_time, seq_num)`. The dispatcher SHALL hold packets until `physics_time >= release_time - ε` where ε = 0.001 seconds, then deliver them in release-time order. The dispatcher SHALL be thread-safe: `enqueue()` and the release loop SHALL run on separate threads.

#### Scenario: Packet released after delay elapses
- **WHEN** `enqueue(packet, physics_time=1.0, delay_s=0.005)` is called
- **THEN** the dispatcher SHALL NOT deliver the packet until `update_physics_time(t)` is called with `t >= 1.005 - 0.001`
- **THEN** the packet SHALL be delivered by calling the registered `on_release` callback with the packet bytes

#### Scenario: Packets released in arrival-time order
- **WHEN** two packets are enqueued: A at `(pt=1.0, delay=0.010)` and B at `(pt=1.0, delay=0.005)`
- **THEN** B SHALL be released before A (lower release_time)
- **THEN** if release times are equal, the packet with lower `seq_num` SHALL be released first

#### Scenario: Epsilon tolerance prevents tight-loop
- **WHEN** `physics_time = 1.004` and a packet has `release_time = 1.005`
- **THEN** the dispatcher SHALL release the packet immediately (within ε = 0.001s)
- **THEN** the dispatcher SHALL NOT spin-wait for the exact threshold

### Requirement: Real-time factor scaled sleep between checks
The dispatcher SHALL sleep `max(0, (release_time - physics_time) / rtf) * sleep_scale` seconds between queue polls, where `rtf` is the real-time factor (default 1.0) and `sleep_scale` is a tunable constant (default 0.5). When `rtf = 0`, the dispatcher SHALL use a minimum sleep of 0.0001 seconds to prevent busy-waiting.

#### Scenario: RTF=1 produces correct sleep duration
- **WHEN** `rtf = 1.0` and the next packet releases in 0.1 physics-seconds
- **THEN** the dispatcher SHALL sleep approximately 0.05 wall-clock seconds before rechecking

#### Scenario: RTF fast-forward mode
- **WHEN** `rtf = 0` (maximum speed, no wall-clock alignment)
- **THEN** the dispatcher SHALL use minimum sleep of 0.0001 seconds between polls
- **THEN** the dispatcher SHALL still respect packet ordering and release_time thresholds

### Requirement: Deadline discard for stale packets
The dispatcher SHALL discard packets whose `release_time` is more than `deadline_s` seconds in the past relative to current `physics_time`. Discarded packets SHALL be counted in `PacketDispatcher.stats.discarded` and a WARNING SHALL be logged with the packet's flow key and age.

#### Scenario: Stale packet discarded at release check
- **WHEN** `physics_time = 5.0`, a packet has `release_time = 4.0`, and `deadline_s = 0.5`
- **THEN** the packet is 1.0 seconds stale (> 0.5 deadline)
- **THEN** the dispatcher SHALL discard the packet without calling `on_release`
- **THEN** `dispatcher.stats.discarded` SHALL increment by 1

#### Scenario: Fresh packet not discarded
- **WHEN** `physics_time = 5.0`, a packet has `release_time = 4.8`, and `deadline_s = 0.5`
- **THEN** the packet is 0.2 seconds stale (< 0.5 deadline)
- **THEN** the dispatcher SHALL release it normally

### Requirement: Optional BER injection on packet release
When `ber > 0.0` is configured, the dispatcher SHALL apply bit-error injection to the IP payload (bytes 20 onward) of each packet before calling `on_release`. Bit-flip positions SHALL follow a geometric distribution with parameter `ber`. Packets where a bit-flip position falls within the first 20 bytes (IP header) SHALL be discarded rather than corrupted.

#### Scenario: BER=0 disables injection
- **WHEN** `ber = 0.0`
- **THEN** packet bytes SHALL be delivered unchanged to `on_release`

#### Scenario: BER injection flips payload bits
- **WHEN** `ber = 0.01` and a packet with known payload is processed
- **THEN** the released packet payload SHALL differ from the original at geometrically distributed positions
- **THEN** the number of bit-flips per packet SHALL follow `Geometric(p=0.01)` in expectation

#### Scenario: Header bit-flip causes discard
- **WHEN** the geometric distribution would place a flip in bytes 0–19 (IP header)
- **THEN** the dispatcher SHALL discard the packet and increment `stats.header_corrupted`

### Requirement: Dispatcher statistics collection
The dispatcher SHALL maintain a `stats` object with counters: `enqueued`, `released`, `discarded`, `header_corrupted`. `stats.snapshot()` SHALL return a dict copy safe to read from any thread.

#### Scenario: Stats reflect experiment activity
- **WHEN** 100 packets are enqueued and 97 are released normally, 2 are deadline-discarded, and 1 has header corruption
- **THEN** `stats.snapshot()` SHALL return `{"enqueued": 100, "released": 97, "discarded": 2, "header_corrupted": 1}`
