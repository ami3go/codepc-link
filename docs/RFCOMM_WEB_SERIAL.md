# RFCOMM + Web Serial prototype

This branch evaluates Bluetooth Classic RFCOMM as an alternative transport for
CodePC Link. The management core remains authoritative; only the Bluetooth
transport changes.

## Prototype contract

- BlueZ profile UUID: `0330ce6c-09db-5189-b7ad-e16bcafac7ee`
- Default RFCOMM channel: `22`
- Profile name: `CodePC Link`
- Production/default mode requires Bluetooth authentication and authorization.
- The transport is request/response, not a periodic push service.
- Messages are UTF-8 JSON, one document per line (`\n`).
- Requests are limited to 4096 bytes.

The first supported request is:

```json
{"schema":1,"op":"status"}
```

A successful response is:

```json
{"schema":1,"ok":true,"op":"status","status":{"schema":1}}
```

The `status` object is the same document produced by `codepc-link status --json`.
Protocol errors are returned as structured JSON with `ok:false` and an error code.

## Run the Linux prototype

Use a writable development state directory when running from a source checkout:

```bash
mkdir -p ~/.local/state/codepc-link
codepc-link serve-rfcomm \
  --state-dir ~/.local/state/codepc-link \
  --verbose
```

For D-Bus-level diagnostics, repeat the verbose flag:

```bash
codepc-link serve-rfcomm \
  --state-dir ~/.local/state/codepc-link \
  -vv
```

The default profile uses RFCOMM channel 22. If another local service already owns
that channel, select a different channel from 1 through 30 with `--channel`.

An insecure mode exists only for isolated feasibility testing:

```bash
codepc-link serve-rfcomm \
  --state-dir ~/.local/state/codepc-link \
  --insecure-development \
  --verbose
```

Do not use insecure mode for deployment.

## Pairing

The secure profile registers the existing headless CodePC Link BlueZ pairing
agent and authorizes only CodePC Link service UUIDs. Pairing can also be done
before starting the server with `bluetoothctl`. For a pre-paired phone, mark the
device trusted when testing authorization behavior.

## Android Chrome / Web Serial test

The browser client is the next slice of this prototype. It should request a
Bluetooth serial port filtered by the RFCOMM service UUID:

```js
const serviceUuid = "0330ce6c-09db-5189-b7ad-e16bcafac7ee";

const port = await navigator.serial.requestPort({
  allowedBluetoothServiceClassIds: [serviceUuid],
  filters: [{ bluetoothServiceClassId: serviceUuid }],
});

await port.open({ baudRate: 115200 });
```

The baud rate is part of the Web Serial API contract; RFCOMM itself is carrying
the byte stream.

The client then writes one line:

```text
{"schema":1,"op":"status"}\n
```

and reads one JSON line in response.

## R1 feasibility gate

Before RFCOMM is integrated into the production systemd service, validate on the
real CodePC and Android device that:

1. BlueZ registers the vendor RFCOMM profile and SDP service.
2. Android Chrome can discover/select the service through Web Serial.
3. A `status` request returns the current CodePC status document.
4. The browser can construct and open a valid Cockpit target from that status.
5. Disconnect/reconnect works repeatedly.
6. Reboot and BlueZ-restart behavior are understood.
7. Unpaired/unauthorized clients are rejected in secure mode.

The prototype intentionally keeps RFCOMM separate from the existing BLE GATT
server until those checks pass.
