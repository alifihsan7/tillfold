package id.my.alifihsan.tillfold.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.res.painterResource
import id.my.alifihsan.tillfold.R
import id.my.alifihsan.tillfold.data.*
import id.my.alifihsan.tillfold.ui.theme.*

@Composable fun TransactionRow(tx: Transaction, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        val color = if (tx.isTransfer || tx.type.startsWith("adjustment")) MaterialTheme.colorScheme.onSurfaceVariant else if (tx.incoming) positive() else MaterialTheme.colorScheme.error
        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant) {
            Icon(if (tx.incoming) Icons.Default.KeyboardArrowDown else Icons.Default.KeyboardArrowUp, null, Modifier.padding(10.dp).size(18.dp), tint = color)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(tx.description, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Muted("${tx.category} · ${tx.account}")
            if (tx.isInternalLoan) Muted("Dana talangan internal")
        }
        Text(signedRupiah(tx.amount, tx.incoming), style = MaterialTheme.typography.labelLarge, color = color)
    }
}

@Composable fun OverviewScreen(state: UiState, refresh: () -> Unit, showAll: () -> Unit, edit: (Transaction) -> Unit, transfer: () -> Unit, paycheck: () -> Unit) {
    val data = state.dashboard
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        if (data.loading) item { LoadingCard("Memuat ringkasan…") }
        else if (data.error != null) item { ErrorCard(data.error, refresh) }
        else data.data?.let { dashboard ->
            val summary = dashboard.summary
            item {
                val ink = Color(0xFF15181D)
                Surface(shape = RoundedCornerShape(28.dp), color = ink, contentColor = Color(0xFFF3F5F7)) {
                    Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        Text("Total saldo kas", color = Color(0xFFAAB2BD), style = MaterialTheme.typography.bodyMedium)
                        Text(rupiah(summary.balance), style = MaterialTheme.typography.displaySmall)
                        Text("Seluruh rekening · saldo saat ini", style = MaterialTheme.typography.bodySmall, color = Color(0xFFAAB2BD))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Column(Modifier.weight(1f)) { Text("Pemasukan", style = MaterialTheme.typography.bodySmall, color = Color(0xFFAAB2BD)); Text(rupiah(summary.income), fontWeight = FontWeight.SemiBold, color = Color(0xFFB9DFC9)) }
                            Column(Modifier.weight(1f)) { Text("Pengeluaran", style = MaterialTheme.typography.bodySmall, color = Color(0xFFAAB2BD)); Text(rupiah(summary.expense), fontWeight = FontWeight.SemiBold, color = Color(0xFFFF9E96)) }
                        }
                    }
                }
            }
            item {
                val safe = summary.safe
                FoldPanel {
                    Text("Batas belanja harian", style = MaterialTheme.typography.titleMedium)
                    when {
                        safe == null || safe.budget <= 0 -> { Text("Anggaran belum tersedia", style = MaterialTheme.typography.titleLarge); Muted("Catat gaji dan atur rekening belanja untuk melihat batas harian.") }
                        safe.daysRemaining <= 0 || todayWib() > safe.end -> { Text("Siklus selesai", style = MaterialTheme.typography.titleLarge); Muted("Batas harian tidak berlaku untuk siklus yang sudah berakhir.") }
                        todayWib() < safe.start -> { Text("Siklus belum dimulai", style = MaterialTheme.typography.titleLarge); Muted("Batas harian tersedia setelah siklus dimulai.") }
                        else -> {
                            Text(rupiah(safe.daily), style = MaterialTheme.typography.headlineMedium,
                                color = if (safe.pace == "warning") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                            Muted("per hari · ${safe.daysRemaining} hari tersisa · ${safe.account}")
                            LinearProgressIndicator(progress = { (safe.spent.toDouble() / safe.budget.coerceAtLeast(1)).toFloat().coerceIn(0f, 1f) }, Modifier.fillMaxWidth(),
                                color = if (safe.pace == "warning") MaterialTheme.colorScheme.error else positive(), trackColor = MaterialTheme.colorScheme.surfaceVariant)
                            Muted("Sisa anggaran ${rupiah(safe.remaining)}")
                        }
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilledTonalButton(paycheck, Modifier.weight(1f)) { Text("Catat gaji") }
                    FilledTonalButton(transfer, Modifier.weight(1f), enabled = dashboard.accounts.count { !it.isArchived } > 1) { Text("Transfer") }
                }
            }
            item {
                SectionTitle("Transaksi terbaru") { TextButton(showAll) { Text("Lihat semua") } }
                FoldPanel {
                    if (dashboard.recent.items.isEmpty()) Muted("Belum ada transaksi pada periode ini.")
                    else dashboard.recent.items.forEach { TransactionRow(it) { edit(it) } }
                }
            }
            if (summary.categories.isNotEmpty()) item {
                SectionTitle("Pengeluaran terbesar")
                Spacer(Modifier.height(12.dp))
                FoldPanel {
                    summary.categories.take(4).forEach { category ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(category.category, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                            Text(rupiah(category.total), style = MaterialTheme.typography.labelLarge)
                        }
                        LinearProgressIndicator(progress = { (category.percentage / 100).toFloat().coerceIn(0f, 1f) }, Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primary,
                            trackColor = MaterialTheme.colorScheme.surfaceVariant)
                    }
                }
            }
        }
        item { Spacer(Modifier.height(72.dp)) }
    }
}

