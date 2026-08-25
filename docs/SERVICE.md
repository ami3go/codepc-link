# CodePC Link systemd service

Milestone B includes a hardened service template at `packaging/systemd/codepc-link.service`.

## Development installation

After installing the Python package so `codepc-link` is available at `/usr/bin/codepc-link`:

```bash
sudo install -m 0644 packaging/systemd/codepc-link.service \
  /usr/lib/systemd/system/codepc-link.service
sudo systemctl daemon-reload
sudo systemctl enable --now codepc-link.service
```

For source/virtual-environment testing, run `codepc-link serve` directly instead of modifying the production unit path.

## Security defaults

The service:

- runs with `DynamicUser=yes`
- gets a persistent private state directory via `StateDirectory=codepc-link`
- has no Linux capabilities
- has no direct device access
- limits address families to `AF_UNIX` because Bluetooth access is through BlueZ D-Bus
- uses a read-only system filesystem apart from the managed state directory
- starts BLE characteristics with encrypted reads enabled

The persistent device ID is therefore stored through systemd's state-directory mechanism and survives service restarts.

## BlueZ restart behavior

The unit is `PartOf=bluetooth.service`, so an explicit `systemctl restart bluetooth.service` also restarts CodePC Link and re-registers its GATT application/advertisement.

This behavior must still be verified on the target mini-PC. Unexpected BlueZ crashes/restarts are part of the hardware/integration test matrix and may require an additional D-Bus owner-change watchdog if the target system does not propagate the restart as expected.

## Development-only unencrypted reads

For hardware bring-up only:

```bash
codepc-link serve --insecure-development
```

Do not put this flag in the production systemd unit.
