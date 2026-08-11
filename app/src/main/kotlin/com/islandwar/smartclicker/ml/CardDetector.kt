package com.islandwar.smartclicker.ml

import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import kotlin.math.abs

data class CardRegion(
    val rect: Rect,
    val confidence: Double,
    val image: Mat
)

class CardDetector {
    companion object {
        const val MIN_CARD_WIDTH = 50
        const val MIN_CARD_HEIGHT = 70
        const val CARD_RATIO_MIN = 0.6f
        const val CARD_RATIO_MAX = 0.9f
    }

    fun detectCards(image: Mat): List<CardRegion> {
        val gray = Mat()
        Imgproc.cvtColor(image, gray, Imgproc.COLOR_BGR2GRAY)

        val blurred = Mat()
        Imgproc.GaussianBlur(gray, blurred, org.opencv.core.Size(5.0, 5.0), 0.0)

        val edges = Mat()
        Imgproc.Canny(blurred, edges, 50.0, 150.0)

        val dilated = Mat()
        val kernel = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, org.opencv.core.Size(5.0, 5.0))
        Imgproc.dilate(edges, dilated, kernel, org.opencv.core.Point(-1.0, -1.0), 2)

        val contours = mutableListOf<MatOfPoint>()
        Imgproc.findContours(dilated, contours, Mat(), Imgproc.RETR_EXTERNAL, Imgproc.CHAIN_APPROX_SIMPLE)

        val cardRegions = mutableListOf<CardRegion>()

        for (contour in contours) {
            val rect = Imgproc.boundingRect(contour)

            if (rect.width < MIN_CARD_WIDTH || rect.height < MIN_CARD_HEIGHT) {
                continue
            }

            val ratio = rect.width.toFloat() / rect.height.toFloat()
            if (ratio < CARD_RATIO_MIN || ratio > CARD_RATIO_MAX) {
                continue
            }

            val area = Imgproc.contourArea(contour)
            val rectArea = rect.width * rect.height
            val fill = area / rectArea

            if (fill < 0.5) {
                continue
            }

            val cardImage = image.submat(rect)
            val confidence = calculateConfidence(fill, ratio)

            cardRegions.add(CardRegion(rect, confidence, cardImage.clone()))
        }

        gray.release()
        blurred.release()
        edges.release()
        dilated.release()
        kernel.release()

        return cardRegions.sortedByDescending { it.confidence }
    }

    private fun calculateConfidence(fill: Double, ratio: Float): Double {
        val fillScore = (fill - 0.5) / 0.5
        val ratioScore = 1.0 - abs(ratio - 0.75f) / 0.15f
        return (fillScore * 0.6 + ratioScore * 0.4).coerceIn(0.0, 1.0)
    }
}
