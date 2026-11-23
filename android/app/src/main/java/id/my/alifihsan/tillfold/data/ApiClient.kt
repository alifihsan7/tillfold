package id.my.alifihsan.tillfold.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.*

interface TillfoldApi {
    @POST("auth/login") suspend fun login(@Body body: LoginRequest): AuthResponse
    @POST("auth/register") suspend fun register(@Body body: RegisterRequest): AuthResponse
    @GET("auth/me") suspend fun me(): User
    @POST("onboarding/complete") suspend fun onboard(@Body body: OnboardingWrite): User
    @GET("analytics/periods") suspend fun periods(): Periods
    @GET("analytics/summary") suspend fun summary(@Query("period_type") type: String = "cycle", @Query("start") start: String? = null, @Query("end") end: String? = null, @Query("month") month: String? = null): Summary
    @GET("accounts") suspend fun accounts(): List<Account>
    @GET("categories") suspend fun categories(): List<Category>
    @GET("transactions/history") suspend fun history(
        @Query("skip") skip: Int = 0, @Query("limit") limit: Int = 25,
        @Query("start_date") start: String? = null, @Query("end_date") end: String? = null,
        @Query("search") search: String? = null, @Query("type") type: String? = null,
    ): TransactionHistory
    @POST("transactions") suspend fun createTransaction(@Body body: TransactionWrite): Transaction
    @PUT("transactions/{id}") suspend fun editTransaction(@Path("id") id: Long, @Body body: TransactionWrite): Transaction
    @DELETE("transactions/{id}") suspend fun deleteTransaction(@Path("id") id: Long)
    @POST("transactions/transfer") suspend fun transfer(@Body body: TransferWrite)
    @GET("goals") suspend fun goals(): List<Goal>
    @POST("goals") suspend fun createGoal(@Body body: GoalWrite): Goal
    @GET("subscriptions") suspend fun bills(): Bills
    @POST("subscriptions/{id}/payment") suspend fun payBill(@Path("id") id: Long, @Body body: BillPayment)
    @GET("accounts/{id}/pockets") suspend fun pockets(@Path("id") id: Long): Pockets
    @POST("paycheck/record") suspend fun paycheck(@Body body: PaycheckWrite): PaycheckResult
}

object ApiClient {
    @OptIn(ExperimentalSerializationApi::class)
    val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; explicitNulls = true }

    fun create(baseUrl: String, session: Session, client: OkHttpClient? = null): TillfoldApi {
        val http = (client ?: OkHttpClient()).newBuilder()
            .connectTimeout(15, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS)
            // Ordinary ledger writes have no idempotency key. Never transparently replay them.
            .retryOnConnectionFailure(false)
            .addInterceptor { chain ->
                val request = chain.request().newBuilder()
                session.token?.let { request.header("Authorization", "Bearer $it") }
                request.header("Accept", "application/json")
                chain.proceed(request.build())
            }.build()
        return Retrofit.Builder().baseUrl(baseUrl).client(http)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build().create(TillfoldApi::class.java)
    }
}

fun Throwable.isExpiredSession() = this is HttpException && code() == 401

fun Throwable.readableMessage(writing: Boolean = false): String {
    if (this is CancellationException) throw this
    if (this is HttpException) {
        if (code() == 401) return "Sesi berakhir. Silakan masuk kembali."
        val detail = runCatching { ApiClient.json.parseToJsonElement(response()?.errorBody()?.string().orEmpty()).jsonObject["detail"] }.getOrNull()
        if (detail is JsonPrimitive && detail.isString) return detail.content.take(400)
        if (detail is JsonArray) return detail.mapNotNull {
            (it as? JsonObject)?.get("msg")?.jsonPrimitive?.contentOrNull
        }.joinToString("\n").take(400).ifBlank { "Periksa kembali isian formulir." }
        return when (code()) {
            429 -> "Terlalu banyak permintaan. Coba lagi sebentar."
            in 500..599 -> "Layanan sedang bermasalah. Coba muat ulang."
            else -> "Permintaan belum berhasil (${code()}). Coba muat ulang."
        }
    }
    if (this is IOException) return if (writing)
        "Koneksi terputus. Muat ulang untuk memeriksa apakah perubahan tersimpan sebelum mencoba lagi."
        else "Tidak dapat terhubung. Periksa koneksi lalu coba lagi."
    return "Ada kendala. Coba muat ulang."
}
