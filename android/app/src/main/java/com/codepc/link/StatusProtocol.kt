package com.codepc.link

import org.json.JSONObject
import java.util.UUID

object StatusProtocol {
    val RFCOMM_SERVICE_UUID: UUID = UUID.fromString("0330ce6c-09db-5189-b7ad-e16bcafac7ee")
    const val STATUS_REQUEST = "{\"schema\":1,\"op\":\"status\"}\n"

    data class ParsedStatus(
        val summary: String,
        val cockpitUrl: String?,
        val raw: String,
    )

    fun parseResponse(line: String): ParsedStatus {
        val root = JSONObject(line)
        require(root.optInt("schema", -1) == 1) { "Unsupported response schema" }
        if (!root.optBoolean("ok", false)) {
            val error = root.optJSONObject("error")
            val code = error?.optString("code", "UNKNOWN") ?: "UNKNOWN"
            val message = error?.optString("message", "RFCOMM request failed")
                ?: "RFCOMM request failed"
            error("$code: $message")
        }
        require(root.optString("op") == "status") { "Unexpected RFCOMM operation" }

        val status = root.getJSONObject("status")
        require(status.optInt("schema", -1) == 1) { "Unsupported status schema" }
        val device = status.optJSONObject("device") ?: JSONObject()
        val network = status.optJSONObject("network") ?: JSONObject()
        val cockpit = status.optJSONObject("cockpit") ?: JSONObject()
        val interfaces = network.optJSONArray("interfaces")

        val interfaceLines = mutableListOf<String>()
        val cockpitCandidates = mutableListOf<Pair<Boolean, String>>()

        if (interfaces != null) {
            for (index in 0 until interfaces.length()) {
                val iface = interfaces.optJSONObject(index) ?: continue
                val name = iface.optString("name", "unknown")
                val type = iface.optString("type", "unknown")
                val link = iface.optString("link", "unknown")
                val defaultRoute = iface.optBoolean("default_route", false)
                val addresses = iface.optJSONArray("addresses")
                val addressValues = mutableListOf<String>()

                if (addresses != null) {
                    for (addressIndex in 0 until addresses.length()) {
                        val value = addresses.optString(addressIndex)
                        if (value.isBlank()) continue
                        addressValues += value
                        val host = value.substringBefore('/')
                        if (isUsableIpv4(host)) {
                            cockpitCandidates += defaultRoute to host
                        }
                    }
                }

                val flags = if (defaultRoute) " default" else ""
                interfaceLines += "- $name [$type] $link$flags: " +
                    (addressValues.ifEmpty { listOf("no address") }.joinToString(", "))
            }
        }

        val cockpitPort = cockpit.optInt("port", 9090)
        val selectedHost = cockpitCandidates
            .sortedByDescending { it.first }
            .firstOrNull()
            ?.second
        val cockpitUrl = selectedHost?.let { "https://$it:$cockpitPort/" }

        val summary = buildString {
            appendLine(device.optString("name", "CodePC Link"))
            appendLine("Hostname: ${device.optString("hostname", "unknown")}")
            appendLine("Daemon: ${device.optString("version", "unknown")}")
            appendLine()
            appendLine("Network:")
            if (interfaceLines.isEmpty()) {
                appendLine("- no interfaces reported")
            } else {
                interfaceLines.forEach(::appendLine)
            }
            appendLine()
            append("Cockpit: ")
            append(
                when {
                    cockpit.optBoolean("available", false) -> "running"
                    cockpit.has("available") && cockpit.isNull("available") -> "unknown"
                    else -> "not running"
                },
            )
            append(" on port $cockpitPort")
            if (cockpitUrl != null) {
                appendLine()
                append("Target: $cockpitUrl")
            }
        }

        return ParsedStatus(summary = summary, cockpitUrl = cockpitUrl, raw = line)
    }

    private fun isUsableIpv4(host: String): Boolean {
        val octets = host.split('.')
        if (octets.size != 4) return false
        val numbers = octets.map { it.toIntOrNull() ?: return false }
        if (numbers.any { it !in 0..255 }) return false
        if (numbers[0] == 0 || numbers[0] == 127) return false
        if (numbers[0] == 169 && numbers[1] == 254) return false
        return true
    }
}