@Composable fun HistoryScreen(state: UiState, search: (String) -> Unit, filter: (String?) -> Unit, allTime: (Boolean) -> Unit,
    retry: () -> Unit, more: () -> Unit, select: (Transaction) -> Unit) {
    val history = state.history
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            OutlinedTextField(state.historySearch, search, Modifier.fillMaxWidth(), label = { Text("Cari transaksi") }, singleLine = true,
                leadingIcon = { Icon(Icons.Default.Search, null) }, shape = RoundedCornerShape(50))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(state.historyType == null, { filter(null) }, label = { Text("Semua") })
                FilterChip(state.historyType == "expense", { filter("expense") }, label = { Text("Pengeluaran") })
                FilterChip(state.historyType == "income", { filter("income") }, label = { Text("Pemasukan") })
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Semua waktu", style = MaterialTheme.typography.bodyMedium)
                Switch(state.allTime, allTime)
            }
        }
        if (history.loading) item { LoadingCard() }
        else {
            history.error?.let { item { ErrorCard(it, retry) } }
            history.data?.let { result ->
                item { FoldPanel {
                    Muted("${result.total} transaksi sesuai filter")
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Metric("Pemasukan", result.income, positive(), Modifier.weight(1f))
                        Metric("Pengeluaran", result.expense, MaterialTheme.colorScheme.error, Modifier.weight(1f))
                    }
                } }
                if (result.items.isEmpty()) item { EmptyCard("Belum ada transaksi", "Coba periode atau kata pencarian lain.") }
                items(result.items, key = { it.id }) { tx ->
                    Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
                        Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) { Muted(shortDate(tx.date)); TransactionRow(tx) { select(tx) } }
                    }
                }
                if (result.items.size < result.total) item { FullButton("Muat lebih banyak", state.moreLoading, onClick = more) }
            }
        }
        item { Spacer(Modifier.height(72.dp)) }
    }
}

@Composable fun AccountsScreen(state: UiState, retry: () -> Unit, select: (Account) -> Unit, transfer: () -> Unit) {
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { Muted("Saldo rekening mencakup semua transaksi, transfer, dan penyesuaian saldo.") }
        when {
            state.dashboard.loading -> item { LoadingCard() }
            state.dashboard.error != null -> item { ErrorCard(state.dashboard.error, retry) }
            else -> {
                val accounts = state.dashboard.data?.accounts.orEmpty()
                items(accounts, key = { it.id }) { account ->
                    FoldPanel(Modifier.clickable { select(account) }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant) { Icon(painterResource(R.drawable.ic_bank), null, Modifier.padding(12.dp)) }
                            Column(Modifier.weight(1f)) { Text(account.name, style = MaterialTheme.typography.titleMedium); Muted(roleName(account.type) + if (account.isArchived) " · Diarsipkan" else "") }
                            Icon(Icons.Default.KeyboardArrowRight, "Lihat kantong")
                        }
                        Text(rupiah(account.balance), style = MaterialTheme.typography.headlineMedium,
                            color = if (account.balance < 0) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                    }
                }
                if (accounts.isEmpty()) item { EmptyCard("Belum ada rekening", "Tambahkan rekening melalui dashboard web untuk mulai mencatat.") }
                if (accounts.count { !it.isArchived } > 1) item { FullButton("Transfer antar-rekening", onClick = transfer) }
            }
        }
        item { Spacer(Modifier.height(72.dp)) }
    }
}

@Composable fun PlansScreen(state: UiState, retry: () -> Unit, addGoal: () -> Unit) {
    var bills by remember { mutableStateOf(false) }
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(!bills, { bills = false }, label = { Text("Target tabungan") })
            FilterChip(bills, { bills = true }, label = { Text("Tagihan") })
        } }
        when {
            state.plans.loading -> item { LoadingCard() }
            state.plans.error != null -> item { ErrorCard(state.plans.error, retry) }
            else -> state.plans.data?.let { plans ->
                if (!bills) {
                    item { FullButton("Tambah target", onClick = addGoal) }
                    if (plans.goals.isEmpty()) item { EmptyCard("Belum ada target", "Buat tujuan menabung tanpa memindahkan saldo rekening.") }
                    items(plans.goals, key = { it.id }) { goal -> FoldPanel {
                        Text(goal.name, style = MaterialTheme.typography.titleMedium)
                        Text(rupiah(goal.current), style = MaterialTheme.typography.headlineMedium)
                        LinearProgressIndicator(progress = { (goal.percentage / 100).toFloat().coerceIn(0f, 1f) }, Modifier.fillMaxWidth(),
                            color = goalAccent(goal.color ?: "emerald"), trackColor = MaterialTheme.colorScheme.surfaceVariant)
                        Muted("Target ${rupiah(goal.target)} · ${goal.percentage.toInt()}%")
                        goal.deadline?.let { Muted("Target tanggal ${shortDate(it)}") }
                        if (goal.remaining == 0L) Text("Target tercapai", color = positive(), style = MaterialTheme.typography.labelLarge)
                        else goal.estimatedCycles?.let { Muted("Perkiraan $it siklus berdasarkan alokasi tercatat.") }
                    } }
                } else {
                    item { FoldPanel { Muted("Komitmen bulanan"); Text(rupiah(plans.bills.monthly), style = MaterialTheme.typography.headlineMedium) } }
                    if (plans.bills.items.isEmpty()) item { EmptyCard("Belum ada tagihan", "Tagihan yang dibuat di dashboard web akan muncul di sini.") }
                    items(plans.bills.items, key = { it.id }) { bill -> FoldPanel {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(bill.name, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                            Text(if (!bill.active) "Nonaktif" else if (bill.paid) "Dibayar" else "Belum dibayar",
                                color = if (bill.paid) positive() else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelMedium)
                        }
                        Text(rupiah(bill.amount), style = MaterialTheme.typography.titleLarge)
                        Muted(bill.account + " · " + bill.category)
                        bill.nextDate?.let { Muted("Jatuh tempo ${shortDate(it)}") }
                    } }
                }
            }
        }
        item { Spacer(Modifier.height(72.dp)) }
    }
}
