import assert from "node:assert/strict";
import test from "node:test";

import {
  MANAGEMENT_SERVICE_UUID,
  NETWORK_STATUS_CHARACTERISTIC_UUID,
  SYSTEM_INFO_CHARACTERISTIC_UUID,
  addressWithoutPrefix,
  buildCockpitTargets,
  buildCockpitUrl,
  decodeJsonValue,
  validateNetworkStatus,
  validateSystemInfo,
} from "../site/js/protocol.mjs";

function dataViewFor(document, prefixBytes = 0) {
  const encoded = new TextEncoder().encode(JSON.stringify(document));
  const bytes = new Uint8Array(encoded.byteLength + prefixBytes + 2);
  bytes.set(encoded, prefixBytes);
  return new DataView(bytes.buffer, prefixBytes, encoded.byteLength);
}

const systemInfo = {
  schema: 1,
  device: {
    id: "5e8e2ba4-2a08-42bf-b68a-7e256812240d",
    name: "CodePC Link - nucbox5",
    hostname: "nucbox5",
    version: "0.1.0",
  },
  cockpit: { port: 9090, available: true },
  errors: [],
};

const networkStatus = {
  schema: 1,
  network: {
    internet: true,
    default_route_interfaces: ["wlan0"],
    interfaces: [
      {
        name: "enp2s0",
        type: "ethernet",
        link: "up",
        addresses: ["10.10.10.1/24"],
        default_route: false,
        internet: false,
      },
      {
        name: "wlan0",
        type: "wifi",
        link: "up",
        addresses: ["192.168.1.73/24", "2001:db8::73/64", "fe80::12/64"],
        default_route: true,
        internet: true,
      },
    ],
  },
  errors: [],
};

test("protocol UUIDs stay on the frozen v1 values", () => {
  assert.equal(MANAGEMENT_SERVICE_UUID, "78561c99-7412-45b5-84b6-4ef7062fe7d0");
  assert.equal(SYSTEM_INFO_CHARACTERISTIC_UUID, "83cf19fa-bf46-4fc9-8366-321b545c4bf4");
  assert.equal(NETWORK_STATUS_CHARACTERISTIC_UUID, "6ef6c725-99f8-4533-bd85-874453f28af3");
});

test("JSON decoding respects a DataView byte offset", () => {
  assert.deepEqual(decodeJsonValue(dataViewFor(systemInfo, 7)), systemInfo);
});

test("schema validators reject unknown versions", () => {
  assert.throws(() => validateSystemInfo({ ...systemInfo, schema: 2 }), /Unsupported SYSTEM_INFO schema 2/);
  assert.throws(
    () => validateNetworkStatus({ ...networkStatus, schema: 2 }),
    /Unsupported NETWORK_STATUS schema 2/,
  );
});

test("address helpers preserve IPv6 while removing CIDR prefixes", () => {
  assert.equal(addressWithoutPrefix("192.168.1.73/24"), "192.168.1.73");
  assert.equal(addressWithoutPrefix("2001:db8::73/64"), "2001:db8::73");
  assert.equal(buildCockpitUrl("192.168.1.73/24", 9090), "https://192.168.1.73:9090/");
  assert.equal(buildCockpitUrl("2001:db8::73/64", 9090), "https://[2001:db8::73]:9090/");
});

test("unscoped link-local IPv6 does not create a misleading Cockpit URL", () => {
  assert.equal(buildCockpitUrl("fe80::12/64", 9090), null);
});

test("Cockpit targets prefer default-route/Internet candidates without hiding others", () => {
  const targets = buildCockpitTargets(systemInfo, networkStatus);

  assert.equal(targets.length, 4);
  assert.equal(targets[0].interfaceName, "wlan0");
  assert.equal(targets[0].defaultRoute, true);
  assert.equal(targets[0].internet, true);
  assert.ok(targets.some((target) => target.host === "10.10.10.1"));
  assert.equal(targets.find((target) => target.host === "fe80::12")?.url, null);
});

test("invalid Cockpit ports are rejected rather than interpolated into a URL", () => {
  assert.throws(() => buildCockpitUrl("192.168.1.2/24", 0), /Invalid Cockpit port/);
  assert.throws(() => buildCockpitUrl("192.168.1.2/24", "9090/path"), /Invalid Cockpit port/);
});
