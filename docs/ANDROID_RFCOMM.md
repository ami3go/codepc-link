# Android RFCOMM app prototype

This branch keeps the Linux BlueZ RFCOMM server from the Web Serial spike and adds a native Android client. The Android app is now the primary experiment; Web Serial remains in the branch only as a comparison path until the native test succeeds.

## Architecture

```text
CodePC mini                                      Android app
-----------------------------                   -----------------------------
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

## Android project

The native project is under `android/` and intentionally uses platform Android APIs only:

- Kotlin with AGP built-in Kotlin support.
- `BluetoothDevice.createRfcommSocketToServiceRecord()` for a secure authenticated RFCOMM connection.
- `BLUETOOTH_CONNECT` on Android 12+.
- Paired devices only for the first prototype; pairing is done in Android Bluetooth settings.
- No Bluetooth scan permission is required because the app does not perform discovery.
- One newline-delimited JSON request/response at a time.

## Build

The repository has an Android workflow that installs the required Gradle version and builds a debug APK. Locally, open `android/` in Android Studio or use Gradle 9.6 with JDK 17:

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
codepc-link serve-rfcomm --state-dir ~/.local/state/codepc-link --verbose
```

A healthy server reaches `rfcomm.server.stage=ready`.

On Android:

1. Pair the phone with CodePC in normal Bluetooth settings.
2. Install the debug APK.
3. Grant the Nearby devices / Bluetooth connection permission when requested.
4. Tap **Choose paired PC** and select CodePC.
5. Tap **Connect**.
6. Tap **Request status**.
7. Verify the hostname and network addresses match `codepc-link status --json` on the PC.
8. Tap **Open Cockpit** and verify the selected IP reaches Cockpit over the phone's normal IP network.

## R1 native-app pass criteria

- Android can establish the secure RFCOMM socket using the custom CodePC service UUID.
- Status request/response succeeds repeatedly without `/dev/rfcomm0` on Linux.
- Disconnect/reconnect succeeds at least five times.
- Unpaired devices cannot use the secure RFCOMM profile.
- CodePC reboot and Bluetooth service restart behavior are understood.
- The app can select the correct CodePC when more than one PC is paired.

Do not add a foreground service, background reconnect loop, or periodic status push until the foreground request/response path is proven on real hardware.
