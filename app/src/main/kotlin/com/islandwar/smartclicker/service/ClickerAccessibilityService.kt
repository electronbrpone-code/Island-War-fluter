package com.islandwar.smartclicker.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.view.accessibility.AccessibilityEvent
import android.util.Log

class ClickerAccessibilityService : AccessibilityService() {
    private val TAG = "SmartClicker"
    private var isRunning = false

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event != null) {
            Log.d(TAG, "Event type: ${event.eventType}")
        }
    }

    override fun onInterrupt() {
        Log.d(TAG, "Accessibility service interrupted")
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        Log.d(TAG, "Accessibility service connected")
    }

    fun performClick(x: Float, y: Float) {
        if (!isRunning) return

        val path = Path().apply {
            moveTo(x, y)
        }

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()

        dispatchGesture(gesture) { success ->
            if (success) {
                Log.d(TAG, "Click performed at ($x, $y)")
            }
        }
    }

    fun startAutoClicking() {
        isRunning = true
        Log.d(TAG, "Auto-clicker started")
    }

    fun stopAutoClicking() {
        isRunning = false
        Log.d(TAG, "Auto-clicker stopped")
    }
}