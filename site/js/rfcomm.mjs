import {
  RFCOMM_SERVICE_UUID,
  SCHEMA_VERSION,
  validateNetworkStatus,
  validateSystemInfo,
} from "./protocol.mjs";

export const RFCOMM_BAUD_RATE = 115200;
export const RFCOMM_RESPONSE_TIMEOUT_MS = 10000;
export const RFCOMM_MAX_RESPONSE_BYTES = 256 * 1024;

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object`);
  }
}

export function isCodePcRfcommPort(port) {
  if (!port || typeof port.getInfo !== "function") return false;
  const info = port.getInfo() || {};
  return (
    typeof info.bluetoothServiceClassId === "string" &&
    info.bluetoothServiceClassId.toLowerCase() === RFCOMM_SERVICE_UUID
  );
}

export function encodeStatusRequest() {
  return new TextEncoder().encode(
    `${JSON.stringify({ schema: SCHEMA_VERSION, op: "status" })}\n`,
  );
}

export function adaptStatusDocument(status, readAt = new Date()) {
  assertObject(status, "RFCOMM status");
  if (status.schema !== SCHEMA_VERSION) {
    throw new Error(`Unsupported RFCOMM status schema ${String(status.schema)}`);
  }
  assertObject(status.device, "RFCOMM status.device");
  assertObject(status.network, "RFCOMM status.network");
  assertObject(status.cockpit, "RFCOMM status.cockpit");

  const errors = Array.isArray(status.errors) ? status.errors : [];
  const systemInfo = validateSystemInfo({
    schema: SCHEMA_VERSION,
    device: status.device,
    cockpit: status.cockpit,
    errors: errors.filter((error) =>
      ["identity", "system"].includes(String(error?.component || "")),
    ),
  });
  const networkStatus = validateNetworkStatus({
    schema: SCHEMA_VERSION,
    network: status.network,
    errors: errors.filter((error) => error?.component === "network"),
  });

  return {
    systemInfo,
    networkStatus,
    rawStatus: status,
    readAt,
  };
}

export function decodeStatusResponse(line, readAt = new Date()) {
  let response;
  try {
    response = JSON.parse(line);
  } catch (error) {
    throw new Error("CodePC Link returned invalid JSON over RFCOMM", { cause: error });
  }

  assertObject(response, "RFCOMM response");
  if (response.schema !== SCHEMA_VERSION) {
    throw new Error(`Unsupported RFCOMM response schema ${String(response.schema)}`);
  }
  if (response.ok !== true) {
    const code = response.error?.code || "RFCOMM_ERROR";
    const message = response.error?.message || "CodePC Link rejected the RFCOMM request";
    throw new Error(`${code}: ${message}`);
  }
  if (response.op !== "status") {
    throw new Error(`Unexpected RFCOMM response operation ${String(response.op)}`);
  }

  return adaptStatusDocument(response.status, readAt);
}

function appendBytes(left, right) {
  if (left.byteLength === 0) return new Uint8Array(right);
  const joined = new Uint8Array(left.byteLength + right.byteLength);
  joined.set(left, 0);
  joined.set(right, left.byteLength);
  return joined;
}

async function readLine(reader, timeoutMs, state) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`RFCOMM status response timed out after ${timeoutMs} ms`)),
      timeoutMs,
    );
  });

  try {
    while (true) {
      const newline = state.buffer.indexOf(0x0a);
      if (newline >= 0) {
        const line = state.buffer.slice(0, newline);
        state.buffer = state.buffer.slice(newline + 1);
        return new TextDecoder("utf-8", { fatal: true }).decode(line).trim();
      }

      if (state.buffer.byteLength > RFCOMM_MAX_RESPONSE_BYTES) {
        throw new Error(`RFCOMM response exceeds ${RFCOMM_MAX_RESPONSE_BYTES} bytes`);
      }

      const { value, done } = await Promise.race([reader.read(), timeout]);
      if (done) throw new Error("RFCOMM connection closed before a complete response arrived");
      if (!(value instanceof Uint8Array)) {
        throw new TypeError("Web Serial returned a non-byte RFCOMM chunk");
      }

      state.buffer = appendBytes(state.buffer, value);
    }
  } finally {
    clearTimeout(timer);
  }
}

export class CodePcRfcommClient extends EventTarget {
  constructor(serial = globalThis.navigator?.serial) {
    super();
    this.serial = serial;
    this.port = null;
    this._readState = { buffer: new Uint8Array() };
    this._statusInFlight = false;
    this._boundDisconnect = (event) => this._onDisconnect(event);
    if (this.serial?.addEventListener) {
      this.serial.addEventListener("disconnect", this._boundDisconnect);
    }
  }

  get supported() {
    return Boolean(this.serial && typeof this.serial.requestPort === "function");
  }

  get connected() {
    return Boolean(this.port?.readable && this.port?.writable);
  }

  async getRememberedPorts() {
    if (!this.supported || typeof this.serial.getPorts !== "function") return [];
    const ports = await this.serial.getPorts();
    return ports.filter(isCodePcRfcommPort);
  }

  async requestPort() {
    if (!this.supported) {
      throw new Error("Web Serial is not available in this browser.");
    }

    const port = await this.serial.requestPort({
      allowedBluetoothServiceClassIds: [RFCOMM_SERVICE_UUID],
      filters: [{ bluetoothServiceClassId: RFCOMM_SERVICE_UUID }],
    });
    await this.connect(port);
    return port;
  }

  async connect(port) {
    if (!port || typeof port.open !== "function") {
      throw new TypeError("Selected Web Serial port is invalid.");
    }
    if (!isCodePcRfcommPort(port)) {
      throw new Error("Selected serial port is not the CodePC Link RFCOMM service.");
    }

    if (this.port && this.port !== port && this.connected) {
      await this.disconnect();
    }
    if (this.port !== port) {
      this._resetReadState();
    }
    this.port = port;

    if (!this.connected) {
      await port.open({ baudRate: RFCOMM_BAUD_RATE });
    }
    if (!port.readable || !port.writable) {
      throw new Error("CodePC Link RFCOMM port opened without readable/writable streams.");
    }

    this.dispatchEvent(new Event("connect"));
    return port;
  }

  async reconnect() {
    if (!this.port) {
      throw new Error("No previously selected CodePC Link RFCOMM port is available.");
    }
    return this.connect(this.port);
  }

  async readStatus({ timeoutMs = RFCOMM_RESPONSE_TIMEOUT_MS } = {}) {
    if (!this.connected) {
      throw new Error("CodePC Link RFCOMM is not connected.");
    }
    if (this._statusInFlight) {
      throw new Error("An RFCOMM status request is already in progress.");
    }

    this._statusInFlight = true;
    try {
      const writer = this.port.writable.getWriter();
      try {
        await writer.write(encodeStatusRequest());
      } finally {
        writer.releaseLock();
      }

      const reader = this.port.readable.getReader();
      try {
        const line = await readLine(reader, timeoutMs, this._readState);
        const status = decodeStatusResponse(line);
        this.dispatchEvent(new Event("status"));
        return status;
      } catch (error) {
        this._resetReadState();
        try {
          await reader.cancel(error);
        } catch {
          // The stream may already be closed after a radio disconnect.
        }
        throw error;
      } finally {
        reader.releaseLock();
      }
    } finally {
      this._statusInFlight = false;
    }
  }

  async disconnect() {
    const port = this.port;
    if (!port) return;

    try {
      if (port.readable || port.writable) await port.close();
    } finally {
      this._resetReadState();
      this.dispatchEvent(new Event("disconnect"));
    }
  }

  _resetReadState() {
    this._readState.buffer = new Uint8Array();
  }

  _onDisconnect(event) {
    const disconnectedPort = event.port || event.target;
    if (disconnectedPort !== this.port) return;
    this._resetReadState();
    this.dispatchEvent(new Event("disconnect"));
  }
}
