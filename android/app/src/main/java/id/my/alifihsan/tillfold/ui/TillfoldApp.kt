package id.my.alifihsan.tillfold.ui

import android.app.Activity
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import id.my.alifihsan.tillfold.data.*
import id.my.alifihsan.tillfold.ui.theme.TillfoldTheme

private enum class Tab(val title: String) {
    Overview("Ringkasan"), History("Transaksi"), Plans("Rencana"), Accounts("Rekening"), Settings("Pengaturan")
}

@Composable fun TillfoldApp(model: TillfoldViewModel) {
    val state by model.state.collectAsStateWithLifecycle()
    TillfoldTheme(state.theme) {
        val view = LocalView.current
        val light = MaterialTheme.colorScheme.background.luminance() > 0.5f
        SideEffect {
            (view.context as? Activity)?.window?.let { window ->
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = light
                    isAppearanceLightNavigationBars = light
                }
            }
        }
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            when {
                state.booting -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { LoadingCard("Menghubungkan akun…") }
                state.user == null -> AuthScreen(state, model::authenticate, model::enterDemo, model::restoreSession)
                !state.user!!.isOnboarded -> OnboardingScreen(state, model::onboard)
                else -> DashboardApp(state, model)
            }
        }
    }
}

@Composable private fun AuthScreen(state: UiState, authenticate: (String, String, String?) -> Unit, demo: () -> Unit, restore: () -> Unit) {
    var register by rememberSaveable { mutableStateOf(false) }
    var identity by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var reveal by remember { mutableStateOf(false) }
    val uri = LocalUriHandler.current
    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Spacer(Modifier.height(24.dp))
        Text("Tillfold", style = MaterialTheme.typography.displaySmall)
        Text("Uang lebih tertata.\nHari lebih tenang.", style = MaterialTheme.typography.headlineMedium)
        Muted("Catatan keuanganmu, sekarang di Android.")
        FoldPanel {
            Text(if (register) "Buat akun" else "Selamat datang kembali", style = MaterialTheme.typography.titleLarge)
            if (register) OutlinedTextField(name, { name = it.take(100) }, Modifier.fillMaxWidth(), label = { Text("Nama lengkap") }, singleLine = true, enabled = !state.authBusy)
            OutlinedTextField(identity, { identity = it.take(100) }, Modifier.fillMaxWidth(), label = { Text(if (register) "Username" else "Username atau email") }, singleLine = true, enabled = !state.authBusy,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
            OutlinedTextField(password, { password = it }, Modifier.fillMaxWidth(), label = { Text("Kata sandi") }, singleLine = true, enabled = !state.authBusy,
                visualTransformation = if (reveal) VisualTransformation.None else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = { TextButton({ reveal = !reveal }) { Text(if (reveal) "Sembunyi" else "Lihat", style = MaterialTheme.typography.labelMedium) } })
            FormError(state.authError)
            FullButton(if (register) "Buat akun" else "Masuk", state.authBusy,
                identity.isNotBlank() && password.isNotBlank() && (!register || (password.length >= 8 && name.isNotBlank()))) {
                authenticate(identity, password, name.takeIf { register })
            }
            TextButton({ register = !register }, Modifier.fillMaxWidth(), enabled = !state.authBusy) { Text(if (register) "Sudah punya akun? Masuk" else "Belum punya akun? Daftar") }
        }
        if (state.authError != null) TextButton(restore, Modifier.align(Alignment.CenterHorizontally)) { Text("Coba sambungkan ulang sesi") }
        TextButton(demo, Modifier.fillMaxWidth(), enabled = !state.authBusy) { Text("Lihat demo tanpa akun") }
        Muted("Biasanya masuk lewat Google? Atur kata sandi dari profil di dashboard web, lalu gunakan akun yang sama di sini.")
        TextButton({ uri.openUri("https://tillfold.alifihsan.my.id/#/settings/profile") }, Modifier.align(Alignment.CenterHorizontally)) { Text("Buka dashboard web") }
        Muted("Kata sandi tidak disimpan di perangkat.")
    }
}

