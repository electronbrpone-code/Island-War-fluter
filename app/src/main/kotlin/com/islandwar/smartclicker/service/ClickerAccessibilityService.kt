package com.islandwar.smartclicker.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.view.AccessibilityEvent
import android.view.WindowManager
import androidx.datastore.preferences.preferencesDataStore
import com.islandwar.smartclicker.data.PreferenceManager
import com.islandwar.smartclicker.data.db.AppDatabase
import com.islandwar.smartclicker.data.db.DetectionHistoryEntity
import com.islandwar.smartclicker.ml.CardDetector
import com.islandwar.smartclicker.ml.CardRecognizer
import com.islandwar.smartclicker.ml.FingerprintGenerator
import kotlinx.coroutines.*
import org.opencv.android.Utils
import org.opencv.core.Mat

class ClickerAccessibilityService : AccessibilityService() {
    private lateinit var db: AppDatabase
    private lateinit var preferenceManager: PreferenceManager
    private lateinit var recognizer: CardRecognizer
    private lateinit var detector: CardDetector
    private var clickerScope = CoroutineScope(Dispatchers.Default + Job())

    private var isClickerActive = false
    private var lastScreenshot: Bitmap? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        db = AppDatabase.getInstance(this)
        preferenceManager = PreferenceManager(this)
        recognizer = CardRecognizer()
        detector = CardDetector()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (!isClickerActive) return

        when (event?.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                processScreenshot()
            }
        }
    }

    override fun onInterrupt() {}

    private fun processScreenshot() {
        clickerScope.launch {
            try {
                val screenshot = takeScreenshot()
                if (screenshot != null) {
                    lastScreenshot = screenshot
                    val mat = Mat()
                    Utils.bitmapToMat(screenshot, mat)

                    val cardRegions = detector.detectCards(mat)

                    for (region in cardRegions) {
                        val result = recognizer.recognize(region.image)
                        if (result != null && result.confidence > 50.0) {
                            performClick(region.rect.x + region.rect.width / 2, 
                                        region.rect.y + region.rect.height / 2)

                            db.detectionHistoryDao().insertHistory(
                                DetectionHistoryEntity(
                                    cardId = result.entry.id,
                                    confidence = result.confidence,
                                    distance = result.distance
                                )
                            )

                            db.statisticDao().incrementAutoChoices()
                            break
                        }
                    }

                    mat.release()
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    private fun takeScreenshot(): Bitmap? {
        return try {
            val display = display ?: return null
            val width = display.width
            val height = display.height

            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            val canvas = android.graphics.Canvas(bitmap)

            val view = window.decorView
            view.draw(canvas)

            bitmap
        } catch (e: Exception) {
            null
        }
    }

    private fun performClick(x: Int, y: Int) {
        val gesture = GestureDescription.Builder().apply {
            val path = android.graphics.Path().apply {
                moveTo(x.toFloat(), y.toFloat())
                lineTo(x.toFloat(), y.toFloat())
            }
            addStroke(GestureDescription.StrokeDescription(path, 0, 100))
        }.build()

        dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription) {}
            override fun onCancelled(gestureDescription: GestureDescription) {}
        }, null)
    }

    fun setClickerActive(active: Boolean) {
        isClickerActive = active
    }

    override fun onDestroy() {
        super.onDestroy()
        clickerScope.cancel()
    }
}
