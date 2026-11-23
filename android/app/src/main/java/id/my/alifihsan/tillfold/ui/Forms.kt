package id.my.alifihsan.tillfold.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import id.my.alifihsan.tillfold.data.*
import java.util.UUID

@Composable fun TransactionForm(state: UiState, editing: Transaction?, onDismiss: () -> Unit, save: (TransactionWrite, Long?) -> Unit) {
    val accounts = state.dashboard.data?.accounts.orEmpty().filter { !it.isArchived }
    val categories = state.dashboard.data?.categories.orEmpty()
    var kind by rememberSaveable { mutableStateOf(editing?.type ?: "expense") }
    var amount by rememberSaveable { mutableStateOf(editing?.amount?.toString().orEmpty()) }
    var account by rememberSaveable { mutableStateOf(editing?.account ?: accounts.firstOrNull()?.name.orEmpty()) }
    var category by rememberSaveable { mutableStateOf(editing?.category.orEmpty()) }
    var description by rememberSaveable { mutableStateOf(editing?.description.orEmpty()) }
    var date by rememberSaveable { mutableStateOf(editing?.date ?: todayWib()) }
    val transfer = editing?.isTransfer == true
    val options = (categories.filter { it.type == kind }.map { it.name } + listOfNotNull(editing?.category?.takeIf { kind == editing.type })).distinct()
    val categoryValue = if (transfer) "Transfer" else category.takeIf { it in options } ?: options.firstOrNull().orEmpty()
    val valid = parseAmount(amount) != null && account.isNotBlank() && categoryValue.isNotBlank() && description.isNotBlank() && validDate(date)
    FormSheet(if (editing == null) "Catat transaksi" else "Edit transaksi", state.saving, onDismiss) {
        if (!transfer) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(kind == "expense", { kind = "expense"; category = "" }, label = { Text("Pengeluaran") }, enabled = !state.saving)
            FilterChip(kind == "income", { kind = "income"; category = "" }, label = { Text("Pemasukan") }, enabled = !state.saving)
        } else Muted("Perubahan nominal dan tanggal juga memperbarui pasangan transfer.")
        AmountField(amount, { amount = it }, enabled = !state.saving)
        OutlinedTextField(description, { description = it.take(255) }, Modifier.fillMaxWidth(), label = { Text("Keterangan") }, enabled = !state.saving)
        SelectField("Rekening", account, (accounts.map { it.name } + listOfNotNull(editing?.account)).distinct(), { account = it }, !state.saving)
        if (!transfer) SelectField("Kategori", categoryValue, options, { category = it }, !state.saving)
        DateField(date, { date = it }, !state.saving)
        if (accounts.isEmpty()) Muted("Belum ada rekening aktif. Tambahkan rekening melalui Pengaturan di dashboard web.")
        FormError(state.writeError)
        if (state.demo) Muted("Mode demo hanya untuk melihat tampilan. Data contoh tidak dapat diubah.")
        FullButton("Simpan transaksi", state.saving, valid && !state.demo) {
            save(TransactionWrite(kind, parseAmount(amount)!!, account, categoryValue, description.trim(), date,
                editing?.pocketId.takeIf { account == editing?.account }), editing?.id)
        }
    }
}

@Composable fun TransferForm(state: UiState, onDismiss: () -> Unit, save: (TransferWrite) -> Unit) {
    val accounts = state.dashboard.data?.accounts.orEmpty().filter { !it.isArchived }.map { it.name }
    var from by rememberSaveable { mutableStateOf(accounts.firstOrNull().orEmpty()) }
    var to by rememberSaveable { mutableStateOf(accounts.getOrNull(1).orEmpty()) }
    var amount by rememberSaveable { mutableStateOf("") }
    var description by rememberSaveable { mutableStateOf("") }
    var date by rememberSaveable { mutableStateOf(todayWib()) }
    FormSheet("Transfer antar-rekening", state.saving, onDismiss) {
        Muted("Saldo dipindahkan melalui dua catatan berpasangan. Total uangmu tetap sama.")
        SelectField("Dari rekening", from, accounts, { from = it }, !state.saving)
        SelectField("Ke rekening", to, accounts.filter { it != from }, { to = it }, !state.saving)
        AmountField(amount, { amount = it }, enabled = !state.saving)
        OutlinedTextField(description, { description = it.take(200) }, Modifier.fillMaxWidth(), label = { Text("Keterangan (opsional)") })
        DateField(date, { date = it }, !state.saving)
        FormError(state.writeError)
        FullButton("Catat transfer", state.saving, !state.demo && from.isNotBlank() && to.isNotBlank() && from != to && parseAmount(amount) != null) {
            save(TransferWrite(from, to, parseAmount(amount)!!, description.trim().ifBlank { "Transfer antar-rekening" }, date))
        }
    }
}

@Composable fun PaycheckForm(state: UiState, onDismiss: () -> Unit, save: (PaycheckWrite) -> Unit) {
    val accounts = state.dashboard.data?.accounts.orEmpty().filter { !it.isArchived }.map { it.name }
    var account by rememberSaveable { mutableStateOf(accounts.firstOrNull().orEmpty()) }
    var amount by rememberSaveable { mutableStateOf("") }
    var date by rememberSaveable { mutableStateOf(todayWib()) }
    var startCycle by rememberSaveable { mutableStateOf(true) }
    val requestKey = rememberSaveable { UUID.randomUUID().toString() }
    FormSheet("Catat gaji", state.saving, onDismiss) {
        Muted("Gaji dicatat ke satu rekening. Pembagian ke rekening lain belum ditransfer.")
        AmountField(amount, { amount = it }, "Nominal gaji", !state.saving)
        SelectField("Rekening penerima", account, accounts, { account = it }, !state.saving)
        DateField(date, { date = it }, !state.saving)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f)) { Text("Mulai siklus baru"); Muted("Durasi mengikuti pengaturan gajimu.") }
            Switch(startCycle, { startCycle = it }, enabled = !state.saving)
        }
        FormError(state.writeError)
        FullButton("Simpan gaji", state.saving, !state.demo && account.isNotBlank() && parseAmount(amount) != null) {
            save(PaycheckWrite(requestKey, parseAmount(amount)!!, account, date, startCycle))
        }
    }
}

@Composable fun GoalForm(state: UiState, onDismiss: () -> Unit, save: (GoalWrite) -> Unit) {
    var name by rememberSaveable { mutableStateOf("") }
    var target by rememberSaveable { mutableStateOf("") }
    var current by rememberSaveable { mutableStateOf("0") }
    val colors = linkedMapOf("Emerald" to "emerald", "Cyan" to "cyan", "Amber" to "amber", "Purple" to "purple", "Rose" to "rose")
    var color by rememberSaveable { mutableStateOf("Emerald") }
    FormSheet("Tambah target", state.saving, onDismiss) {
        OutlinedTextField(name, { name = it.take(100) }, Modifier.fillMaxWidth(), label = { Text("Nama target") })
        AmountField(target, { target = it }, "Nominal target")
        AmountField(current, { current = it }, "Sudah terkumpul")
        SelectField("Warna aksen", color, colors.keys.toList(), { color = it })
        Muted("Target ini memakai progres manual dan tidak memindahkan saldo rekening.")
        FormError(state.writeError)
        FullButton("Simpan target", state.saving, !state.demo && name.isNotBlank() && parseAmount(target) != null && parseAmount(current, true) != null) {
            save(GoalWrite(name.trim(), parseAmount(target)!!, parseAmount(current, true)!!, colors.getValue(color)))
        }
    }
}
