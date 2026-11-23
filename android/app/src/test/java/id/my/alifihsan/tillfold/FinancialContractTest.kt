package id.my.alifihsan.tillfold

import id.my.alifihsan.tillfold.data.*
import id.my.alifihsan.tillfold.ui.*
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.decodeFromString
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

class MemorySession(override var token: String? = null, override var theme: String = "system") : Session {
    override fun save(token: String) { this.token = token }
    override fun clear() { token = null }
}

class FinancialContractTest {
    @Test fun rupiah_keeps_large_values_exact_and_rejects_invalid_amounts() {
        assertEquals("Rp 9.000.000.000.000.000", rupiah(MAX_MONEY))
        assertEquals(MAX_MONEY, parseAmount("9000000000000000"))
        listOf("", "-1", "0", "1.5", "1e6", "9000000000000001", "999999999999999999999").forEach { assertNull(it, parseAmount(it)) }
        assertEquals(0L, parseAmount("0", allowZero = true))
        assertEquals("−Rp 25.000", signedRupiah(25000, false))
    }
    @Test fun dates_are_validated_as_calendar_dates() {
        assertTrue(validDate("2024-02-29"))
        assertFalse(validDate("2026-02-29"))
        assertFalse(validDate("2026-13-01"))
        assertFalse(validDate("24/11/2026"))
    }
    @Test fun financial_responses_use_longs_and_keep_opening_balances_separate() {
        val history = ApiClient.json.decodeFromString<TransactionHistory>("""{"items":[],"total":0,"income":123,"opening_balance":9000000000000000,"expense":23,"net":100,"future_field":true}""")
        assertEquals(MAX_MONEY, history.openingBalance)
        assertEquals(123L, history.income)
        assertEquals(100L, history.net)
    }
    @Test fun login_uses_existing_json_contract_and_authenticated_requests_use_bearer() = runBlocking {
        MockWebServer().use { server ->
            val session = MemorySession()
            val api = ApiClient.create(server.url("/api/v1/").toString(), session)
            server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"access_token":"test-token","user":{"id":1,"username":"alif","full_name":"Alif"}}"""))
            val user = TillfoldRepository(api, session).login(" alif ", "secret-password")
            assertEquals("Alif", user.fullName)
            val request = server.takeRequest()
            assertEquals("/api/v1/auth/login", request.path)
            val body = request.body.readUtf8()
            assertTrue(body.contains("\"username_or_email\":\"alif\""))
            assertFalse(body.contains("username_or_email\":\" alif"))
            server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"id":1,"username":"alif","full_name":"Alif"}"""))
            api.me()
            assertEquals("Bearer test-token", server.takeRequest().getHeader("Authorization"))
        }
    }
    @Test fun clearing_a_pocket_on_edit_is_an_explicit_json_null() = runBlocking {
        MockWebServer().use { server ->
            val api = ApiClient.create(server.url("/").toString(), MemorySession("token"))
            server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"id":1,"type":"expense","amount":1000,"account":"Cash","category":"Makan","description":"Uji","date":"2026-11-24"}"""))
            api.editTransaction(1, TransactionWrite("expense", 1000, "Cash", "Makan", "Uji", "2026-11-24", pocketId = null))
            val request = server.takeRequest()
            assertEquals("PUT", request.method)
            assertTrue(request.body.readUtf8().contains("\"pocket_id\":null"))
        }
    }
    @Test fun history_queries_include_the_period_filters_and_offset() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"items":[],"total":25}"""))
            val api = ApiClient.create(server.url("/").toString(), MemorySession("token"))
            api.history(skip = 25, start = "2026-11-22", end = "2026-12-05", search = "kopi", type = "expense")
            val url = server.takeRequest().requestUrl!!
            assertEquals("25", url.queryParameter("skip"))
            assertEquals("2026-11-22", url.queryParameter("start_date"))
            assertEquals("2026-12-05", url.queryParameter("end_date"))
            assertEquals("expense", url.queryParameter("type"))
            assertEquals("kopi", url.queryParameter("search"))
        }
    }
    @Test fun past_month_summary_and_history_use_the_same_calendar_range() = runBlocking {
        MockWebServer().use { server ->
            // Route-aware dispatch supports the repository's parallel reads.
            server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
                override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): MockResponse = MockResponse().setHeader("Content-Type", "application/json").setBody(
                    when (request.requestUrl!!.encodedPath) {
                        "/analytics/summary" -> """{"start_date":"2025-10-01","end_date":"2025-10-31"}"""
                        "/transactions/history" -> """{"items":[],"total":0}"""
                        else -> "[]"
                    })
            }
            val api = ApiClient.create(server.url("/").toString(), MemorySession("token"))
            TillfoldRepository(api, MemorySession()).dashboard(Period("month_2025_10", "month", "Oktober 2025", "2025-10-01", "2025-10-31"))
            val requests = List(4) { server.takeRequest().requestUrl!! }
            assertEquals("2025-10", requests.first { it.encodedPath == "/analytics/summary" }.queryParameter("month"))
            assertEquals("2025-10-01", requests.first { it.encodedPath == "/transactions/history" }.queryParameter("start_date"))
        }
    }
    @Test fun errors_are_readable_and_never_show_html_or_invent_success() {
        val error = HttpException(Response.error<Unit>(409, """{"detail":"Saldo berubah. Muat ulang."}""".toResponseBody()))
        assertEquals("Saldo berubah. Muat ulang.", error.readableMessage())
        val html = HttpException(Response.error<Unit>(502, "<html>upstream failure</html>".toResponseBody()))
        assertFalse(html.readableMessage().contains("<html>"))
        assertTrue(IOException().readableMessage(writing = true).contains("memeriksa apakah perubahan tersimpan"))
    }
    @Test fun reconciliation_and_loan_rows_do_not_offer_ordinary_edits() {
        val row = DemoData.history.items.first()
        assertFalse(row.copy(type = "adjustment_out").canEdit)
        assertFalse(row.copy(type = "transfer_out", isInternalLoan = true).canEdit)
        assertTrue(row.copy(type = "transfer_out").canEdit)
    }
}
