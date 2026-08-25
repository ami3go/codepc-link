import { CodePcBluetoothClient } from "./bluetooth.mjs";
import { buildCockpitTargets, describeError } from "./protocol.mjs";

const APP_VERSION = "0.1.0-dev";
const client = new CodePcBluetoothClient();
let lastStatus = null;
let busy = false;
let installPrompt = null;
let reloadForWorkerUpdate = false;

const ui = {
  connect: document.querySelector("#connect-button"),
  disconnect: document.querySelector("#disconnect-button"),
  refresh: document.querySelector("#refresh-button"),
  remembered: document.querySelector("#remembered-devices"),
  browserStatus: document.querySelector("#browser-status"),
  connectionStatus: document.querySelector("#connection-status"),
  offlineStatus: document.querySelector("#offline-status"),
  deviceSection: document.querySelector("#device-section"),
  deviceName: document.querySelector("#device-name"),
  deviceMeta: document.querySelector("#device-meta"),
  lastUpdated: document.querySelector("#last-updated"),
  interfaces: document.querySelector("#interfaces"),
  cockpitTargets: document.querySelector("#cockpit-targets"),
  cockpitState: document.querySelector("#cockpit-state"),
  errors: document.querySelector("#errors"),
  errorSection: document.querySelector("#error-section"),
  updateBanner: document.querySelector("#update-banner"),
  updateButton: document.querySelector("#update-button"),
  installButton: document.querySelector("#install-button"),
  appVersion: document.querySelector("#app-version"),
};

ui.appVersion.textContent = APP_VERSION;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function badge(text, tone = "neutral") {
  const node = element("span", "badge", text);
  node.dataset.tone = tone;
  return node;
}

function setBusy(value) {
  busy = value;
  updateControls();
}

function setConnection(text, tone = "neutral") {
  ui.connectionStatus.textContent = text;
  ui.connectionStatus.dataset.tone = tone;
}

function updateControls() {
  const connected = client.connected;
  ui.connect.disabled = busy || !client.supported;
  ui.disconnect.disabled = busy || !connected;
  ui.refresh.disabled = busy || !connected;
}

function updateOnlineState() {
  const online = navigator.onLine;
  ui.offlineStatus.textContent = online ? "App shell online" : "Offline app shell";
  ui.offlineStatus.dataset.tone = online ? "positive" : "warning";
}

function renderErrors(systemInfo, networkStatus) {
  const errors = [...(systemInfo.errors || []), ...(networkStatus.errors || [])];
  ui.errors.replaceChildren();
  ui.errorSection.hidden = errors.length === 0;

  for (const error of errors) {
    const item = element("li", "error-item");
    item.append(
      element("strong", "", String(error.code || "UNKNOWN")),
      document.createTextNode(` — ${String(error.message || "No detail")}`),
    );
    ui.errors.append(item);
  }
}

function renderInterfaces(networkStatus) {
  const interfaces = networkStatus.network.interfaces || [];
  ui.interfaces.replaceChildren();

  if (interfaces.length === 0) {
    ui.interfaces.append(element("p", "empty-state", "No administrator-facing network interfaces were reported."));
    return;
  }

  for (const iface of interfaces) {
    const card = element("article", "interface-card");
    const header = element("div", "interface-header");
    const title = element("div");
    title.append(
      element("h3", "interface-name", String(iface.name || "Unknown interface")),
      element("p", "interface-type", String(iface.type || "unknown")),
    );

    const badges = element("div", "badge-row");
    badges.append(badge(iface.link === "up" ? "Link up" : String(iface.link || "Link unknown"), iface.link === "up" ? "positive" : "neutral"));
    if (iface.default_route) badges.append(badge("Default route", "accent"));
    if (iface.internet === true) badges.append(badge("Internet", "positive"));
    if (iface.internet === false && iface.default_route) badges.append(badge("No Internet", "warning"));
    header.append(title, badges);
    card.append(header);

    if (iface.ssid) {
      const wifi = element("p", "interface-detail", `Wi-Fi: ${String(iface.ssid)}`);
      if (Number.isFinite(iface.signal)) wifi.append(document.createTextNode(` · ${iface.signal}% signal`));
      card.append(wifi);
    }

    if (iface.gateway) card.append(element("p", "interface-detail", `Gateway: ${String(iface.gateway)}`));

    const addresses = element("div", "address-list");
    const values = Array.isArray(iface.addresses) ? iface.addresses : [];
    if (values.length === 0) {
      addresses.append(element("span", "address muted", "No address"));
    } else {
      for (const address of values) addresses.append(element("code", "address", String(address)));
    }
    card.append(addresses);
    ui.interfaces.append(card);
  }
}

function renderCockpit(systemInfo, networkStatus) {
  const available = systemInfo.cockpit.available;
  if (available === true) {
    ui.cockpitState.textContent = "Cockpit socket is reported active on the mini-PC. This does not prove this phone can reach every address below.";
  } else if (available === false) {
    ui.cockpitState.textContent = "Cockpit socket is reported inactive. Targets are shown for diagnosis, but Cockpit is not expected to answer yet.";
  } else {
    ui.cockpitState.textContent = "Cockpit service state is unknown. Target links are candidates only; reachability is not guaranteed.";
  }

  ui.cockpitTargets.replaceChildren();
  const targets = buildCockpitTargets(systemInfo, networkStatus);
  if (targets.length === 0) {
    ui.cockpitTargets.append(element("p", "empty-state", "No usable Cockpit target addresses were reported."));
    return;
  }

  for (const target of targets) {
    const row = element("div", "target-row");
    const label = element("div", "target-label");
    label.append(
      element("strong", "", target.host),
      element("span", "muted", `${target.interfaceName} · ${target.interfaceType}`),
    );
    const tags = element("div", "badge-row compact");
    if (target.defaultRoute) tags.append(badge("Default route", "accent"));
    if (target.internet) tags.append(badge("Internet", "positive"));
    label.append(tags);
    row.append(label);

    if (target.url) {
      const link = element("a", "button secondary small", "Open Cockpit");
      link.href = target.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.setAttribute("aria-label", `Open Cockpit using ${target.host}`);
      row.append(link);
    } else {
      const unavailable = element("span", "target-unavailable", "No direct URL");
      unavailable.title = "A link-local IPv6 address needs an interface scope that schema v1 does not provide.";
      row.append(unavailable);
    }

    ui.cockpitTargets.append(row);
  }
}

