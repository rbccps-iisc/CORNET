## ADDED Requirements

### Requirement: TUN interface creation via fcntl.ioctl
The system SHALL implement `TunManager` in `cornet/middleware/tun.py`. TUN interfaces SHALL be created by opening `/dev/net/tun` with `open('/dev/net/tun', 'r+b', buffering=0)` and configuring via `fcntl.ioctl(fd, TUNSETIFF, struct.pack('16sH', name, IFF_TUN|IFF_NO_PI))`. If the process lacks `CAP_NET_ADMIN` capability, `setup()` SHALL raise `PermissionError` with the message: `"TunManager requires CAP_NET_ADMIN. Run with sudo or grant the capability."`.

#### Scenario: TUN interfaces created for all configured nodes
- **WHEN** `TunManager(ip_list=["10.0.0.1","10.0.0.2"])` is configured and `setup()` is called
- **THEN** two TUN interfaces `tun0` and `tun1` SHALL be created
- **THEN** `tun0` SHALL be assigned IP `10.0.0.1` via `ip addr add`
- **THEN** `tun1` SHALL be assigned IP `10.0.0.2` via `ip addr add`

#### Scenario: Missing CAP_NET_ADMIN raises descriptive error
- **WHEN** `setup()` is called without root/CAP_NET_ADMIN
- **THEN** `PermissionError` SHALL be raised before any interface is created
- **THEN** the error message SHALL contain `"CAP_NET_ADMIN"` and `"sudo"`

### Requirement: Per-node source-based policy routing
`setup()` SHALL configure policy routing tables so that traffic originating from `ip_list[i]` is routed via `tun_i`. Table indices SHALL follow: outbound table = `i + 1`, loopback interception table = `i + 101`. The default local lookup rule at priority 0 SHALL be deleted and re-added at priority 10 to allow CORNET's rules at priority 5 to take effect.

#### Scenario: Policy routing tables created
- **WHEN** `setup()` is called with `ip_list=["10.0.0.1","10.0.0.2"]`
- **THEN** `ip rule add from 10.0.0.1 lookup 1 pref 5` SHALL be executed
- **THEN** `ip rule add from 10.0.0.2 lookup 2 pref 5` SHALL be executed
- **THEN** `ip rule del pref 0` SHALL be executed (remove default local priority)
- **THEN** `ip rule add pref 10 lookup local` SHALL be executed (restore at priority 10)

#### Scenario: Routing tables cleaned up on teardown
- **WHEN** `teardown()` is called after `setup()`
- **THEN** all `ip rule` entries added by CORNET SHALL be removed
- **THEN** the default local lookup rule SHALL be restored at priority 0
- **THEN** all TUN file descriptors SHALL be closed

### Requirement: Context manager for guaranteed teardown
`TunManager` SHALL implement `__enter__` / `__exit__` so it can be used as a context manager. `teardown()` SHALL be called in `__exit__` even if an exception occurred during the experiment. `teardown()` SHALL be idempotent — calling it twice SHALL NOT raise exceptions.

#### Scenario: Teardown called on exception
- **WHEN** `TunManager` is used as a context manager and an exception occurs inside the block
- **THEN** `teardown()` SHALL be called before the exception propagates
- **THEN** all TUN interfaces and routing rules SHALL be removed

#### Scenario: Double teardown is safe
- **WHEN** `teardown()` is called, then called again
- **THEN** the second call SHALL complete without raising any exception

### Requirement: TUN file descriptor access for middleware read loop
`TunManager.get_fd(node_index)` SHALL return the raw file descriptor integer for `tun_i` suitable for use with `os.read()` in a packet capture loop.

#### Scenario: FD returned for valid index
- **WHEN** `setup()` has been called with 3 nodes
- **THEN** `get_fd(0)`, `get_fd(1)`, `get_fd(2)` SHALL each return a distinct positive integer file descriptor
- **THEN** `os.read(get_fd(0), 65535)` SHALL block until a packet arrives on `tun0`
