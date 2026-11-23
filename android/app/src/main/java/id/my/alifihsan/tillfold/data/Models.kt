package id.my.alifihsan.tillfold.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable data class User(
    val id: Long, val username: String, @SerialName("full_name") val fullName: String,
    val email: String? = null, @SerialName("is_onboarded") val isOnboarded: Boolean = true,
    @SerialName("telegram_chat_id") val telegramChatId: Long? = null,
)
@Serializable data class LoginRequest(@SerialName("username_or_email") val identity: String, val password: String)
@Serializable data class RegisterRequest(val username: String, @SerialName("full_name") val fullName: String, val password: String, val email: String? = null)
@Serializable data class AuthResponse(@SerialName("access_token") val token: String, val user: User)
@Serializable data class Period(
    val id: String, val type: String, val label: String, val start: String, val end: String,
    @SerialName("is_current") val isCurrent: Boolean = false,
)
@Serializable data class Periods(val cycles: List<Period> = emptyList(), val weeks: List<Period> = emptyList(), val months: List<Period> = emptyList())
@Serializable data class Account(
    val id: Long, val name: String, val type: String = "operasional",
    @SerialName("current_balance") val balance: Long = 0,
    @SerialName("is_archived") val isArchived: Boolean = false,
)
@Serializable data class Category(val id: Long, val name: String, val type: String, val color: String = "slateText")
@Serializable data class Transaction(
    val id: Long, val type: String, val amount: Long, val account: String, val category: String,
    val description: String, val date: String,
    @SerialName("pocket_id") val pocketId: Long? = null,
    @SerialName("pocket_name") val pocketName: String? = null,
    @SerialName("is_internal_loan_transfer") val isInternalLoan: Boolean = false,
) {
    val incoming get() = type in setOf("income", "transfer_in", "adjustment_in")
    val isTransfer get() = type.startsWith("transfer_")
    val canEdit get() = type in setOf("expense", "income", "transfer_out", "transfer_in") && !isInternalLoan
}
@Serializable data class TransactionWrite(
    val type: String, val amount: Long, val account: String, val category: String,
    val description: String, val date: String, @SerialName("pocket_id") val pocketId: Long? = null,
)
@Serializable data class TransferWrite(
    @SerialName("from_account") val from: String, @SerialName("to_account") val to: String,
    val amount: Long, val description: String, val date: String,
)
@Serializable data class TransactionHistory(
    val items: List<Transaction> = emptyList(), val total: Int = 0,
    val income: Long = 0, val expense: Long = 0, val net: Long = 0,
    @SerialName("opening_balance") val openingBalance: Long = 0,
)
@Serializable data class CategoryTotal(val category: String, val total: Long, val count: Int = 0, val percentage: Double = 0.0)
@Serializable data class SafeToSpend(
    @SerialName("cycle_start") val start: String, @SerialName("cycle_end") val end: String,
    @SerialName("pocket_account") val account: String = "",
    @SerialName("pocket_budget") val budget: Long = 0,
    @SerialName("pocket_spent") val spent: Long = 0,
    @SerialName("pocket_remaining") val remaining: Long = 0,
    @SerialName("safe_daily") val daily: Long = 0,
    @SerialName("days_remaining") val daysRemaining: Int = 0,
    @SerialName("pace_status") val pace: String = "on_track",
)
@Serializable data class Summary(
    @SerialName("start_date") val start: String, @SerialName("end_date") val end: String,
    @SerialName("period_label") val label: String = "Siklus aktif",
    @SerialName("total_balance") val balance: Long = 0,
    val income: Long = 0, val expense: Long = 0, val net: Long = 0,
    @SerialName("opening_balance") val openingBalance: Long = 0,
    @SerialName("savings_rate") val savingsRate: Double = 0.0,
    @SerialName("safe_to_spend") val safe: SafeToSpend? = null,
    val categories: List<CategoryTotal> = emptyList(),
)
@Serializable data class Goal(
    val id: Long, val name: String,
    @SerialName("target_amount") val target: Long,
    @SerialName("current_amount") val current: Long = 0,
    @SerialName("remaining_amount") val remaining: Long = 0,
    val percentage: Double = 0.0, val color: String? = "emerald",
    @SerialName("target_date") val deadline: String? = null,
    @SerialName("estimated_cycles") val estimatedCycles: Int? = null,
)
@Serializable data class GoalWrite(val name: String, @SerialName("target_amount") val target: Long,
    @SerialName("manual_current_amount") val current: Long = 0, val color: String = "emerald")
@Serializable data class Bill(
    val id: Long, val name: String, val amount: Long, val account: String, val category: String,
    @SerialName("is_active") val active: Boolean = true,
    @SerialName("is_paid") val paid: Boolean = false,
    @SerialName("next_billing_date") val nextDate: String? = null,
    @SerialName("payment_period") val paymentPeriod: String? = null,
    @SerialName("days_until_due") val daysUntil: Int? = null,
)
@Serializable data class Bills(val items: List<Bill> = emptyList(), @SerialName("total_monthly_commitment") val monthly: Long = 0)
@Serializable data class BillPayment(
    val period: String, @SerialName("expected_amount") val amount: Long,
    @SerialName("expected_account") val account: String, @SerialName("paid_date") val date: String,
)
@Serializable data class Pocket(
    val id: Long, val name: String, val role: String = "operasional", val balance: Long = 0,
    @SerialName("target_amount") val target: Long = 0,
    @SerialName("spent_amount") val spent: Long = 0,
)
@Serializable data class Pockets(val pockets: List<Pocket> = emptyList(), @SerialName("account_name") val accountName: String? = null)
@Serializable data class PaycheckWrite(
    @SerialName("request_key") val requestKey: String,
    @SerialName("total_amount") val amount: Long, val account: String, val date: String,
    @SerialName("start_cycle") val startCycle: Boolean = true,
)
@Serializable data class PaycheckResult(val id: Long)
@Serializable data class InitialAccount(val name: String, @SerialName("initial_balance") val balance: Long = 0, val type: String = "operasional")
@Serializable data class InitialBucket(val account: String, val percentage: Int = 100, val purpose: String = "Operasional")
@Serializable data class OnboardingWrite(
    @SerialName("initial_accounts") val accounts: List<InitialAccount>,
    @SerialName("source_account") val source: String, @SerialName("pocket_account") val spending: String,
    @SerialName("cycle_start_date") val start: String,
    val buckets: List<InitialBucket>, @SerialName("cycle_type") val cycleType: String = "biweekly",
    @SerialName("cycle_days") val days: Int = 14, @SerialName("use_gate") val useGate: Boolean = false,
)
