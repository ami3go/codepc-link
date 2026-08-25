# Milestone A — Feasibility

Milestone A proves that the target mini-PC can act as a BLE peripheral/GATT server before the project commits to the full BLE protocol implementation.

## 1. Install the development build

On the target mini-PC:

```bash
git clone https://github.com/ami3go/codepc-link.git
cd codepc-link
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## 2. Run the automated host check

```bash
codepc-link doctor
```

For the complete machine-readable record:

```bash
codepc-link doctor --json
```

To save the result for an issue or test record:

```bash
codepc-link doctor --output codepc-link-feasibility.json
```

A failing check exits with status `2`. A successful host-level feasibility result exits with status `0`.

## What the doctor checks

The report records:

- Linux distribution and version
- kernel and CPU architecture
- Python version
- BlueZ version
- NetworkManager version
- Cockpit version where available
- `bluetooth.service` state
- `NetworkManager.service` state
- `cockpit.socket` state
- detected `hci*` Bluetooth adapters
- Bluetooth rfkill state
- `btmgmt` LE/advertising capability flags when available
- BlueZ `org.bluez.LEAdvertisingManager1`
- BlueZ `org.bluez.GattManager1`

The two BlueZ manager interfaces are particularly important: CodePC Link needs the advertising manager to register advertisements and the GATT manager to register the application service.

## 3. Manual host tests

The automated report does not replace real adapter behavior tests.

Run these on the target system and record the result:

- [ ] Bluetooth can be enabled after an rfkill soft block
- [ ] adapter survives a normal disable/enable cycle
- [ ] adapter returns after `bluetooth.service` restart
- [ ] adapter returns after suspend/resume if suspend is a supported deployment mode
- [ ] BlueZ still exposes advertising and GATT manager interfaces after recovery

Do not intentionally reset production hardware remotely unless you have another recovery path.

## 4. Android discovery test

Milestone A is not complete until a real Android phone sees an advertisement from the target mini-PC.

Start the temporary feasibility advertiser:

```bash
codepc-link advertise-test
```

It advertises the local name `CodePC Link` on `hci0` until Ctrl-C. To use another adapter or a timed run:

```bash
codepc-link advertise-test --adapter hci1 --seconds 60
```

This command is intentionally only a feasibility probe. It does not use the final CodePC Link service UUIDs and it does not expose GATT status data yet.

Acceptance test:

1. Run `codepc-link doctor` and confirm no Bluetooth host blocker is reported.
2. Run `codepc-link advertise-test` on the mini-PC.
3. Open a BLE scanner on Android.
4. Confirm `CodePC Link` is visible.
5. Stop the test advertiser.
6. Restart `bluetooth.service` on the mini-PC.
7. Run `codepc-link doctor` again.
8. Start the advertiser again and confirm Android can rediscover it.

## Milestone A exit criteria

- [ ] target software versions are recorded
- [ ] `codepc-link doctor` reports no host-level blockers
- [ ] BLE LE + advertising capability is available
- [ ] BlueZ exposes `LEAdvertisingManager1`
- [ ] BlueZ exposes `GattManager1`
- [ ] rfkill/restart behavior is understood
- [ ] Android can discover a CodePC Link test advertisement

Only after these checks pass should Milestone B freeze the production UUIDs/schema and build the stable BLE service.
