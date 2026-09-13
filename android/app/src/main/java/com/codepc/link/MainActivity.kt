package com.codepc.link

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.text.method.ScrollingMovementMethod
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var bluetoothAdapter: BluetoothAdapter
    private val client = BluetoothSerialClient()

    private var selectedDevice: BluetoothDevice? = null
    private var cockpitUrl: String? = null

    private lateinit var deviceView: TextView
    private lateinit var connectionView: TextView
    private lateinit var resultView: TextView
    private lateinit var connectButton: Button
    private lateinit var statusButton: Button
    private lateinit var disconnectButton: Button
    private lateinit var cockpitButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val bluetoothManager = getSystemService(BluetoothManager::class.java)
        bluetoothAdapter = bluetoothManager.adapter
        setContentView(buildUi())

        if (!packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)) {
            setConnection("Bluetooth Classic is not available on this device")
            setControlsEnabled(false)
            return
        }

        if (ensureConnectPermission()) {
            restoreSelectedDevice()
            updateSelectedDevice()
        }
    }

    override fun onResume() {
        super.onResume()
        if (hasConnectPermission()) {
            restoreSelectedDevice()
            updateSelectedDevice()
        }
    }

    private fun buildUi(): LinearLayout {
        val padding = (20 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
        }

        fun text(text: String, size: Float = 16f) = TextView(this).apply {
            this.text = text
            textSize = size
            setPadding(0, 0, 0, padding / 2)
        }

        root.addView(text("CodePC Link", 26f))
        root.addView(text("Bluetooth Classic / RFCOMM"))
        root.addView(
            text(
                "First pairing is controlled by the CodePC. Open Cockpit → CodePC Link on the mini-PC, " +
                    "scan for this phone, and start Pair from CodePC. This app never initiates pairing.",
                14f,
            ),
        )

        deviceView = text("Paired PC: not selected")
        connectionView = text("Disconnected")
        root.addView(deviceView)
        root.addView(connectionView)

        val chooseButton = Button(this).apply {
            text = "Choose paired CodePC"
            setOnClickListener { choosePairedDevice() }
        }
        root.addView(chooseButton)

        connectButton = Button(this).apply {
            text = "Connect"
            setOnClickListener { connectSelectedDevice() }
        }
        root.addView(connectButton)

        statusButton = Button(this).apply {
            text = "Request status"
            isEnabled = false
            setOnClickListener { requestStatus() }
        }
        root.addView(statusButton)

        disconnectButton = Button(this).apply {
            text = "Disconnect"
            isEnabled = false
            setOnClickListener { disconnect() }
        }
        root.addView(disconnectButton)

        cockpitButton = Button(this).apply {
            text = "Open Cockpit"
            isEnabled = false
            setOnClickListener { openCockpit() }
        }
        root.addView(cockpitButton)

        resultView = text("No status received yet.").apply {
            setTextIsSelectable(true)
            movementMethod = ScrollingMovementMethod()
        }
        root.addView(
            resultView,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ),
        )
        return root
    }

    private fun ensureConnectPermission(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED) {
            return true
        }
        requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT), REQUEST_CONNECT_PERMISSION)
        return false
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_CONNECT_PERMISSION) {
            if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
                restoreSelectedDevice()
                updateSelectedDevice()
            } else {
                setConnection("Bluetooth permission is required to connect to CodePC")
            }
        }
    }

    private fun choosePairedDevice() {
        if (!ensureConnectPermission()) return
        val devices = pairedDevices()
        if (devices.isEmpty()) {
            Toast.makeText(
                this,
                "No paired devices. Start the first pair from Cockpit → CodePC Link on the mini-PC.",
                Toast.LENGTH_LONG,
            ).show()
            return
        }

        val labels = devices.map { deviceLabel(it) }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("Choose paired CodePC")
            .setItems(labels) { _, which ->
                selectedDevice = devices[which]
                rememberSelectedDevice(devices[which])
                cockpitUrl = null
                cockpitButton.isEnabled = false
                updateSelectedDevice()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    @Suppress("MissingPermission")
    private fun pairedDevices(): List<BluetoothDevice> =
        bluetoothAdapter.bondedDevices
            .sortedWith(compareBy({ it.name ?: "" }, { it.address }))

    @Suppress("MissingPermission")
    private fun deviceLabel(device: BluetoothDevice): String =
        "${device.name ?: "Unnamed device"} · ${device.address}"

    @Suppress("MissingPermission")
    private fun rememberSelectedDevice(device: BluetoothDevice) {
        getPreferences(MODE_PRIVATE)
            .edit()
            .putString(PREF_DEVICE_ADDRESS, device.address)
            .apply()
    }

    @Suppress("MissingPermission")
    private fun restoreSelectedDevice() {
        if (!hasConnectPermission()) return
        val remembered = getPreferences(MODE_PRIVATE).getString(PREF_DEVICE_ADDRESS, null)
        if (remembered == null) {
            if (selectedDevice == null) {
                val codePcCandidates = pairedDevices().filter {
                    (it.name ?: "").contains("CodePC", ignoreCase = true)
                }
                if (codePcCandidates.size == 1) selectedDevice = codePcCandidates.single()
            }
            return
        }
        selectedDevice = pairedDevices().firstOrNull { it.address == remembered }
    }

    private fun updateSelectedDevice() {
        val device = selectedDevice
        deviceView.text = if (device == null || !hasConnectPermission()) {
            "Paired PC: not selected"
        } else {
            "Paired PC: ${deviceLabel(device)}"
        }
        connectButton.isEnabled = device != null && hasConnectPermission() && !client.connected
    }

    private fun connectSelectedDevice() {
        if (!ensureConnectPermission()) return
        val device = selectedDevice ?: return
        setConnection("Connecting to ${deviceLabel(device)} …")
        setControlsEnabled(false)
        client.connect(device) { result ->
            runOnUiThread {
                result.fold(
                    onSuccess = {
                        setConnection("Connected via RFCOMM")
                        connectButton.isEnabled = false
                        statusButton.isEnabled = true
                        disconnectButton.isEnabled = true
                    },
                    onFailure = { error ->
                        setConnection("Connection failed: ${error.message ?: error.javaClass.simpleName}")
                        connectButton.isEnabled = true
                        statusButton.isEnabled = false
                        disconnectButton.isEnabled = false
                    },
                )
            }
        }
    }

    private fun requestStatus() {
        setConnection("Requesting current CodePC status …")
        statusButton.isEnabled = false
        client.requestStatus { result ->
            runOnUiThread {
                result.fold(
                    onSuccess = { line ->
                        runCatching { StatusProtocol.parseResponse(line) }
                            .onSuccess { parsed ->
                                resultView.text = parsed.summary + "\n\nRaw response:\n" + parsed.raw
                                cockpitUrl = parsed.cockpitUrl
                                cockpitButton.isEnabled = parsed.cockpitUrl != null
                                setConnection("Status received")
                            }
                            .onFailure { error ->
                                resultView.text = line
                                setConnection("Invalid status response: ${error.message}")
                            }
                    },
                    onFailure = { error ->
                        setConnection("Status request failed: ${error.message ?: error.javaClass.simpleName}")
                    },
                )
                statusButton.isEnabled = client.connected
                disconnectButton.isEnabled = client.connected
            }
        }
    }

    private fun disconnect() {
        setConnection("Disconnecting …")
        client.disconnect {
            runOnUiThread {
                setConnection("Disconnected")
                connectButton.isEnabled = selectedDevice != null && hasConnectPermission()
                statusButton.isEnabled = false
                disconnectButton.isEnabled = false
            }
        }
    }

    private fun openCockpit() {
        val target = cockpitUrl ?: return
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target)))
    }

    private fun setConnection(message: String) {
        connectionView.text = message
    }

    private fun setControlsEnabled(enabled: Boolean) {
        connectButton.isEnabled = enabled && selectedDevice != null
        statusButton.isEnabled = enabled && client.connected
        disconnectButton.isEnabled = enabled && client.connected
    }

    private fun hasConnectPermission(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED

    override fun onDestroy() {
        client.close()
        super.onDestroy()
    }

    companion object {
        private const val REQUEST_CONNECT_PERMISSION = 1001
        private const val PREF_DEVICE_ADDRESS = "selected_device_address"
    }
}
