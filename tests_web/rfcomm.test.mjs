import assert from "node:assert/strict";
import test from "node:test";

import {
  CodePcRfcommClient,
  RFCOMM_BAUD_RATE,
  adaptStatusDocument,
  decodeStatusResponse,
  encodeStatusRequest,
  isCodePcRfcommPort,
} from "../site/js/rfcomm.mjs";
import { RFCOMM_SERVICE_UUID } from "../site/js/protocol.mjs";

function statusDocument() {
  return {
    schema: 1,
    generated_at: "2026-09-13T10:00:00+00:00",
    device: {
      id: "test-device",
      name: "CodePC Link - test",
      hostname: "codepc-test",
      version: "0.0.0.dev0",
    },
    network: {
      interfaces: [
        {
          name: "enp2s0",
          type: "ethernet",
          link: "up",
          addresses: ["192.168.31.198/24"],
          default_route: true,
          internet: true,
        },
      ],
    },
    cockpit: { port: 9090, available: true },
    errors: [],
  };
}

test("RFCOMM status request is newline-delimited schema-v1 JSON", () => {
  const request = new TextDecoder().decode(encodeStatusRequest());
  assert.equal(request, '{"schema":1,"op":"status"}\n');
});

test("RFCOMM port filtering requires the custom service UUID", () => {
  assert.equal(
    isCodePcRfcommPort({
      getInfo: () => ({ bluetoothServiceClassId: RFCOMM_SERVICE_UUID.toUpperCase() }),
    }),
    true,
  );
  assert.equal(
    isCodePcRfcommPort({
      getInfo: () => ({ bluetoothServiceClassId: "00001101-0000-1000-8000-00805f9b34fb" }),
    }),
    false,
  );
});

test("full RFCOMM status adapts to the existing BLE-shaped renderer contract", () => {
  const readAt = new Date("2026-09-13T10:01:00Z");
  const adapted = adaptStatusDocument(statusDocument(), readAt);
  assert.equal(adapted.systemInfo.device.hostname, "codepc-test");
  assert.equal(adapted.networkStatus.network.interfaces[0].name, "enp2s0");
  assert.equal(adapted.rawStatus.cockpit.port, 9090);
  assert.equal(adapted.readAt, readAt);
});

test("structured RFCOMM error becomes a client error", () => {
  assert.throws(
    () =>
      decodeStatusResponse(
        JSON.stringify({
          schema: 1,
          ok: false,
          error: { code: "UNSUPPORTED_OPERATION", message: "supported operation: status" },
        }),
      ),
    /UNSUPPORTED_OPERATION/,
  );
});

test("client filters requestPort and exchanges a status line", async () => {
  const writes = [];
  const response = new TextEncoder().encode(
    `${JSON.stringify({ schema: 1, ok: true, op: "status", status: statusDocument() })}\n`,
  );

  const port = {
    readable: null,
    writable: null,
    getInfo() {
      return { bluetoothServiceClassId: RFCOMM_SERVICE_UUID };
    },
    async open(options) {
      assert.deepEqual(options, { baudRate: RFCOMM_BAUD_RATE });
      this.readable = new ReadableStream({
        start(controller) {
          controller.enqueue(response.subarray(0, 17));
          controller.enqueue(response.subarray(17));
        },
      });
      this.writable = new WritableStream({
        write(chunk) {
          writes.push(new Uint8Array(chunk));
        },
      });
    },
    async close() {
      this.readable = null;
      this.writable = null;
    },
  };

  let chooserOptions = null;
  const serial = new EventTarget();
  serial.requestPort = async (options) => {
    chooserOptions = options;
    return port;
  };
  serial.getPorts = async () => [port];

  const client = new CodePcRfcommClient(serial);
  await client.requestPort();
  assert.deepEqual(chooserOptions, {
    allowedBluetoothServiceClassIds: [RFCOMM_SERVICE_UUID],
    filters: [{ bluetoothServiceClassId: RFCOMM_SERVICE_UUID }],
  });

  const status = await client.readStatus({ timeoutMs: 1000 });
  assert.equal(status.systemInfo.device.hostname, "codepc-test");
  assert.equal(new TextDecoder().decode(writes[0]), '{"schema":1,"op":"status"}\n');

  const remembered = await client.getRememberedPorts();
  assert.deepEqual(remembered, [port]);
  await client.disconnect();
});
