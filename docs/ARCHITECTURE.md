# CodePC Link Architecture

## Purpose

CodePC Link provides an out-of-band BLE discovery/status path for a headless Linux mini-PC, then hands full administration off to Cockpit over normal IP networking.

It does **not** tunnel Cockpit over BLE.

## Target architecture

```text
NetworkManager ─┐
systemd         ├──> CodePC Management Core
kernel/sysfs  ──┘            │
                              ├──> BLE GATT / BlueZ
                              │       │
                              │       └──> Android Chrome / PWA
                              │
                              └──> local status API
                                      │
                                      └──> Cockpit Management
```

## Core boundaries

### BLE

BLE is for:

- device identity and discovery
- network/interface/IP status
- basic diagnostics
- Cockpit target discovery
- later, authenticated recovery operations

BLE is not for:

- tunnelling the Cockpit UI
- arbitrary shell execution
- generic systemd control

### Cockpit

Cockpit remains the full host-management interface over IP. The CodePC Link Management page should expose only CodePC Link-specific state/actions and link to existing Cockpit Networking, Services, and Logs where appropriate.

## Authoritative backend

BLE and Cockpit must consume the same normalized Management Core. Network normalization must not be independently reimplemented by two frontends.

The initial local contract is expected to be conceptually equivalent to:

```bash
codepc-link status --json
```

The exact implementation may later use D-Bus.

## Network model

CodePC Link is explicitly designed for multi-homed systems. For example:

```text
wlan0   192.168.1.73   default route / Internet
eth0    10.10.10.1     isolated local-services LAN
```

The data model separates:

- link state
- assigned addresses
- default-route ownership
- Internet connectivity

A default route does not prove Internet access.

Each interface may have multiple addresses. Bridges/bonds can own useful addresses and must not be filtered solely by name. Container/veth/VPN interfaces should not dominate the primary UI.

## Web Bluetooth bootstrap limitation

The browser client must run from a secure HTTPS origin. v0.1 therefore does not solve first-ever use on a completely offline, previously unused phone.

Supported flow:

```text
First use with network access
  -> load/cache CodePC Link PWA
Later, Internet unavailable
  -> open cached PWA
  -> connect to CodePC Link over BLE
```

## Security model

v0.1 is read-only over BLE. Production read/pairing policy is a release decision and must be documented.

Privileged writes require:

- encrypted/authenticated transport policy
- application-level authorization
- narrowly scoped commands
- explicit confirmation for dangerous actions
- no generic shell or arbitrary systemd endpoint

## Protocol principles

- project-specific permanent 128-bit UUIDs
- UTF-8 JSON status payloads
- explicit schema version
- partial data plus structured errors on collector failure
- long-read/chunk-safe payload handling
- stable device identity independent of current IP

See `ROADMAP.md` for implementation order.
