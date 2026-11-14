package com.v2ray.ang.core

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class SessionTrafficCounterTest {
    @Test fun `totals and rates use monotonic elapsed time`() {
        val counter = SessionTrafficCounter()
        counter.start(1000)
        assertNull(counter.snapshot()!!.sent)
        val first = counter.record(1000, 4000, 600, 300)!!
        assertEquals(200.0, first.sendRate)
        assertEquals(100.0, first.receiveRate)
        assertEquals(600L, first.sent)
        assertEquals(900L, counter.record(1000, 7000, 300, 0)!!.sent)
    }
    @Test fun `stop and restart invalidate old session samples`() {
        val counter = SessionTrafficCounter()
        counter.start(1000)
        counter.stop()
        assertNull(counter.record(1000, 2000, 500, 200))
        counter.start(3000)
        assertNull(counter.record(1000, 4000, 500, 200))
        assertNull(counter.record(3000, 3000, 500, 200))
        assertNull(counter.snapshot()!!.sent)
    }
    @Test fun `negative samples and overflow cannot corrupt totals`() {
        val counter = SessionTrafficCounter()
        counter.start(1)
        assertEquals(0L, counter.record(1, 2, -1, -1)!!.sent)
        counter.record(1, 3, Long.MAX_VALUE, 0)
        assertEquals(Long.MAX_VALUE, counter.record(1, 4, 100, 0)!!.sent)
    }
}
