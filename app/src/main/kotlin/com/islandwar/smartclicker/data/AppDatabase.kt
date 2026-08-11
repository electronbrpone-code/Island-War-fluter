package com.islandwar.smartclicker.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [GameCard::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun gameCardDao(): GameCardDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "smart_clicker_db"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
