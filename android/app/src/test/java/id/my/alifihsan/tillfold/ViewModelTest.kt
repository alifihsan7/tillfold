package id.my.alifihsan.tillfold

import id.my.alifihsan.tillfold.data.*
import id.my.alifihsan.tillfold.ui.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestWatcher
import org.junit.runner.Description
import java.io.IOException
import okhttp3.ResponseBody.Companion.toResponseBody

@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule : TestWatcher() {
    val dispatcher = StandardTestDispatcher()
    override fun starting(description: Description) { Dispatchers.setMain(dispatcher) }
    override fun finished(description: Description) { Dispatchers.resetMain() }
}

open class FakeApi : TillfoldApi {
    var calls = 0
    var writes = 0
    var summaryFailure: Exception? = null
    var meGate: CompletableDeferred<User>? = null
    var writeGate: CompletableDeferred<Unit>? = null
    override suspend fun login(body: LoginRequest): AuthResponse { calls++; return AuthResponse("test", DemoData.user) }
    override suspend fun register(body: RegisterRequest): AuthResponse = login(LoginRequest(body.username, body.password))
    override suspend fun me(): User { calls++; return meGate?.await() ?: DemoData.user }
    override suspend fun onboard(body: OnboardingWrite): User { calls++; return DemoData.user }
    override suspend fun periods(): Periods { calls++; return Periods(cycles = listOf(DemoData.period)) }
    override suspend fun summary(type: String, start: String?, end: String?, month: String?): Summary { calls++; summaryFailure?.let { throw it }; return DemoData.dashboard.summary }
    override suspend fun accounts(): List<Account> { calls++; return DemoData.accounts }
    override suspend fun categories(): List<Category> { calls++; return DemoData.categories }
    override suspend fun history(skip: Int, limit: Int, start: String?, end: String?, search: String?, type: String?): TransactionHistory { calls++; return DemoData.history }
    override suspend fun createTransaction(body: TransactionWrite): Transaction { writes++; writeGate?.await(); return DemoData.history.items.first() }
    override suspend fun editTransaction(id: Long, body: TransactionWrite): Transaction = createTransaction(body)
    override suspend fun deleteTransaction(id: Long) { writes++ }
    override suspend fun transfer(body: TransferWrite) { writes++ }
    override suspend fun goals(): List<Goal> { calls++; return DemoData.plans.goals }
    override suspend fun createGoal(body: GoalWrite): Goal { writes++; return DemoData.plans.goals.first() }
    override suspend fun bills(): Bills { calls++; return DemoData.plans.bills }
    override suspend fun payBill(id: Long, body: BillPayment) { writes++ }
    override suspend fun pockets(id: Long): Pockets { calls++; return DemoData.pockets }
    override suspend fun paycheck(body: PaycheckWrite): PaycheckResult { writes++; return PaycheckResult(1) }
}

@OptIn(ExperimentalCoroutinesApi::class)
class ViewModelTest {
    @get:Rule val main = MainDispatcherRule()
    private fun model(api: FakeApi, session: MemorySession = MemorySession("token")) = TillfoldViewModel(TillfoldRepository(api, session), session)

    @Test fun a_failed_refresh_clears_stale_financial_values() = runTest {
        val api = FakeApi()
        val model = model(api)
        advanceUntilIdle()
        assertNotNull(model.state.value.dashboard.data)
        api.summaryFailure = IOException("offline")
        model.refresh()
        advanceUntilIdle()
        assertNull(model.state.value.dashboard.data)
        assertNotNull(model.state.value.dashboard.error)
    }
    @Test fun double_taps_cannot_create_two_financial_writes() = runTest {
        val api = FakeApi()
        val model = model(api)
        advanceUntilIdle()
        api.writeGate = CompletableDeferred()
        val body = TransactionWrite("expense", 25000, "Mandiri", "Makan", "Siang", todayWib())
        model.saveTransaction(body)
        model.saveTransaction(body)
        runCurrent()
        assertEquals(1, api.writes)
        assertTrue(model.state.value.saving)
        api.writeGate!!.complete(Unit)
        advanceUntilIdle()
        assertEquals(1, model.state.value.mutationVersion)
        assertFalse(model.state.value.saving)
    }
    @Test fun an_old_session_response_cannot_log_the_user_back_in_after_logout() = runTest {
        val api = FakeApi().apply { meGate = CompletableDeferred() }
        val session = MemorySession("token")
        val model = model(api, session)
        runCurrent()
        model.logout()
        api.meGate!!.complete(DemoData.user)
        advanceUntilIdle()
        assertNull(model.state.value.user)
        assertNull(session.token)
        assertNull(model.state.value.dashboard.data)
    }
    @Test fun expired_session_clears_every_account_screen() = runTest {
        val api = FakeApi()
        val session = MemorySession("token")
        val model = model(api, session)
        advanceUntilIdle()
        api.summaryFailure = retrofit2.HttpException(retrofit2.Response.error<Unit>(401,
            "{}".toResponseBody()))
        model.refresh()
        advanceUntilIdle()
        assertNull(session.token)
        assertNull(model.state.value.user)
        assertNull(model.state.value.dashboard.data)
        assertNull(model.state.value.history.data)
        assertTrue(model.state.value.authError!!.contains("Sesi berakhir"))
    }
    @Test fun demo_never_uses_the_api_or_writes_financial_data() = runTest {
        val api = FakeApi()
        val model = model(api, MemorySession())
        model.enterDemo()
        model.refresh(); model.loadHistory(); model.loadPlans(); model.loadPockets(1)
        model.saveTransaction(TransactionWrite("expense", 25000, "Mandiri", "Makan", "Siang", todayWib()))
        advanceUntilIdle()
        assertEquals(0, api.calls)
        assertEquals(0, api.writes)
        assertTrue(model.state.value.demo)
    }
}
