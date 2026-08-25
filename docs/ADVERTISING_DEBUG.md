# BLE Advertising Debugging

Use this checklist when `codepc-link doctor` passes but a phone cannot see the advertisement.

## Important: Android Settings is not a BLE scanner

Android's normal **Settings → Bluetooth** UI may omit BLE-only peripherals. For validation, use a BLE scanner such as nRF Connect or LightBlue, or the CodePC Link Web Bluetooth PWA once the production service is running.

## Run the feasibility advertisement

```bash
codepc-link advertise-test --seconds 60
```

The probe advertises:

- local name: `CodePC Link`
- CodePC Link management service UUID: `78561c99-7412-45b5-84b6-4ef7062fe7d0`
- peripheral/general-discoverable mode

## Verify BlueZ has an active advertisement

While `advertise-test` is still running, open a second terminal:

```bash
busctl get-property \
  org.bluez \
  /org/bluez/hci0 \
  org.bluez.LEAdvertisingManager1 \
  ActiveInstances
```

Expected: a value greater than zero.

Also inspect the controller:

```bash
bluetoothctl show
sudo btmgmt info
```

Check that the adapter is powered and advertising is supported.

## If ActiveInstances is zero

Capture the terminal output from `codepc-link advertise-test` plus:

```bash
journalctl -u bluetooth.service --since '5 minutes ago' --no-pager
```

That indicates a BlueZ/controller registration problem rather than a phone-side scan problem.

## If ActiveInstances is non-zero but the phone sees nothing

Use a true BLE scanner and search by either:

- name: `CodePC Link`
- service UUID: `78561c99-7412-45b5-84b6-4ef7062fe7d0`

If it still does not appear, test from another nearby BLE-capable device and record the adapter/controller details from `btmgmt info`.
