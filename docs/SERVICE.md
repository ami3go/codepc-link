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

The production state directory `/var/lib/codepc-link` is intentionally owned by the systemd service. Do not `chown` it to a development user. For source/virtual-environment work, use one persistent per-user state directory for every CodePC Link command:

```bash
export CODEPC_LINK_STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/codepc-link"
mkdir -p "$CODEPC_LINK_STATE_DIR"

codepc-link status
codepc-link serve --insecure-development --verbose
```

This keeps the development device UUID stable while preserving the production service ownership and permissions. `--state-dir PATH` remains available when a one-command override is preferred.

## Security defaults

The service:

- runs with `DynamicUser=yes`
- gets a persistent private state directory via `StateDirectory=codepc-link`
- has no Linux capabilities
- has no direct device access
- limits address families to `AF_UNIX` because Bluetooth access is through BlueZ D-Bus
- uses a read-only system filesystem apart from the managed state directory
- starts BLE characteristics with encrypted reads enabled
- registers a BlueZ `org.bluez.Agent1` with `NoInputNoOutput` capability for headless Just Works pairing

The persistent device ID is therefore stored through systemd's state-directory mechanism and survives service restarts.

### Built-in pairing agent

Encrypted GATT reads require BlueZ to establish an encrypted link. A headless CodePC must not depend on a GNOME/KDE `bluetoothctl` agent being present, so secure `codepc-link serve` now registers its own agent at `/org/codepc/link/agent0` and requests it as BlueZ's default agent while the server is running.

The agent uses `NoInputNoOutput`, which maps the current read-only v0.1 service to Bluetooth Just Works pairing. It accepts incoming Just Works authorization and confirmation callbacks, rejects pairing flows that require local PIN/passkey input, and only authorizes the CodePC Link management service when BlueZ asks for service authorization.

This provides link encryption but not MITM-authenticated pairing. That is acceptable only for the current read-only status surface. Privileged BLE writes remain blocked until a stronger authorization and confirmation design is implemented.

The agent is unregistered during normal shutdown or startup rollback. `--insecure-development` skips pairing-agent registration because its characteristics use plain `read` rather than `encrypt-read`.

## Verbose diagnostics

For interactive bring-up, enable staged server diagnostics:

```bash
codepc-link serve --verbose
```

The log records the current `server.stage`, including system D-Bus connection, GATT object creation/export, BlueZ adapter introspection, pairing-agent registration, GATT application registration, advertisement registration, pairing callbacks, characteristic reads, and cleanup. If startup fails, the CLI reports the exact stage where it failed.

A healthy secure startup now includes stages similar to:

```text
server.stage=resolve-agent-manager
server.stage=register-pairing-agent
ble.pairing agent registered ... capability=NoInputNoOutput default=true
server.stage=register-gatt-application
server.stage=register-advertisement
server.stage=ready
```

During an incoming Just Works pairing attempt, verbose logging can include:

```text
ble.pairing Just Works authorization accepted device=/org/bluez/hci0/dev_...
ble.pairing confirmation accepted device=/org/bluez/hci0/dev_... passkey=......
```

Use a second `-v` only when D-Bus library detail is needed:

```bash
codepc-link serve -vv
```

`-vv` enables `dbus-next` debug logging and can be substantially noisier. BLE-derived payload contents are not dumped; verbose reads log characteristic UUID, offsets, payload size, and returned byte count so diagnostics do not unnecessarily copy network-status data into logs.

When running under systemd, normal Python logging is captured by journald. To temporarily run the packaged service with verbose diagnostics, use a systemd override rather than editing the packaged unit:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/codepc-link serve --verbose
```

Then inspect it with:

```bash
journalctl -u codepc-link.service -f
```

Remove the override after troubleshooting.

## BlueZ restart behavior

The unit is `PartOf=bluetooth.service`, so an explicit `systemctl restart bluetooth.service` also restarts CodePC Link and re-registers its pairing agent, GATT application, and advertisement.

This behavior must still be verified on the target mini-PC. Unexpected BlueZ crashes/restarts are part of the hardware/integration test matrix and may require an additional D-Bus owner-change watchdog if the target system does not propagate the restart as expected.

## Development-only unencrypted reads

For hardware bring-up only:

```bash
codepc-link serve --insecure-development
```

Combine it with verbose diagnostics when debugging GATT discovery or reads:

```bash
codepc-link serve --insecure-development --verbose
```

Do not put `--insecure-development` in the production systemd unit.
