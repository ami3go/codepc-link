package io.github.ami3go.codepclink.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build

class BluetoothRepository(context: Context) {
    private val appContext = context.applicationContext
    private val manager = appContext.getSystemService(BluetoothManager::class.java)
    val adapter: BluetoothAdapter? = manager?.adapter

    fun hasConnectPermission(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            appContext.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) ==
            PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")
    fun isBluetoothEnabled(): Boolean {
        val bluetoothAdapter = adapter ?: return false
        if (!hasConnectPermission()) return true
        return bluetoothAdapter.isEnabled
    }

    @SuppressLint("MissingPermission")
    fun bondedDevices(): List<BondedDevice> {
        val bluetoothAdapter = adapter ?: return emptyList()
        if (!hasConnectPermission()) return emptyList()

        return bluetoothAdapter.bondedDevices
            .filter { it.bondState == BluetoothDevice.BOND_BONDED }
            .map {
                BondedDevice(
                    name = it.name ?: "Unnamed Bluetooth device",
                    address = it.address,
                )
            }
            .sortedWith(
                compareByDescending<BondedDevice> {
                    it.name.contains("codepc", ignoreCase = true)
                }.thenBy { it.name }
            )
    }

    @SuppressLint("MissingPermission")
    fun remoteDevice(address: String): BluetoothDevice? {
        if (!hasConnectPermission()) return null
        return adapter?.getRemoteDevice(address)
    }
}

data class BondedDevice(
    val name: String,
    val address: String,
)
