package com.carfeed.app

import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore

/**
 * Videos never come from TikTok's private feed (there is no public API for it,
 * and scraping it would violate TikTok's terms of service). Instead this app
 * plays whatever the user has copied into the device folder Movies/CarFeed.
 */
object VideoRepository {

    private const val FOLDER = "CarFeed"

    fun loadLocalVideos(context: Context): List<Uri> {
        val videos = mutableListOf<Uri>()
        val collection = MediaStore.Video.Media.EXTERNAL_CONTENT_URI
        val pathColumn = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Video.Media.RELATIVE_PATH
        } else {
            MediaStore.Video.Media.DATA
        }
        val projection = arrayOf(MediaStore.Video.Media._ID, pathColumn)
        val selection = "$pathColumn LIKE ?"
        val selectionArgs = arrayOf("%$FOLDER%")
        val sortOrder = "${MediaStore.Video.Media.DATE_ADDED} ASC"

        context.contentResolver.query(collection, projection, selection, selectionArgs, sortOrder)
            ?.use { cursor ->
                val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Video.Media._ID)
                while (cursor.moveToNext()) {
                    val id = cursor.getLong(idColumn)
                    videos.add(Uri.withAppendedPath(collection, id.toString()))
                }
            }
        return videos
    }
}
