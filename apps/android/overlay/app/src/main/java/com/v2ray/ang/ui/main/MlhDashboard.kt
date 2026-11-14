package com.v2ray.ang.ui.main

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.v2ray.ang.R
import java.util.Locale

@Composable
fun MainScreen(mainViewModel: MainViewModel, onAction: (MainAction) -> Unit, onNavigate: (MainDestination) -> Unit) {
    var profiles by rememberSaveable { mutableStateOf(false) }
    if (profiles) {
        BackHandler { profiles = false }
        MainProfilesScreen(mainViewModel, onAction, onNavigate)
        return
    }
    val state by mainViewModel.uiState.collectAsStateWithLifecycle()
    val now by mainViewModel.clock.collectAsStateWithLifecycle()
    val connecting = !state.isRunning && now < state.connectingUntil
    val unknown = stringResource(R.string.mlh_unknown)
    val unavailable = stringResource(R.string.mlh_unavailable)
    val result = (state.status as? MainStatus.ConnectionTest)?.result?.takeIf { state.isRunning && it.delayMillis >= 0 }
    val traffic = state.telemetry?.takeIf { state.isRunning }
    val fresh = traffic != null && now - traffic.sampledAt in 0..10_000
    val country = result?.country?.takeIf { it.isNotBlank() }?.let {
        if (Regex("[A-Za-z]{2}").matches(it)) Locale.Builder().setRegion(it.uppercase(Locale.ROOT)).build().displayCountry else it
    } ?: unknown
    Scaffold { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
            .verticalScroll(rememberScrollState()).padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineSmall)
                TextButton(onClick = { profiles = true }) { Text(stringResource(R.string.mlh_profiles)) }
            }
            Column(Modifier.fillMaxWidth().background(
                Brush.linearGradient(listOf(Color(0xFF083D58), Color(0xFF116D79))), RoundedCornerShape(28.dp))
                .padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text(stringResource(if (connecting) R.string.mlh_connecting else if (state.isRunning) R.string.mlh_connected else R.string.mlh_disconnected),
                    color = Color.White, style = MaterialTheme.typography.titleLarge)
                Button(onClick = { onAction(MainAction.ToggleService) }, enabled = !connecting, shape = CircleShape,
                    modifier = Modifier.size(132.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF63F5CD), contentColor = Color(0xFF083D58))) {
                    Text(stringResource(if (state.isRunning) R.string.mlh_disconnect else R.string.mlh_connect))
                }
                Text(stringResource(R.string.mlh_timer), color = Color.White.copy(alpha = 0.8f))
                Text(traffic?.let { formatSessionTime((now - it.startedAt).coerceAtLeast(0)) } ?: unavailable,
                    color = Color.White, style = MaterialTheme.typography.headlineMedium)
            }
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp)) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(R.string.mlh_exit), style = MaterialTheme.typography.labelLarge)
                    Text(country, style = MaterialTheme.typography.titleLarge)
                    Text(result?.ipAddress?.takeIf { it.isNotBlank() } ?: unknown)
                    TextButton(enabled = state.isRunning && !state.isTesting,
                        onClick = { onAction(MainAction.TestCurrentServer) }) { Text(stringResource(R.string.mlh_probe)) }
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Metric(stringResource(R.string.mlh_ping), result?.let { "${it.delayMillis} ms" } ?: unavailable, Modifier.weight(1f))
                Metric(stringResource(R.string.mlh_send), if (fresh) traffic?.sendRate?.let { formatTraffic(it) + "/s" } ?: unavailable else unavailable, Modifier.weight(1f))
                Metric(stringResource(R.string.mlh_receive), if (fresh) traffic?.receiveRate?.let { formatTraffic(it) + "/s" } ?: unavailable else unavailable, Modifier.weight(1f))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Metric(stringResource(R.string.mlh_sent_total), traffic?.sent?.let { formatTraffic(it.toDouble()) } ?: unavailable, Modifier.weight(1f))
                Metric(stringResource(R.string.mlh_received_total), traffic?.received?.let { formatTraffic(it.toDouble()) } ?: unavailable, Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: String, modifier: Modifier) {
    Card(modifier, shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(value, style = MaterialTheme.typography.titleMedium)
        }
    }
}

internal fun formatSessionTime(milliseconds: Long): String {
    val seconds = milliseconds.coerceAtLeast(0) / 1000
    return String.format(Locale.ROOT, "%02d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
}

internal fun formatTraffic(bytes: Double): String = when {
    bytes >= 1_073_741_824 -> String.format(Locale.ROOT, "%.1f GiB", bytes / 1_073_741_824)
    bytes >= 1_048_576 -> String.format(Locale.ROOT, "%.1f MiB", bytes / 1_048_576)
    bytes >= 1024 -> String.format(Locale.ROOT, "%.1f KiB", bytes / 1024)
    else -> String.format(Locale.ROOT, "%.0f B", bytes.coerceAtLeast(0.0))
}
