<p align="center">
  <img src="assets/codepc-link-icon.svg" width="180" alt="CodePC Link icon">
</p>

<h1 align="center">CodePC Link</h1>

<p align="center">
  BLE discovery, network-status, and recovery companion for headless Linux mini-PC systems managed with Cockpit.
</p>

<p align="center">
  <a href="https://github.com/ami3go/codepc-link/actions/workflows/ci.yml"><img src="https://github.com/ami3go/codepc-link/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/ami3go/codepc-link/releases"><img src="https://img.shields.io/github/v/release/ami3go/codepc-link?include_prereleases&sort=semver" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/ami3go/codepc-link" alt="MIT License"></a>
</p>

> **Status:** pre-alpha / feasibility and specification stage. The repository infrastructure is ready; the BLE daemon and Web Bluetooth client are not implemented yet.

## What CodePC Link is for

A headless mini-PC can be connected to more than one network at once—for example Wi-Fi for Internet access and Ethernet for isolated local services. When you are standing next to the machine, discovering the correct current IP can be awkward.

CodePC Link adds a small out-of-band BLE path so a nearby phone can identify the machine and read useful network status without already knowing an IP address.

The intended flow is:

```text
Android Chrome / cached PWA
           │
           │ BLE GATT
           ▼
      CodePC Link
           │
      status / discovery
           │
           ▼
   choose reachable target
           │
           │ normal IP network
           ▼
        Cockpit
```

BLE is for discovery, diagnostics, and recovery. **Cockpit itself is not tunnelled over BLE.**

## Target capabilities

### v0.1 — read-only BLE + browser client

- discover a nearby CodePC Link device
- stable device identity independent of DHCP/IP changes
- show Wi-Fi and Ethernet interfaces simultaneously
- show all relevant IP addresses
- distinguish link state, assigned IP, default route, and Internet connectivity
- show Cockpit targets
- open Cockpit using normal IP networking
- cached PWA continues to show BLE status when Internet access is unavailable

### v0.2 — Cockpit Management

- CodePC Link Management page/tab inside the existing Cockpit integration
- Bluetooth adapter, daemon, and advertising status
- normalized Wi-Fi/Ethernet status from the same backend as BLE
- start/stop/restart `codepc-link.service` using Cockpit privilege elevation
- diagnostics without duplicating Cockpit Networking, Services, or Logs

### Later — secure recovery

Wi-Fi provisioning and other privileged BLE operations are deliberately deferred until authentication/authorization is designed and reviewed.

## Important design rules

- v0.1 BLE is read-only.
- NetworkManager is the authoritative network-management source.
- BLE and Cockpit consume one normalized Management Core.
- The first IP returned by the OS is **not** assumed to be the correct address.
- Bridges/bonds may own valid addresses; container/veth interfaces should not clutter the primary UI.
- No generic shell-over-BLE endpoint.
- No arbitrary systemd-control-over-BLE endpoint.
- Passwords, tokens, and Wi-Fi credentials must never appear in BLE status or journald.

## Web Bluetooth limitation

The browser client must be loaded from an HTTPS secure origin. For v0.1, a new phone needs network access once to load/cache the CodePC Link PWA. After that, the cached PWA can communicate with the mini-PC over BLE even when the mini-PC has no Internet connection.

The initial browser target is **Android + Chrome/Chromium Web Bluetooth**. A native iOS client is a future option if browser-only Web Bluetooth remains unavailable there.

## Repository layout

```text
assets/                 Project artwork
src/codepc_link/        Python daemon/CLI package (currently scaffold only)
tests/                   Automated tests
docs/                    Architecture, roadmap, and release checklists
site/                    GitHub Pages / future Web Bluetooth PWA origin
.github/workflows/       CI, Pages, and tag-driven release automation
```

## Development

```bash
git clone https://github.com/ami3go/codepc-link.git
cd codepc-link
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
ruff check src tests
pytest
```

The development CLI currently exists only as a scaffold:

```bash
codepc-link --version
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Complications / release checklist](docs/COMPLICATIONS_CHECKLIST.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Release procedure](RELEASING.md)
- [Recommended repository settings](docs/REPOSITORY_SETTINGS.md)

Project site: **https://ami3go.github.io/codepc-link/**

## Releases

Tags matching `v*.*.*` trigger the GitHub Release workflow. See [RELEASING.md](RELEASING.md).

## Security

Please do not report vulnerabilities in public issues. See [SECURITY.md](SECURITY.md) for the private reporting path and project security boundaries.

## License

CodePC Link is released under the [MIT License](LICENSE).
