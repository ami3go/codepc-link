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

Implemented in the Milestone B branch:

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

- [ ] Deploy HTTPS Web Bluetooth frontend
- [ ] Device chooser and permission handling
- [ ] Disconnect/reconnect/page reload behavior
- [ ] Multi-interface/IP presentation
- [ ] Labelled Cockpit targets without promising reachability
- [ ] Document raw-IP TLS/certificate behavior
- [ ] PWA offline caching after first load
- [ ] Safe cache/version update behavior
- [ ] Document first-use-offline and iOS/Safari limitations
- [ ] Run the full target-hardware integration matrix

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
