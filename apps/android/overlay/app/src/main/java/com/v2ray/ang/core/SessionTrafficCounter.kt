package com.v2ray.ang.core

import com.v2ray.ang.dto.SessionTelemetry

/** Daemon-owned totals; consumes the existing notification collector, never native stats twice. */
class SessionTrafficCounter {
    private var current: SessionTelemetry? = null
    @Synchronized fun start(now: Long) { current = SessionTelemetry(now, now) }
    @Synchronized fun stop() { current = null }
    @Synchronized fun snapshot(): SessionTelemetry? = current
    @Synchronized fun record(session: Long, now: Long, sent: Long, received: Long): SessionTelemetry? {
        val old = current ?: return null
        if (old.startedAt != session || now <= old.sampledAt) return null
        val up = sent.coerceAtLeast(0)
        val down = received.coerceAtLeast(0)
        val seconds = (now - old.sampledAt) / 1000.0
        val result = old.copy(sampledAt = now,
            sent = add(old.sent ?: 0, up), received = add(old.received ?: 0, down),
            sendRate = up / seconds, receiveRate = down / seconds)
        current = result
        return result
    }
    private fun add(total: Long, delta: Long): Long = if (Long.MAX_VALUE - total < delta) Long.MAX_VALUE else total + delta
}
