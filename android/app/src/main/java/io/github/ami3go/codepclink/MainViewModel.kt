package io.github.ami3go.codepclink

import android.app.Application
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.ami3go.codepclink.bluetooth.BluetoothRepository
import io.github.ami3go.codepclink.bluetooth.BondedDevice
import io.github.ami3go.codepclink.bluetooth.RfcommClient
import io.github.ami3go.codepclink.protocol.CodePcStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = BluetoothRepository(application)
    private val preferences = application.getSharedPreferences("codepc-link", 0)
    private val client: RfcommClient? = repository.adapter?.let(::RfcommClient)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refreshDevices()
    }

    fun refreshDevices() {
        val adapter = repository.adapter
        val permissionGranted = repository.hasConnectPermission()
        val devices = if (permissionGranted) repository.bondedDevices() else emptyList()
        val remembered = preferences.getString("last-device-address", null)
        _uiState.value = _uiState.value.copy(
            bluetoothSupported = adapter != null,
            bluetoothEnabled = repository.isBluetoothEnabled(),
            permissionRequired = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !permissionGranted,
            devices = devices,
            selectedAddress = _uiState.value.selectedAddress
                ?.takeIf { selected -> devices.any { it.address == selected } }
                ?: remembered?.takeIf { saved -> devices.any { it.address == saved } }
                ?: devices.firstOrNull { it.name.contains("codepc", ignoreCase = true) }?.address,
        )
    }

    fun selectDevice(address: String) {
        _uiState.value = _uiState.value.copy(selectedAddress = address)
    }

    fun connect() {
        val state = _uiState.value
        val address = state.selectedAddress ?: return
        val device = repository.remoteDevice(address) ?: run {
            _uiState.value = state.copy(error = "Bluetooth permission is required")
            return
        }
        val activeClient = client ?: return

        viewModelScope.launch {
            _uiState.value = state.copy(busy = true, error = null, connectionLabel = "Connecting…")
            runCatching {
                activeClient.connect(device)
                preferences.edit().putString("last-device-address", address).apply()
                activeClient.requestStatus()
            }.onSuccess { status ->
                _uiState.value = _uiState.value.copy(
                    busy = false,
                    connected = true,
                    connectionLabel = "Connected",
                    status = status,
                    error = null,
                )
            }.onFailure { error ->
                activeClient.close()
                _uiState.value = _uiState.value.copy(
                    busy = false,
                    connected = false,
                    connectionLabel = "Disconnected",
                    error = error.message ?: error::class.java.simpleName,
                )
            }
        }
    }

    fun refreshStatus() {
        val activeClient = client ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(busy = true, error = null)
            runCatching { activeClient.requestStatus() }
                .onSuccess { status ->
                    _uiState.value = _uiState.value.copy(busy = false, status = status)
                }
                .onFailure { error ->
                    activeClient.close()
                    _uiState.value = _uiState.value.copy(
                        busy = false,
                        connected = false,
                        connectionLabel = "Disconnected",
                        error = error.message ?: error::class.java.simpleName,
                    )
                }
        }
    }

    fun disconnect() {
        val activeClient = client ?: return
        viewModelScope.launch {
            activeClient.disconnect()
            _uiState.value = _uiState.value.copy(
                connected = false,
                busy = false,
                connectionLabel = "Disconnected",
            )
        }
    }

    override fun onCleared() {
        client?.close()
        super.onCleared()
    }
}

data class UiState(
    val bluetoothSupported: Boolean = true,
    val bluetoothEnabled: Boolean = true,
    val permissionRequired: Boolean = false,
    val devices: List<BondedDevice> = emptyList(),
    val selectedAddress: String? = null,
    val busy: Boolean = false,
    val connected: Boolean = false,
    val connectionLabel: String = "Disconnected",
    val status: CodePcStatus? = null,
    val error: String? = null,
)
