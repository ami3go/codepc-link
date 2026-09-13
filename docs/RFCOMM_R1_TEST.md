# RFCOMM R1 hardware test

Use this checklist on the real CodePC and an Android phone before promoting RFCOMM beyond the feasibility branch.

## CodePC

```bash
git switch feat/rfcomm-webserial
git pull
python -m pip install -e '.[dev]'
mkdir -p ~/.local/state/codepc-link
```

First run the RFCOMM-specific doctor checks:

```bash
codepc-link doctor --transport rfcomm
```

The important RFCOMM checks are:

```text
[PASS   ] profile_manager: ProfileManager1 available
[PASS   ] bredr_support: btmgmt reports BR/EDR support
```

Then start the prototype:

```bash
codepc-link serve-rfcomm \
  --state-dir ~/.local/state/codepc-link \
  --verbose
```

A successful startup reaches:

```text
rfcomm.server.stage=register-profile
rfcomm.server.stage=ready
```

If startup fails, repeat with `-vv` and capture the first failing stage and BlueZ error.

## Pair the phone

Pair the Android phone with the CodePC using normal Bluetooth settings or `bluetoothctl`. For controlled testing with `bluetoothctl`:

```text
power on
pairable on
agent on
default-agent
scan on
```

Pair and trust the phone once its Bluetooth address appears.

## Browser

Use Android Chrome 138 or later and open the RFCOMM prototype from an HTTPS deployment. Select **Choose RFCOMM service**. The chooser should expose the CodePC Link Bluetooth serial service identified by UUID:

```text
0330ce6c-09db-5189-b7ad-e16bcafac7ee
```

The page sends:

```json
{"schema":1,"op":"status"}
```

and should display the returned schema-v1 host status plus candidate Cockpit URLs.

## Pass criteria

- `codepc-link doctor --transport rfcomm` passes `ProfileManager1` and BR/EDR capability checks.
- BlueZ accepts and registers the RFCOMM profile.
- Chrome can select and open the custom Bluetooth service.
- One `status` request returns valid JSON.
- The reported network interface/address matches `codepc-link status --json` on the CodePC.
- A candidate Cockpit target opens over the phone's normal IP network.
- Disconnect then reconnect succeeds at least five times.
- Unpairing the phone prevents the secure profile from being used until pairing is restored.

Do not merge RFCOMM into the production systemd path until these checks are recorded.
