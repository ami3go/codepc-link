# CodePC Link Web Client

Milestone C provides the v0.1 browser client at the project's GitHub Pages HTTPS origin. The web client consumes the frozen BLE protocol v1; it does not duplicate NetworkManager normalization logic.

## Supported path

The v0.1 validation target is **Android Chrome/Chromium with Web Bluetooth support**.

Web Bluetooth is a limited-availability API and requires a secure context. CodePC Link therefore treats the GitHub Pages HTTPS site (or another HTTPS deployment of `site/`) as the application origin.

Authoritative API references:

- MDN Web Bluetooth API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API
- Chrome Web Bluetooth guide: https://developer.chrome.com/docs/capabilities/bluetooth
- MDN `Bluetooth.getDevices()`: https://developer.mozilla.org/en-US/docs/Web/API/Bluetooth/getDevices

CodePC Link v0.1 does **not** claim Safari/iOS support. A native iOS client remains a future option if Web Bluetooth is unavailable for the browser/runtime in use.

## Permission and connection flow

1. Open the CodePC Link HTTPS PWA.
2. Press **Choose CodePC Link**.
3. The page calls `navigator.bluetooth.requestDevice()` from that user gesture.
4. The chooser is filtered to the permanent CodePC Link management service UUID.
5. After permission is granted, the page connects to GATT and reads `SYSTEM_INFO` and `NETWORK_STATUS`.
6. The page validates `schema: 1` before displaying data.

A cancelled chooser is not treated as a daemon failure.

When the browser implements `navigator.bluetooth.getDevices()`, previously permitted devices are displayed as reconnect buttons after a page reload. `getDevices()` only means this origin has permission to refer to the device; it does not prove that the device is powered on, in range, advertising, or currently connectable.

An unexpected `gattserverdisconnected` event leaves the last rendered status visible but marks the connection as disconnected. Reconnect is explicit; the page does not run an uncontrolled reconnect loop.

## What the UI shows

The client preserves the backend's normalized distinctions:

- interface name/type
- link state
- every reported address
- default-route state
- Internet state
- Wi-Fi SSID/signal when available
- partial collector errors

No BLE-provided string is inserted using `innerHTML`; values are rendered as text nodes.

## Cockpit targets

For each usable reported IP address the browser client creates a candidate URL of the form:

```text
https://<address>:<cockpit-port>/
```

IPv6 addresses are bracketed. Unscoped link-local IPv6 addresses are shown but not turned into links because schema v1 does not carry the interface scope required for a correct URL.

A displayed Cockpit link is **not a reachability promise**. BLE only tells the phone what the mini-PC reported. The phone must still have a valid IP route to that address.

TLS validation is also independent from BLE. Opening Cockpit by raw IP may produce a browser certificate warning when the Cockpit certificate is not trusted for that IP address. CodePC Link must not suppress or work around browser TLS validation.

## Offline behavior

The first visit cannot be fully offline: the browser must load the HTTPS application shell and install its service worker at least once.

After the app shell has been cached, the service worker can load these same-origin resources without Internet access:

- HTML
- CSS
- PWA manifest
- project icon
- protocol/client JavaScript modules

The BLE path itself does not require Internet access. A cached/installed PWA can therefore read CodePC Link status while the mini-PC or phone has no Internet route, subject to the browser still permitting Web Bluetooth.

The app does not persist BLE status into IndexedDB/localStorage in v0.1. The most recent read remains visible only in the current page session and is labelled with its read time.

## Safe web-client updates

The service worker uses a versioned app-shell cache.

A newly installed worker does **not** immediately call `skipWaiting()`. This avoids activating new JavaScript underneath an older open HTML page. When a new worker is waiting, the client shows an **Update and reload** banner. Activating that button asks the new worker to take over, then reloads once after `controllerchange`.

Old versioned caches are removed during activation.

## Security and privacy boundaries

- v0.1 has no BLE write operation.
- production GATT reads require the encrypted-link policy defined in `PROTOCOL.md`.
- BLE status can contain local IP addresses, hostname, and Wi-Fi SSID; treat it as local administrative information.
- the static Pages client contains no analytics/telemetry code.
- Cockpit credentials and traffic never pass through BLE or through the CodePC Link Pages origin.
- no certificate bypass, generic shell, or arbitrary systemd control is exposed.

## Manual Android validation matrix

Run this only after the target mini-PC passes the Milestone B hardware gates.

- [ ] First visit over HTTPS loads the client
- [ ] Web Bluetooth support/availability state is reported correctly
- [ ] Device chooser shows the CodePC Link peripheral
- [ ] Cancelled chooser is handled cleanly
- [ ] Production encrypted-read pairing succeeds
- [ ] `SYSTEM_INFO` renders device identity/version/Cockpit state
- [ ] `NETWORK_STATUS` renders Wi-Fi + Ethernet simultaneously
- [ ] Response larger than one ATT packet is read correctly
- [ ] Multiple addresses on one interface are all shown
- [ ] Default route and Internet badges reflect the backend independently
- [ ] Cockpit links use correct IPv4/IPv6 syntax
- [ ] An unreachable candidate fails as normal IP navigation, without corrupting BLE state
- [ ] GATT disconnect changes UI state
- [ ] Reconnect works without a new chooser when `getDevices()` permission is retained
- [ ] Page reload preserves permission when the browser retains it
- [ ] Installed/cached PWA opens with Internet disabled
- [ ] Offline PWA can still establish BLE and refresh status
- [ ] Service-worker update waits and activates through the update banner

Record the Android version, Chrome version, device model, and outcome in the integration issue before declaring v0.1 validated.
