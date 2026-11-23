package id.my.alifihsan.tillfold

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.activity.ComponentActivity
import android.graphics.Canvas
import android.graphics.Bitmap
import id.my.alifihsan.tillfold.data.TillfoldRepository
import id.my.alifihsan.tillfold.ui.TillfoldApp
import id.my.alifihsan.tillfold.ui.TillfoldViewModel
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeUiTest {
    @get:Rule val compose = createAndroidComposeRule<ComponentActivity>()
    @Test fun login_and_demo_navigation_render_without_network() {
        val api = FakeApi()
        val session = MemorySession(theme = "light")
        val model = TillfoldViewModel(TillfoldRepository(api, session), session)
        compose.setContent { TillfoldApp(model) }
        compose.onNodeWithText("Selamat datang kembali").assertIsDisplayed()
        screenshot("login-light")
        compose.onNodeWithText("Lihat demo tanpa akun").performScrollTo().performClick()
        compose.onNodeWithText("Mode demo · semua angka adalah data contoh").assertIsDisplayed()
        compose.onNodeWithText("Total saldo kas").assertIsDisplayed()
        screenshot("overview-light")
        compose.onNodeWithText("Transaksi", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Cari transaksi").assertIsDisplayed()
        screenshot("transactions-light")
        compose.onNodeWithText("Rencana", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Target tabungan").assertIsDisplayed()
        screenshot("plans-light")
        compose.onNodeWithText("Rekening", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Mandiri").assertIsDisplayed()
        screenshot("accounts-light")
        assertEquals(0, api.calls)
        assertEquals(0, api.writes)
    }
    @Test fun dark_mode_and_transaction_sheet_render_with_honest_demo_state() {
        val session = MemorySession(theme = "dark")
        val model = TillfoldViewModel(TillfoldRepository(FakeApi(), session), session)
        model.enterDemo()
        compose.setContent { TillfoldApp(model) }
        compose.onNodeWithText("Total saldo kas").assertIsDisplayed()
        screenshot("overview-dark")
        compose.onNodeWithContentDescription("Catat transaksi").performClick()
        compose.onNodeWithText("Keterangan").assertIsDisplayed()
        compose.onNodeWithText("Simpan transaksi").performScrollTo().assertIsNotEnabled()
        screenshot("transaction-sheet-dark")
    }
    private fun screenshot(name: String) {
        compose.waitForIdle()
        val directory = File("build/screenshots").apply { mkdirs() }
        compose.runOnIdle {
            val view = org.robolectric.shadows.ShadowDialog.getLatestDialog()?.takeIf { it.isShowing }?.window?.decorView
                ?: compose.activity.window.decorView
            val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(bitmap))
            File(directory, "$name.png").outputStream().use { stream ->
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
            }
            bitmap.recycle()
        }
    }
}
