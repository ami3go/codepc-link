package com.codepc.link

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothHidDevice
import android.bluetooth.BluetoothHidDeviceAppSdpSettings
import android.bluetooth.BluetoothProfile
import android.content.Context
import java.io.ByteArrayOutputStream

class BluetoothHidTransport(
    private val context: Context,
    private val listener: Listener,
) : BluetoothProfile.ServiceListener {
    interface Listener {
        fun onHidRegistrationChanged(registered: Boolean)
        fun onHidConnectionStateChanged(device: BluetoothDevice, state: Int)
        fun onStatusJson(json: String)
        fun onHidError(message: String)
    }

    private var hidDevice: BluetoothHidDevice? = null
    private var registered = false
    private var connectedHost: BluetoothDevice? = null
    private var sequence = 0

    private var receiveSequence = -1
    private var receiveChunkCount = 0
    private var receiveChunks: Array<ByteArray?> = emptyArray()

    val isRegistered: Boolean
        get() = registered

    val isConnected: Boolean
        get() = connectedHost != null

    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        val started = android.bluetooth.BluetoothAdapter.getDefaultAdapter()
            ?.getProfileProxy(context, this, BluetoothProfile.HID_DEVICE)
            ?: false
        if (!started) listener.onHidError("Android HID Device profile is unavailable")
        return started
    }

    @SuppressLint("MissingPermission")
    fun ensureRegistered(): Boolean {
        val profile = hidDevice ?: return false
        if (registered) return true

        val settings = BluetoothHidDeviceAppSdpSettings(
            HID_NAME,
            "Vendor status transport; not a keyboard",
            "CodePC Link",
            BluetoothHidDevice.SUBCLASS1_NONE,
            REPORT_DESCRIPTOR,
        )
        val accepted = profile.registerApp(
            settings,
            null,
            null,
            context.mainExecutor,
            callback,
        )
        if (!accepted) listener.onHidError("Android rejected HID application registration")
        return accepted
    }

    @SuppressLint("MissingPermission")
    fun connect(host: BluetoothDevice): Boolean {
        val profile = hidDevice ?: run {
            listener.onHidError("HID profile is not ready")
            return false
        }
        if (!registered) {
            listener.onHidError("HID transport is not registered")
            return false
        }
        val accepted = profile.connect(host)
        if (!accepted) listener.onHidError("Android rejected the HID connect request")
        return accepted
    }

    @SuppressLint("MissingPermission")
    fun disconnect(): Boolean {
        val profile = hidDevice ?: return false
        val host = connectedHost ?: return false
        return profile.disconnect(host)
    }

    fun requestStatus(): Boolean = sendCommand(OP_REQUEST_STATUS, byteArrayOf())

    fun setPushInterval(seconds: Int): Boolean {
        require(seconds in 0..65535)
        val payload = byteArrayOf(
            (seconds and 0xff).toByte(),
            ((seconds ushr 8) and 0xff).toByte(),
        )
        return sendCommand(OP_SET_PUSH_INTERVAL, payload)
    }

    @SuppressLint("MissingPermission")
    private fun sendCommand(opcode: Int, payload: ByteArray): Boolean {
        val profile = hidDevice ?: return false
        val host = connectedHost ?: run {
            listener.onHidError("CodePC HID host is not connected")
            return false
        }
        if (payload.size > MAX_CHUNK_PAYLOAD) {
            listener.onHidError("HID command payload is too large")
            return false
        }

        val frame = ByteArray(REPORT_DATA_BYTES)
        frame[0] = PROTOCOL_VERSION.toByte()
        frame[1] = opcode.toByte()
        frame[2] = nextSequence().toByte()
        frame[3] = 0
        frame[4] = 0
        frame[5] = 1
        frame[6] = 0
        frame[7] = payload.size.toByte()
        payload.copyInto(frame, destinationOffset = HEADER_BYTES)

        val accepted = profile.sendReport(host, REPORT_ID_COMMAND, frame)
        if (!accepted) listener.onHidError("Unable to send HID command report")
        return accepted
    }

    private fun nextSequence(): Int {
        val value = sequence
        sequence = (sequence + 1) and 0xff
        return value
    }

    private fun unsigned(value: Byte): Int = value.toInt() and 0xff

    private fun handleStatusReport(data: ByteArray) {
        if (data.size < HEADER_BYTES) return
        if (unsigned(data[0]) != PROTOCOL_VERSION) return
        if (unsigned(data[1]) != OP_STATUS_JSON) return

        val reportSequence = unsigned(data[2])
        val chunkIndex = unsigned(data[3]) or (unsigned(data[4]) shl 8)
        val chunkCount = unsigned(data[5]) or (unsigned(data[6]) shl 8)
        val payloadLength = unsigned(data[7])

        if (chunkCount <= 0 || chunkIndex >= chunkCount) return
        if (payloadLength > MAX_CHUNK_PAYLOAD) return
        if (data.size < HEADER_BYTES + payloadLength) return

        if (reportSequence != receiveSequence || chunkCount != receiveChunkCount) {
            receiveSequence = reportSequence
            receiveChunkCount = chunkCount
            receiveChunks = arrayOfNulls(chunkCount)
        }

        receiveChunks[chunkIndex] = data.copyOfRange(
            HEADER_BYTES,
            HEADER_BYTES + payloadLength,
        )
        if (receiveChunks.any { it == null }) return

        val output = ByteArrayOutputStream()
        receiveChunks.forEach { chunk -> output.write(chunk!!) }
        val json = output.toByteArray().toString(Charsets.UTF_8)
        receiveSequence = -1
        receiveChunkCount = 0
        receiveChunks = emptyArray()
        listener.onStatusJson(json)
    }

    @SuppressLint("MissingPermission")
    private val callback = object : BluetoothHidDevice.Callback() {
        override fun onAppStatusChanged(pluggedDevice: BluetoothDevice?, registered: Boolean) {
            this@BluetoothHidTransport.registered = registered
            if (!registered) connectedHost = null
            if (registered && pluggedDevice != null) connectedHost = pluggedDevice
            listener.onHidRegistrationChanged(registered)
        }

        override fun onConnectionStateChanged(device: BluetoothDevice, state: Int) {
            connectedHost = if (state == BluetoothProfile.STATE_CONNECTED) device else null
            listener.onHidConnectionStateChanged(device, state)
        }

        override fun onGetReport(
            device: BluetoothDevice,
            type: Byte,
            id: Byte,
            bufferSize: Int,
        ) {
            val profile = hidDevice ?: return
            if (id.toInt() and 0xff == REPORT_ID_COMMAND) {
                profile.replyReport(device, type, id, ByteArray(REPORT_DATA_BYTES))
            } else {
                profile.reportError(device, BluetoothHidDevice.ERROR_RSP_INVALID_RPT_ID)
            }
        }

        override fun onSetReport(
            device: BluetoothDevice,
            type: Byte,
            id: Byte,
            data: ByteArray,
        ) {
            val profile = hidDevice ?: return
            if (id.toInt() and 0xff == REPORT_ID_STATUS) {
                handleStatusReport(data)
                profile.reportError(device, BluetoothHidDevice.ERROR_RSP_SUCCESS)
            } else {
                profile.reportError(device, BluetoothHidDevice.ERROR_RSP_INVALID_RPT_ID)
            }
        }

        override fun onInterruptData(device: BluetoothDevice, reportId: Byte, data: ByteArray) {
            if (reportId.toInt() and 0xff == REPORT_ID_STATUS) handleStatusReport(data)
        }

        override fun onVirtualCableUnplug(device: BluetoothDevice) {
            connectedHost = null
            listener.onHidConnectionStateChanged(device, BluetoothProfile.STATE_DISCONNECTED)
        }
    }

    @SuppressLint("MissingPermission")
    fun close() {
        val profile = hidDevice
        if (profile != null) {
            if (registered) profile.unregisterApp()
            android.bluetooth.BluetoothAdapter.getDefaultAdapter()
                ?.closeProfileProxy(BluetoothProfile.HID_DEVICE, profile)
        }
        hidDevice = null
        registered = false
        connectedHost = null
    }

    override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
        if (profile != BluetoothProfile.HID_DEVICE) return
        hidDevice = proxy as BluetoothHidDevice
        ensureRegistered()
    }

    override fun onServiceDisconnected(profile: Int) {
        if (profile != BluetoothProfile.HID_DEVICE) return
        hidDevice = null
        registered = false
        connectedHost = null
        listener.onHidRegistrationChanged(false)
    }

    companion object {
        const val HID_NAME = "CodePC Link Transport"
        const val REPORT_ID_COMMAND = 1
        const val REPORT_ID_STATUS = 2
        const val REPORT_DATA_BYTES = 63
        const val HEADER_BYTES = 8
        const val MAX_CHUNK_PAYLOAD = REPORT_DATA_BYTES - HEADER_BYTES
        const val PROTOCOL_VERSION = 1
        const val OP_REQUEST_STATUS = 0x01
        const val OP_SET_PUSH_INTERVAL = 0x02
        const val OP_STATUS_JSON = 0x10

        // Vendor usage page 0xFF00. There are deliberately no Keyboard or Mouse
        // collections, so Linux should expose this as hidraw instead of an input keyboard.
        val REPORT_DESCRIPTOR = byteArrayOf(
            0x06, 0x00, 0xFF.toByte(), // Usage Page (Vendor 0xFF00)
            0x09, 0x01, // Usage (1)
            0xA1.toByte(), 0x01, // Collection (Application)
            0x15, 0x00, // Logical Minimum (0)
            0x26, 0xFF.toByte(), 0x00, // Logical Maximum (255)
            0x75, 0x08, // Report Size (8)
            0x85.toByte(), REPORT_ID_COMMAND.toByte(),
            0x95.toByte(), REPORT_DATA_BYTES.toByte(),
            0x09, 0x01,
            0x81.toByte(), 0x02, // Input (Data, Variable, Absolute)
            0x85.toByte(), REPORT_ID_STATUS.toByte(),
            0x95.toByte(), REPORT_DATA_BYTES.toByte(),
            0x09, 0x02,
            0x91.toByte(), 0x02, // Output (Data, Variable, Absolute)
            0xC0.toByte(),
        )
    }
}
