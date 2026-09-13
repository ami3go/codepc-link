package io.github.ami3go.codepclink.protocol

import org.json.JSONObject

const val CODEPC_RFCOMM_UUID = "0330ce6c-09db-5189-b7ad-e16bcafac7ee"
const val SCHEMA_VERSION = 1
const val MAX_RESPONSE_BYTES = 64 * 1024

fun statusRequest(): ByteArray =
    "{\"schema\":$SCHEMA_VERSION,\"op\":\"status\"}\n".toByteArray(Charsets.UTF_8)

fun parseStatusResponse(line: String): CodePcStatus {
    val root = JSONObject(line)
    require(root.optInt("schema", -1) == SCHEMA_VERSION) { "Unsupported schema" }
    require(root.optBoolean("ok", false)) {
        root.optJSONObject("error")?.optString("message") ?: "CodePC returned an error"
    }
    require(root.optString("op") == "status") { "Unexpected response operation" }

    val status = root.getJSONObject("status")
    val deviceJson = status.optJSONObject("device") ?: JSONObject()
    val cockpitJson = status.optJSONObject("cockpit") ?: JSONObject()
    val networkJson = status.optJSONObject("network") ?: JSONObject()
    val interfacesJson = networkJson.optJSONArray("interfaces")

    val interfaces = buildList {
        if (interfacesJson != null) {
            for (index in 0 until interfacesJson.length()) {
                val item = interfacesJson.optJSONObject(index) ?: continue
                val addressesJson = item.optJSONArray("addresses")
                val addresses = buildList {
                    if (addressesJson != null) {
                        for (addressIndex in 0 until addressesJson.length()) {
                            addressesJson.optString(addressIndex)
                                .takeIf { it.isNotBlank() }
                                ?.let(::add)
                        }
                    }
                }
                add(
                    NetworkInterfaceStatus(
                        name = item.optString("name", "unknown"),
                        type = item.optString("type", "unknown"),
                        link = item.optString("link", "unknown"),
                        addresses = addresses,
                        ssid = item.optString("ssid").takeIf { it.isNotBlank() },
                        defaultRoute = item.optBoolean("default_route", false),
                        internet = if (item.has("internet") && !item.isNull("internet")) {
                            item.optBoolean("internet")
                        } else {
                            null
                        },
                    )
                )
            }
        }
    }

    return CodePcStatus(
        deviceName = deviceJson.optString("name", "CodePC Link"),
        hostname = deviceJson.optString("hostname", "unknown"),
        version = deviceJson.optString("version").takeIf { it.isNotBlank() },
        cockpitPort = cockpitJson.optInt("port", 9090),
        cockpitAvailable = if (cockpitJson.has("available") && !cockpitJson.isNull("available")) {
            cockpitJson.optBoolean("available")
        } else {
            null
        },
        interfaces = interfaces,
    )
}

data class CodePcStatus(
    val deviceName: String,
    val hostname: String,
    val version: String?,
    val cockpitPort: Int,
    val cockpitAvailable: Boolean?,
    val interfaces: List<NetworkInterfaceStatus>,
)

data class NetworkInterfaceStatus(
    val name: String,
    val type: String,
    val link: String,
    val addresses: List<String>,
    val ssid: String?,
    val defaultRoute: Boolean,
    val internet: Boolean?,
)
