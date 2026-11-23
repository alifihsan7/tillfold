package id.my.alifihsan.tillfold.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalConfiguration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

@Composable fun FoldPanel(modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.surface, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(28.dp), color = color, tonalElevation = 0.dp) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}
@Composable fun SectionTitle(title: String, action: @Composable (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
        action?.invoke()
    }
}
@Composable fun Muted(text: String, modifier: Modifier = Modifier) {
    Text(text, modifier, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
}
@Composable fun ErrorCard(text: String, retry: (() -> Unit)? = null) {
    FoldPanel {
        Icon(Icons.Default.Info, contentDescription = null, tint = MaterialTheme.colorScheme.error)
        Text(text, style = MaterialTheme.typography.bodyMedium)
        retry?.let { FilledTonalButton(onClick = it) { Text("Coba lagi") } }
    }
}
@Composable fun LoadingCard(label: String = "Memuat data…") {
    FoldPanel {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
@Composable fun EmptyCard(title: String, description: String) {
    FoldPanel { Text(title, style = MaterialTheme.typography.titleMedium); Muted(description) }
}
@Composable fun FullButton(text: String, busy: Boolean = false, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick, Modifier.fillMaxWidth().heightIn(min = 50.dp), enabled = enabled && !busy, shape = RoundedCornerShape(50)) {
        if (busy) CircularProgressIndicator(Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
        else Text(text)
    }
}
@Composable fun FormError(message: String?) {
    if (message != null) Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(16.dp)) {
        Text(message, Modifier.fillMaxWidth().padding(14.dp), color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodyMedium)
    }
}
@Composable fun AmountField(value: String, onChange: (String) -> Unit, label: String = "Nominal", enabled: Boolean = true) {
    OutlinedTextField(value, { next -> if (next.length <= 16 && next.all(Char::isDigit)) onChange(next) },
        Modifier.fillMaxWidth(), label = { Text(label) }, prefix = { Text("Rp ") }, singleLine = true,
        enabled = enabled, shape = RoundedCornerShape(14.dp), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        supportingText = { parseAmount(value, allowZero = true)?.let { Muted(rupiah(it)) } })
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun SelectField(label: String, value: String, options: List<String>, onChange: (String) -> Unit, enabled: Boolean = true) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded, { if (enabled) expanded = !expanded }) {
        OutlinedTextField(value, {}, Modifier.menuAnchor().fillMaxWidth(), readOnly = true, enabled = enabled,
            label = { Text(label) }, singleLine = true, shape = RoundedCornerShape(14.dp),
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) })
        ExposedDropdownMenu(expanded, { expanded = false }) {
            options.forEach { option -> DropdownMenuItem(text = { Text(option) }, onClick = { expanded = false; onChange(option) }) }
        }
    }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun DateField(value: String, onChange: (String) -> Unit, enabled: Boolean = true) {
    var open by remember { mutableStateOf(false) }
    OutlinedTextField(shortDate(value), {}, Modifier.fillMaxWidth(), label = { Text("Tanggal") }, readOnly = true,
        shape = RoundedCornerShape(14.dp), enabled = enabled,
        trailingIcon = { IconButton({ open = true }, enabled = enabled) { Icon(Icons.Default.DateRange, "Pilih tanggal") } })
    if (open) {
        val initial = runCatching { LocalDate.parse(value).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() }.getOrNull()
        val picker = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(onDismissRequest = { open = false }, confirmButton = {
            TextButton(onClick = {
                picker.selectedDateMillis?.let { onChange(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate().toString()) }
                open = false
            }, enabled = picker.selectedDateMillis != null) { Text("Pilih") }
        }, dismissButton = { TextButton({ open = false }) { Text("Batal") } }) { DatePicker(picker) }
    }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun FormSheet(title: String, saving: Boolean, onDismiss: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    ModalBottomSheet(onDismissRequest = { if (!saving) onDismiss() }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp)) {
        Column(Modifier.fillMaxWidth().heightIn(max = (LocalConfiguration.current.screenHeightDp * 0.85f).dp)
            .imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp).padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            content()
        }
    }
}
@Composable fun Metric(label: String, amount: Long, color: Color = MaterialTheme.colorScheme.onSurface, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Muted(label)
        Text(rupiah(amount), fontSize = 19.sp, fontWeight = FontWeight.Bold, color = color)
    }
}
