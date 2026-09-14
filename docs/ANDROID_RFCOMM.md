# Android RFCOMM app prototype

This branch keeps the Linux BlueZ RFCOMM server and adds a native Android client. The Android app is the primary client experiment. Initial Bluetooth pairing is deliberately initiated from the CodePC Cockpit GUI, not from the Android app.

## Architecture

```text
CodePC mini                                      Android app
-----------------------------                   -----------------------------
Cockpit CodePC Link page
        |
        +---- scan / Pair from CodePC --------> Android pairing confirmation
        |
codepc-link Management Core                     CodePC Link
        |                                               |
        v                                               v
BlueZ Profile1 RFCOMM server  <---- paired BT ----> BluetoothSocket
UUID 0330ce6c-09db-5189-b7ad-e16bcafac7ee        createRfcommSocketToServiceRecord()
        |                                               |
        +---- {"schema":1,"op":"status"}\n <----------+
        +---- schema-v1 status JSON\n -------------------->+
                                                        |
                                                        +---- Open Cockpit IP
```

The PC remains the RFCOMM server and Android is the client. This avoids `/dev/rfcomm0`, shell polling, a hard-coded client-side RFCOMM channel, and periodic push traffic. Android performs SDP lookup using the custom service UUID and requests status only when needed.

The first app version runs only while visible. It does **not** use a foreground service yet. Background reconnect/monitoring can be added later if there is a real requirement for it.

## Pairing model

The first Bluetooth bond must originate on CodePC:

- Android opens its normal **Pair new device** screen only to become discoverable.
- Cockpit scans for nearby Bluetooth Classic devices.
- The administrator selects the phone and starts **Pair from CodePC**.
- A temporary BlueZ pairing agent is registered by the same process that calls `Device1.Pair()`, so BlueZ uses that targeted agent for the locally initiated pair.
- The agent accepts only the selected BlueZ device path and the CodePC Link RFCOMM service.
- After a successful bond the phone is marked `Trusted` in BlueZ.
- The Android application itself only enumerates already-bonded devices and has no Pair action.
- The always-on CodePC Link agent rejects unsolicited incoming first-pair requests.

See `ANDROID_RFCOMM_PAIRING.md` for the detailed Cockpit installation and test procedure.

## Android project

The native project is under `android/`, supports Android 6.0 (API 23) and later,
and intentionally uses platform Android APIs only:

- Kotlin with AGP built-in Kotlin support.
- `BluetoothDevice.createRfcommSocketToServiceRecord()` for a secure authenticated RFCOMM connection.
- `BLUETOOTH_CONNECT` on Android 12+.
- Bonded devices only; discovery and pairing are handled by CodePC/Cockpit.
- No Bluetooth scan permission is required by the app.
- One newline-delimited JSON request/response at a time.
- The selected CodePC Bluetooth address is remembered for later launches.

## Build

The repository has an Android workflow that builds a debug APK against Android API 36. Locally, open `android/` in Android Studio or use Gradle 9.7.1 with JDK 17:

```bash
gradle -p android :app:assembleDebug
```

The APK is produced at:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## First hardware test

On CodePC:

```bash
git switch feat/android-rfcomm-app
git pull
python -m pip install -e '.[dev]'
mkdir -p ~/.local/state/codepc-link
codepc-link doctor --transport rfcomm
sudo sh packaging/install-rfcomm-service.sh
sudo sh packaging/install-cockpit-plugin.sh
```

In Cockpit, enable **Keep RFCOMM server alive**. A healthy service reaches
`rfcomm.server.stage=ready`; systemd restarts it automatically if it exits. For
a foreground development run instead, leave keep-alive disabled and run:

```bash
codepc-link serve-rfcomm --state-dir ~/.local/state/codepc-link --verbose
```

For a pairing test, `doctor --transport rfcomm` also reports
`profile_isolation`. A warning means the same physical adapter is advertising
desktop audio, hands-free, phonebook, messaging, or file-transfer profiles in
addition to CodePC Link. Android may consequently present unrelated audio,
call, or contact-sharing options. Use a dedicated adapter, or temporarily
disable those desktop integrations, when validating the CodePC RFCOMM path.

Then pair from Cockpit:

1. On Android, open **Pair new device** so the phone is discoverable; do not initiate pairing with CodePC from Android.
2. Open Cockpit → **CodePC Link**.
3. Click **Scan for phones**.
4. Select the phone and click **Pair from CodePC**.
5. Confirm the Android system pairing prompt if shown.
6. Verify the Cockpit page shows the phone as **Paired** and **Trusted**.

Then test the app:

1. Install the debug APK.
2. Grant the Nearby devices / Bluetooth connection permission when requested.
3. Tap **Choose paired CodePC** and select CodePC.
4. Tap **Connect**.
5. Tap **Request status**.
6. Verify the hostname and network addresses match `codepc-link status --json` on the PC.
7. Open the **Cockpit** tab and verify the selected IP reaches Cockpit over the phone's normal IP network.
8. For a self-signed Cockpit certificate, compare the displayed fingerprint and explicitly approve it for the current app session. The app never silently bypasses TLS errors.

The embedded Cockpit tab requires a current Android System WebView. Older Android
devices may need the WebView component updated from Google Play before Cockpit's
current JavaScript can load. **Open externally** remains available as a fallback.

## R1 native-app pass criteria

- The first pair can be initiated from Cockpit and cannot be initiated by the CodePC Link Android app.
- Android can establish the secure RFCOMM socket using the custom CodePC service UUID after pairing.
- Status request/response succeeds repeatedly without `/dev/rfcomm0` on Linux.
- Disconnect/reconnect succeeds at least five times.
- Removing the pairing in Cockpit prevents the Android app from reconnecting until server-side pairing is repeated.
- CodePC reboot and Bluetooth service restart behavior are understood.
- The app can select the correct CodePC when more than one PC is paired.

Do not add a foreground service, background reconnect loop, or periodic status push until the foreground request/response path is proven on real hardware.
