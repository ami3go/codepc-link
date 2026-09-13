<p align="center">
  <img src="assets/codepc-link-icon.svg" width="180" alt="CodePC Link icon">
</p>

<h1 align="center">CodePC Link</h1>

<p align="center">
  BLE/RFCOMM discovery, network-status, and recovery companion for headless Linux mini-PC systems managed with Cockpit.
</p>

<p align="center">
  <a href="https://github.com/ami3go/codepc-link/actions/workflows/ci.yml"><img src="https://github.com/ami3go/codepc-link/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/ami3go/codepc-link/releases"><img src="https://img.shields.io/github/v/release/ami3go/codepc-link?include_prereleases&sort=semver" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/ami3go/codepc-link" alt="MIT License"></a>
</p>

> **Status:** pre-alpha. BLE and RFCOMM transport prototypes are implemented. The current Android experiment uses a native RFCOMM client and a Cockpit page that initiates the first Bluetooth pairing from the CodePC side. Real mini-PC + Android validation remains required before release.

## What CodePC Link is for

A headless mini-PC can be connected to more than one network at once—for example Wi-Fi for Internet access and Ethernet for isolated local services. When you are standing next to the machine, discovering the correct current IP can be awkward.

CodePC Link adds a small out-of-band Bluetooth path so a nearby phone can identify the machine and read useful network status without already knowing an IP address.

The current native Android prototype flow is:

```text
Cockpit on CodePC
       │
       │ initiate first Bluetooth pair
       ▼
Android phone
       │
       │ paired Bluetooth Classic / RFCOMM
       ▼
CodePC Link
       │
       │ schema-v1 status
       ▼
Android app chooses reachable IP
       │
       │ normal IP network
       ▼
Cockpit
```

Bluetooth is for discovery, diagnostics, and recovery. **Cockpit itself is not tunnelled over Bluetooth.**

See `docs/ANDROID_RFCOMM_PAIRING.md` for the current pairing and test flow.

## Current transport work

The repository currently contains:

- persistent device identity in `/var/lib/codepc-link/device-id`
- schema-v1 normalized status shared by CLI and Bluetooth transports
- NetworkManager-backed Wi-Fi/Ethernet/bridge/bond normalization
- separate link, address, default-route, and Internet states
- BLE GATT read-only status prototype
- Bluetooth Classic RFCOMM read-only status prototype
- native Android RFCOMM client under `android/`
- Cockpit Bluetooth pairing package under `cockpit/codepc-link/`
- server-side `codepc-link-bt` pairing control CLI
- first-pair policy that rejects unsolicited phone-initiated pairing

The Android/Cockpit RFCOMM path remains experimental until validated on the real CodePC and phone.
