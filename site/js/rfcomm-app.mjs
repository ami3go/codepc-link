import { CodePcRfcommClient } from "./rfcomm.mjs";
import { buildCockpitTargets, describeError } from "./protocol.mjs";

const client = new CodePcRfcommClient();
let busy = false;

const ui = {
  browserStatus: document.querySelector("#rfcomm-browser-status"),
  connectionStatus: document.querySelector("#rfcomm-connection-status"),
  connect: document.querySelector("#rfcomm-connect-button"),
  reconnect: document.querySelector("#rfcomm-reconnect-button"),
  refresh: document.querySelector("#rfcomm-refresh-button"),
  disconnect: document.querySelector("#rfcomm-disconnect-button"),
  remembered: document.querySelector("#rfcomm-remembered"),
  result: document.querySelector("#rfcomm-result"),
  summary: document.querySelector("#rfcomm-summary"),
  targets: document.querySelector("#rfcomm-targets"),
  raw: document.querySelector("#rfcomm-raw"),
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setConnection(text, tone = "neutral") {
  ui.connectionStatus.textContent = text;
  ui.connectionStatus.dataset.tone = tone;
}

function updateControls() {
  ui.connect.disabled = busy || !client.supported;
  ui.reconnect.disabled = busy || !client.port || client.connected;
  ui.refresh.disabled = busy || !client.connected;
  ui.disconnect.disabled = busy || !client.connected;
}

async function runAction(action) {
  busy = true;
  updateControls();
  try {
    return await action();
  } catch (error) {
    setConnection(describeError(error), "negative");
    throw error;
  } finally {
    busy = false;
    updateControls();
  }
}

function renderTargets(status) {
  ui.targets.replaceChildren();
  const targets = buildCockpitTargets(status.systemInfo, status.networkStatus);
  if (targets.length === 0) {
    ui.targets.append(element("p", "empty-state", "No usable Cockpit targets were reported."));
    return;
  }

  for (const target of targets) {
    const row = element("div", "target-row");
    const label = element("div", "target-label");
    label.append(
      element("strong", "", target.host),
      element("span", "muted", `${target.interfaceName} · ${target.interfaceType}`),
    );
    row.append(label);

    if (target.url) {
      const link = element("a", "button secondary small", "Open Cockpit");
      link.href = target.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      row.append(link);
    } else {
      row.append(element("span", "target-unavailable", "No direct URL"));
    }
    ui.targets.append(row);
  }
}

function renderStatus(status) {
  const device = status.systemInfo.device || {};
  const interfaces = status.networkStatus.network.interfaces || [];
  const addressCount = interfaces.reduce(
    (total, iface) => total + (Array.isArray(iface.addresses) ? iface.addresses.length : 0),
    0,
  );

  ui.result.hidden = false;
  ui.summary.textContent = [
    device.name || "CodePC Link",
    device.hostname || "hostname unavailable",
    `${interfaces.length} interface${interfaces.length === 1 ? "" : "s"}`,
    `${addressCount} address${addressCount === 1 ? "" : "es"}`,
    `read ${status.readAt.toLocaleString()}`,
  ].join(" · ");
  ui.raw.textContent = JSON.stringify(status.rawStatus, null, 2);
  renderTargets(status);
}

async function readStatus() {
  const status = await client.readStatus();
  renderStatus(status);
  setConnection("RFCOMM connected and status received", "positive");
}

async function choosePort() {
  try {
    await runAction(async () => {
      await client.requestPort();
      setConnection("RFCOMM connected; reading status…", "positive");
      await readStatus();
    });
  } catch {
    // The visible connection pill contains the actionable error.
  }
}

async function reconnect() {
  try {
    await runAction(async () => {
      await client.reconnect();
      setConnection("RFCOMM reconnected; reading status…", "positive");
      await readStatus();
    });
  } catch {
    // Keep the previously selected port for another retry.
  }
}

async function connectRemembered(port) {
  try {
    await runAction(async () => {
      await client.connect(port);
      setConnection("RFCOMM connected; reading status…", "positive");
      await readStatus();
    });
  } catch {
    // The remembered button remains available for another retry.
  }
}

function renderRemembered(ports) {
  ui.remembered.replaceChildren();
  if (ports.length === 0) {
    ui.remembered.append(
      element("p", "muted remembered-empty", "No previously permitted CodePC Link RFCOMM port was found."),
    );
    return;
  }

  ui.remembered.append(element("p", "remembered-title", "Previously permitted RFCOMM service"));
  ports.forEach((port, index) => {
    const button = element("button", "remembered-device", `CodePC Link RFCOMM ${index + 1}`);
    button.type = "button";
    button.addEventListener("click", () => connectRemembered(port));
    ui.remembered.append(button);
  });
}

async function initialize() {
  if (!isSecureContext) {
    ui.browserStatus.textContent = "Web Serial requires a secure context (HTTPS or localhost).";
    ui.browserStatus.dataset.tone = "negative";
    updateControls();
    return;
  }

  if (!client.supported) {
    ui.browserStatus.textContent = "Web Serial is unavailable. Android Chrome 138+ is required for Bluetooth RFCOMM.";
    ui.browserStatus.dataset.tone = "negative";
    updateControls();
    return;
  }

  ui.browserStatus.textContent = "Web Serial RFCOMM ready";
  ui.browserStatus.dataset.tone = "positive";
  try {
    renderRemembered(await client.getRememberedPorts());
  } catch (error) {
    ui.browserStatus.textContent = describeError(error);
    ui.browserStatus.dataset.tone = "warning";
  }
  updateControls();
}

client.addEventListener("connect", () => {
  setConnection("RFCOMM connected", "positive");
  updateControls();
});
client.addEventListener("disconnect", () => {
  setConnection("RFCOMM disconnected", "warning");
  updateControls();
});

ui.connect.addEventListener("click", choosePort);
ui.reconnect.addEventListener("click", reconnect);
ui.refresh.addEventListener("click", async () => {
  try {
    await runAction(readStatus);
  } catch {
    // The visible connection pill contains the actionable error.
  }
});
ui.disconnect.addEventListener("click", async () => {
  try {
    await runAction(() => client.disconnect());
  } catch {
    // The visible connection pill contains the actionable error.
  }
});

initialize();
