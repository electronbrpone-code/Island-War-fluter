package com.islandwar.smartclicker.ml

import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import kotlin.math.abs

data class CardFingerprint(
    val full: BooleanArray,
    val art: BooleanArray,
    val name: BooleanArray
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is CardFingerprint) return false
        if (!full.contentEquals(other.full)) return false
        if (!art.contentEquals(other.art)) return false
        if (!name.contentEquals(other.name)) return false
        return true
    }

    override fun hashCode(): Int {
        var result = full.contentHashCode()
        result = 31 * result + art.contentHashCode()
        result = 31 * result + name.contentHashCode()
        return result
    }
}

class FingerprintGenerator {
    companion object {
        private const val HASH_SIZE = 16
        private const val PHASH_SIZE = 32
    }

    fun generate(image: Mat): CardFingerprint {
        val split = (image.rows() * 0.78).toInt()
        
        return CardFingerprint(
            full = phash(image),
            art = phash(image.submat(0, split, 0, image.cols())),
            name = phash(image.submat(split, image.rows(), 0, image.cols()))
        )
    }

    private fun phash(image: Mat): BooleanArray {
        val gray = Mat()
        Imgproc.cvtColor(image, gray, Imgproc.COLOR_BGR2GRAY)

        val resized = Mat()
        Imgproc.resize(gray, resized, Size(PHASH_SIZE.toDouble(), PHASH_SIZE.toDouble()))

        val dct = resized.clone()
        Imgproc.dct(dct, dct)

        val hash = BooleanArray(HASH_SIZE * HASH_SIZE)
        val median = calculateMedian(dct.submat(0, HASH_SIZE, 0, HASH_SIZE))

        var idx = 0
        for (i in 0 until HASH_SIZE) {
            for (j in 0 until HASH_SIZE) {
                if (i == 0 && j == 0) continue
                hash[idx++] = dct.get(i, j)[0] > median
            }
        }

        resized.release()
        gray.release()
        dct.release()

        return hash
    }

    private fun calculateMedian(mat: Mat): Double {
        val values = DoubleArray(mat.rows() * mat.cols())
        var idx = 0
        for (i in 0 until mat.rows()) {
            for (j in 0 until mat.cols()) {
                values[idx++] = mat.get(i, j)[0]
            }
        }
        return values.sorted()[values.size / 2].toDouble()
    }
}

class FingerprintMatcher {
    companion object {
        const val MATCH_THRESHOLD = 55.0
        const val MATCH_MARGIN = 12.0
    }

    fun distance(left: CardFingerprint, right: CardFingerprint): Double {
        return (
            0.45 * hammingDistance(left.full, right.full) +
            0.30 * hammingDistance(left.art, right.art) +
            0.25 * hammingDistance(left.name, right.name)
        )
    }

    private fun hammingDistance(left: BooleanArray, right: BooleanArray): Int {
        return left.indices.count { left[it] != right[it] }
    }
}
