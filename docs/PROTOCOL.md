# CodePC Link BLE Protocol v1

This document freezes the initial read-only CodePC Link BLE contract. Changes that break these UUIDs or JSON meanings require a new protocol/schema version.

## Service and characteristic UUIDs

| Role | UUID |
|---|---|
| CodePC Link Management service | `78561c99-7412-45b5-84b6-4ef7062fe7d0` |
| `SYSTEM_INFO` | `83cf19fa-bf46-4fc9-8366-321b545c4bf4` |
| `NETWORK_STATUS` | `6ef6c725-99f8-4533-bd85-874453f28af3` |
| Reserved `EVENT` notification | `5b45ee1f-060f-48db-9fa4-b0096115967d` |

The event characteristic UUID is reserved for a later release. v0.1 does not require notifications.

## Encoding

Characteristics return compact UTF-8 JSON. Every document contains:

```json
{"schema":1}
```

Clients must reject schema versions they do not understand.

Maximum serialized characteristic size is **16 KiB**. The server implements BlueZ `ReadValue` offset semantics so clients can perform GATT long reads instead of assuming the entire JSON document fits in one ATT packet or negotiated MTU.

## Production read security

Production characteristics use the BlueZ `encrypt-read` flag. This requires an encrypted BLE link/pairing before status is readable.

An explicit development mode may use plain `read` while bringing up hardware, but it must not be the production default.

CodePC Link v0.1 exposes no BLE write characteristic.

## `SYSTEM_INFO`

Example:

```json
{
  "schema": 1,
  "device": {
    "id": "5e8e2ba4-2a08-42bf-b68a-7e256812240d",
    "name": "CodePC Link - nucbox5",
    "hostname": "nucbox5",
    "version": "0.1.0"
  },
  "cockpit": {
    "port": 9090,
    "available": true
  },
  "errors": []
}
```

`device.id` is persistent and is not derived from the current IP address. The display name and hostname may change without changing the stable identity.

## `NETWORK_STATUS`

Example for Wi-Fi Internet plus isolated Ethernet:

```json
{
  "schema": 1,
  "network": {
    "internet": true,
    "default_route_interfaces": ["wlan0"],
    "interfaces": [
      {
        "name": "enp2s0",
        "type": "ethernet",
        "managed": true,
        "link": "up",
        "addresses": ["10.10.10.1/24"],
        "gateway": null,
        "default_route": false,
        "internet": false
      },
      {
        "name": "wlan0",
        "type": "wifi",
        "managed": true,
        "link": "up",
        "addresses": ["192.168.1.73/24"],
        "gateway": "192.168.1.1",
        "default_route": true,
        "internet": true,
        "ssid": "HomeNetwork",
        "signal": 78
      }
    ]
  },
  "errors": []
}
```

`link`, `addresses`, `default_route`, and `internet` are deliberately separate. A default route is not proof of Internet connectivity.

The primary UI should hide transient container/veth and VPN interfaces by default, but useful administrator-facing bridges/bonds are retained.

## Partial failures

Collectors return useful partial data when possible. Errors use stable machine-readable codes:

```json
{
  "component": "network",
  "code": "NM_UNAVAILABLE",
  "message": "NetworkManager is unavailable"
}
```

The presence of an error does not automatically invalidate unrelated fields.

## Local management contract

`codepc-link status --json` returns the complete normalized schema-v1 status used by both BLE and the future Cockpit Management page. Frontends must not independently duplicate NetworkManager normalization logic.
