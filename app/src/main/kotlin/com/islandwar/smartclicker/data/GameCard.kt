package com.islandwar.smartclicker.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "game_cards")
data class GameCard(
    @PrimaryKey(autoGenerate = true)
    val id: Int = 0,
    val name: String,
    val imagePath: String,
    val priority: Int,
    val detectionThreshold: Float = 0.85f,
    val createdAt: Long = System.currentTimeMillis()
)
