package com.islandwar.smartclicker.data.db

import androidx.room.*

@Dao
interface CardDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCard(card: CardEntity)

    @Update
    suspend fun updateCard(card: CardEntity)

    @Delete
    suspend fun deleteCard(card: CardEntity)

    @Query("SELECT * FROM cards WHERE id = :id")
    suspend fun getCardById(id: String): CardEntity?

    @Query("SELECT * FROM cards ORDER BY priority DESC, name ASC")
    suspend fun getAllCards(): List<CardEntity>

    @Query("SELECT COUNT(*) FROM cards")
    suspend fun getCardCount(): Int

    @Query("DELETE FROM cards")
    suspend fun deleteAllCards()
}

@Dao
interface PreferenceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPreference(pref: PreferenceEntity)

    @Query("SELECT * FROM preferences WHERE cardFromId = :fromId ORDER BY count DESC")
    suspend fun getPreferencesFor(fromId: String): List<PreferenceEntity>

    @Query("SELECT cardToId FROM preferences WHERE cardFromId = :fromId ORDER BY count DESC LIMIT 1")
    suspend fun getMostPreferredCard(fromId: String): String?

    @Query("DELETE FROM preferences")
    suspend fun deleteAllPreferences()
}

@Dao
interface StatisticDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertStatistic(stat: StatisticEntity)

    @Query("SELECT * FROM statistics WHERE id = 'main'")
    suspend fun getStatistics(): StatisticEntity?

    @Query("UPDATE statistics SET totalChoices = totalChoices + 1 WHERE id = 'main'")
    suspend fun incrementTotalChoices()

    @Query("UPDATE statistics SET autoChoices = autoChoices + 1 WHERE id = 'main'")
    suspend fun incrementAutoChoices()
}

@Dao
interface DetectionHistoryDao {
    @Insert
    suspend fun insertHistory(history: DetectionHistoryEntity)

    @Query("SELECT * FROM detection_history ORDER BY timestamp DESC LIMIT :limit")
    suspend fun getRecentDetections(limit: Int = 50): List<DetectionHistoryEntity>

    @Query("DELETE FROM detection_history WHERE timestamp < :beforeTime")
    suspend fun deleteOldDetections(beforeTime: Long)
}
