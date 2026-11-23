package id.my.alifihsan.tillfold

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import id.my.alifihsan.tillfold.data.SessionStore
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SessionStoreDeviceTest {
    @Test fun token_round_trips_through_keystore_and_logout_clears_ciphertext() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val store = SessionStore(context)
        store.save("dummy-device-test-token")
        val raw = context.getSharedPreferences("tillfold_session", 0).getString("token", null)
        assertNotNull(raw)
        assertFalse(raw!!.contains("dummy-device-test-token"))
        assertEquals("dummy-device-test-token", SessionStore(context).token)
        store.clear()
        assertNull(SessionStore(context).token)
        assertNull(context.getSharedPreferences("tillfold_session", 0).getString("token", null))
    }
}
