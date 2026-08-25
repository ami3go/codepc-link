import assert from "node:assert/strict";
import test from "node:test";

import { CodePcBluetoothClient } from "../site/js/bluetooth.mjs";
import {
  MANAGEMENT_SERVICE_UUID,
  NETWORK_STATUS_CHARACTERISTIC_UUID,
  SYSTEM_INFO_CHARACTERISTIC_UUID,
} from "../site/js/protocol.mjs";

function valueFor(document) {
  const bytes = new TextEncoder().encode(JSON.stringify(document));
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

class FakeCharacteristic {
  constructor(document) {
    this.document = document;
    this.readCount = 0;
  }

  async readValue() {
    this.readCount += 1;
    return valueFor(this.document);
  }
}

class FakeService {
  constructor(systemCharacteristic, networkCharacteristic) {
    this.characteristics = new Map([
      [SYSTEM_INFO_CHARACTERISTIC_UUID, systemCharacteristic],
      [NETWORK_STATUS_CHARACTERISTIC_UUID, networkCharacteristic],
    ]);
  }

  async getCharacteristic(uuid) {
    const characteristic = this.characteristics.get(uuid);
    if (!characteristic) throw new Error(`Unknown characteristic ${uuid}`);
    return characteristic;
  }
}

class FakeDevice extends EventTarget {
  constructor(service) {
    super();
    this.name = "CodePC Link - testbox";
    this.service = service;
    this.gatt = {
      connected: false,
      connect: async () => {
        this.gatt.connected = true;
        return this.gatt;
      },
      getPrimaryService: async (uuid) => {
        assert.equal(uuid, MANAGEMENT_SERVICE_UUID);
        return this.service;
      },
      disconnect: () => {
        this.gatt.connected = false;
        this.dispatchEvent(new Event("gattserverdisconnected"));
      },
    };
  }
}

class FakeBluetooth {
  constructor(device) {
    this.device = device;
    this.lastRequestOptions = null;
  }

  async getAvailability() {
    return true;
  }

  async getDevices() {
    return [this.device];
  }

  async requestDevice(options) {
    this.lastRequestOptions = options;
    return this.device;
  }
}

function fixture() {
  const systemCharacteristic = new FakeCharacteristic({
    schema: 1,
    device: { id: "abc", name: "CodePC Link - testbox", hostname: "testbox", version: "0.1.0" },
    cockpit: { port: 9090, available: true },
    errors: [],
  });
  const networkCharacteristic = new FakeCharacteristic({
    schema: 1,
    network: {
      internet: true,
      default_route_interfaces: ["wlan0"],
      interfaces: [{ name: "wlan0", type: "wifi", link: "up", addresses: ["192.168.1.10/24"], default_route: true, internet: true }],
    },
    errors: [],
  });
  const service = new FakeService(systemCharacteristic, networkCharacteristic);
  const device = new FakeDevice(service);
  const bluetooth = new FakeBluetooth(device);
  return { systemCharacteristic, networkCharacteristic, device, bluetooth };
}

test("device chooser is filtered to the permanent management service", async () => {
  const { bluetooth } = fixture();
  const client = new CodePcBluetoothClient(bluetooth);

  await client.requestDevice();

  assert.deepEqual(bluetooth.lastRequestOptions.filters, [{ services: [MANAGEMENT_SERVICE_UUID] }]);
  assert.deepEqual(bluetooth.lastRequestOptions.optionalServices, [MANAGEMENT_SERVICE_UUID]);
  assert.equal(client.connected, true);
});

test("status reads both protocol-v1 characteristics", async () => {
  const { bluetooth, device, systemCharacteristic, networkCharacteristic } = fixture();
  const client = new CodePcBluetoothClient(bluetooth);

  const status = await client.connect(device);

  assert.equal(status.systemInfo.device.hostname, "testbox");
  assert.equal(status.networkStatus.network.interfaces[0].name, "wlan0");
  assert.equal(systemCharacteristic.readCount, 1);
  assert.equal(networkCharacteristic.readCount, 1);
  assert.ok(status.readAt instanceof Date);
});

test("remembered devices can be enumerated without opening a chooser", async () => {
  const { bluetooth, device } = fixture();
  const client = new CodePcBluetoothClient(bluetooth);

  assert.deepEqual(await client.getRememberedDevices(), [device]);
  assert.equal(bluetooth.lastRequestOptions, null);
});

test("disconnect clears the active GATT handles and emits a disconnect event", async () => {
  const { bluetooth, device } = fixture();
  const client = new CodePcBluetoothClient(bluetooth);
  let disconnectEvents = 0;
  client.addEventListener("disconnect", () => { disconnectEvents += 1; });

  await client.connect(device);
  client.disconnect();

  assert.equal(client.connected, false);
  assert.equal(client.server, null);
  assert.equal(client.service, null);
  assert.equal(disconnectEvents, 1);
});
