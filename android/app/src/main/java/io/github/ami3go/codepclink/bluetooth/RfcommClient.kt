package io.github.ami3go.codepclink.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import io.github.ami3go.codepclink.protocol.CODEPC_RFCOMM_UUID
import io.github.ami3go.codepclink.protocol.MAX_RESPONSE_BYTES
import io.github.ami3go.codepclink.protocol.CodePcStatus
import io.github.ami3go.codepclink.protocol.parseStatusResponse
import io.github.ami3go.codepclink.protocol.statusRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.util.UUID

class RfcommClient(
    private val adapter: BluetoothAdapter,
) {
    private var socket: BluetoothSocket? = null
    private var input: BufferedInputStream? = null

    val connected: Boolean
        get() = socket?.isConnected == true

    @SuppressLint("MissingPermission")
    suspend fun connect(device: BluetoothDevice) = withContext(Dispatchers.IO) {
        close()
        adapter.cancelDiscovery()
        val newSocket = device.createRfcommSocketToServiceRecord(
            UUID.fromString(CODEPC_RFCOMM_UUID)
        )
        try {
            newSocket.connect()
            socket = newSocket
            input = BufferedInputStream(newSocket.inputStream)
        } catch (error: Throwable) {
            runCatching { newSocket.close() }
            throw error
        }
    }

    suspend fun requestStatus(): CodePcStatus = withContext(Dispatchers.IO) {
        val activeSocket = socket?.takeIf { it.isConnected }
            ?: error("Not connected")
        val activeInput = input ?: error("RFCOMM input stream unavailable")

        activeSocket.outputStream.write(statusRequest())
        activeSocket.outputStream.flush()

        parseStatusResponse(readLine(activeInput))
    }

    suspend fun disconnect() = withContext(Dispatchers.IO) {
        close()
    }

    fun close() {
        runCatching { input?.close() }
        runCatching { socket?.close() }
        input = null
        socket = null
    }

    private fun readLine(stream: BufferedInputStream): String {
        val output = ByteArrayOutputStream()
        while (true) {
            val value = stream.read()
            if (value < 0) error("RFCOMM connection closed")
            if (value == '\n'.code) break
            output.write(value)
            if (output.size() > MAX_RESPONSE_BYTES) {
                error("CodePC response exceeds $MAX_RESPONSE_BYTES bytes")
            }
        }
        return output.toString(Charsets.UTF_8.name())
    }
}
