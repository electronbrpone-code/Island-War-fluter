package com.islandwar.smartclicker

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SmartClickerApp()
        }
    }
}

@Composable
fun SmartClickerApp() {
    val navController = rememberNavController()
    val snackbarHostState = remember { SnackbarHostState() }

    SmartClickerTheme {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbarHostState) },
            bottomBar = { BottomNavigationBar(navController) },
            modifier = Modifier.fillMaxSize()
        ) { paddingValues ->
            NavHost(
                navController = navController,
                startDestination = "cards",
                modifier = Modifier.padding(paddingValues)
            ) {
                composable("cards") {
                    CardsScreen(snackbarHostState)
                }
                composable("clicker") {
                    ClickerScreen(snackbarHostState)
                }
                composable("statistics") {
                    StatisticsScreen()
                }
                composable("settings") {
                    SettingsScreen()
                }
            }
        }
    }
}

@Composable
fun BottomNavigationBar(navController: NavHostController) {
    NavigationBar {
        NavigationBarItem(
            icon = { Icon(Icons.Default.CreditCard, contentDescription = "Cards") },
            label = { Text("Cards") },
            selected = false,
            onClick = { navController.navigate("cards") }
        )
        NavigationBarItem(
            icon = { Icon(Icons.Default.TouchApp, contentDescription = "Clicker") },
            label = { Text("Clicker") },
            selected = false,
            onClick = { navController.navigate("clicker") }
        )
        NavigationBarItem(
            icon = { Icon(Icons.Default.BarChart, contentDescription = "Stats") },
            label = { Text("Stats") },
            selected = false,
            onClick = { navController.navigate("statistics") }
        )
        NavigationBarItem(
            icon = { Icon(Icons.Default.Settings, contentDescription = "Settings") },
            label = { Text("Settings") },
            selected = false,
            onClick = { navController.navigate("settings") }
        )
    }
}

@Composable
fun CardsScreen(snackbarHostState: SnackbarHostState) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Game Cards", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(16.dp))
        Button(onClick = { }) {
            Text("Add Card")
        }
    }
}

@Composable
fun ClickerScreen(snackbarHostState: SnackbarHostState) {
    var isActive by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Auto-Clicker", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(32.dp))
        
        StatusBadge(isActive)
        
        Spacer(modifier = Modifier.height(32.dp))
        
        Button(
            onClick = { isActive = !isActive },
            modifier = Modifier.size(120.dp),
            shape = MaterialTheme.shapes.medium
        ) {
            Text(if (isActive) "STOP" else "START")
        }
    }
}

@Composable
fun StatusBadge(isActive: Boolean) {
    Surface(
        color = if (isActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.padding(8.dp)
    ) {
        Text(
            text = if (isActive) "Active" else "Inactive",
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.labelLarge
        )
    }
}

@Composable
fun StatisticsScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Statistics", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(16.dp))
        StatItem("Total Clicks", "0")
        StatItem("Auto Clicks", "0")
        StatItem("Accuracy", "0%")
    }
}

@Composable
fun StatItem(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label)
        Text(value, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun SettingsScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(16.dp))
        
        SettingItem("Auto Mode", "Enabled")
        SettingItem("Detection Threshold", "0.85")
        SettingItem("Click Delay", "100ms")
    }
}

@Composable
fun SettingItem(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(value, style = MaterialTheme.typography.bodySmall)
        }
        Icon(Icons.Default.ChevronRight, contentDescription = null)
    }
}

@Composable
fun SmartClickerTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(),
        typography = Typography(),
        content = content
    )
}