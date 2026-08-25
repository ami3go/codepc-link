import {
  MANAGEMENT_SERVICE_UUID,
  NETWORK_STATUS_CHARACTERISTIC_UUID,
  SYSTEM_INFO_CHARACTERISTIC_UUID,
  readNetworkStatus,
  readSystemInfo,
} from "./protocol.mjs";

export class CodePcBluetoothClient extends EventTarget {
  constructor(bluetooth = globalThis.navigator?.bluetooth) {
    super();
    this.bluetooth = bluetooth;
    this.device = null;
    this.server = null;
    this.service = null;
    this.systemInfoCharacteristic = null;
    this.networkStatusCharacteristic = null;
    this._boundDisconnect = () => this._handleDisconnect();
  }

  get supported() {
    return Boolean(this.bluetooth && typeof this.bluetooth.requestDevice === "function");
  }

  get connected() {
    return Boolean(this.device?.gatt?.connected && this.server);
  }

  async getAvailability() {
    if (!this.supported) return false;
    if (typeof this.bluetooth.getAvailability !== "function") return true;
    return Boolean(await this.bluetooth.getAvailability());
  }

  async requestDevice() {
    if (!this.supported) {
      throw new Error("Web Bluetooth is not available in this browser.");
    }

    const device = await this.bluetooth.requestDevice({
      filters: [{ services: [MANAGEMENT_SERVICE_UUID] }],
      optionalServices: [MANAGEMENT_SERVICE_UUID],
    });
    await this.connect(device);
    return device;
  }

  async getRememberedDevices() {
    if (!this.supported || typeof this.bluetooth.getDevices !== "function") return [];
    const devices = await this.bluetooth.getDevices();
    return devices.filter((device) => Boolean(device?.gatt));
  }

  async connect(device) {
    if (!device?.gatt) {
      throw new TypeError("Selected Bluetooth device does not expose a GATT server.");
    }

    if (this.device && this.device !== device) {
      this.device.removeEventListener("gattserverdisconnected", this._boundDisconnect);
    }

    this.device = device;
    this.device.removeEventListener("gattserverdisconnected", this._boundDisconnect);
    this.device.addEventListener("gattserverdisconnected", this._boundDisconnect);

    this.server = device.gatt.connected ? device.gatt : await device.gatt.connect();
    this.service = await this.server.getPrimaryService(MANAGEMENT_SERVICE_UUID);
    [this.systemInfoCharacteristic, this.networkStatusCharacteristic] = await Promise.all([
      this.service.getCharacteristic(SYSTEM_INFO_CHARACTERISTIC_UUID),
      this.service.getCharacteristic(NETWORK_STATUS_CHARACTERISTIC_UUID),
    ]);

    this.dispatchEvent(new Event("connect"));
    return this.readStatus();
  }

  async reconnect() {
    if (!this.device) {
      throw new Error("No previously selected CodePC Link device is available.");
    }
    return this.connect(this.device);
  }

  async readStatus() {
    if (!this.connected || !this.systemInfoCharacteristic || !this.networkStatusCharacteristic) {
      throw new Error("CodePC Link is not connected.");
    }

    const [systemValue, networkValue] = await Promise.all([
      this.systemInfoCharacteristic.readValue(),
      this.networkStatusCharacteristic.readValue(),
    ]);

    const status = {
      systemInfo: readSystemInfo(systemValue),
      networkStatus: readNetworkStatus(networkValue),
      readAt: new Date(),
    };
    this.dispatchEvent(new Event("status"));
    return status;
  }

  disconnect() {
    if (this.device?.gatt?.connected) this.device.gatt.disconnect();
    else this._handleDisconnect();
  }

  _handleDisconnect() {
    this.server = null;
    this.service = null;
    this.systemInfoCharacteristic = null;
    this.networkStatusCharacteristic = null;
    this.dispatchEvent(new Event("disconnect"));
  }
}
