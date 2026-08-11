package com.islandwar.smartclicker.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        CardEntity::class,
        PreferenceEntity::class,
        StatisticEntity::class,
        DetectionHistoryEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun cardDao(): CardDao
    abstract fun preferenceDao(): PreferenceDao
    abstract fun statisticDao(): StatisticDao
    abstract fun detectionHistoryDao(): DetectionHistoryDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "smartclicker.db"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
