package id.my.alifihsan.tillfold

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import id.my.alifihsan.tillfold.ui.TillfoldApp
import id.my.alifihsan.tillfold.ui.TillfoldViewModel

class MainActivity : ComponentActivity() {
    private val model: TillfoldViewModel by viewModels {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                val app = application as TillfoldApplication
                return TillfoldViewModel(app.repository, app.session) as T
            }
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { TillfoldApp(model) }
    }
}
