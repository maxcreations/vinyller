"""
Vinyller — Player class
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

import os
import random
import time
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from src.utils.utils import resource_path
from src.utils.utils_translator import translate


class RepeatMode(Enum):
    """
    Enum representing the different repeat modes for playback.
    """
    NO_REPEAT = 0
    REPEAT_ALL = 1
    REPEAT_ONE = 2


class Player(QObject):
    """
    Player class using the PyQt6.QtMultimedia engine.
    Manages audio playback, queue progression, and custom sound effects (crackle, scratch).
    """

    errorOccurred = pyqtSignal(str)
    currentTrackChanged = pyqtSignal(str, str, int)
    queueChanged = pyqtSignal()
    missingTrackDetected = pyqtSignal(dict)

    def __init__(self, parent = None):
        """
        Initializes the Player instance, setting up QMediaPlayer objects for
        the main track, crackle (warm) sound, and scratch sound effects.
        """
        super().__init__(parent)
        self.main_window = parent

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.crackle_player = QMediaPlayer()
        self.crackle_audio_output = QAudioOutput()
        self.crackle_player.setAudioOutput(self.crackle_audio_output)
        self.crackle_player.setLoops(QMediaPlayer.Loops.Infinite)
        crackle_sound_path = resource_path("assets/sound/vinyl_crackle.mp3")
        if os.path.exists(crackle_sound_path):
            self.crackle_player.setSource(QUrl.fromLocalFile(crackle_sound_path))
        else:
            print(f"Warning: Crackle sound file not found at {crackle_sound_path}")

        self.scratch_forward_player = QMediaPlayer()
        self.scratch_forward_audio_output = QAudioOutput()
        self.scratch_forward_player.setAudioOutput(self.scratch_forward_audio_output)

        self.scratch_forward_paths = []
        for i in range(1, 4):
            path = resource_path(f"assets/sound/vinyl_interrupt_forward_{i}.mp3")
            if os.path.exists(path):
                self.scratch_forward_paths.append(path)

        self.scratch_backward_player = QMediaPlayer()
        self.scratch_backward_audio_output = QAudioOutput()
        self.scratch_backward_player.setAudioOutput(self.scratch_backward_audio_output)

        self.scratch_backward_paths = []
        for i in range(1, 4):
            path = resource_path(f"assets/sound/vinyl_interrupt_backward_{i}.mp3")
            if os.path.exists(path):
                self.scratch_backward_paths.append(path)

        self._queue = []
        self._play_history = []
        self._current_index = -1
        self._is_shuffled = False
        self._repeat_mode = RepeatMode.NO_REPEAT
        self._warm_sound_enabled = False
        self._scratch_sound_enabled = False

        self._last_missing_error_time = 0
        self._last_missing_path = ""

        self._pending_seek = 0

        self.player.errorOccurred.connect(self._handle_error)
        self.player.mediaStatusChanged.connect(self._handle_media_status_changed)

    def _handle_error(self, error):
        """
        Emits an error signal when the media player encounters a playback issue.
        """
        self.errorOccurred.emit(
            translate(
                "Player error: {error_string}", error_string=self.player.errorString()
            )
        )

    def _handle_media_status_changed(self, status):
        """
        Handles media status changes, triggering the next track when the current one finishes,
        and applying pending seeks when a new media file is fully loaded.
        """
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._on_playback_finished()

        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            if getattr(self, '_pending_seek', 0) > 0:
                self.player.setPosition(self._pending_seek)
                self._pending_seek = 0

    def _on_playback_finished(self):
        """
        Determines the next action when a track finishes playing, based on the
        current repeat and shuffle modes.
        """
        if self._repeat_mode == RepeatMode.REPEAT_ONE:
            self.play(self._current_index)
            return

        is_last_track = self._current_index == len(self._queue) - 1

        if (
            is_last_track
            and self._repeat_mode != RepeatMode.REPEAT_ALL
            and not self._is_shuffled
        ):
            self.stop()
            self.currentTrackChanged.emit(
                translate("Track Title"), translate("Artist Name"), -1
            )
            return

        self.next()

    def set_queue(self, tracks_data, preserve_playback=False, silent=False):
        """
        Sets the playback queue to a new list of tracks, optionally preserving
        the currently playing track's state and position.
        """
        current_track = None
        if preserve_playback and 0 <= self._current_index < len(self._queue):
            current_track = self._queue[self._current_index]

        self._queue = list(tracks_data)
        self._play_history = []

        if not preserve_playback and self.main_window:
            self.main_window.library_manager.reset_last_played_entity_metadata()

        if preserve_playback and current_track:
            try:
                self._current_index = self._queue.index(current_track)
            except ValueError:
                self.stop()
                self._current_index = 0 if self._queue else -1
        else:
            self._current_index = 0 if self._queue else -1

        if not silent:
            self.queueChanged.emit()

    def add_to_queue(self, tracks_to_add):
        """
        Appends a list of tracks to the end of the current playback queue.
        Starts playback if the queue was previously empty.
        """
        if not tracks_to_add:
            return
        was_empty = not self._queue
        self._queue.extend(tracks_to_add)
        self.queueChanged.emit()
        if (
            was_empty
            and self.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        ):
            self.play(0)

    def insert_tracks(self, tracks_to_insert, at_index):
        """
        Inserts a list of tracks into the queue at the specified index.
        Adjusts the current playback index if necessary.
        """
        if not tracks_to_insert:
            return
        was_empty = not self._queue
        if at_index < 0 or at_index > len(self._queue):
            at_index = len(self._queue)
        if self._current_index >= at_index:
            self._current_index += len(tracks_to_insert)
        for i, track in enumerate(tracks_to_insert):
            self._queue.insert(at_index + i, track)
        self.queueChanged.emit()
        if (
            was_empty
            and self.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        ):
            self.play(0)

    def remove_tracks(self, indices_to_remove: list[int]):
        """
        Removes tracks from the queue at the specified indices and safely updates
        the current playback index and history.
        """
        if not indices_to_remove or not self._queue:
            return
        was_playing = (
            self.get_current_state() == QMediaPlayer.PlaybackState.PlayingState
        )
        is_current_track_removed = self._current_index in indices_to_remove
        tracks_being_removed = [
            self._queue[i] for i in indices_to_remove if 0 <= i < len(self._queue)
        ]
        ids_being_removed = {id(t) for t in tracks_being_removed}
        self._play_history = [
            t for t in self._play_history if id(t) not in ids_being_removed
        ]

        for index in indices_to_remove:
            if 0 <= index < len(self._queue):
                self._queue.pop(index)

        if not self._queue:
            self.stop()
            self._current_index = -1
            self.queueChanged.emit()
            self.currentTrackChanged.emit(
                translate("Track Title"), translate("Artist Name"), -1
            )
            return

        if is_current_track_removed:
            if self._current_index >= len(self._queue):
                self._current_index = 0
        else:
            num_removed_before = sum(
                1 for i in indices_to_remove if i < self._current_index
            )
            self._current_index -= num_removed_before

        self.queueChanged.emit()

        if was_playing and is_current_track_removed:
            self.play(self._current_index)
        else:
            if self._current_index != -1:
                track_info = self._queue[self._current_index]
                self.currentTrackChanged.emit(
                    ", ".join(track_info.get("artists", [translate("Unknown")])),
                    track_info.get("title", os.path.basename(track_info.get("path"))),
                    self._current_index,
                )

    def get_current_queue(self):
        """
        Returns the current list of tracks in the playback queue.
        """
        return self._queue

    def play(self, selection = None, pause = False, resume_pos_ms = 0):
        """
        Starts playback of the selected track with support for resuming position
        and missing file handling.
        """
        if not self._queue:
            return

        if resume_pos_ms is None:
            resume_pos_ms = 0

        if isinstance(selection, dict):
            try:
                self._current_index = self._queue.index(selection)
            except ValueError:
                return
        elif isinstance(selection, int):
            self._current_index = selection

        if not (0 <= self._current_index < len(self._queue)):
            return

        track_info = self._queue[self._current_index]
        raw_path = track_info.get("path")
        if not raw_path:
            return

        real_path = raw_path
        cue_start_ms = 0

        if "::" in raw_path:
            real_path = raw_path.split("::")[0]
            cue_start_ms = track_info.get("start_ms", 0)

        final_seek_pos = resume_pos_ms if resume_pos_ms > 0 else cue_start_ms

        if os.path.exists(real_path):
            current_source = self.player.source().toLocalFile()
            is_same_file = current_source and os.path.normpath(
                current_source
            ) == os.path.normpath(real_path)

            if is_same_file:
                self.player.setPosition(final_seek_pos)
                self.player.play()
            else:
                self.player.blockSignals(True)
                self.player.setSource(QUrl())
                self.player.blockSignals(False)

                self.player.stop()
                try:
                    self._pending_seek = final_seek_pos

                    self.player.setSource(QUrl.fromLocalFile(real_path))
                    self.player.play()
                except Exception as e:
                    print(f"Critical Player Error setting source: {e}")
                    self._handle_error(str(e))
                    return

            if self._warm_sound_enabled:
                self.crackle_player.play()

            if pause:
                self.pause()

            self.currentTrackChanged.emit(
                ", ".join(track_info.get("artists", [translate("Unknown")])),
                track_info.get("title", os.path.basename(real_path)),
                self._current_index,
            )
        else:

            current_time = time.time()
            if (real_path == self._last_missing_path and
                    (current_time - self._last_missing_error_time) < 1.5):
                print(f"Ignored rapid retry on missing file: {real_path}")
                return

            self._last_missing_error_time = current_time
            self._last_missing_path = real_path

            self.stop()

            missing_tag = translate("File not found")
            original_title = track_info.get("title", os.path.basename(real_path))

            if not original_title.startswith(f"[{missing_tag}]"):
                track_info["title"] = f"[{missing_tag}] {original_title}"

            self.queueChanged.emit()

            if self.main_window:
                if hasattr(self.main_window, "handle_missing_track"):
                    self.missingTrackDetected.emit(track_info)

                if self._current_index < len(self._queue) - 1:
                    QTimer.singleShot(500, self.next)

    def pause(self):
        """
        Pauses the main media player and any active background crackle sounds.
        """
        self.player.pause()
        if self._warm_sound_enabled:
            self.crackle_player.pause()

    def resume(self):
        """
        Resumes playback of the main media player and the background crackle sound if enabled.
        """
        self.player.play()
        if self._warm_sound_enabled:
            self.crackle_player.play()

    def stop(self):
        """
        Stops all playback including the main track, crackle, and scratch sounds.
        """
        if self.main_window:
            self.main_window.library_manager.reset_last_played_entity_metadata()
        self.player.stop()
        self.crackle_player.stop()
        self.scratch_forward_player.stop()
        self.scratch_backward_player.stop()

    def next(self):
        """
        Advances to the next track in the queue based on the current shuffle and repeat settings.
        """
        if not self._queue:
            return

        if not self._is_shuffled:
            self._current_index = (self._current_index + 1) % len(self._queue)
        else:
            unplayed_tracks = [
                track for track in self._queue if track not in self._play_history
            ]
            if not unplayed_tracks:
                last_track = self._play_history[-1] if self._play_history else None
                self._play_history = [last_track] if last_track else []
                unplayed_tracks = [
                    track for track in self._queue if track not in self._play_history
                ]

            if unplayed_tracks:
                next_track = random.choice(unplayed_tracks)
                self._current_index = self._queue.index(next_track)
            elif self._queue:
                self._current_index = 0
            else:
                return

        self.play()

    def previous(self):
        """
        Goes back to the previous track or restarts the current track if it has
        been playing for more than 3 seconds.
        """
        current_pos = self.player.position()
        track_start = 0
        if 0 <= self._current_index < len(self._queue):
            track_info = self._queue[self._current_index]
            track_start = track_info.get("start_ms", 0)

        if current_pos > (track_start + 3000) and not self._is_shuffled:
            self.player.setPosition(track_start)
            return

        if not self._queue:
            return

        if not self._is_shuffled:
            self._current_index = (self._current_index - 1 + len(self._queue)) % len(
                self._queue
            )
        else:
            if len(self._play_history) > 1:
                self._play_history.pop()
                prev_track = self._play_history[-1]
                self._current_index = self._queue.index(prev_track)
            else:
                self.player.setPosition(track_start)
                return

        self.play()

    def set_volume(self, volume):
        """
        Sets the volume for the main audio and adjusts the relative volumes of
        background crackle and scratch sounds.
        """
        volume_float = volume / 100.0
        self.audio_output.setVolume(volume_float)
        self.crackle_audio_output.setVolume(volume_float * 0.25)
        self.scratch_forward_audio_output.setVolume(volume_float * 0.7)
        self.scratch_backward_audio_output.setVolume(volume_float * 0.7)

    def set_position(self, position_ms):
        """
        Seeks to a specific position (in milliseconds) within the current track.
        """
        self.player.setPosition(position_ms)

    def toggle_shuffle(self):
        """
        Toggles the shuffle mode on or off and resets the playback history accordingly.
        """
        self._is_shuffled = not self._is_shuffled
        if self._is_shuffled:
            current_track = None
            if 0 <= self._current_index < len(self._queue):
                current_track = self._queue[self._current_index]
            self._play_history = [current_track] if current_track else []
        return self._is_shuffled

    def is_shuffled(self):
        """
        Returns True if shuffle mode is currently enabled.
        """
        return self._is_shuffled

    def cycle_repeat_mode(self):
        """
        Cycles through the available repeat modes (No Repeat, Repeat All, Repeat One).
        """
        current_mode_val = self._repeat_mode.value
        next_mode_val = (current_mode_val + 1) % len(RepeatMode)
        self._repeat_mode = RepeatMode(next_mode_val)
        return self._repeat_mode

    def get_repeat_mode(self):
        """
        Returns the current repeat mode.
        """
        return self._repeat_mode

    def set_repeat_mode(self, mode: RepeatMode):
        """
        Sets the repeat mode directly to the specified RepeatMode enum value.
        """
        if isinstance(mode, RepeatMode):
            self._repeat_mode = mode
        else:
            print(
                f"Warning: Invalid repeat mode type passed to set_repeat_mode: {type(mode)}"
            )

    def get_current_state(self):
        """
        Returns the current playback state of the main media player.
        """
        return self.player.playbackState()

    def get_current_index(self):
        """
        Returns the index of the currently playing track in the queue.
        """
        return self._current_index

    def set_warm_sound(self, enabled: bool):
        """
        Enables or disables the continuous vinyl crackle background sound.
        """
        self._warm_sound_enabled = enabled
        if enabled:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.crackle_player.play()
        else:
            self.crackle_player.stop()

    def set_scratch_sound(self, enabled: bool):
        """
        Enables or disables the vinyl scratch sound effects.
        """
        self._scratch_sound_enabled = enabled
        if not enabled:
            self.stop_scratch_sound()

    def play_scratch_forward(self):
        """
        Plays a random forward vinyl scratch sound effect.
        """
        if not self._scratch_sound_enabled or not self.scratch_forward_paths:
            return
        random_sound_path = random.choice(self.scratch_forward_paths)
        self.scratch_forward_player.setSource(QUrl.fromLocalFile(random_sound_path))
        self.scratch_forward_player.stop()
        current_volume_float = self.audio_output.volume()
        self.scratch_forward_audio_output.setVolume(current_volume_float * 0.7)
        self.scratch_forward_audio_output.setMuted(self.audio_output.isMuted())
        self.scratch_forward_player.play()

    def stop_scratch_forward(self):
        """
        Stops the forward vinyl scratch sound effect.
        """
        if (
            self.scratch_forward_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.scratch_forward_player.stop()

    def play_scratch_backward(self):
        """
        Plays a random backward vinyl scratch sound effect.
        """
        if not self._scratch_sound_enabled or not self.scratch_backward_paths:
            return
        random_sound_path = random.choice(self.scratch_backward_paths)
        self.scratch_backward_player.setSource(QUrl.fromLocalFile(random_sound_path))
        self.scratch_backward_player.stop()
        current_volume_float = self.audio_output.volume()
        self.scratch_backward_audio_output.setVolume(current_volume_float * 0.7)
        self.scratch_backward_audio_output.setMuted(self.audio_output.isMuted())
        self.scratch_backward_player.play()

    def stop_scratch_backward(self):
        """
        Stops the backward vinyl scratch sound effect.
        """
        if (
            self.scratch_backward_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.scratch_backward_player.stop()

    def stop_scratch_sound(self):
        """
        Stops both forward and backward vinyl scratch sound effects.
        """
        self.stop_scratch_forward()
        self.stop_scratch_backward()