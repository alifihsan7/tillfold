package id.my.alifihsan.tillfold.data

import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

/** A single source for server data; all financial calculations remain on the backend. */
class TillfoldRepository(val api: TillfoldApi, private val session: Session) {
    suspend fun login(identity: String, password: String): User {
        val response = api.login(LoginRequest(identity.trim(), password))
        session.save(response.token)
        return response.user
    }
    suspend fun register(name: String, username: String, password: String): User {
        val response = api.register(RegisterRequest(username.trim(), name.trim(), password))
        session.save(response.token)
        return response.user
    }
    suspend fun dashboard(period: Period?): Dashboard = coroutineScope {
        val summary = async { api.summary(period?.type ?: "cycle", period?.start, period?.end, period?.start?.take(7).takeIf { period?.type == "month" }) }
        val accounts = async { api.accounts() }
        val categories = async { api.categories() }
        val recent = async { api.history(limit = 5, start = period?.start, end = period?.end) }
        Dashboard(summary.await(), accounts.await(), categories.await(), recent.await())
    }
}

data class Dashboard(val summary: Summary, val accounts: List<Account>, val categories: List<Category>, val recent: TransactionHistory)
