export const SCHEMA_VERSION = 1;
export const MANAGEMENT_SERVICE_UUID = "78561c99-7412-45b5-84b6-4ef7062fe7d0";
export const SYSTEM_INFO_CHARACTERISTIC_UUID = "83cf19fa-bf46-4fc9-8366-321b545c4bf4";
export const NETWORK_STATUS_CHARACTERISTIC_UUID = "6ef6c725-99f8-4533-bd85-874453f28af3";

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object`);
  }
}

export function decodeJsonValue(value) {
  if (!(value instanceof DataView)) {
    throw new TypeError("Bluetooth characteristic value must be a DataView");
  }

  const bytes = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  return JSON.parse(text);
}

export function validateSystemInfo(document) {
  assertObject(document, "SYSTEM_INFO");
  if (document.schema !== SCHEMA_VERSION) {
    throw new Error(`Unsupported SYSTEM_INFO schema ${String(document.schema)}`);
  }
  assertObject(document.device, "SYSTEM_INFO.device");
  assertObject(document.cockpit, "SYSTEM_INFO.cockpit");

  return document;
}

export function validateNetworkStatus(document) {
  assertObject(document, "NETWORK_STATUS");
  if (document.schema !== SCHEMA_VERSION) {
    throw new Error(`Unsupported NETWORK_STATUS schema ${String(document.schema)}`);
  }
  assertObject(document.network, "NETWORK_STATUS.network");
  if (!Array.isArray(document.network.interfaces)) {
    throw new TypeError("NETWORK_STATUS.network.interfaces must be an array");
  }

  return document;
}

export function readSystemInfo(value) {
  return validateSystemInfo(decodeJsonValue(value));
}

export function readNetworkStatus(value) {
  return validateNetworkStatus(decodeJsonValue(value));
}

export function addressWithoutPrefix(address) {
  if (typeof address !== "string") return "";
  const trimmed = address.trim();
  const slash = trimmed.indexOf("/");
  return slash >= 0 ? trimmed.slice(0, slash) : trimmed;
}

function isLinkLocalIpv6(address) {
  return address.toLowerCase().startsWith("fe80:");
}

function isUnusableHost(address) {
  return (
    !address ||
    address === "0.0.0.0" ||
    address === "::" ||
    address.startsWith("127.") ||
    address === "::1"
  );
}

function isIpv4(address) {
  const parts = address.split(".");
  return (
    parts.length === 4 &&
    parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) >= 0 && Number(part) <= 255)
  );
}

function isIpv6(address) {
  if (!address.includes(":") || !/^[0-9a-f:.]+$/i.test(address)) return false;
  try {
    // URL parsing gives us a compact standards-backed syntax check without
    // accepting hostnames or URL metacharacters from BLE-provided data.
    new URL(`https://[${address}]/`);
    return true;
  } catch {
    return false;
  }
}

export function buildCockpitUrl(address, port = 9090) {
  const host = addressWithoutPrefix(address);
  if (isUnusableHost(host)) return null;

  // Schema v1 does not carry the interface scope required for a reliable
  // link-local IPv6 URL, so show the address but do not make it clickable.
  if (isLinkLocalIpv6(host)) return null;
  if (!isIpv4(host) && !isIpv6(host)) return null;

  const safePort = Number(port);
  if (!Number.isInteger(safePort) || safePort < 1 || safePort > 65535) {
    throw new RangeError(`Invalid Cockpit port ${String(port)}`);
  }

  const urlHost = host.includes(":") ? `[${host}]` : host;
  return `https://${urlHost}:${safePort}/`;
}

export function buildCockpitTargets(systemInfo, networkStatus) {
  validateSystemInfo(systemInfo);
  validateNetworkStatus(networkStatus);

  const port = Number(systemInfo.cockpit.port || 9090);
  const targets = [];

  for (const iface of networkStatus.network.interfaces) {
    if (!iface || typeof iface !== "object") continue;
    for (const address of iface.addresses || []) {
      const host = addressWithoutPrefix(address);
      if (!host) continue;

      let url = null;
      try {
        url = buildCockpitUrl(address, port);
      } catch {
        // A malformed backend port should not stop the rest of the BLE status
        // from rendering. The candidate remains visible without a link.
      }

      targets.push({
        interfaceName: String(iface.name || "unknown"),
        interfaceType: String(iface.type || "unknown"),
        address: String(address),
        host,
        url,
        defaultRoute: Boolean(iface.default_route),
        internet: iface.internet === true,
      });
    }
  }

  targets.sort((left, right) => {
    if (left.defaultRoute !== right.defaultRoute) return left.defaultRoute ? -1 : 1;
    if (left.internet !== right.internet) return left.internet ? -1 : 1;
    return left.interfaceName.localeCompare(right.interfaceName) || left.host.localeCompare(right.host);
  });

  return targets;
}

export function describeError(error) {
  if (typeof DOMException !== "undefined" && error instanceof DOMException) {
    if (error.name === "NotFoundError") return "No device was selected.";
    if (error.name === "SecurityError") return "Bluetooth permission was denied or the page is not in a secure context.";
    if (error.name === "NetworkError") return "The Bluetooth connection was lost.";
  }
  return error instanceof Error ? error.message : String(error);
}
