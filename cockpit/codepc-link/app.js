(() => {
  "use strict";

  const ui = {
    refresh: document.querySelector("#refresh-button"),
    scan: document.querySelector("#scan-button"),
    statusDot: document.querySelector("#status-dot"),
    statusTitle: document.querySelector("#status-title"),
    statusDetail: document.querySelector("#status-detail"),
    adapterSummary: document.querySelector("#adapter-summary"),
    deviceList: document.querySelector("#device-list"),
    template: document.querySelector("#device-template"),
  };

  let busy = false;

  function setBusy(value) {
    busy = value;
    ui.refresh.disabled = value;
    ui.scan.disabled = value;
    for (const button of ui.deviceList.querySelectorAll("button")) {
      button.disabled = value;
    }
  }

  function setStatus(title, detail, tone = "neutral") {
    ui.statusTitle.textContent = title;
    ui.statusDetail.textContent = detail;
    ui.statusDot.className = `status-dot ${tone}`;
  }

  function parsePayload(text) {
    let payload;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new Error(`CodePC Link returned invalid JSON: ${error.message}`);
    }
    if (!payload.ok) {
      const message = payload.error?.message || "Bluetooth operation failed";
      throw new Error(message);
    }
    return payload;
  }

  function runBluetooth(args) {
    return cockpit.spawn(
      ["codepc-link-bt", ...args],
      {
        superuser: "require",
        err: "message",
        environ: ["LC_ALL=C.UTF-8"],
      },
    ).then(parsePayload);
  }

  function badge(text, tone = "neutral") {
    const node = document.createElement("span");
    node.className = `badge ${tone}`;
    node.textContent = text;
    return node;
  }

  function renderAdapter(adapter) {
    if (!adapter) {
      ui.adapterSummary.textContent = "Adapter status unavailable.";
      return;
    }
    const state = adapter.powered ? "powered" : "off";
    const pairing = adapter.pairable ? "remote pairing enabled" : "server-side pairing only";
    const address = adapter.address ? ` · ${adapter.address}` : "";
    ui.adapterSummary.textContent = `${adapter.name} · ${state} · ${pairing}${address}`;
  }

  function renderDevices(payload) {
    renderAdapter(payload.adapter);
    ui.deviceList.replaceChildren();
    const devices = Array.isArray(payload.devices) ? payload.devices : [];

    if (devices.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No Bluetooth devices are known yet. Put the phone in Android's Pair new device screen and scan again.";
      ui.deviceList.append(empty);
      return;
    }

    for (const device of devices) {
      const fragment = ui.template.content.cloneNode(true);
      const card = fragment.querySelector(".device-card");
      fragment.querySelector(".device-name").textContent = device.name || "Unnamed Bluetooth device";
      fragment.querySelector(".device-address").textContent = device.address || "Unknown address";

      const badges = fragment.querySelector(".badges");
      if (device.paired) badges.append(badge("Paired", "positive"));
      if (device.trusted) badges.append(badge("Trusted", "accent"));
      if (device.connected) badges.append(badge("Connected", "positive"));
      if (!device.paired) badges.append(badge("Not paired"));

      const details = [];
      if (device.address_type) details.push(device.address_type);
      if (Number.isFinite(device.rssi)) details.push(`RSSI ${device.rssi} dBm`);
      fragment.querySelector(".device-meta").textContent = details.join(" · ") || "Bluetooth Classic device";

      const actions = fragment.querySelector(".device-actions");
      if (device.paired) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "danger secondary";
        remove.textContent = "Remove pairing";
        remove.addEventListener("click", () => removeDevice(device));
        actions.append(remove);
      } else {
        const pair = document.createElement("button");
        pair.type = "button";
        pair.textContent = "Pair from CodePC";
        pair.addEventListener("click", () => pairDevice(device));
        actions.append(pair);
      }

      card.dataset.address = device.address || "";
      ui.deviceList.append(fragment);
    }
  }

  async function refresh() {
    setBusy(true);
    setStatus("Loading Bluetooth devices", "Reading BlueZ device state…", "working");
    try {
      const payload = await runBluetooth(["devices"]);
      renderDevices(payload);
      setStatus("Bluetooth ready", "Initial pairing is controlled from this CodePC page.", "positive");
    } catch (error) {
      setStatus("Unable to read Bluetooth state", error.message, "negative");
    } finally {
      setBusy(false);
    }
  }

  async function scan() {
    setBusy(true);
    setStatus(
      "Scanning for phones",
      "Keep Android on the Pair new device screen. Pairing will still be initiated only from CodePC.",
      "working",
    );
    try {
      const payload = await runBluetooth(["scan", "--seconds", "8"]);
      renderDevices(payload);
      setStatus("Scan complete", "Choose the phone and click Pair from CodePC.", "positive");
    } catch (error) {
      setStatus("Bluetooth scan failed", error.message, "negative");
    } finally {
      setBusy(false);
    }
  }

  async function pairDevice(device) {
    const label = device.name || device.address || "device";
    setBusy(true);
    setStatus(
      `Pairing ${label}`,
      "Confirm the Bluetooth pairing prompt on the Android phone if it appears.",
      "working",
    );
    try {
      const payload = await runBluetooth(["pair", device.address]);
      const paired = payload.device || device;
      setStatus(
        `Paired ${paired.name || paired.address}`,
        "The phone is now paired and trusted. Open the CodePC Link Android app and choose this paired CodePC.",
        "positive",
      );
      await refresh();
    } catch (error) {
      setStatus("Pairing failed", error.message, "negative");
    } finally {
      setBusy(false);
    }
  }

  async function removeDevice(device) {
    const label = device.name || device.address || "device";
    if (!window.confirm(`Remove Bluetooth pairing for ${label}?`)) return;

    setBusy(true);
    setStatus(`Removing ${label}`, "Deleting the BlueZ pairing record…", "working");
    try {
      await runBluetooth(["remove", device.address]);
      setStatus("Pairing removed", `${label} must be paired again from this CodePC page.`, "positive");
      await refresh();
    } catch (error) {
      setStatus("Unable to remove pairing", error.message, "negative");
    } finally {
      setBusy(false);
    }
  }

  ui.refresh.addEventListener("click", refresh);
  ui.scan.addEventListener("click", scan);
  refresh();
})();