function renderStatus(status) {
  lastStatus = status;
  const { systemInfo, networkStatus, readAt } = status;
  const device = systemInfo.device || {};

  ui.deviceSection.hidden = false;
  ui.deviceName.textContent = String(device.name || client.device?.name || "CodePC Link");
  const identityParts = [device.hostname, device.version ? `daemon ${device.version}` : null, device.id].filter(Boolean);
  ui.deviceMeta.textContent = identityParts.join(" · ");
  ui.lastUpdated.textContent = `Last BLE read: ${readAt.toLocaleString()}`;

  renderInterfaces(networkStatus);
  renderCockpit(systemInfo, networkStatus);
  renderErrors(systemInfo, networkStatus);
}

async function readAndRender() {
  const status = await client.readStatus();
  renderStatus(status);
  setConnection(`Connected to ${client.device?.name || "CodePC Link"}`, "positive");
}

async function runAction(action) {
  setBusy(true);
  try {
    return await action();
  } catch (error) {
    setConnection(describeError(error), "negative");
    throw error;
  } finally {
    setBusy(false);
  }
}

async function chooseDevice() {
  try {
    await runAction(async () => {
      await client.requestDevice();
      await readAndRender();
    });
  } catch {
    // The visible status already contains the actionable error.
  }
}

async function connectRemembered(device) {
  try {
    await runAction(async () => {
      const status = await client.connect(device);
      renderStatus(status);
      setConnection(`Connected to ${device.name || "CodePC Link"}`, "positive");
    });
  } catch {
    // Keep the remembered device button so the user can retry.
  }
}

function renderRememberedDevices(devices) {
  ui.remembered.replaceChildren();
  if (devices.length === 0) {
    ui.remembered.append(element("p", "muted remembered-empty", "Previously permitted CodePC Link devices will appear here after the first connection."));
    return;
  }

  ui.remembered.append(element("p", "remembered-title", "Previously permitted"));
  for (const device of devices) {
    const button = element("button", "remembered-device", device.name || "CodePC Link device");
    button.type = "button";
    button.addEventListener("click", () => connectRemembered(device));
    ui.remembered.append(button);
  }
}

async function initializeBluetooth() {
  if (!isSecureContext) {
    ui.browserStatus.textContent = "Web Bluetooth requires a secure HTTPS context.";
    ui.browserStatus.dataset.tone = "negative";
    updateControls();
    return;
  }

  if (!client.supported) {
    ui.browserStatus.textContent = "Web Bluetooth is not available in this browser. Use a supported Chromium browser on Android for v0.1.";
    ui.browserStatus.dataset.tone = "negative";
    updateControls();
    return;
  }

  try {
    const available = await client.getAvailability();
    ui.browserStatus.textContent = available ? "Web Bluetooth ready" : "Web Bluetooth is supported, but Bluetooth is currently unavailable.";
    ui.browserStatus.dataset.tone = available ? "positive" : "warning";
    renderRememberedDevices(await client.getRememberedDevices());
  } catch (error) {
    ui.browserStatus.textContent = describeError(error);
    ui.browserStatus.dataset.tone = "warning";
  }
  updateControls();
}

client.addEventListener("disconnect", () => {
  const name = client.device?.name || "CodePC Link";
  setConnection(`Disconnected from ${name}. Use the remembered-device button to reconnect.`, "warning");
  updateControls();
});

client.addEventListener("connect", updateControls);
ui.connect.addEventListener("click", chooseDevice);
ui.disconnect.addEventListener("click", () => client.disconnect());
ui.refresh.addEventListener("click", async () => {
  try {
    await runAction(readAndRender);
  } catch {
    // Visible connection state already updated.
  }
});

window.addEventListener("online", updateOnlineState);
window.addEventListener("offline", updateOnlineState);
updateOnlineState();

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  ui.installButton.hidden = false;
});

ui.installButton.addEventListener("click", async () => {
  if (!installPrompt) return;
  await installPrompt.prompt();
  installPrompt = null;
  ui.installButton.hidden = true;
});

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.register("./sw.js");

  const showUpdate = () => {
    ui.updateBanner.hidden = false;
  };

  if (registration.waiting) showUpdate();
  registration.addEventListener("updatefound", () => {
    const worker = registration.installing;
    if (!worker) return;
    worker.addEventListener("statechange", () => {
      if (worker.state === "installed" && navigator.serviceWorker.controller) showUpdate();
    });
  });

  ui.updateButton.addEventListener("click", () => {
    const worker = registration.waiting;
    if (worker) worker.postMessage({ type: "SKIP_WAITING" });
  });

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloadForWorkerUpdate) return;
    reloadForWorkerUpdate = true;
    location.reload();
  });
}

registerServiceWorker().catch((error) => {
  console.warn("Service worker registration failed", error);
});
initializeBluetooth();

// Keep the most recently rendered BLE data visible when the IP network drops.
// It is diagnostic state, not a claim that it is still current.
window.addEventListener("offline", () => {
  if (lastStatus) ui.lastUpdated.textContent += " · cached on this page";
});
