package com.codepc.link

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.text.method.ScrollingMovementMethod
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity(), BluetoothHidTransport.Listener {
    private lateinit var bluetoothAdapter: BluetoothAdapter
    private lateinit var transport: BluetoothHidTransport

    private var selectedHost: BluetoothDevice? = null
    private var cockpitUrl: String? = null
    private var autoPushEnabled = true

    private lateinit var hidStateView: TextView
    private lateinit var hostView: TextView
    private lateinit var resultView: TextView
    private lateinit var chooseButton: Button
    private lateinit var connectButton: Button
    private lateinit var disconnectButton: Button
    private lateinit var requestButton: Button
    private lateinit var autoButton: Button
    private lateinit var cockpitButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            setContentView(messageView("CodePC Link HID requires Android 9 (API 28) or newer."))
            return
        }

        val manager = getSystemService(BluetoothManager::class.java)
        val adapter = manager.adapter
        if (adapter == null || !packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)) {
            setContentView(messageView("Bluetooth is not available on this phone."))
            return
        }
        bluetoothAdapter = adapter
        setContentView(buildUi())

        transport = BluetoothHidTransport(this, this)
        if (ensureBluetoothPermissions()) {
            restoreSelectedHost()
            refreshHostUi()
            transport.start()
        }
    }

    override fun onResume() {
        super.onResume()
        if (::transport.isInitialized && hasBluetoothPermissions()) {
            restoreSelectedHost()
            refreshHostUi()
            if (!transport.isRegistered) transport.ensureRegistered()
        }
    }

    override fun onDestroy() {
        if (::transport.isInitialized) transport.close()
        super.onDestroy()
    }

    private fun messageView(message: String): TextView = TextView(this).apply {
        text = message
        textSize = 18f
        val padding = (24 * resources.displayMetrics.density).toInt()
        setPadding(padding, padding, padding, padding)
    }

    private fun buildUi(): ScrollView {
        val padding = (20 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
        }

        fun text(value: String, size: Float = 16f) = TextView(this).apply {
            text = value
            textSize = size
            setPadding(0, 0, 0, padding / 2)
        }

        root.addView(text("CodePC Link HID", 26f))
        root.addView(
            text(
                "This phone is a vendor-defined Bluetooth HID device. It does not declare Keyboard " +
                    "or Mouse usages, so CodePC receives data through hidraw instead of key events.",
                14f,
            ),
        )
        root.addView(
            text(
                "First pair: keep this app open, make the phone discoverable, then start pairing " +
                    "from Cockpit → CodePC Link. Do not initiate pairing from Android.",
                14f,
            ),
        )

        hidStateView = text("HID profile: starting…")
        hostView = text("CodePC host: not selected")
        root.addView(hidStateView)
        root.addView(hostView)

        root.addView(Button(this).apply {
            text = "Make phone discoverable (120 s)"
            setOnClickListener { requestDiscoverable() }
        })

        chooseButton = Button(this).apply {
            text = "Choose paired CodePC"
            setOnClickListener { choosePairedHost() }
        }
        root.addView(chooseButton)

        connectButton = Button(this).apply {
            text = "Connect HID transport"
            isEnabled = false
            setOnClickListener { connectSelectedHost() }
        }
        root.addView(connectButton)

        disconnectButton = Button(this).apply {
            text = "Disconnect HID"
            isEnabled = false
            setOnClickListener { transport.disconnect() }
        }
        root.addView(disconnectButton)

        requestButton = Button(this).apply {
            text = "Request status now"
            isEnabled = false
            setOnClickListener {
                if (!transport.requestStatus()) toast("Status request was not sent")
            }
        }
        root.addView(requestButton)

        autoButton = Button(this).apply {
            text = autoButtonText()
            isEnabled = false
            setOnClickListener { toggleAutoPush() }
        }
        root.addView(autoButton)

        cockpitButton = Button(this).apply {
            text = "Open Cockpit"
            isEnabled = false
            setOnClickListener {
                cockpitUrl?.let { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(it))) }
            }
        }
        root.addView(cockpitButton)

        resultView = text("No CodePC status received yet.", 14f).apply {
            setTextIsSelectable(true)
            movementMethod = ScrollingMovementMethod()
        }
        root.addView(
            resultView,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ),
        )

        return ScrollView(this).apply { addView(root) }
    }

    private fun autoButtonText(): String =
        if (autoPushEnabled) "Auto status: 5 s (tap to disable)" else "Auto status: off (tap for 5 s)"

    private fun ensureBluetoothPermissions(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        val needed = mutableListOf<String>()
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            needed += Manifest.permission.BLUETOOTH_CONNECT
        }
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_ADVERTISE) != PackageManager.PERMISSION_GRANTED) {
            needed += Manifest.permission.BLUETOOTH_ADVERTISE
        }
        if (needed.isEmpty()) return true
        requestPermissions(needed.toTypedArray(), REQUEST_BLUETOOTH_PERMISSIONS)
        return false
    }

    private fun hasBluetoothPermissions(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        return checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED &&
            checkSelfPermission(Manifest.permission.BLUETOOTH_ADVERTISE) == PackageManager.PERMISSION_GRANTED
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_BLUETOOTH_PERMISSIONS) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            restoreSelectedHost()
            refreshHostUi()
            transport.start()
        } else {
            hidStateView.text = "Nearby devices permission is required for HID transport."
        }
    }

    private fun requestDiscoverable() {
        if (!ensureBluetoothPermissions()) return
        val intent = Intent(BluetoothAdapter.ACTION_REQUEST_DISCOVERABLE).apply {
            putExtra(BluetoothAdapter.EXTRA_DISCOVERABLE_DURATION, DISCOVERABLE_SECONDS)
        }
        startActivityForResult(intent, REQUEST_DISCOVERABLE)
    }

    @Deprecated("Deprecated in Android API; retained for the Bluetooth discoverability result.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_DISCOVERABLE) return
        if (resultCode == RESULT_CANCELED) {
            hidStateView.text = "Discoverability canceled. HID registration remains local-only."
        } else {
            hidStateView.text =
                "Phone discoverable for $resultCode s. Keep this app open and pair from CodePC Cockpit."
        }
        transport.ensureRegistered()
    }

    @Suppress("MissingPermission")
    private fun pairedHosts(): List<BluetoothDevice> {
        if (!hasBluetoothPermissions()) return emptyList()
        return bluetoothAdapter.bondedDevices.sortedWith(compareBy({ it.name ?: "" }, { it.address }))
    }

    private fun choosePairedHost() {
        if (!ensureBluetoothPermissions()) return
        val devices = pairedHosts()
        if (devices.isEmpty()) {
            toast("No bonded devices yet. Make this phone discoverable and pair it from CodePC Cockpit.")
            return
        }
        val labels = devices.map { deviceLabel(it) }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("Choose paired CodePC host")
            .setItems(labels) { _, index ->
                selectedHost = devices[index]
                rememberSelectedHost(devices[index])
                cockpitUrl = null
                cockpitButton.isEnabled = false
                refreshHostUi()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    @Suppress("MissingPermission")
    private fun deviceLabel(device: BluetoothDevice): String =
        "${device.name ?: "Unnamed device"} · ${device.address}"

    @Suppress("MissingPermission")
    private fun rememberSelectedHost(device: BluetoothDevice) {
        getPreferences(MODE_PRIVATE)
            .edit()
            .putString(PREF_HOST_ADDRESS, device.address)
            .apply()
    }

    @Suppress("MissingPermission")
    private fun restoreSelectedHost() {
        if (!hasBluetoothPermissions()) return
        val devices = pairedHosts()
        val remembered = getPreferences(MODE_PRIVATE).getString(PREF_HOST_ADDRESS, null)
        selectedHost = when {
            remembered != null -> devices.firstOrNull { it.address == remembered }
            selectedHost != null -> devices.firstOrNull { it.address == selectedHost?.address }
            else -> devices.filter { (it.name ?: "").contains("codepc", ignoreCase = true) }
                .singleOrNull()
        }
    }

    private fun refreshHostUi() {
        val host = selectedHost
        hostView.text = if (host == null || !hasBluetoothPermissions()) {
            "CodePC host: not selected"
        } else {
            "CodePC host: ${deviceLabel(host)}"
        }
        connectButton.isEnabled = host != null && transport.isRegistered && !transport.isConnected
    }

    private fun connectSelectedHost() {
        if (!ensureBluetoothPermissions()) return
        val host = selectedHost ?: return
        hidStateView.text = "Connecting HID transport to ${deviceLabel(host)}…"
        transport.connect(host)
    }

    private fun toggleAutoPush() {
        autoPushEnabled = !autoPushEnabled
        autoButton.text = autoButtonText()
        val seconds = if (autoPushEnabled) AUTO_PUSH_SECONDS else 0
        if (!transport.setPushInterval(seconds)) toast("Unable to change auto status interval")
    }

    override fun onHidRegistrationChanged(registered: Boolean) {
        runOnUiThread {
            hidStateView.text = if (registered) {
                "HID profile registered as “${BluetoothHidTransport.HID_NAME}” (vendor-defined, not keyboard)."
            } else {
                "HID profile is not registered. Keep this app in the foreground."
            }
            refreshHostUi()
        }
    }

    override fun onHidConnectionStateChanged(device: BluetoothDevice, state: Int) {
        runOnUiThread {
            val stateText = when (state) {
                BluetoothProfile.STATE_CONNECTED -> "connected"
                BluetoothProfile.STATE_CONNECTING -> "connecting"
                BluetoothProfile.STATE_DISCONNECTING -> "disconnecting"
                else -> "disconnected"
            }
            hidStateView.text = "HID transport $stateText: ${deviceLabel(device)}"
            val connected = state == BluetoothProfile.STATE_CONNECTED
            connectButton.isEnabled = !connected && selectedHost != null && transport.isRegistered
            disconnectButton.isEnabled = connected
            requestButton.isEnabled = connected
            autoButton.isEnabled = connected
            if (connected) {
                transport.setPushInterval(if (autoPushEnabled) AUTO_PUSH_SECONDS else 0)
                transport.requestStatus()
            }
        }
    }

    override fun onStatusJson(json: String) {
        runOnUiThread {
            runCatching { StatusProtocol.parseResponse(json) }
                .onSuccess { parsed ->
                    resultView.text = parsed.summary + "\n\nRaw response:\n" + parsed.raw
                    cockpitUrl = parsed.cockpitUrl
                    cockpitButton.isEnabled = parsed.cockpitUrl != null
                    hidStateView.text = "Status received over vendor HID transport."
                }
                .onFailure { error ->
                    resultView.text = json
                    hidStateView.text = "Invalid CodePC status: ${error.message}"
                }
        }
    }

    override fun onHidError(message: String) {
        runOnUiThread {
            hidStateView.text = message
            toast(message)
        }
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    companion object {
        private const val REQUEST_BLUETOOTH_PERMISSIONS = 40
        private const val REQUEST_DISCOVERABLE = 41
        private const val DISCOVERABLE_SECONDS = 120
        private const val AUTO_PUSH_SECONDS = 5
        private const val PREF_HOST_ADDRESS = "selected-hid-host-address"
    }
}
