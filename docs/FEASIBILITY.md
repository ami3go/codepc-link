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

The next implementation step will add the minimal CodePC Link test advertisement. The acceptance test is:

1. Start the CodePC Link test advertiser on the mini-PC.
2. Open a BLE scanner on Android.
3. Confirm the advertised local name/service is visible.
4. Stop and restart Bluetooth on the mini-PC.
5. Confirm advertising can be restored.

## Milestone A exit criteria

- [ ] target software versions are recorded
- [ ] `codepc-link doctor` reports no host-level blockers
- [ ] BLE LE + advertising capability is available
- [ ] BlueZ exposes `LEAdvertisingManager1`
- [ ] BlueZ exposes `GattManager1`
- [ ] rfkill/restart behavior is understood
- [ ] Android can discover a CodePC Link test advertisement

Only after these checks pass should Milestone B freeze the production UUIDs/schema and build the stable BLE service.
