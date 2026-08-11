package com.islandwar.smartclicker.data

import android.content.Context
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore by preferencesDataStore(name = "settings")

class PreferenceManager(private val context: Context) {
    companion object {
        private val MATCH_THRESHOLD = doublePreferencesKey("match_threshold")
        private val MATCH_MARGIN = doublePreferencesKey("match_margin")
        private val QUICK_THRESHOLD = doublePreferencesKey("quick_threshold")
        private val AUTO_CLICK_ENABLED = booleanPreferencesKey("auto_click_enabled")
        private val SERVICE_ENABLED = booleanPreferencesKey("service_enabled")
    }

    val matchThreshold: Flow<Double> = context.dataStore.data.map { prefs ->
        prefs[MATCH_THRESHOLD] ?: 55.0
    }

    val matchMargin: Flow<Double> = context.dataStore.data.map { prefs ->
        prefs[MATCH_MARGIN] ?: 12.0
    }

    val quickThreshold: Flow<Double> = context.dataStore.data.map { prefs ->
        prefs[QUICK_THRESHOLD] ?: 25.0
    }

    val autoClickEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[AUTO_CLICK_ENABLED] ?: true
    }

    val serviceEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[SERVICE_ENABLED] ?: false
    }

    suspend fun setMatchThreshold(value: Double) {
        context.dataStore.edit { prefs ->
            prefs[MATCH_THRESHOLD] = value
        }
    }

    suspend fun setMatchMargin(value: Double) {
        context.dataStore.edit { prefs ->
            prefs[MATCH_MARGIN] = value
        }
    }

    suspend fun setAutoClickEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[AUTO_CLICK_ENABLED] = enabled
        }
    }

    suspend fun setServiceEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[SERVICE_ENABLED] = enabled
        }
    }
}
