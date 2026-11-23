package id.my.alifihsan.tillfold.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import id.my.alifihsan.tillfold.R

private val jakarta = FontFamily(
    Font(R.font.plus_jakarta_sans, FontWeight.Normal),
    Font(R.font.plus_jakarta_sans, FontWeight.Medium),
    Font(R.font.plus_jakarta_sans, FontWeight.SemiBold),
    Font(R.font.plus_jakarta_sans, FontWeight.Bold),
)
private val light = lightColorScheme(
    primary = Color(0xFF15181D), onPrimary = Color.White,
    primaryContainer = Color(0xFFD8DDE3), onPrimaryContainer = Color(0xFF262B32),
    secondary = Color(0xFF48505B), secondaryContainer = Color(0xFFD8DDE3), onSecondaryContainer = Color(0xFF111419),
    background = Color(0xFFE4E7EB), onBackground = Color(0xFF111419),
    surface = Color.White, onSurface = Color(0xFF111419),
    surfaceVariant = Color(0xFFF2F4F6), onSurfaceVariant = Color(0xFF5A626D),
    outline = Color(0xFF818C9A), outlineVariant = Color(0xFFD6DBE1),
    error = Color(0xFFB3352E), errorContainer = Color(0xFFF4E3E1), onErrorContainer = Color(0xFF792A24),
)
private val dark = darkColorScheme(
    primary = Color(0xFFEEF1F4), onPrimary = Color(0xFF15181D),
    primaryContainer = Color(0xFF3B414A), onPrimaryContainer = Color(0xFFF3F5F7),
    secondary = Color(0xFFD5DAE1), secondaryContainer = Color(0xFF2D323A), onSecondaryContainer = Color(0xFFF3F5F7),
    background = Color(0xFF171A1F), onBackground = Color(0xFFF3F5F7),
    surface = Color(0xFF23272E), onSurface = Color(0xFFF3F5F7),
    surfaceVariant = Color(0xFF2D323A), onSurfaceVariant = Color(0xFFAAB2BD),
    outline = Color(0xFF858D99), outlineVariant = Color(0xFF3B424D),
    error = Color(0xFFFF9E96), errorContainer = Color(0xFF452D2D), onErrorContainer = Color(0xFFFF9E96),
)
@Composable fun positive(): Color = if (MaterialTheme.colorScheme.background == light.background) Color(0xFF147A46) else Color(0xFFB9DFC9)
@Composable fun goalAccent(value: String): Color {
    val isLight = MaterialTheme.colorScheme.background == light.background
    return when (value) {
        "cyan" -> if (isLight) Color(0xFF0369A1) else Color(0xFF67E8F9)
        "amber" -> if (isLight) Color(0xFFB45309) else Color(0xFFFCD34D)
        "purple" -> if (isLight) Color(0xFF6D28D9) else Color(0xFFD8B4FE)
        "rose" -> MaterialTheme.colorScheme.error
        else -> positive()
    }
}
@Composable fun TillfoldTheme(mode: String = "system", content: @Composable () -> Unit) {
    val isDark = when (mode) { "dark" -> true; "light" -> false; else -> isSystemInDarkTheme() }
    val base = TextStyle(fontFamily = jakarta, fontFeatureSettings = "tnum")
    MaterialTheme(colorScheme = if (isDark) dark else light, typography = Typography(
        displaySmall = base.copy(fontSize = 34.sp, fontWeight = FontWeight.Bold, letterSpacing = (-1).sp),
        headlineMedium = base.copy(fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.7).sp),
        titleLarge = base.copy(fontSize = 22.sp, fontWeight = FontWeight.Bold),
        titleMedium = base.copy(fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
        titleSmall = base.copy(fontSize = 14.sp, fontWeight = FontWeight.SemiBold),
        bodyLarge = base.copy(fontSize = 16.sp), bodyMedium = base.copy(fontSize = 14.sp),
        bodySmall = base.copy(fontSize = 12.sp), labelLarge = base.copy(fontSize = 14.sp, fontWeight = FontWeight.SemiBold),
        labelMedium = base.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium),
    ), content = content)
}
