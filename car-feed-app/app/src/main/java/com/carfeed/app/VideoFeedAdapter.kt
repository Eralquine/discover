package com.carfeed.app

import android.net.Uri
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.recyclerview.widget.RecyclerView

class VideoFeedAdapter(private val videos: List<Uri>) :
    RecyclerView.Adapter<VideoFeedAdapter.VideoViewHolder>() {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VideoViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_video, parent, false)
        return VideoViewHolder(view)
    }

    override fun onBindViewHolder(holder: VideoViewHolder, position: Int) {
        holder.bind(videos[position], position, itemCount)
    }

    override fun getItemCount() = videos.size

    override fun onViewAttachedToWindow(holder: VideoViewHolder) = holder.play()

    override fun onViewDetachedFromWindow(holder: VideoViewHolder) = holder.release()

    class VideoViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val playerView: PlayerView = itemView.findViewById(R.id.playerView)
        private val positionLabel: TextView = itemView.findViewById(R.id.positionLabel)
        private var player: ExoPlayer? = null
        private var uri: Uri? = null

        fun bind(uri: Uri, position: Int, total: Int) {
            this.uri = uri
            positionLabel.text = "${position + 1} / $total"
        }

        fun play() {
            val mediaUri = uri ?: return
            val exoPlayer = ExoPlayer.Builder(itemView.context).build().apply {
                setMediaItem(MediaItem.fromUri(mediaUri))
                repeatMode = Player.REPEAT_MODE_ONE
                prepare()
                playWhenReady = true
            }
            playerView.player = exoPlayer
            player = exoPlayer
        }

        fun release() {
            player?.release()
            player = null
            playerView.player = null
        }
    }
}
