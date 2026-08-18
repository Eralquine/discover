package com.carfeed.app

import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.viewpager2.widget.ViewPager2

class MainActivity : AppCompatActivity() {

    private lateinit var pager: ViewPager2
    private lateinit var emptyText: TextView

    private val storagePermission =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            android.Manifest.permission.READ_MEDIA_VIDEO
        } else {
            android.Manifest.permission.READ_EXTERNAL_STORAGE
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        hideSystemBars()

        pager = findViewById(R.id.pager)
        emptyText = findViewById(R.id.emptyText)
        pager.orientation = ViewPager2.ORIENTATION_VERTICAL

        if (ActivityCompat.checkSelfPermission(this, storagePermission)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(storagePermission), REQUEST_STORAGE)
        } else {
            loadFeed()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_STORAGE && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            loadFeed()
        }
    }

    private fun loadFeed() {
        val videos = VideoRepository.loadLocalVideos(this)
        if (videos.isEmpty()) {
            emptyText.visibility = View.VISIBLE
            return
        }
        emptyText.visibility = View.GONE
        pager.adapter = VideoFeedAdapter(videos)
    }

    private fun hideSystemBars() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_FULLSCREEN
            )
    }

    /**
     * Los botones físicos/rueda de volumen del auto pasan por acá antes que
     * cualquier otra vista. Los consumimos para pasar de video (swipe) en vez
     * de dejar que suban o bajen el volumen del sistema.
     */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN && ::pager.isInitialized) {
            when (event.keyCode) {
                KeyEvent.KEYCODE_VOLUME_DOWN -> {
                    pager.setCurrentItem(pager.currentItem + 1, true)
                    return true
                }
                KeyEvent.KEYCODE_VOLUME_UP -> {
                    pager.setCurrentItem(pager.currentItem - 1, true)
                    return true
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }

    companion object {
        private const val REQUEST_STORAGE = 100
    }
}
