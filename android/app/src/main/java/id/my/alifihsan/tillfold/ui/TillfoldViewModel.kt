package id.my.alifihsan.tillfold.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import id.my.alifihsan.tillfold.data.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex

data class LoadState<T>(val data: T? = null, val loading: Boolean = false, val error: String? = null)
data class PlanData(val goals: List<Goal>, val bills: Bills)
data class UiState(
    val booting: Boolean = false, val user: User? = null, val authBusy: Boolean = false,
    val authError: String? = null, val demo: Boolean = false, val theme: String = "system",
    val dashboard: LoadState<Dashboard> = LoadState(), val plans: LoadState<PlanData> = LoadState(),
    val history: LoadState<TransactionHistory> = LoadState(), val moreLoading: Boolean = false,
    val periods: List<Period> = emptyList(), val selectedPeriod: Period? = null,
    val historySearch: String = "", val historyType: String? = null, val allTime: Boolean = false,
    val pockets: LoadState<Pockets> = LoadState(), val pocketAccountId: Long? = null,
    val saving: Boolean = false, val writeError: String? = null,
    val mutationVersion: Int = 0, val message: String? = null,
)

class TillfoldViewModel(private val repository: TillfoldRepository, private val session: Session) : ViewModel() {
    private val mutable = MutableStateFlow(UiState(theme = session.theme, booting = session.token != null))
    val state = mutable.asStateFlow()
    private var dashboardJob: Job? = null
    private var historyJob: Job? = null
    private var plansJob: Job? = null
    private var pocketsJob: Job? = null
    private var generation = 0
    private val writes = Mutex()
    init { if (session.token != null) restoreSession() }

    fun restoreSession() = viewModelScope.launch {
        val epoch = generation
        mutable.update { it.copy(booting = true, authError = null) }
        try {
            val user = repository.api.me()
            if (epoch == generation) authenticated(user)
        }
        catch (e: Exception) {
            if (e is CancellationException) throw e
            if (epoch == generation) {
                if (e.isExpiredSession()) session.clear()
                mutable.update { it.copy(booting = false, authError = e.readableMessage()) }
            }
        }
    }
    fun authenticate(identity: String, password: String, fullName: String? = null) = viewModelScope.launch {
        if (mutable.value.authBusy) return@launch
        mutable.update { it.copy(authBusy = true, authError = null) }
        try {
            val user = if (fullName == null) repository.login(identity, password) else repository.register(fullName, identity, password)
            authenticated(user)
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            mutable.update { it.copy(authBusy = false, authError = e.readableMessage()) }
        }
    }
    private fun authenticated(user: User) {
        generation++
        mutable.value = UiState(user = user, theme = session.theme)
        if (user.isOnboarded) refresh()
    }
    fun logout(message: String? = null) {
        generation++
        dashboardJob?.cancel(); historyJob?.cancel(); plansJob?.cancel(); pocketsJob?.cancel()
        session.clear()
        mutable.value = UiState(theme = session.theme, authError = message)
    }
    private fun failed(e: Exception): String {
        if (e is CancellationException) throw e
        if (e.isExpiredSession()) logout("Sesi berakhir. Silakan masuk kembali.")
        return e.readableMessage()
    }
    fun enterDemo() {
        generation++
        mutable.value = UiState(user = DemoData.user, demo = true, theme = session.theme,
            periods = listOf(DemoData.period), selectedPeriod = DemoData.period,
            dashboard = LoadState(DemoData.dashboard), history = LoadState(DemoData.history),
            plans = LoadState(DemoData.plans))
    }
    fun theme(value: String) { session.theme = value; mutable.update { it.copy(theme = value) } }
    fun consumeMessage() { mutable.update { it.copy(message = null) } }
    fun clearWriteError() { mutable.update { it.copy(writeError = null) } }

