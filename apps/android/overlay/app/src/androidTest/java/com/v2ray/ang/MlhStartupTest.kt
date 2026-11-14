package com.v2ray.ang

import android.os.SystemClock
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.WorkManager
import com.v2ray.ang.handler.CommunitySubscriptions
import com.v2ray.ang.handler.MmkvManager
import com.v2ray.ang.handler.SubscriptionUpdater
import com.v2ray.ang.ui.main.MainActivity
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.TimeUnit

@RunWith(AndroidJUnit4::class)
class MlhStartupTest {
    private fun awaitCondition(condition: () -> Boolean) {
        val deadline = SystemClock.elapsedRealtime() + 30000
        while (!condition() && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(100)
        assertTrue("Startup condition timed out", condition())
    }

    @Test fun offlineLaunchSeedsSchedulesAndPreservesDeletionAfterRelaunch() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals("io.github.hidooch980.mlhvpn.fdroid", context.packageName)
        assertEquals("MLH VPN", context.getString(R.string.app_name))
        ActivityScenario.launch(MainActivity::class.java).use {
            awaitCondition { MmkvManager.decodeSettingsBool(CommunitySubscriptions.INSTALLED_KEY, false) }
            assertTrue(MmkvManager.decodeSettingsBool(AppConfig.PREF_SPEED_ENABLED))
            for (source in CommunitySubscriptions.sources) {
                val item = MmkvManager.decodeSubscription(source.id)
                assertNotNull(item)
                assertEquals(source.url, item!!.url)
                assertTrue(item.autoUpdate)
                assertEquals(60L, item.updateInterval)
            }
            awaitCondition {
                WorkManager.getInstance(context)
                    .getWorkInfosByTag(AppConfig.SUBSCRIPTION_UPDATE_TASK_NAME)
                    .get(5, TimeUnit.SECONDS).count { work -> !work.state.isFinished } >= CommunitySubscriptions.sources.size
            }
        }
        MmkvManager.encodeSettings(AppConfig.PREF_SPEED_ENABLED, false)
        val removed = CommunitySubscriptions.sources.first().id
        MmkvManager.removeSubscription(removed)
        SubscriptionUpdater.cancelOne(context, removed)
        val kept = CommunitySubscriptions.sources.last().id
        val edited = MmkvManager.decodeSubscription(kept)!!
        edited.autoUpdate = false
        MmkvManager.encodeSubscription(kept, edited)
        SubscriptionUpdater.syncOne(context, kept)
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.recreate()
            InstrumentationRegistry.getInstrumentation().waitForIdleSync()
            assertFalse(MmkvManager.decodeSettingsBool(AppConfig.PREF_SPEED_ENABLED))
            assertNull(MmkvManager.decodeSubscription(removed))
            assertFalse(MmkvManager.decodeSubscription(kept)!!.autoUpdate)
        }
    }
}