@Composable private fun OnboardingScreen(state: UiState, onboard: (String, Long) -> Unit) {
    var name by rememberSaveable { mutableStateOf("") }
    var balance by rememberSaveable { mutableStateOf("0") }
    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Spacer(Modifier.height(20.dp))
        Text("Mulai dari satu rekening", style = MaterialTheme.typography.headlineMedium)
        Muted("Halo, ${state.user?.fullName}. Tambahkan rekening harianmu dan saldo yang benar saat ini.")
        FoldPanel {
            OutlinedTextField(name, { name = it.take(50) }, Modifier.fillMaxWidth(), label = { Text("Nama rekening") }, placeholder = { Text("Contoh: Mandiri") })
            AmountField(balance, { balance = it }, "Saldo awal")
            Muted("Saldo awal dipisahkan dari pemasukan. Siklus awal memakai 14 hari dan bisa diubah di dashboard web.")
            FormError(state.writeError)
            FullButton("Mulai mencatat", state.saving, name.isNotBlank() && parseAmount(balance, true) != null) { onboard(name.trim(), parseAmount(balance, true)!!) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun DashboardApp(state: UiState, model: TillfoldViewModel) {
    var tab by rememberSaveable { mutableStateOf(Tab.Overview) }
    var form by rememberSaveable { mutableStateOf("") }
    var transactionId by rememberSaveable { mutableStateOf<Long?>(null) }
    var deleteId by rememberSaveable { mutableStateOf<Long?>(null) }
    var detailId by rememberSaveable { mutableStateOf<Long?>(null) }
    var periodMenu by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val allTransactions = (state.history.data?.items.orEmpty() + state.dashboard.data?.recent?.items.orEmpty()).distinctBy { it.id }
    val selected = allTransactions.find { it.id == transactionId }
    val toDelete = allTransactions.find { it.id == deleteId }
    val detail = allTransactions.find { it.id == detailId }
    fun openForm(value: String) { model.clearWriteError(); transactionId = null; form = value }
    fun choose(tx: Transaction) { detailId = tx.id }
    LaunchedEffect(tab, state.selectedPeriod?.id) {
        when (tab) { Tab.History -> model.loadHistory(); Tab.Plans -> model.loadPlans(); else -> Unit }
    }
    LaunchedEffect(state.mutationVersion) {
        if (state.mutationVersion > 0) { form = ""; transactionId = null; deleteId = null; detailId = null }
    }
    LaunchedEffect(state.message) { state.message?.let { snackbar.showSnackbar(it); model.consumeMessage() } }
    Scaffold(containerColor = MaterialTheme.colorScheme.background,
        topBar = { Column {
            TopAppBar(title = { Column { Text("Tillfold", style = MaterialTheme.typography.titleLarge); Muted(tab.title) } },
                actions = { IconButton({ model.refresh(); if (tab == Tab.History) model.loadHistory(); if (tab == Tab.Plans) model.loadPlans() }) { Icon(Icons.Default.Refresh, "Muat ulang") } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background))
            if (state.demo) Surface(color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.fillMaxWidth()) {
                Text("Mode demo · semua angka adalah data contoh", Modifier.padding(horizontal = 16.dp, vertical = 10.dp), style = MaterialTheme.typography.bodySmall)
            }
            if (tab != Tab.Settings) Box(Modifier.padding(horizontal = 16.dp)) {
                FilledTonalButton({ periodMenu = true }, enabled = state.periods.isNotEmpty()) {
                    Text(state.selectedPeriod?.let { "${shortDate(it.start)} – ${shortDate(it.end)}" } ?: "Siklus aktif", style = MaterialTheme.typography.labelMedium)
                    Icon(Icons.Default.ArrowDropDown, null)
                }
                DropdownMenu(periodMenu, { periodMenu = false }, Modifier.heightIn(max = 380.dp)) {
                    state.periods.forEach { period -> DropdownMenuItem(text = { Text(period.label) }, onClick = { model.selectPeriod(period); periodMenu = false }) }
                }
            }
        } },
        bottomBar = { NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
            Tab.entries.forEach { entry -> NavigationBarItem(selected = tab == entry, onClick = { tab = entry },
                icon = { Icon(when (entry) { Tab.Overview -> Icons.Default.Home; Tab.History -> Icons.AutoMirrored.Filled.List; Tab.Plans -> Icons.Default.Star; Tab.Accounts -> Icons.Default.AccountCircle; Tab.Settings -> Icons.Default.Settings }, null) },
                label = { Text(entry.title, maxLines = 1, style = MaterialTheme.typography.labelMedium) }) }
        } },
        floatingActionButton = { if (tab == Tab.Overview || tab == Tab.History) FloatingActionButton({ openForm("transaction") }, shape = RoundedCornerShape(24.dp)) { Icon(Icons.Default.Add, "Catat transaksi") } },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Box(Modifier.fillMaxHeight().widthIn(max = 840.dp)) {
                when (tab) {
                    Tab.Overview -> OverviewScreen(state, model::refresh, { tab = Tab.History }, ::choose, { openForm("transfer") }, { openForm("paycheck") })
                    Tab.History -> HistoryScreen(state, model::search, model::filter, model::allTime, { model.loadHistory() }, { model.loadHistory(more = true) }, ::choose)
                    Tab.Accounts -> AccountsScreen(state, model::refresh, { model.loadPockets(it.id); openForm("pockets") }, { openForm("transfer") })
                    Tab.Plans -> PlansScreen(state, model::loadPlans) { openForm("goal") }
                    Tab.Settings -> SettingsScreen(state, model::theme) { model.logout() }
                }
            }
        }
    }
    when (form) {
        "transaction" -> if (transactionId != null && selected == null) {
            FormSheet("Transaksi tidak tersedia", false, { form = "" }) {
                Muted("Tutup formulir dan muat ulang daftar transaksi untuk melanjutkan.")
            }
        } else key(transactionId) { TransactionForm(state, selected, { form = "" }, model::saveTransaction) }
        "transfer" -> TransferForm(state, { form = "" }, model::transfer)
        "paycheck" -> PaycheckForm(state, { form = "" }, model::paycheck)
        "goal" -> GoalForm(state, { form = "" }, model::saveGoal)
        "pockets" -> FormSheet("Kantong rekening", false, { form = "" }) {
            when {
                state.pockets.loading -> LoadingCard()
                state.pockets.error != null -> ErrorCard(state.pockets.error) { state.pocketAccountId?.let(model::loadPockets) }
                else -> {
                    state.pockets.data?.accountName?.let { Text(it, style = MaterialTheme.typography.titleMedium) }
                    val pockets = state.pockets.data?.pockets.orEmpty()
                    if (pockets.isEmpty()) Muted("Belum ada kantong untuk rekening ini.")
                    pockets.forEach { pocket -> FoldPanel(color = MaterialTheme.colorScheme.surfaceVariant) {
                        Text(pocket.name, style = MaterialTheme.typography.titleMedium)
                        Muted(roleName(pocket.role))
                        Text(rupiah(pocket.balance), style = MaterialTheme.typography.titleLarge)
                        if (pocket.target > 0) Muted("Target ${rupiah(pocket.target)}")
                    } }
                }
            }
        }
    }
    if (detail != null) AlertDialog(onDismissRequest = { detailId = null }, title = { Text(detail.description) }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(signedRupiah(detail.amount, detail.incoming), style = MaterialTheme.typography.titleLarge)
            Text("${detail.category} · ${detail.account}"); Muted(shortDate(detail.date))
            if (!detail.canEdit) Muted("Penyesuaian saldo dan dana talangan dikelola melalui alur khusus di dashboard web.")
        }
    }, confirmButton = {
        if (detail.canEdit) TextButton({ model.clearWriteError(); transactionId = detail.id; form = "transaction"; detailId = null }) { Text("Edit") }
        else TextButton({ detailId = null }) { Text("Tutup") }
    }, dismissButton = { if (detail.canEdit) TextButton({ model.clearWriteError(); deleteId = detail.id; detailId = null }, enabled = !state.demo) { Text("Hapus", color = MaterialTheme.colorScheme.error) } })
    if (toDelete != null) AlertDialog(onDismissRequest = { if (!state.saving) deleteId = null }, title = { Text("Hapus transaksi?") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("${toDelete.description} · ${rupiah(toDelete.amount)}")
            Text(if (toDelete.isTransfer) "Transfer beserta pasangannya akan dihapus. Saldo kedua rekening ikut diperbarui." else "Saldo rekening akan disesuaikan setelah transaksi dihapus.")
            FormError(state.writeError)
        }
    }, confirmButton = { TextButton({ model.deleteTransaction(toDelete.id) }, enabled = !state.saving && !state.demo) { Text(if (state.saving) "Menghapus…" else "Hapus", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton({ deleteId = null }, enabled = !state.saving) { Text("Batal") } })
}

