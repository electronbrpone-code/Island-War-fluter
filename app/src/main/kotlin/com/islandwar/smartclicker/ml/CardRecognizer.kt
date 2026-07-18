package com.islandwar.smartclicker.ml

import org.opencv.core.Mat
import kotlin.math.sqrt

class CardRecognizer(private val matcher: FingerprintMatcher = FingerprintMatcher()) {
    private val database = mutableListOf<CardEntry>()

    data class CardEntry(
        val id: String,
        val name: String,
        val rarity: String,
        val fingerprint: CardFingerprint
    )

    data class RecognitionResult(
        val entry: CardEntry,
        val distance: Double,
        val confidence: Double
    )

    fun addCard(id: String, name: String, rarity: String, fingerprint: CardFingerprint) {
        database.add(CardEntry(id, name, rarity, fingerprint))
    }

    fun recognize(image: Mat): RecognitionResult? {
        val generator = FingerprintGenerator()
        val imageFingerprint = generator.generate(image)

        var bestMatch: CardEntry? = null
        var bestDistance = Double.MAX_VALUE

        for (entry in database) {
            val distance = matcher.distance(imageFingerprint, entry.fingerprint)
            if (distance < bestDistance) {
                bestDistance = distance
                bestMatch = entry
            }
        }

        if (bestMatch == null || bestDistance > FingerprintMatcher.MATCH_THRESHOLD) {
            return null
        }

        val confidence = 100.0 - (bestDistance / FingerprintMatcher.MATCH_THRESHOLD * 100.0)

        return RecognitionResult(
            entry = bestMatch,
            distance = bestDistance,
            confidence = confidence.coerceIn(0.0, 100.0)
        )
    }

    fun getTopMatches(image: Mat, count: Int = 5): List<RecognitionResult> {
        val generator = FingerprintGenerator()
        val imageFingerprint = generator.generate(image)

        return database
            .map { entry ->
                val distance = matcher.distance(imageFingerprint, entry.fingerprint)
                val confidence = 100.0 - (distance / FingerprintMatcher.MATCH_THRESHOLD * 100.0)
                RecognitionResult(
                    entry = entry,
                    distance = distance,
                    confidence = confidence.coerceIn(0.0, 100.0)
                )
            }
            .sortedBy { it.distance }
            .take(count)
    }

    fun clearDatabase() {
        database.clear()
    }

    fun getDatabaseSize(): Int = database.size
}
