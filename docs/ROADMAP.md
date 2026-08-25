# CodePC Link Roadmap

The roadmap is dependency-ordered. The project should prove the BLE path before adding privileged recovery features.

## Milestone A — Feasibility

Goal: prove the target mini-PC can operate as a BLE peripheral/GATT server.

- [ ] Record target distro, BlueZ, NetworkManager, Cockpit, Python, Android, and Chrome versions
- [ ] Verify BLE peripheral/GATT advertising capability
- [ ] Test rfkill, adapter reset, suspend/resume, and BlueZ restart behavior
- [ ] Confirm Android can discover the advertisement

## Milestone B — BLE Core

Goal: stable read-only status protocol.

- [ ] Persistent device identity
- [ ] Freeze normalized status schema v1 and fixtures
- [ ] Commit permanent BLE UUIDs
- [ ] Decide production read/pairing/privacy policy
- [ ] Implement Management Core
- [ ] Implement NetworkManager collector and interface normalization
- [ ] Separate link, addresses, default route, and Internet state
- [ ] Implement local `status --json` contract
- [ ] Register GATT service and advertisement
- [ ] Implement `SYSTEM_INFO` and `NETWORK_STATUS`
- [ ] Validate payloads larger than one ATT packet/MTU
- [ ] Recover after BlueZ restart
- [ ] Add minimal systemd hardening

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
