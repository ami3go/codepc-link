package io.github.ami3go.codepclink

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.ami3go.codepclink.protocol.CodePcStatus
import io.github.ami3go.codepclink.protocol.NetworkInterfaceStatus

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                CodePcApp(vm)
            }
        }
    }
}

@Composable
private fun CodePcApp(vm: MainViewModel = viewModel()) {
    val state by vm.uiState.collectAsState()
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { vm.refreshDevices() }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("CodePC Link", style = MaterialTheme.typography.headlineMedium)
            Text("Bluetooth Serial / RFCOMM", style = MaterialTheme.typography.bodyMedium)

            when {
                !state.bluetoothSupported -> Text("Bluetooth is not available on this device.")
                state.permissionRequired -> {
                    Text("CodePC Link needs permission to communicate with paired Bluetooth devices.")
                    Button(onClick = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                            permissionLauncher.launch(Manifest.permission.BLUETOOTH_CONNECT)
                        }
                    }) { Text("Grant Bluetooth permission") }
                }
                !state.bluetoothEnabled -> {
                    Text("Bluetooth is turned off.")
                    Button(onClick = {
                        context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    }) { Text("Open Bluetooth settings") }
                    Button(onClick = vm::refreshDevices) { Text("Check again") }
                }
                else -> {
                    Text("Paired devices", style = MaterialTheme.typography.titleMedium)
                    if (state.devices.isEmpty()) {
                        Text("No paired devices. Pair the CodePC in Android Bluetooth settings first.")
                    }
                    state.devices.forEach { device ->
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(
                                    selected = state.selectedAddress == device.address,
                                    onClick = { vm.selectDevice(device.address) },
                                )
                                Column {
                                    Text(device.name)
                                    Text(device.address, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            enabled = !state.busy && !state.connected && state.selectedAddress != null,
                            onClick = vm::connect,
                        ) { Text("Connect") }
                        Button(
                            enabled = !state.busy && state.connected,
                            onClick = vm::refreshStatus,
                        ) { Text("Refresh") }
                        Button(
                            enabled = !state.busy && state.connected,
                            onClick = vm::disconnect,
                        ) { Text("Disconnect") }
                    }
                    Button(enabled = !state.busy, onClick = vm::refreshDevices) {
                        Text("Reload paired devices")
                    }
                }
            }

            Text("Connection: ${state.connectionLabel}")
            state.error?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }
            state.status?.let { status ->
                StatusCard(status = status) { host, port ->
                    val safeHost = if (host.contains(":")) "[$host]" else host
                    context.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse("https://$safeHost:$port"))
                    )
                }
            }
        }
    }
}

@Composable
private fun StatusCard(
    status: CodePcStatus,
    onOpenCockpit: (String, Int) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(status.deviceName, style = MaterialTheme.typography.titleLarge)
            Text(status.hostname)
            status.version?.let { Text("Daemon $it", style = MaterialTheme.typography.bodySmall) }
            Text(
                "Cockpit: " + when (status.cockpitAvailable) {
                    true -> "running"
                    false -> "not running"
                    null -> "unknown"
                }
            )

            status.interfaces.forEach { iface ->
                InterfaceBlock(iface, status.cockpitPort, onOpenCockpit)
            }
        }
    }
}

@Composable
private fun InterfaceBlock(
    iface: NetworkInterfaceStatus,
    cockpitPort: Int,
    onOpenCockpit: (String, Int) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Spacer(Modifier.height(4.dp))
        Text("${iface.name} · ${iface.type}", style = MaterialTheme.typography.titleMedium)
        Text(
            listOfNotNull(
                iface.link,
                if (iface.defaultRoute) "default route" else null,
                when (iface.internet) {
                    true -> "internet"
                    false -> "no internet"
                    null -> null
                },
            ).joinToString(" · ")
        )
        iface.ssid?.let { Text("Wi‑Fi: $it") }
        if (iface.addresses.isEmpty()) Text("No address")
        iface.addresses.forEach { addressWithPrefix ->
            val host = addressWithPrefix.substringBefore("/")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(host, modifier = Modifier.weight(1f))
                if (isUsableHost(host)) {
                    Button(onClick = { onOpenCockpit(host, cockpitPort) }) {
                        Text("Open Cockpit")
                    }
                }
            }
        }
    }
}

private fun isUsableHost(host: String): Boolean {
    if (host.isBlank()) return false
    if (host == "0.0.0.0" || host == "::" || host == "::1") return false
    if (host.startsWith("127.")) return false
    if (host.startsWith("169.254.")) return false
    if (host.startsWith("fe80:", ignoreCase = true)) return false
    return true
}
