# Android RFCOMM app and Cockpit pairing

This branch uses Bluetooth Classic RFCOMM with a native Android client. The first Bluetooth pairing is deliberately initiated from the CodePC side, not from the Android app.

## Pairing policy

The always-on CodePC Link agent rejects unsolicited first-pair requests. The Cockpit page launches a short-lived BlueZ pairing agent for exactly one administrator-selected device, pairs it, and marks it trusted. The Android app only lists Android devices that are already bonded and does not expose a Pair button or open Bluetooth settings for pairing.

The intended first-pair flow is:

```text
Android phone                         CodePC / Cockpit
-------------                         ----------------
Open Pair new device screen           Open CodePC Link page
Become discoverable              <-   Scan for phones
                                      Select phone
Confirm Android pairing prompt   <-   Pair from CodePC
Bond stored on Android                 Bond + Trusted stored in BlueZ
Open CodePC Link app                   RFCOMM server already running
Choose paired CodePC             ->   authenticated RFCOMM connection
Request status                   ->   schema-v1 CodePC status
Open Cockpit over IP
```

Do not select the CodePC from Android's Pair new device list during the first pair. Android only needs to be discoverable so the CodePC can find it.

## Install the Python package

Install CodePC Link system-wide so Cockpit elevation can find both commands:

```bash
python -m pip install .
command -v codepc-link
command -v codepc-link-bt
```

For a development checkout, use an environment/install method that makes `codepc-link-bt` visible in the root/elevated PATH used by Cockpit.

## Install the Cockpit page

From the repository root:

```bash
sudo sh packaging/install-cockpit-plugin.sh
```

Reload Cockpit. A **CodePC Link** item should appear in the Cockpit menu.

The page uses Cockpit privilege escalation for Bluetooth management and calls only argument-array commands; it does not construct a shell command from device names or addresses.

## Pair a phone from Cockpit

1. On Android, open Bluetooth settings and enter **Pair new device** so the phone is discoverable.
2. In Cockpit, open **CodePC Link**.
3. Click **Scan for phones**.
4. Find the phone by name/MAC address.
5. Click **Pair from CodePC**.
6. Confirm the Android pairing prompt if Android presents one.
7. The device should return as **Paired** and **Trusted**.

The pairing controller also disables BlueZ's `Pairable` property before scanning/pairing. That blocks normal remote-initiated first pairing while CodePC Link is managing the adapter. Local `Device1.Pair()` is still used for the selected phone.

## Run the RFCOMM server

For source-checkout testing:

```bash
mkdir -p ~/.local/state/codepc-link
codepc-link serve-rfcomm \
  --state-dir ~/.local/state/codepc-link \
  --verbose
```

The server uses the CodePC Link RFCOMM UUID:

```text
0330ce6c-09db-5189-b7ad-e16bcafac7ee
```

## Android app

The Android project is under `android/`. Build locally with a compatible Android SDK/Gradle installation or use the `Android RFCOMM` GitHub Actions workflow.

The app requests only Bluetooth connection permission on Android 12+. It does not request discovery/scan permission because device discovery and first pairing are handled on the CodePC.

After installation:

1. Open CodePC Link.
2. Grant Bluetooth connection permission.
3. Tap **Choose paired CodePC**.
4. Select the CodePC.
5. Tap **Connect**.
6. Tap **Request status**.
7. Use **Open Cockpit** when a suitable IP address is returned.

The selected paired CodePC address is remembered for subsequent app launches.

## Remove pairing

Use **Remove pairing** from the Cockpit CodePC Link page. The Android app will then be unable to reconnect until the device is paired again from the server side.
