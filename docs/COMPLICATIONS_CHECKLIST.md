# CodePC Link Complications Checklist

Use this during implementation and release review.

## v0.1 blockers

- [ ] Target Bluetooth controller supports BLE peripheral/GATT advertising
- [ ] Supported BlueZ/NetworkManager/Python/Android/Chrome versions are recorded
- [ ] Persistent CodePC device ID is stable across reboot and IP changes
- [ ] Schema v1 is frozen and tested
- [ ] Permanent BLE UUIDs are committed
- [ ] Production BLE pairing/read-access/privacy policy is decided
- [ ] Wi-Fi + Ethernet multi-homing is handled correctly
- [ ] Link, IP, default route, and Internet states remain distinct
- [ ] Multiple addresses per interface work
- [ ] Payloads larger than one ATT packet/MTU work on target BlueZ + Android
- [ ] GATT/advertising recovers after BlueZ restart
- [ ] Minimal systemd permissions/hardening are reviewed
- [ ] Web Bluetooth frontend is served from HTTPS
- [ ] Android Chrome permission/disconnect/reconnect flows pass
- [ ] PWA works offline after it has previously been loaded
- [ ] First-use-offline limitation is documented
- [ ] Full target-hardware integration matrix passes

## Important complications

- [ ] The phone may not route to every IP reported by CodePC Link
- [ ] Cockpit opened by raw IP may show a TLS/certificate warning
- [ ] Bridges/bonds may own the useful address and must not be filtered blindly
- [ ] VPN/container/veth interfaces must not clutter the primary UI
- [ ] Multiple nearby CodePC Link units must be distinguishable by stable identity
- [ ] PWA upgrades must not leave incompatible cached JavaScript active
- [ ] Hostname, SSID, IP, and service state are treated as potentially sensitive
- [ ] Journald never contains passwords, tokens, or Wi-Fi credentials
- [ ] Partial NetworkManager failure returns partial data plus structured errors
- [ ] iOS/Safari browser-only Web Bluetooth is not a v0.1 target

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