@Composable private fun SettingsScreen(state: UiState, theme: (String) -> Unit, logout: () -> Unit) {
    val uri = LocalUriHandler.current
    var confirmLogout by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        FoldPanel {
            Text(state.user?.fullName.orEmpty(), style = MaterialTheme.typography.titleLarge)
            Muted("@${state.user?.username}")
            state.user?.email?.let { Muted(it) }
            Muted(if (state.user?.telegramChatId != null) "Telegram terhubung" else "Telegram belum terhubung")
        }
        FoldPanel {
            Text("Tampilan", style = MaterialTheme.typography.titleMedium)
            SelectField("Tema", when (state.theme) { "light" -> "Terang"; "dark" -> "Gelap"; else -> "Ikuti perangkat" }, listOf("Ikuti perangkat", "Terang", "Gelap"), {
                theme(when (it) { "Terang" -> "light"; "Gelap" -> "dark"; else -> "system" })
            })
        }
        FoldPanel {
            Text("Kategori transaksi", style = MaterialTheme.typography.titleMedium)
            state.dashboard.data?.categories.orEmpty().filter { it.type in setOf("expense", "income") }.groupBy { it.type }.forEach { (type, categories) ->
                Text(if (type == "income") "Pemasukan" else "Pengeluaran", style = MaterialTheme.typography.titleSmall)
                Muted(categories.joinToString(" · ") { it.name })
            }
        }
        FoldPanel {
            Text("Tillfold untuk Android", style = MaterialTheme.typography.titleMedium)
            Muted("Versi 0.1.0")
            Muted("Terhubung ke akun Tillfold yang sama. Pengaturan lanjutan, integrasi Google Sheets, dan pengelolaan tagihan tersedia di dashboard web.")
            FilledTonalButton({ uri.openUri("https://tillfold.alifihsan.my.id/#/settings") }) { Text("Pengaturan lanjutan") }
        }
        FullButton(if (state.demo) "Keluar dari demo" else "Keluar akun") { confirmLogout = true }
        Spacer(Modifier.height(20.dp))
    }
    if (confirmLogout) AlertDialog(onDismissRequest = { confirmLogout = false }, title = { Text("Keluar dari Tillfold?") },
        text = { Text("Sesi di perangkat ini akan dihapus. Data di akunmu tetap tersimpan.") },
        confirmButton = { TextButton(logout) { Text("Keluar") } }, dismissButton = { TextButton({ confirmLogout = false }) { Text("Batal") } })
}
