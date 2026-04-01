"""
Vinyller — Mixed batch editor widget
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

import difflib
import html
import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QListWidgetItem, QStackedWidget, QAbstractItemView, QFrame
)

from src.meta_editor.editor_components import (
    FilenameDelegate, BatchTrackDetailWidget, MultiTrackEditWidget, get_original_tag_value
)
from src.ui.custom_base_widgets import (
    StyledScrollArea, StyledListWidget, set_custom_tooltip, TranslucentMenu
)
from src.utils import theme
from src.utils.utils import create_svg_icon, resource_path
from src.utils.utils_translator import translate


class MixedBatchEditor(QWidget):
    """
    Editor widget for modifying a mixed selection of tracks from different albums.
    Implements standard interface for UniversalMetadataEditorDialog.
    """
    supports_fast_save = False
    dataChanged = pyqtSignal()
    statusMessage = pyqtSignal(str)

    def __init__(self, tracks, main_window, parent = None):
        """
        Initializes the MixedBatchEditor.

        Args:
            tracks (list): A list of track data dictionaries representing a mixed selection of albums.
            main_window (QMainWindow): Reference to the main application window.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.mw = main_window
        self.tracks = tracks

        self.all_artists = sorted(list(self.mw.data_manager.artists_data.keys()))
        self.all_genres = sorted(list(self.mw.data_manager.genres_data.keys()))
        self.all_albums = sorted(set(k[1] for k in self.mw.data_manager.albums_data.keys()))

        self.batch_detail_widgets = [None] * len(self.tracks)
        self.pending_batch_edits = {}
        self.fetched_tracks = []

        self.status_icon = QIcon(create_svg_icon("assets/control/caution.svg", theme.COLORS["ACCENT"], QSize(16, 16)))

        self.setupUi()
        self.load_data()

    def setupUi(self):
        """Builds the 2-column layout specific to mixed-album batch editing."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        files_scroll = StyledScrollArea()
        files_scroll.setWidgetResizable(True)
        files_scroll.setFrameShape(QFrame.Shape.NoFrame)
        files_scroll.setProperty("class", "backgroundTransparent borderRight")
        files_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        files_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        files_scroll.setFixedWidth(280)

        files_list_widget = QWidget()
        files_list_widget.setProperty("class", "backgroundPrimary")
        files_list_widget.setContentsMargins(16, 16, 16, 16)

        files_list_layout = QVBoxLayout(files_list_widget)
        files_list_layout.setContentsMargins(0, 0, 0, 0)
        files_list_layout.setSpacing(8)

        tracks_list_layout_lbl = QLabel(translate("Selected files"))
        tracks_list_layout_lbl.setProperty("class", "textTertiary textColorTertiary")
        files_list_layout.addWidget(tracks_list_layout_lbl)

        self.tracks_list_widget = StyledListWidget()
        self.tracks_list_widget.setProperty("class", "listWidgetNav")
        self.tracks_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tracks_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tracks_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tracks_list_widget.setItemDelegate(FilenameDelegate(self.tracks_list_widget))
        self.tracks_list_widget.itemSelectionChanged.connect(self._on_track_selection_changed)

        self.tracks_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tracks_list_widget.customContextMenuRequested.connect(self._show_track_list_context_menu)

        files_list_layout.addWidget(self.tracks_list_widget)
        files_scroll.setWidget(files_list_widget)

        content_scroll = StyledScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_scroll.setProperty("class", "backgroundPrimary")

        right_widget = QWidget()
        right_widget.setProperty("class", "backgroundPrimary")

        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(24, 24, 24, 24)
        right_layout.setSpacing(24)
        content_scroll.setWidget(right_widget)

        self.details_stack = QStackedWidget()
        right_layout.addWidget(self.details_stack)

        layout.addWidget(files_scroll, 0)
        layout.addWidget(content_scroll, 1)

    def load_data(self):
        """Populates the list view and initializes the multi-track editor."""
        first_track = self.tracks[0]
        extended_info = self.mw.library_manager.get_extended_track_info(first_track["path"])
        fmt_raw = extended_info.get("format", "MP3")

        self.tracks_list_widget.clear()

        for i, track in enumerate(self.tracks):
            filename = os.path.basename(track["path"])
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, track["path"])
            item.setData(Qt.ItemDataRole.UserRole + 1, i)

            safe_text = html.escape(filename)
            set_custom_tooltip(item, title = translate("File Name"), text = safe_text)
            self.tracks_list_widget.addItem(item)

        self.multi_edit_widget = MultiTrackEditWidget(
            self.all_artists, self.all_genres, fmt_raw,
            is_mixed_mode = True, all_albums = self.all_albums, parent = self
        )
        self.multi_edit_widget.fieldApplied.connect(self._apply_multi_edit)
        self.multi_edit_widget.coverApplied.connect(self._apply_multi_cover)
        self.details_stack.addWidget(self.multi_edit_widget)

        if self.tracks:
            self.tracks_list_widget.setCurrentRow(0)

    def _get_track_cover_path(self, index):
        """
        Retrieves the current cover art path for a specific track, taking into account any pending edits.
        """
        widget = self.batch_detail_widgets[index]
        if widget is not None:
            if widget.new_cover_path: return widget.new_cover_path
            artwork_data = widget.local_track.get("artwork")
        else:
            pending = self.pending_batch_edits.get(index, {})
            if "artwork_path" in pending: return pending["artwork_path"]
            track = self.tracks[index]
            artwork_data = track.get("artwork")

        if artwork_data:
            if isinstance(artwork_data, dict):
                avail = sorted([int(s) for s in artwork_data.keys()])
                return artwork_data.get(str(avail[-1])) if avail else None
            return artwork_data
        return None

    def _on_track_selection_changed(self):
        """
        Handles list selection changes to toggle between the individual track detail editor and the multi-track bulk editor.
        """
        selected_items = self.tracks_list_widget.selectedItems()
        if not selected_items:
            return

        if len(selected_items) == 1:
            idx = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)

            if self.batch_detail_widgets[idx] is None:
                track = self.tracks[idx]
                detail_widget = BatchTrackDetailWidget(
                    track, self.all_artists, self.all_genres, self.mw,
                    is_mixed_mode = True, all_albums = self.all_albums
                )

                pending = self.pending_batch_edits.get(idx, {})
                for ui_key, val in pending.items():
                    if ui_key == "artwork_path":
                        detail_widget._apply_new_cover(val)
                        continue

                    target = detail_widget.inputs if ui_key in detail_widget.inputs else detail_widget.advanced_widget.inputs
                    if ui_key in target:
                        target[ui_key].setCurrentText(val)
                        if target[ui_key].lineEdit():
                            target[ui_key].lineEdit().setText(val)
                        target[ui_key]._update_style()

                detail_widget.dataChanged.connect(lambda i = idx: self._update_track_status_icon(i))
                detail_widget.dataChanged.connect(self.dataChanged.emit)
                detail_widget.coverChanged.connect(lambda path, i = idx: self._update_track_status_icon(i))
                detail_widget.statusMessage.connect(self.statusMessage.emit)

                self.details_stack.addWidget(detail_widget)
                self.batch_detail_widgets[idx] = detail_widget

            self.details_stack.setCurrentWidget(self.batch_detail_widgets[idx])

        elif len(selected_items) > 1:
            indices = [item.data(Qt.ItemDataRole.UserRole + 1) for item in selected_items]

            first_path = self._get_track_cover_path(indices[0])
            has_different_covers = False

            for idx in indices[1:]:
                if self._get_track_cover_path(idx) != first_path:
                    has_different_covers = True
                    break

            if has_different_covers or not first_path:
                default_missing = "assets/view/missing_cover.png"
                missing_path = theme.COLORS.get("MISSING_COVER", default_missing)
                try:
                    pixmap = QIcon(resource_path(missing_path)).pixmap(256, 256)
                except Exception:
                    pixmap = QPixmap(256, 256)
                    pixmap.fill(Qt.GlobalColor.gray)
            else:
                pixmap = QPixmap(first_path)

            self.multi_edit_widget.set_common_cover(pixmap)
            self.multi_edit_widget.load_selection(indices, self.batch_detail_widgets, self.tracks,
                                                  self.pending_batch_edits)
            self.details_stack.setCurrentWidget(self.multi_edit_widget)

    def _apply_multi_edit(self, key, value):
        """
        Applies a metadata change to all currently selected tracks in the batch list.
        """
        selected_items = self.tracks_list_widget.selectedItems()
        is_reset_mixed = (value == "__RESET_MIXED__")
        if value is None: value = ""

        for item in selected_items:
            idx = item.data(Qt.ItemDataRole.UserRole + 1)
            widget = self.batch_detail_widgets[idx]
            track = self.tracks[idx]

            if widget is not None:
                target_inputs = widget.inputs if key in widget.inputs else widget.advanced_widget.inputs
                if key in target_inputs:
                    inp = target_inputs[key]
                    if is_reset_mixed:
                        inp.reset_to_original()
                    else:
                        inp.setCurrentText(value)
                        if inp.lineEdit(): inp.lineEdit().setText(value)
                    inp._update_style()
            else:
                if is_reset_mixed:
                    if idx in self.pending_batch_edits and key in self.pending_batch_edits[idx]:
                        del self.pending_batch_edits[idx][key]
                else:
                    orig_val = get_original_tag_value(key, track, self.mw.library_manager)

                    if str(value).strip() == str(orig_val).strip():
                        if idx in self.pending_batch_edits and key in self.pending_batch_edits[idx]:
                            del self.pending_batch_edits[idx][key]
                    else:
                        if idx not in self.pending_batch_edits:
                            self.pending_batch_edits[idx] = {}
                        self.pending_batch_edits[idx][key] = value

            if idx in self.pending_batch_edits and not self.pending_batch_edits[idx]:
                del self.pending_batch_edits[idx]

            self._update_track_status_icon(idx)
        self.dataChanged.emit()

    def _apply_multi_cover(self, path):
        """
        Applies a new cover image to all currently selected tracks in the batch list.
        """
        selected_items = self.tracks_list_widget.selectedItems()
        for item in selected_items:
            idx = item.data(Qt.ItemDataRole.UserRole + 1)
            widget = self.batch_detail_widgets[idx]

            if widget is not None:
                if path == "__RESET_MIXED__":
                    widget._reset_cover()
                else:
                    widget._apply_new_cover(path)
            else:
                if idx not in self.pending_batch_edits:
                    self.pending_batch_edits[idx] = {}

                if path == "__RESET_MIXED__":
                    if "artwork_path" in self.pending_batch_edits[idx]:
                        del self.pending_batch_edits[idx]["artwork_path"]
                else:
                    self.pending_batch_edits[idx]["artwork_path"] = path

            self._update_track_status_icon(idx)

    def _update_track_status_icon(self, index):
        """
        Updates the warning icon next to a track in the list if it contains unsaved modifications.
        """
        if 0 <= index < len(self.batch_detail_widgets):
            widget = self.batch_detail_widgets[index]
            item = self.tracks_list_widget.item(index)

            has_mods = False
            if widget is not None:
                has_mods = widget.has_modifications()
            else:
                has_mods = index in self.pending_batch_edits and bool(self.pending_batch_edits[index])

            if has_mods:
                item.setIcon(self.status_icon)
            else:
                item.setIcon(QIcon())

    def get_data(self):
        """
        Compiles and returns the finalized metadata for all tracks, merging active widget data and pending background edits.
        """
        results = {}
        for idx, track in enumerate(self.tracks):
            widget = self.batch_detail_widgets[idx]
            if widget is not None:
                row_data = widget.get_data()
                path = row_data.pop("path")
                results[path] = row_data
            else:
                pending = self.pending_batch_edits.get(idx, {})
                if pending:
                    row_data = self._build_lazy_data(track, pending)
                    results[track["path"]] = row_data
        return results

    def _build_lazy_data(self, track, pending_edits):
        """
        Constructs the final data dictionary for a track without instantiating its detail UI widget.
        """
        artists = track.get("artists", [])
        if not artists and track.get("artist"): artists = [track.get("artist")]
        artist_str = "; ".join([x for x in artists if x]) if isinstance(artists, list) else str(artists)
        g = track.get("genre", [])
        genre_str = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g)

        data = {
            "title": track.get("title", ""),
            "artist": artist_str,
            "composer": track.get("composer", ""),
            "genre": genre_str,
            "tracknumber": str(track.get("tracknumber", "")),
            "discnumber": str(track.get("discnumber", "")),
            "lyrics": track.get("lyrics", ""),
            "album": track.get("album", ""),
            "albumartist": track.get("album_artist", ""),
            "date": str(track.get("year", ""))
        }

        key_map = {
            "Title": "title", "Artist": "artist", "Composer": "composer", "Genre": "genre",
            "Track Number": "tracknumber", "Disc Number": "discnumber",
            "Album": "album", "Album Artist": "albumartist", "Year": "date"
        }

        for ui_key, val in pending_edits.items():
            if ui_key == "artwork_path":
                if val != "__RESET_MIXED__": data["artwork_path"] = val
            elif ui_key in key_map:
                data[key_map[ui_key]] = val
            else:
                data[ui_key] = val

        return data

    def get_diff_summary(self):
        """
        Generates a summary of all modifications made across the mixed batch for the confirmation view.
        """
        diff_summary = []
        new_data_map = self.get_data()

        display_names = {
            "title": translate("Title"), "artist": translate("Artist"),
            "album": translate("Album"), "albumartist": translate("Album Artist"),
            "composer": translate("Composer"), "genre": translate("Genre"),
            "date": translate("Year"), "tracknumber": translate("Track #"),
            "discnumber": translate("Disc #"), "lyrics": translate("Lyrics"),
            "artwork_path": translate("Cover Art"),
            "original_year": translate("Original Release Year"),
            "comment": translate("Comment"), "copyright": translate("Copyright"),
            "source_url": translate("Source URL"), "user_url": translate("User URL"),
            "bpm": translate("BPM"), "isrc": translate("ISRC"),
            "media_type": translate("Media Type"), "encoded_by": translate("Encoded By"),
            "encoder_settings": translate("Encoder Settings")
        }
        advanced_keys = {
            "original_year", "comment", "copyright", "source_url", "user_url",
            "bpm", "isrc", "media_type", "encoded_by", "encoder_settings"
        }

        for i, track in enumerate(self.tracks):
            path = track["path"]
            if path not in new_data_map:
                continue

            new_tags = new_data_map[path]
            widget = self.batch_detail_widgets[i]
            if widget is not None:
                original_ext = widget.extended_data
            else:
                original_ext = self.mw.library_manager.get_extended_track_info(path)

            for key, new_val in new_tags.items():
                if key == "artwork_path":
                    diff_summary.append((os.path.basename(path), display_names["artwork_path"], translate("Current"),
                                         translate("New Image")))
                    continue

                old_val = ""
                if key in advanced_keys:
                    old_val = original_ext.get(key, "")
                else:
                    if key == "genre":
                        g = track.get("genre", [])
                        old_val = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g) if g else ""
                    elif key == "artist":
                        a = track.get("artists", [])
                        if not a and track.get("artist"): a = [track.get("artist")]
                        old_val = "; ".join([x for x in a if x]) if isinstance(a, list) else str(a) if a else ""
                    elif key == "date":
                        old_val = track.get("year", "")
                    elif key == "albumartist":
                        old_val = track.get("album_artist", "")
                    else:
                        old_val = track.get(key, "")

                s_old = str(old_val).strip() if old_val is not None else ""
                s_new = str(new_val).strip() if new_val is not None else ""

                if s_old != s_new:
                    if key == "lyrics":
                        disp_old = (s_old[:20] + "...") if len(s_old) > 20 else s_old
                        disp_new = (s_new[:20] + "...") if len(s_new) > 20 else s_new
                    else:
                        disp_old, disp_new = s_old, s_new

                    diff_summary.append((os.path.basename(path), display_names.get(key, key), disp_old, disp_new))

        return diff_summary

    def get_search_queries(self):
        """
        Returns the search parameters (artist, album) based on the currently visible editor context for Apple Music querying.
        """
        if self.details_stack.currentWidget() == self.multi_edit_widget:
            artist = self.multi_edit_widget.inputs.get("Album Artist",
                                                       self.multi_edit_widget.inputs["Artist"]).get_final_value()
            album = self.multi_edit_widget.inputs.get("Album").get_final_value()
        else:
            selected_items = self.tracks_list_widget.selectedItems()
            if selected_items:
                idx = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)
                widget = self.batch_detail_widgets[idx]
                artist = widget.inputs["Album Artist"].get_final_value() or widget.inputs["Artist"].get_final_value()
                album = widget.inputs["Album"].get_final_value()
            else:
                artist, album = "", ""
        return (artist, album)

    def apply_search_results(self, result, raw_data, fetched_tracks):
        """
        Applies metadata fetched from Apple Music to all tracks in the mixed batch selection.
        """
        self.fetched_tracks = fetched_tracks

        album_name = result.get("album", "")
        artist_name = result.get("artist", "")
        year_val = result.get("year", "")

        if "Album" in self.multi_edit_widget.inputs:
            self.multi_edit_widget.inputs["Album"].set_fetched_value(album_name)
            self.multi_edit_widget.inputs["Album Artist"].set_fetched_value(artist_name)
            self.multi_edit_widget.inputs["Year"].set_fetched_value(year_val)

        self.tracks_list_widget.selectAll()
        self._apply_multi_edit("Album", album_name)
        self._apply_multi_edit("Album Artist", artist_name)
        self._apply_multi_edit("Year", year_val)

        for i, widget in enumerate(self.batch_detail_widgets):
            found_idx = self._find_best_match_index(self.tracks[i], fetched_tracks, i)
            if found_idx != -1:
                if widget is not None:
                    widget.show_match_container()
                    widget.set_match_options(fetched_tracks)
                    widget.match_combo.setCurrentIndex(found_idx + 1)
                else:
                    if i not in self.pending_batch_edits:
                        self.pending_batch_edits[i] = {}
                    ft = fetched_tracks[found_idx]
                    self.pending_batch_edits[i]["Title"] = ft["title"]
                    self.pending_batch_edits[i]["Artist"] = ft["artist"]
                    self.pending_batch_edits[i]["Genre"] = ft.get("genre", "")
                    self.pending_batch_edits[i]["Track Number"] = str(ft["track_number"])
                    self.pending_batch_edits[i]["Disc Number"] = str(ft["_raw"].get("discNumber", 1))

    def apply_new_cover(self, path):
        """
        Passes a newly downloaded or selected cover art path to the active sub-widget.
        """
        active_widget = self.details_stack.currentWidget()
        if hasattr(active_widget, '_apply_new_cover'):
            active_widget._apply_new_cover(path)
        self.dataChanged.emit()

    def _find_best_match_index(self, local_track_data, fetched_tracks_list, default_index):
        """
        Attempts to match a local physical track to an Apple Music track result using title similarity and track numbers.
        """
        local_title = local_track_data.get("title", "")
        filename = os.path.splitext(os.path.basename(local_track_data.get("path", "")))[0]
        try:
            local_disc = int(str(local_track_data.get("discnumber", "1")).split("/")[0])
            local_track = int(str(local_track_data.get("tracknumber", "0")).split("/")[0])
        except:
            local_disc, local_track = 1, 0

        if local_title:
            best_score, best_idx = 0.0, -1
            for i, ft in enumerate(fetched_tracks_list):
                score = difflib.SequenceMatcher(None, str(local_title).lower().strip(),
                                                str(ft["title"]).lower().strip()).ratio()
                if score > best_score: best_score, best_idx = score, i
            if best_score > 0.85: return best_idx

        if local_track > 0:
            for i, ft in enumerate(fetched_tracks_list):
                if ft["_raw"].get("discNumber", 1) == local_disc and ft["track_number"] == local_track:
                    return i

        best_score, best_idx = 0.0, -1
        for i, ft in enumerate(fetched_tracks_list):
            score = difflib.SequenceMatcher(None, filename.lower().strip(), str(ft["title"]).lower().strip()).ratio()
            if score > best_score: best_score, best_idx = score, i
        if best_score > 0.6: return best_idx

        if 0 <= default_index < len(fetched_tracks_list):
            return default_index
        return -1

    def has_modifications(self):
        """
        Checks if any track in the mixed batch has unsaved metadata or cover art modifications.

        Returns:
            bool: True if there are pending edits, False otherwise.
        """
        if bool(self.pending_batch_edits): return True

        for widget in self.batch_detail_widgets:
            if widget is not None and widget.has_modifications():
                return True
        return False

    def _show_track_list_context_menu(self, pos):
        """Spawns a context menu directly from a selected track item in the left-hand track panel."""
        item = self.tracks_list_widget.itemAt(pos)
        if not item:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = TranslucentMenu(self)
        icn_folder = QIcon(
            create_svg_icon(
                "assets/control/search_folder.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        action = QAction(icn_folder, translate("Show File Location"), self)
        action.triggered.connect(lambda: self.mw.action_handler.show_in_explorer(path))
        menu.addAction(action)
        menu.exec(self.tracks_list_widget.mapToGlobal(pos))