# CodePC Link Complications Checklist

Use this during implementation and release review.

## v0.1 blockers

Target/hardware validation still required:

- [ ] Target Bluetooth controller supports BLE peripheral/GATT advertising
- [ ] Supported BlueZ/NetworkManager/Python/Android/Chrome versions are recorded
- [ ] Persistent CodePC device ID is verified stable across reboot and IP changes on target hardware
- [ ] Payloads larger than one ATT packet/MTU work on target BlueZ + Android
- [ ] GATT/advertising recovers after BlueZ restart on the target
- [ ] Web Bluetooth frontend is served/verified from the production HTTPS Pages origin
- [ ] Android Chrome permission/disconnect/reconnect flows pass on a real phone
- [ ] PWA works offline after it has previously been loaded on that phone
- [ ] Full target-hardware integration matrix passes

Implemented and covered by software tests/review:

- [x] Schema v1 is frozen and tested
- [x] Permanent BLE UUIDs are committed
- [x] Production BLE policy is encrypted read-only; no v0.1 BLE writes
- [x] Wi-Fi + Ethernet multi-homing is normalized
- [x] Link, IP, default route, and Internet states remain distinct
- [x] Multiple addresses per interface are preserved
- [x] Minimal systemd permissions/hardening are defined
- [x] Web Bluetooth chooser is restricted to the CodePC Link service UUID
- [x] Explicit disconnect/reconnect/refresh paths are implemented
- [x] Remembered-device reconnect is used when `Bluetooth.getDevices()` is available
- [x] First-use-offline limitation is documented
- [x] Versioned PWA app-shell caching and controlled worker activation are implemented
- [x] Browser-side protocol and connection lifecycle tests run in CI

## Important complications

- [x] Cockpit addresses are labelled as candidates; the UI does not promise phone reachability
- [x] Raw-IP Cockpit TLS/certificate behavior is documented
- [x] Useful bridges/bonds are retained by backend normalization
- [x] Container/veth/VPN-style noise is filtered from the primary backend view
- [ ] Multiple nearby CodePC Link units are validated as distinguishable enough in the Android chooser/connection flow
- [x] PWA upgrades avoid forced activation underneath an open old page
- [x] BLE-derived hostname, SSID, IP, and error text are inserted as text, not HTML
- [x] Cockpit links are generated only from numeric IPv4/IPv6 values
- [x] The static PWA contains no analytics/telemetry code
- [x] Journald policy excludes passwords, tokens, and Wi-Fi credentials
- [x] Partial NetworkManager failure returns partial data plus structured errors
- [x] iOS/Safari browser-only Web Bluetooth is not claimed as a v0.1 target

## v0.2 Cockpit blockers

- [ ] Existing CodePC Cockpit package/build/manifest integration point is confirmed
- [ ] Management consumes the same backend as BLE
- [ ] Cockpit privilege elevation is validated
- [ ] Start/stop/restart is limited to `codepc-link.service`
- [ ] Page handles daemon restart, permission failure, and stale status
- [ ] Existing Cockpit Networking/Services/Logs are not duplicated unnecessarily

## Before privileged BLE writes

- [ ] Encrypted/authenticated transport policy is defined
- [ ] Application-level authorization exists
- [ ] Commands are narrowly scoped
- [ ] Dangerous actions require explicit confirmation
- [ ] No generic shell endpoint exists
- [ ] No arbitrary systemd-control endpoint exists
- [ ] Sensitive data is excluded from logs
