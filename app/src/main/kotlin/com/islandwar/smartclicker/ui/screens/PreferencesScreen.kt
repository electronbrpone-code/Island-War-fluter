package com.islandwar.smartclicker.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PreferencesScreen(onBack: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("Переваги карток") },
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(Icons.Default.ArrowBack, "Назад")
                }
            }
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            item {
                Card(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Card #001 > Card #002", style = MaterialTheme.typography.labelLarge)
                        Text("Кількість виборів: 45")
                    }
                }
            }
        }
    }
}
