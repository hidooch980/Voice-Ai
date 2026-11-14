package com.v2ray.ang.dto

import java.io.Serializable

data class SessionTelemetry(
    val startedAt: Long,
    val sampledAt: Long,
    val sent: Long? = null,
    val received: Long? = null,
    val sendRate: Double? = null,
    val receiveRate: Double? = null
) : Serializable {
    companion object { const val MESSAGE = 2101 }
}
