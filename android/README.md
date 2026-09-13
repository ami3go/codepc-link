# CodePC Link Android client

Native Android client for CodePC Link over Bluetooth Classic RFCOMM.

## Current scope

- Kotlin + Jetpack Compose
- uses already-paired Bluetooth devices; pair the CodePC in Android settings first
- connects to the CodePC Link RFCOMM service UUID `0330ce6c-09db-5189-b7ad-e16bcafac7ee`
- sends the existing newline-delimited `status` request
- displays hostname, interfaces, addresses, default-route/Internet state, and Cockpit state
- opens Cockpit over the phone's normal IP network
- remembers the last selected Bluetooth device
- no background service, polling loop, cloud backend, or Android-side RFCOMM server

## Build

Open the `android/` directory in Android Studio. Use JDK 17. The project targets Android 16 / API 36 and supports Android 8.0+.

The project intentionally does not commit a Gradle wrapper binary yet. Android Studio can sync the project using an installed compatible Gradle version; a wrapper can be generated later with:

```bash
gradle wrapper
```

## Test

1. Start the CodePC RFCOMM server:

   ```bash
   codepc-link serve-rfcomm \
     --state-dir ~/.local/state/codepc-link \
     --verbose
   ```

2. Pair the Android device with the CodePC in Android Bluetooth settings.
3. Install/run the app from Android Studio.
4. Grant the Bluetooth permission on Android 12+.
5. Select the paired CodePC and tap **Connect**.
6. The app connects using the custom CodePC Link UUID, sends:

   ```json
   {"schema":1,"op":"status"}
   ```

7. Verify the displayed addresses match `codepc-link status --json` on the CodePC.
8. Tap **Open Cockpit** for a reachable address.

## Security

The Linux RFCOMM profile remains authoritative. In default mode it requires Bluetooth authentication and authorization. The Android app does not bypass pairing or trust checks.
