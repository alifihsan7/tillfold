package id.my.alifihsan.tillfold

import android.app.Application
import id.my.alifihsan.tillfold.data.ApiClient
import id.my.alifihsan.tillfold.data.SessionStore
import id.my.alifihsan.tillfold.data.TillfoldRepository

class TillfoldApplication : Application() {
    val session by lazy { SessionStore(this) }
    val repository by lazy { TillfoldRepository(ApiClient.create(BuildConfig.API_BASE_URL, session), session) }
}
