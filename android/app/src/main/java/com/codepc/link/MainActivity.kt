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
import android.net.http.SslCertificate
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.text.method.ScrollingMovementMethod
import android.view.ViewGroup
import android.webkit.SslErrorHandler
import android.webkit.ConsoleMessage
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebChromeClient
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import java.security.MessageDigest

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
    private lateinit var connectionTabButton: Button
    private lateinit var cockpitTabButton: Button
    private lateinit var connectionPanel: LinearLayout
    private lateinit var cockpitPanel: LinearLayout
    private lateinit var cockpitAddressView: TextView
    private lateinit var cockpitWebView: WebView
    private var cockpitLoadedUrl: String? = null
    private var cockpitPageProblem: String? = null
    private val approvedSslOrigins = mutableSetOf<String>()

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

        val tabs = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        connectionTabButton = Button(this).apply {
            text = "Connection"
            setOnClickListener { showConnectionTab() }
        }
        cockpitTabButton = Button(this).apply {
            text = "Cockpit"
            isEnabled = false
            setOnClickListener { showCockpitTab() }
        }
        tabs.addView(
            connectionTabButton,
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f),
        )
        tabs.addView(
            cockpitTabButton,
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f),
        )
        root.addView(tabs)

        connectionPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        root.addView(
            connectionPanel,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ),
        )

        connectionPanel.addView(
            text(
                "First pairing is controlled by the CodePC. Open Cockpit → CodePC Link on the mini-PC, " +
                    "scan for this phone, and start Pair from CodePC. This app never initiates pairing.",
                14f,
            ),
        )

        deviceView = text("Paired PC: not selected")
        connectionView = text("Disconnected")
        connectionPanel.addView(deviceView)
        connectionPanel.addView(connectionView)

        val chooseButton = Button(this).apply {
            text = "Choose paired CodePC"
            setOnClickListener { choosePairedDevice() }
        }
        connectionPanel.addView(chooseButton)

        connectButton = Button(this).apply {
            text = "Connect"
            setOnClickListener { connectSelectedDevice() }
        }
        connectionPanel.addView(connectButton)

        statusButton = Button(this).apply {
            text = "Request status"
            isEnabled = false
            setOnClickListener { requestStatus() }
        }
        connectionPanel.addView(statusButton)

        disconnectButton = Button(this).apply {
            text = "Disconnect"
            isEnabled = false
            setOnClickListener { disconnect() }
        }
        connectionPanel.addView(disconnectButton)

        cockpitButton = Button(this).apply {
            text = "Open Cockpit"
            isEnabled = false
            setOnClickListener { openCockpit() }
        }
        connectionPanel.addView(cockpitButton)

        resultView = text("No status received yet.").apply {
            setTextIsSelectable(true)
            movementMethod = ScrollingMovementMethod()
        }
        connectionPanel.addView(
            resultView,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ),
        )

        cockpitPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = LinearLayout.GONE
        }
        cockpitAddressView = text("Request status to discover the Cockpit address.", 14f).apply {
            setTextIsSelectable(true)
        }
        cockpitPanel.addView(cockpitAddressView)

        val webControls = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        webControls.addView(
            Button(this).apply {
                text = "Reload"
                setOnClickListener { cockpitWebView.reload() }
            },
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f),
        )
        webControls.addView(
            Button(this).apply {
                text = "Open externally"
                setOnClickListener { openCockpit() }
            },
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f),
        )
        cockpitPanel.addView(webControls)
        cockpitPanel.addView(
            Button(this).apply {
                text = "Update Android System WebView"
                setOnClickListener { openWebViewUpdate() }
            },
        )

        cockpitWebView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            webChromeClient = object : WebChromeClient() {
                override fun onConsoleMessage(consoleMessage: ConsoleMessage): Boolean {
                    if (
                        consoleMessage.messageLevel() == ConsoleMessage.MessageLevel.ERROR &&
                        consoleMessage.message().contains("SyntaxError", ignoreCase = true)
                    ) {
                        cockpitPageProblem =
                            "Cockpit needs a newer Android System WebView. " +
                            "Installed: ${installedWebViewVersion()}. Update WebView, restart this app, " +
                            "and request status again."
                        cockpitAddressView.text = cockpitPageProblem
                    }
                    return super.onConsoleMessage(consoleMessage)
                }
            }
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    request: WebResourceRequest,
                ): Boolean = handleWebNavigation(request.url)

                @Suppress("DEPRECATION")
                override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean =
                    handleWebNavigation(Uri.parse(url))

                override fun onPageFinished(view: WebView, url: String) {
                    cockpitAddressView.text = cockpitPageProblem ?: url
                }

                override fun onReceivedSslError(
                    view: WebView,
                    handler: SslErrorHandler,
                    error: SslError,
                ) {
                    handleCockpitSslError(handler, error)
                }
            }
        }
        cockpitPanel.addView(
            cockpitWebView,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ),
        )
        root.addView(
            cockpitPanel,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ),
        )
        showConnectionTab()
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
                updateCockpitTarget(null)
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
                                updateCockpitTarget(parsed.cockpitUrl)
                                setConnection("Status received")
                                if (parsed.cockpitUrl != null) showCockpitTab()
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

    private fun updateCockpitTarget(target: String?) {
        cockpitUrl = target
        cockpitButton.isEnabled = target != null
        cockpitTabButton.isEnabled = target != null
        cockpitLoadedUrl = null
        cockpitPageProblem = null
        cockpitWebView.stopLoading()
        cockpitWebView.loadUrl("about:blank")
        cockpitWebView.clearHistory()
        cockpitAddressView.text = target ?: "Request status to discover the Cockpit address."
        if (target == null) showConnectionTab()
    }

    private fun showConnectionTab() {
        connectionPanel.visibility = LinearLayout.VISIBLE
        cockpitPanel.visibility = LinearLayout.GONE
        connectionTabButton.alpha = 1f
        cockpitTabButton.alpha = 0.65f
    }

    private fun showCockpitTab() {
        val target = cockpitUrl ?: return
        connectionPanel.visibility = LinearLayout.GONE
        cockpitPanel.visibility = LinearLayout.VISIBLE
        connectionTabButton.alpha = 0.65f
        cockpitTabButton.alpha = 1f
        if (cockpitLoadedUrl != target) {
            cockpitLoadedUrl = target
            cockpitPageProblem = null
            cockpitAddressView.text = target
            cockpitWebView.loadUrl(target)
        }
    }

    private fun handleWebNavigation(uri: Uri): Boolean {
        val allowed = Uri.parse(cockpitUrl ?: return true)
        val staysOnSelectedPc = sameOrigin(uri, allowed)
        if (!staysOnSelectedPc) {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        }
        return !staysOnSelectedPc
    }

    private fun handleCockpitSslError(handler: SslErrorHandler, error: SslError) {
        val target = Uri.parse(cockpitUrl ?: run {
            handler.cancel()
            return
        })
        val failed = Uri.parse(error.url)
        if (!sameOrigin(failed, target)) {
            handler.cancel()
            return
        }

        val origin = "${target.scheme}://${target.host}:${target.port}"
        if (origin in approvedSslOrigins) {
            handler.proceed()
            return
        }

        val fingerprint = certificateFingerprint(error.certificate)
        val detail = buildString {
            appendLine("Android does not trust the Cockpit certificate for:")
            appendLine(origin)
            appendLine()
            appendLine("Certificate: ${error.certificate.issuedTo.cName ?: "unknown"}")
            if (fingerprint != null) appendLine("SHA-256: $fingerprint")
            appendLine()
            append("Continue only if this is your CodePC. Approval lasts until the app closes.")
        }
        cockpitAddressView.text = "Cockpit certificate confirmation required"

        AlertDialog.Builder(this)
            .setTitle("Untrusted Cockpit certificate")
            .setMessage(detail)
            .setPositiveButton("Continue this session") { _, _ ->
                approvedSslOrigins += origin
                handler.proceed()
            }
            .setNegativeButton("Open externally") { _, _ ->
                handler.cancel()
                openCockpit()
            }
            .setOnCancelListener { handler.cancel() }
            .show()
    }

    private fun sameOrigin(first: Uri, second: Uri): Boolean =
        first.scheme == "https" &&
            first.scheme == second.scheme &&
            first.host == second.host &&
            first.port == second.port

    @Suppress("DEPRECATION")
    private fun installedWebViewVersion(): String = runCatching {
        packageManager.getPackageInfo("com.google.android.webview", 0).versionName ?: "unknown"
    }.getOrDefault("unknown")

    private fun openWebViewUpdate() {
        val packageUri = Uri.parse("market://details?id=com.google.android.webview")
        val storeIntent = Intent(Intent.ACTION_VIEW, packageUri)
        runCatching { startActivity(storeIntent) }
            .onFailure {
                startActivity(
                    Intent(
                        Intent.ACTION_VIEW,
                        Uri.parse(
                            "https://play.google.com/store/apps/details?id=com.google.android.webview",
                        ),
                    ),
                )
            }
    }

    private fun certificateFingerprint(certificate: SslCertificate): String? = runCatching {
        val state = SslCertificate.saveState(certificate)
        val encoded = state.getByteArray("x509-certificate") ?: return@runCatching null
        MessageDigest.getInstance("SHA-256")
            .digest(encoded)
            .joinToString(":") { byte -> "%02X".format(byte.toInt() and 0xff) }
    }.getOrNull()

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
        cockpitWebView.stopLoading()
        cockpitWebView.destroy()
        super.onDestroy()
    }

    companion object {
        private const val REQUEST_CONNECT_PERMISSION = 1001
        private const val PREF_DEVICE_ADDRESS = "selected_device_address"
    }
}
