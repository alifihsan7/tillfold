package id.my.alifihsan.tillfold.ui

import id.my.alifihsan.tillfold.data.*
import java.time.LocalDate

/** Explicitly labelled fixtures. Never merged with authenticated API responses. */
object DemoData {
    val user = User(0, "demo", "Teman Tillfold", isOnboarded = true)
    private val start = LocalDate.parse(todayWib()).minusDays(3)
    val period = Period("demo", "cycle", "Siklus contoh", start.toString(), start.plusDays(13).toString(), true)
    val accounts = listOf(Account(1, "Mandiri", "operasional", 1_450_000), Account(2, "Bank Jago", "tagihan", 550_000), Account(3, "Bibit", "investasi", 3_000_000))
    val categories = listOf(Category(1, "Makanan & Minuman", "expense", "amberGold"), Category(2, "Transportasi", "expense", "cyanHub"), Category(3, "Belanja", "expense", "pink"), Category(4, "Gaji", "income", "mintRise"))
    private val transactions = listOf(
        Transaction(1, "expense", 28_000, "Mandiri", "Makanan & Minuman", "Makan siang", todayWib()),
        Transaction(2, "expense", 15_000, "Mandiri", "Transportasi", "Perjalanan pulang", todayWib()),
        Transaction(3, "expense", 32_000, "Mandiri", "Makanan & Minuman", "Kopi dan roti", start.plusDays(2).toString()),
        Transaction(4, "income", 3_000_000, "Mandiri", "Gaji", "Gaji bulan ini", start.toString()),
    )
    val history = TransactionHistory(transactions, 4, 3_000_000, 75_000, 2_925_000)
    val dashboard = Dashboard(
        Summary(period.start, period.end, period.label, 5_000_000, 3_000_000, 75_000, 2_925_000,
            savingsRate = 97.5, safe = SafeToSpend(period.start, period.end, "Mandiri", 1_525_000, 75_000, 1_450_000, 131_818, 11),
            categories = listOf(CategoryTotal("Makanan & Minuman", 60_000, 2, 80.0), CategoryTotal("Transportasi", 15_000, 1, 20.0))),
        accounts, categories, history,
    )
    val plans = PlanData(listOf(Goal(1, "Dana darurat", 10_000_000, 3_000_000, 7_000_000, 30.0), Goal(2, "Perjalanan berikutnya", 5_000_000, 1_500_000, 3_500_000, 30.0, "cyan")),
        Bills(listOf(Bill(1, "Gym", 225_000, "Bank Jago", "Gym & Fitness", nextDate = LocalDate.parse(todayWib()).plusDays(3).toString(), paymentPeriod = "demo", daysUntil = 3)), 225_000))
    val pockets = Pockets(listOf(Pocket(1, "Kas bebas", balance = 325_000), Pocket(2, "Gym", "tagihan", 225_000, 225_000)), "Bank Jago")
}
