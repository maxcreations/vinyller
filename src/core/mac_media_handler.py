"""
Vinyller — macOS MPRemoteCommandCenter integration
Copyright (C) 2026 Maxim Moshkin
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys

if sys.platform == "darwin":
    import objc
    from Foundation import NSObject, NSNumber, NSMutableDictionary
    from MediaPlayer import (
        MPRemoteCommandCenter,
        MPNowPlayingInfoCenter,
        MPMediaItemPropertyTitle,
        MPMediaItemPropertyArtist,
        MPMediaItemPropertyAlbumTitle,
        MPMediaItemPropertyPlaybackDuration,
        MPNowPlayingInfoPropertyElapsedPlaybackTime,
        MPNowPlayingInfoPropertyPlaybackRate,
        MPRemoteCommandHandlerStatusSuccess,
    )

    class MacMediaManager(NSObject):
        """
        Manages macOS native media controls (MPRemoteCommandCenter and MPNowPlayingInfoCenter).
        Allows the application to respond to media keys and control center events.
        """

        def initWithWindow_(self, main_window):
            """
            Initializes the MacMediaManager with the main application window.
            """
            self = objc.super(MacMediaManager, self).init()
            if self is None:
                return None

            self.main_window = main_window
            self.player = main_window.player
            self._setup_remote_commands()
            return self

        @objc.python_method
        def _setup_remote_commands(self):
            """
            Registers the application with the macOS command center
            and binds remote commands to internal handlers.
            """
            command_center = MPRemoteCommandCenter.sharedCommandCenter()

            cmd_toggle = command_center.togglePlayPauseCommand()
            cmd_toggle.setEnabled_(True)
            cmd_toggle.addTarget_action_(self, b"onTogglePlayPause:")

            cmd_play = command_center.playCommand()
            cmd_play.setEnabled_(True)
            cmd_play.addTarget_action_(self, b"onPlay:")

            cmd_pause = command_center.pauseCommand()
            cmd_pause.setEnabled_(True)
            cmd_pause.addTarget_action_(self, b"onPause:")

            cmd_next = command_center.nextTrackCommand()
            cmd_next.setEnabled_(True)
            cmd_next.addTarget_action_(self, b"onNext:")

            cmd_prev = command_center.previousTrackCommand()
            cmd_prev.setEnabled_(True)
            cmd_prev.addTarget_action_(self, b"onPrev:")

        def onTogglePlayPause_(self, event):
            """Handler for the toggle play/pause remote command."""
            self.main_window.player_controller.toggle_play_pause()
            return MPRemoteCommandHandlerStatusSuccess
        onTogglePlayPause_ = objc.selector(onTogglePlayPause_, signature=b"q@:@")

        def onPlay_(self, event):
            """Handler for the play remote command."""
            self.main_window.player.play()
            return MPRemoteCommandHandlerStatusSuccess
        onPlay_ = objc.selector(onPlay_, signature=b"q@:@")

        def onPause_(self, event):
            """Handler for the pause remote command."""
            self.main_window.player.pause()
            return MPRemoteCommandHandlerStatusSuccess
        onPause_ = objc.selector(onPause_, signature=b"q@:@")

        def onNext_(self, event):
            """Handler for the next track remote command."""
            self.main_window.player.next()
            return MPRemoteCommandHandlerStatusSuccess
        onNext_ = objc.selector(onNext_, signature=b"q@:@")

        def onPrev_(self, event):
            """Handler for the previous track remote command."""
            self.main_window.player.previous()
            return MPRemoteCommandHandlerStatusSuccess
        onPrev_ = objc.selector(onPrev_, signature=b"q@:@")

        @objc.python_method
        def update_now_playing_info(self, track_data, is_playing = True, current_time_ms = 0):
            """
            Updates the macOS Now Playing Info center with the current track metadata,
            playback duration, and elapsed time.
            """
            if not track_data:
                return

            now_playing_info = NSMutableDictionary.alloc().init()

            title = track_data.get("title", "Unknown Title")
            artist = ", ".join(track_data.get("artists", ["Unknown Artist"]))
            album = track_data.get("album", "")
            duration_s = track_data.get("duration", 0)

            now_playing_info[MPMediaItemPropertyTitle] = title
            now_playing_info[MPMediaItemPropertyArtist] = artist
            now_playing_info[MPMediaItemPropertyAlbumTitle] = album
            now_playing_info[MPMediaItemPropertyPlaybackDuration] = NSNumber.numberWithDouble_(duration_s)
            now_playing_info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = NSNumber.numberWithDouble_(current_time_ms / 1000.0)

            rate = 1.0 if is_playing else 0.0
            now_playing_info[MPNowPlayingInfoPropertyPlaybackRate] = NSNumber.numberWithDouble_(rate)

            if hasattr(MPNowPlayingInfoCenter.defaultCenter(), 'setPlaybackState_'):
                playback_state = 1 if is_playing else 2
                MPNowPlayingInfoCenter.defaultCenter().setPlaybackState_(playback_state)

            MPNowPlayingInfoCenter.defaultCenter().setNowPlayingInfo_(now_playing_info)