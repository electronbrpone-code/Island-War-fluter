package com.islandwar.smartclicker.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.islandwar.smartclicker.ui.screens.*

@Composable
fun MainScreen() {
    var currentScreen by remember { mutableStateOf("main") }

    when (currentScreen) {
        "main" -> MainHomeScreen(
            onNavigate = { currentScreen = it }
        )
        "cards" -> CardsScreen(
            onBack = { currentScreen = "main" }
        )
        "preferences" -> PreferencesScreen(
            onBack = { currentScreen = "main" }
        )
        "settings" -> SettingsScreen(
            onBack = { currentScreen = "main" }
        )
        "status" -> StatusScreen(
            onBack = { currentScreen = "main" }
        )
    }
}

@Composable
fun MainHomeScreen(onNavigate: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "Island War Smart Clicker",
            style = MaterialTheme.typography.headlineLarge,
            modifier = Modifier.padding(bottom = 32.dp)
        )

        Button(
            onClick = { onNavigate("cards") },
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(vertical = 8.dp)
        ) {
            Text("📚 Вивчені картки")
        }

        Button(
            onClick = { onNavigate("preferences") },
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(vertical = 8.dp)
        ) {
            Text("⚖️ Переваги")
        }

        Button(
            onClick = { onNavigate("status") },
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(vertical = 8.dp)
        ) {
            Text("📊 Статус")
        }

        Button(
            onClick = { onNavigate("settings") },
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(vertical = 8.dp)
        ) {
            Text("⚙️ Налаштування")
        }

        Spacer(modifier = Modifier.height(32.dp))

        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 16.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    "Статус Accessibility Service:",
                    style = MaterialTheme.typography.labelLarge
                )
                Text(
                    "✅ Активен",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }
    }
}
