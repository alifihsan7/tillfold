package id.my.alifihsan.tillfold.ui

import java.text.NumberFormat
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

const val MAX_MONEY = 9_000_000_000_000_000L
private val indonesian = Locale.forLanguageTag("id-ID")
fun rupiah(value: Long): String = "Rp " + NumberFormat.getIntegerInstance(indonesian).format(value)
fun signedRupiah(value: Long, incoming: Boolean): String = (if (incoming) "+" else "−") + rupiah(value)
fun todayWib(): String = LocalDate.now(ZoneId.of("Asia/Jakarta")).toString()
fun validDate(value: String): Boolean = runCatching { LocalDate.parse(value).toString() == value }.getOrDefault(false)
fun shortDate(value: String): String = runCatching {
    LocalDate.parse(value).format(DateTimeFormatter.ofPattern("d MMM yyyy", indonesian))
}.getOrDefault(value)
fun parseAmount(value: String, allowZero: Boolean = false): Long? {
    if (value.isEmpty() || value.any { !it.isDigit() }) return null
    return value.toLongOrNull()?.takeIf { it in (if (allowZero) 0L else 1L)..MAX_MONEY }
}
fun roleName(value: String): String = when (value) {
    "operasional" -> "Operasional"; "gajian" -> "Penerimaan gaji"; "tagihan" -> "Tagihan"
    "tabungan" -> "Tabungan"; "investasi" -> "Investasi"; "darurat" -> "Dana darurat"
    "ewallet" -> "Dompet digital"; else -> value.replaceFirstChar { it.uppercase() }
}
