package com.codepc.link

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import java.io.BufferedReader
import java.io.BufferedWriter
import java.io.Closeable
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.util.UUID
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class BluetoothSerialClient(
    private val serviceUuid: UUID = StatusProtocol.RFCOMM_SERVICE_UUID,
) : Closeable {
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()

    @Volatile
    private var socket: BluetoothSocket? = null

    @Volatile
    private var reader: BufferedReader? = null

    @Volatile
    private var writer: BufferedWriter? = null

    val connected: Boolean
        get() = socket?.isConnected == true

    @SuppressLint("MissingPermission")
    fun connect(device: BluetoothDevice, callback: (Result<Unit>) -> Unit) {
        executor.execute {
            closeConnection()
            callback(
                runCatching {
                    val newSocket = device.createRfcommSocketToServiceRecord(serviceUuid)
                    newSocket.connect()
                    socket = newSocket
                    reader = BufferedReader(InputStreamReader(newSocket.inputStream, Charsets.UTF_8))
                    writer = BufferedWriter(OutputStreamWriter(newSocket.outputStream, Charsets.UTF_8))
                },
            )
        }
    }

    fun requestStatus(callback: (Result<String>) -> Unit) {
        executor.execute {
            callback(
                runCatching {
                    val activeWriter = writer ?: error("RFCOMM connection is not open")
                    val activeReader = reader ?: error("RFCOMM connection is not open")
                    activeWriter.write(StatusProtocol.STATUS_REQUEST)
                    activeWriter.flush()
                    activeReader.readLine() ?: error("CodePC closed the RFCOMM connection")
                },
            )
        }
    }

    fun disconnect(callback: (() -> Unit)? = null) {
        executor.execute {
            closeConnection()
            callback?.invoke()
        }
    }

    private fun closeConnection() {
        runCatching { reader?.close() }
        runCatching { writer?.close() }
        runCatching { socket?.close() }
        reader = null
        writer = null
        socket = null
    }

    override fun close() {
        closeConnection()
        executor.shutdownNow()
    }
}
