package com.islandwar.smartclicker.data

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface GameCardDao {
    @Insert
    suspend fun insert(card: GameCard)

    @Update
    suspend fun update(card: GameCard)

    @Delete
    suspend fun delete(card: GameCard)

    @Query("SELECT * FROM game_cards ORDER BY priority DESC")
    fun getAllCards(): Flow<List<GameCard>>

    @Query("SELECT * FROM game_cards WHERE id = :id")
    suspend fun getCardById(id: Int): GameCard?
}
