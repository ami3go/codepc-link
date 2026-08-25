# CodePC Link Roadmap

The roadmap is dependency-ordered. The project should prove the BLE path before adding privileged recovery features.

## Milestone A — Feasibility

Goal: prove the target mini-PC can operate as a BLE peripheral/GATT server.

Implementation tooling is complete and merged. The following remain **target-hardware validation gates**, not software TODOs:

- [ ] Record target distro, BlueZ, NetworkManager, Cockpit, Python, Android, and Chrome versions using `codepc-link doctor`
- [ ] Verify BLE peripheral/GATT advertising capability on the actual mini-PC
- [ ] Test rfkill, adapter reset, suspend/resume, and BlueZ restart behavior
- [ ] Confirm Android can discover the advertisement

See [FEASIBILITY.md](FEASIBILITY.md).

## Milestone B — BLE Core

Goal: stable read-only status protocol.

Implemented:

- [x] Persistent device identity
- [x] Freeze normalized status schema v1 and fixtures
- [x] Commit permanent BLE UUIDs
- [x] Decide production read/privacy policy: encrypted reads by default; no BLE writes
- [x] Implement Management Core
- [x] Implement NetworkManager collector and interface normalization
- [x] Separate link, addresses, default route, and Internet state
- [x] Implement local `status --json` contract
- [x] Register GATT service and advertisement in the daemon implementation
- [x] Implement `SYSTEM_INFO` and `NETWORK_STATUS`
- [x] Implement BlueZ `ReadValue` offset handling and 16 KiB payload guard
- [x] Add minimal systemd hardening

Still requires real target validation before Milestone B is closed:

- [ ] Validate payloads larger than one ATT packet/negotiated MTU on Android + target BlueZ
- [ ] Validate encrypted-read pairing behavior on the headless target
- [ ] Validate advertisement size/name on the target controller
- [ ] Validate `codepc-link.service` recovery after `bluetooth.service` restart

Protocol contract: [PROTOCOL.md](PROTOCOL.md).

## Milestone C — Browser Client / v0.1

Goal: use CodePC Link without a custom Android application.

Software implementation:

- [x] Implement the HTTPS Web Bluetooth frontend in `site/`
- [x] Filter the device chooser to the permanent CodePC Link service UUID
- [x] Implement permission-aware remembered-device reconnect where `getDevices()` is available
- [x] Handle disconnect, explicit reconnect, refresh, and page reload behavior
- [x] Render multiple interfaces and every reported IP address
- [x] Preserve separate link/default-route/Internet presentation
- [x] Generate labelled Cockpit target candidates without promising reachability
- [x] Validate numeric IPv4/IPv6 targets before creating Cockpit links
- [x] Document raw-IP TLS/certificate behavior
- [x] Add PWA offline app-shell caching after first load
- [x] Add controlled service-worker/cache version updates
- [x] Document first-use-offline and browser/iOS limitations
- [x] Add browser protocol/Web Bluetooth contract tests to CI

Deployment and real-device validation gates:

- [ ] Enable/verify the GitHub Pages HTTPS origin (repository setting tracked in issue #6)
- [ ] Validate Android Chrome device chooser and retained permission behavior
- [ ] Validate production encrypted reads through Web Bluetooth
- [ ] Validate long characteristic reads through the browser on the real target
- [ ] Validate cached/installed PWA startup and BLE refresh with Internet disabled
- [ ] Run the full target-hardware integration matrix in [WEB_CLIENT.md](WEB_CLIENT.md)

## Milestone D — Cockpit Management / v0.2

- [ ] Confirm existing CodePC Cockpit plugin integration point
- [ ] Add Management page/tab
- [ ] Use the shared normalized backend
- [ ] Show adapter/service/advertising/network state
- [ ] Use Cockpit privilege elevation for `codepc-link.service` controls
- [ ] Start/stop/restart only the CodePC Link service initially
- [ ] Handle daemon restart, stale status, and permission failures
- [ ] Link to existing Networking/Services/Logs instead of duplicating them
- [ ] Integrate project icon into Cockpit/PWA assets

## Milestone E — Secure Recovery / v0.3+

Security foundation comes first:

- [ ] Define authenticated write protocol
- [ ] Add application-level authorization
- [ ] Add explicit confirmation UX for dangerous actions
- [ ] Wi-Fi scanning
- [ ] Wi-Fi provisioning
- [ ] Narrow NetworkManager recovery action
- [ ] Reboot/shutdown only if justified

Never add a generic shell endpoint or arbitrary systemd-control endpoint.

## Future

- Native iOS client if browser-only Web Bluetooth remains unavailable
- Additional diagnostics and BLE notifications
- Native packaging for supported distributions
