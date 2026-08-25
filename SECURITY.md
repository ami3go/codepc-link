# Security Policy

CodePC Link is intended to expose local system and network status over Bluetooth Low Energy and later may support narrowly scoped recovery actions. Security therefore matters from the first release.

## Supported versions

The project is pre-1.0. Security fixes are applied to the latest development/release line unless a release note states otherwise.

## Reporting a vulnerability

Please do **not** open a public issue for a suspected vulnerability, credential leak, authentication bypass, or unsafe privileged operation.

Use the repository's GitHub **Security Advisories** private reporting flow when available. If private reporting is not enabled, contact the repository owner privately through an established channel before publishing details.

Include:

- affected version/commit
- environment and platform
- reproduction steps
- impact assessment
- suggested mitigation, if known

## Security boundaries

For v0.1:

- BLE is read-only.
- No generic shell interface is allowed.
- No arbitrary systemd-control interface is allowed.
- Wi-Fi passwords, tokens, and secrets must never be emitted in BLE status or journald.
- Production BLE read/pairing policy must be documented before release.

Privileged BLE writes require a separate authenticated and authorized design review before implementation.
