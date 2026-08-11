package com.islandwar.smartclicker.data.db

import androidx.room.*

@Entity(tableName = "cards")
data class CardEntity(
    @PrimaryKey
    val id: String,
    val name: String,
    val rarity: String,
    val fingerprintFull: String,
    val fingerprintArt: String,
    val fingerprintName: String,
    val priority: Int = 100,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)

@Entity(
    tableName = "preferences",
    foreignKeys = [
        ForeignKey(entity = CardEntity::class, parentColumns = ["id"], childColumns = ["cardFromId"], onDelete = ForeignKey.CASCADE),
        ForeignKey(entity = CardEntity::class, parentColumns = ["id"], childColumns = ["cardToId"], onDelete = ForeignKey.CASCADE)
    ],
    indices = [Index("cardFromId"), Index("cardToId")]
)
data class PreferenceEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val cardFromId: String,
    val cardToId: String,
    val count: Int = 1,
    val timestamp: Long = System.currentTimeMillis()
)

@Entity(tableName = "statistics")
data class StatisticEntity(
    @PrimaryKey
    val id: String = "main",
    val totalChoices: Int = 0,
    val autoChoices: Int = 0,
    val manualChoices: Int = 0,
    val learnedCards: Int = 0,
    val updatedAt: Long = System.currentTimeMillis()
)

@Entity(tableName = "detection_history")
data class DetectionHistoryEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val cardId: String,
    val confidence: Double,
    val distance: Double,
    val timestamp: Long = System.currentTimeMillis()
)
