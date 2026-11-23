package id.my.alifihsan.tillfold.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

interface Session {
    val token: String?
    var theme: String
    fun save(token: String)
    fun clear()
}

/** Only ciphertext is persisted. Passwords and financial responses are never written to disk. */
class SessionStore(context: Context) : Session {
    private val preferences = context.getSharedPreferences("tillfold_session", Context.MODE_PRIVATE)
    private val keyAlias = "tillfold.session.v1"
    @Volatile private var currentToken: String? = load()
    override val token: String? get() = currentToken
    override var theme: String
        get() = preferences.getString("theme", "system") ?: "system"
        set(value) { preferences.edit().putString("theme", value).apply() }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(keyAlias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }
    private fun load(): String? = runCatching {
        val encoded = preferences.getString("token", null) ?: return null
        val parts = encoded.split(":")
        require(parts.size == 2)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)))
        cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)).toString(Charsets.UTF_8)
    }.getOrElse { preferences.edit().remove("token").commit(); null }

    override fun save(token: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        val value = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(encrypted, Base64.NO_WRAP)
        check(preferences.edit().putString("token", value).commit()) { "Session could not be saved" }
        currentToken = token
    }
    override fun clear() {
        currentToken = null
        preferences.edit().remove("token").commit()
    }
}