    fun refresh() {
        if (mutable.value.demo || mutable.value.user == null) return
        dashboardJob?.cancel()
        val epoch = generation
        dashboardJob = viewModelScope.launch {
            mutable.update { it.copy(dashboard = LoadState(loading = true)) }
            try {
                val periods = repository.api.periods()
                val choices = periods.cycles + periods.weeks + periods.months
                val selected = mutable.value.selectedPeriod ?: periods.cycles.firstOrNull { it.isCurrent } ?: periods.cycles.firstOrNull()
                val result = repository.dashboard(selected)
                if (generation == epoch) mutable.update { it.copy(dashboard = LoadState(result), periods = choices, selectedPeriod = selected) }
            } catch (e: Exception) {
                if (epoch != generation) return@launch
                val error = failed(e)
                if (generation == epoch) mutable.update { it.copy(dashboard = LoadState(error = error)) }
            }
        }
    }
    fun selectPeriod(period: Period) {
        mutable.update { it.copy(selectedPeriod = period) }
        refresh(); loadHistory()
    }
    fun search(value: String) { mutable.update { it.copy(historySearch = value) }; loadHistory(debounce = true) }
    fun filter(type: String?) { mutable.update { it.copy(historyType = type) }; loadHistory() }
    fun allTime(value: Boolean) { mutable.update { it.copy(allTime = value) }; loadHistory() }
    fun loadHistory(more: Boolean = false, debounce: Boolean = false) {
        if (mutable.value.demo || mutable.value.user == null) return
        if (more && mutable.value.moreLoading) return
        historyJob?.cancel()
        val epoch = generation
        historyJob = viewModelScope.launch {
            if (debounce) delay(350)
            val snapshot = mutable.value
            val previous = if (more) snapshot.history.data else null
            mutable.update { if (more) it.copy(moreLoading = true) else it.copy(history = LoadState(loading = true), moreLoading = false) }
            try {
                val period = snapshot.selectedPeriod.takeUnless { snapshot.allTime }
                val result = repository.api.history(skip = previous?.items?.size ?: 0,
                    start = period?.start, end = period?.end,
                    search = snapshot.historySearch.trim().ifBlank { null }, type = snapshot.historyType)
                val merged = if (previous == null) result else result.copy(items = (previous.items + result.items).distinctBy { it.id })
                if (epoch == generation) mutable.update { it.copy(history = LoadState(merged), moreLoading = false) }
            } catch (e: Exception) {
                if (epoch != generation) return@launch
                val error = failed(e)
                if (epoch == generation) mutable.update { it.copy(history = LoadState(previous, error = error), moreLoading = false) }
            }
        }
    }
    fun loadPlans() {
        if (mutable.value.demo || mutable.value.user == null) return
        plansJob?.cancel()
        val epoch = generation
        plansJob = viewModelScope.launch {
            mutable.update { it.copy(plans = LoadState(loading = true)) }
            try {
                val result = coroutineScope {
                    val goals = async { repository.api.goals() }
                    val bills = async { repository.api.bills() }
                    PlanData(goals.await(), bills.await())
                }
                if (epoch == generation) mutable.update { it.copy(plans = LoadState(result)) }
            } catch (e: Exception) {
                if (epoch != generation) return@launch
                val error = failed(e)
                if (epoch == generation) mutable.update { it.copy(plans = LoadState(error = error)) }
            }
        }
    }
    fun loadPockets(accountId: Long) {
        pocketsJob?.cancel()
        mutable.update { it.copy(pocketAccountId = accountId, pockets = LoadState(loading = true)) }
        if (mutable.value.demo) { mutable.update { it.copy(pockets = LoadState(DemoData.pockets)) }; return }
        val epoch = generation
        pocketsJob = viewModelScope.launch {
            try {
                val result = repository.api.pockets(accountId)
                if (epoch == generation) mutable.update { it.copy(pockets = LoadState(result)) }
            } catch (e: Exception) {
                if (epoch != generation) return@launch
                val error = failed(e)
                if (epoch == generation) mutable.update { it.copy(pockets = LoadState(error = error)) }
            }
        }
    }
    private fun write(message: String, operation: suspend () -> Unit) = viewModelScope.launch {
        if (mutable.value.demo || mutable.value.user == null || !writes.tryLock()) return@launch
        val epoch = generation
        mutable.update { it.copy(saving = true, writeError = null) }
        try {
            operation()
            if (epoch == generation) {
                mutable.update { it.copy(saving = false, mutationVersion = it.mutationVersion + 1, message = message) }
                refresh(); loadHistory(); loadPlans()
            }
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            if (epoch == generation && e.isExpiredSession()) logout("Sesi berakhir. Silakan masuk kembali.")
            if (epoch == generation) mutable.update { it.copy(saving = false, writeError = e.readableMessage(writing = true)) }
        } finally { writes.unlock() }
    }
    fun saveTransaction(body: TransactionWrite, id: Long? = null) = write("Transaksi tersimpan") {
        if (id == null) repository.api.createTransaction(body) else repository.api.editTransaction(id, body)
    }
    fun deleteTransaction(id: Long) = write("Transaksi dihapus") { repository.api.deleteTransaction(id) }
    fun transfer(body: TransferWrite) = write("Transfer tersimpan") { repository.api.transfer(body) }
    fun saveGoal(body: GoalWrite) = write("Target ditambahkan") { repository.api.createGoal(body) }
    fun payBill(bill: Bill) = write("Pembayaran tercatat") {
        val period = requireNotNull(bill.paymentPeriod) { "Periode pembayaran belum tersedia" }
        repository.api.payBill(bill.id, BillPayment(period, bill.amount, bill.account, todayWib()))
    }
    fun paycheck(body: PaycheckWrite): Job {
        val epoch = generation
        return write("Gaji tercatat") {
            repository.api.paycheck(body)
            if (body.startCycle && epoch == generation) mutable.update { it.copy(selectedPeriod = null) }
        }
    }
    fun onboard(name: String, opening: Long): Job {
        val epoch = generation
        return write("Rekening siap digunakan") {
        val body = OnboardingWrite(listOf(InitialAccount(name, opening)), name, name, todayWib(), listOf(InitialBucket(name)))
        val user = repository.api.onboard(body)
        if (epoch == generation) mutable.update { it.copy(user = user) }
        }
    }
}
