"""
Vinyller — Card widgets and classes
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

import re
from functools import partial

from PyQt6.QtCore import (
    pyqtSignal, QEvent, QPoint, QRect, QSize, Qt
)
from PyQt6.QtGui import (
    QContextMenuEvent, QMouseEvent, QPainter, QPixmap, QResizeEvent
)
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QStyle, QStyleOption, QVBoxLayout, QWidget, QListWidgetItem
)

from src.ui.custom_base_widgets import set_custom_tooltip
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ClickableWordWrapLabel, ClickableWidget,
    ElidedLabel, FlowLayout, InteractiveCoverWidget, ViewMode, StackedCoverLabel, RoundedCoverLabel,
    HighDpiIconLabel, highlight_text
)
from src.ui.custom_lists import TrackListWidget, CustomRoles
from src.utils import theme
from src.utils.utils import (
    create_svg_icon, format_time
)
from src.utils.utils_translator import translate


class CardWidget(ClickableWidget):
    """
    Universal card widget for displaying artists, albums, folders.
    """
    artistClicked = pyqtSignal(str)
    playClicked = pyqtSignal(object)
    pauseClicked = pyqtSignal()

    def __init__(
        self,
        data,
        view_mode,
        pixmaps,
        title,
        subtitle1=None,
        subtitle2=None,
        subtitle_extra=None,
        is_artist_card=False,
        artist_name_for_nav=None,
        show_play_button=True,
        icon_pixmap=None,
        disc_info_text=None,
        search_query=None,
        is_virtual=False,
        cue_icon_pixmap=None,
        parent=None,
    ):
        """Initializes the card widget with necessary data and visual properties."""
        super().__init__(data, click_mode="single", parent=parent)
        self.pixmaps = pixmaps
        self.view_mode = view_mode
        self.title_text = title
        self.subtitle1_text = subtitle1
        self.subtitle2_text = subtitle2
        self.subtitle_extra_text = subtitle_extra
        self.is_artist_card = is_artist_card
        self.artist_name_for_nav = artist_name_for_nav
        self.show_play_button = show_play_button
        self.icon_pixmap = icon_pixmap
        self.disc_info_text = disc_info_text
        self.is_virtual = is_virtual
        self.cue_icon_pixmap = cue_icon_pixmap
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        card_size_policy = self.sizePolicy()

        if self.view_mode in [ViewMode.TILE_BIG, ViewMode.TILE_SMALL]:
            card_size_policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
            card_size_policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
            self.setMinimumWidth(224)
            self.setMaximumWidth(280)
        elif self.view_mode == ViewMode.GRID:
            card_size_policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
            card_size_policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)

        self.setSizePolicy(card_size_policy)

        self.is_playlist = False
        if isinstance(self.data, str) and self.data.lower().endswith(('.m3u', '.m3u8')):
            self.is_playlist = True
        elif isinstance(self.data, dict) and self.data.get('type') == 'playlist':
            self.is_playlist = True

        if self.is_playlist:
            self.setAcceptDrops(True)

        self._is_current = False
        self._is_playing = False
        self._force_hover = False
        self.type_icon_label = None
        self.disc_info_label = None
        self.cue_icon_label = None

        self.search_query = search_query

        self._setup_ui()

    def paintEvent(self, event):
        """Overridden paint event to apply QSS styles (background, border)."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def _setup_ui(self):
        """Sets up the UI layout and elements for the card based on the current view mode."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)

        content_widget = QWidget()

        if self.view_mode == ViewMode.GRID:
            pixmap_size = 116
        elif self.view_mode == ViewMode.TILE_BIG:
            pixmap_size = 88
        else:
            pixmap_size = 56

        if self.view_mode in [ViewMode.TILE_BIG, ViewMode.TILE_SMALL]:
            size_policy = content_widget.sizePolicy()
            size_policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
            content_widget.setSizePolicy(size_policy)

        outer_layout.addWidget(content_widget)

        cover_container = QWidget()

        is_stacked = len(self.pixmaps) > 1
        num_pixmaps_for_offset = min(len(self.pixmaps), 3)
        extra_height = (num_pixmaps_for_offset - 1) * 8 if is_stacked else 0

        cover_container_height = pixmap_size + extra_height
        cover_container.setFixedSize(pixmap_size, cover_container_height)

        if is_stacked:
            self.cover_label = StackedCoverLabel(self.pixmaps, 3, cover_container)
            self.cover_label.setGeometry(0, 0, pixmap_size, cover_container_height)
        else:
            main_pixmap = self.pixmaps[0] if self.pixmaps else QPixmap()
            self.cover_label = RoundedCoverLabel(main_pixmap, 3, cover_container)
            self.cover_label.setGeometry(0, 0, pixmap_size, pixmap_size)

        main_cover_rect = QRect(0, extra_height, pixmap_size, pixmap_size)

        button_dim = min(48, int(pixmap_size * 0.6))
        icon_dim = int(button_dim * 0.8)

        play_button_x = (main_cover_rect.width() - button_dim) // 2
        play_button_y = (
            main_cover_rect.y() + (main_cover_rect.height() - button_dim) // 2
        )

        self.play_button = None
        if self.show_play_button:
            self.play_button = QPushButton(cover_container)
            self.play_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.play_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.play_button.setIcon(
                create_svg_icon(
                    "assets/control/play_inverted.svg",
                    theme.COLORS["WHITE"],
                    QSize(icon_dim, icon_dim),
                )
            )
            self.play_button.setFixedSize(button_dim, button_dim)
            self.play_button.setIconSize(QSize(icon_dim, icon_dim))
            self.play_button.setStyleSheet(
                "border: none; background-color: transparent;"
            )
            self.play_button.move(play_button_x, play_button_y)
            self.play_button.clicked.connect(self._on_play_clicked)

            self.opacity_effect = QGraphicsOpacityEffect(self.play_button)
            self.play_button.setGraphicsEffect(self.opacity_effect)
            self.opacity_effect.setOpacity(0.7)
            self.play_button.installEventFilter(self)
            self.play_button.hide()

        self.pause_button = QPushButton(cover_container)
        self.pause_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.setIcon(
            create_svg_icon(
                "assets/control/pause_inverted.svg",
                theme.COLORS["WHITE"],
                QSize(icon_dim, icon_dim),
            )
        )
        self.pause_button.setFixedSize(button_dim, button_dim)
        self.pause_button.setIconSize(QSize(icon_dim, icon_dim))
        self.pause_button.setStyleSheet("border: none; background-color: transparent;")
        self.pause_button.move(play_button_x, play_button_y)
        self.pause_button.clicked.connect(self.pauseClicked.emit)

        self.pause_opacity_effect = QGraphicsOpacityEffect(self.pause_button)
        self.pause_button.setGraphicsEffect(self.pause_opacity_effect)
        self.pause_opacity_effect.setOpacity(0.7)
        self.pause_button.installEventFilter(self)
        self.pause_button.hide()

        if (
            self.is_virtual
            and self.cue_icon_pixmap
            and not self.cue_icon_pixmap.isNull()
        ):
            if self.cue_icon_label is None:
                self.cue_icon_label = HighDpiIconLabel(
                    self.cue_icon_pixmap, cover_container
                )
                self.cue_icon_label.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents
                )

            self.cue_icon_label.setPixmap(self.cue_icon_pixmap)
            self.cue_icon_label.setFixedSize(16, 16)

            cue_x = main_cover_rect.right() - self.cue_icon_label.width() - 4
            cue_y = main_cover_rect.top() + 4

            self.cue_icon_label.move(cue_x, cue_y)
            self.cue_icon_label.show()
            self.cue_icon_label.raise_()
        elif self.cue_icon_label:
            self.cue_icon_label.hide()

        if self.disc_info_text:
            if self.disc_info_label is None:
                self.disc_info_label = QLabel(cover_container)
                self.disc_info_label.setProperty(
                    "class", "textSecondary bold textColorWhite"
                )
                self.disc_info_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
                )
            self.disc_info_label.setText(self.disc_info_text)
            self.disc_info_label.adjustSize()
            self.disc_info_label.show()
        elif self.disc_info_label:
            self.disc_info_label.hide()

        if self.icon_pixmap and not self.icon_pixmap.isNull():
            if self.type_icon_label is None:
                self.type_icon_label = HighDpiIconLabel(
                    self.icon_pixmap, cover_container
                )
                self.type_icon_label.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents
                )

            self.type_icon_label.setPixmap(self.icon_pixmap)
            self.type_icon_label.setFixedSize(16, 16)

            icon_x = main_cover_rect.right() - self.type_icon_label.width() - 4
            icon_y = main_cover_rect.bottom() - self.type_icon_label.height() - 4
            self.type_icon_label.move(icon_x, icon_y)
            self.type_icon_label.show()
            self.type_icon_label.raise_()

            if self.disc_info_label:
                disc_x = icon_x - self.disc_info_label.width() - 4
                disc_y = icon_y
                self.disc_info_label.move(disc_x, disc_y)
                self.disc_info_label.raise_()

        elif self.type_icon_label:
            self.type_icon_label.hide()

        if self.play_button:
            self.play_button.raise_()
        self.pause_button.raise_()

        if self.view_mode == ViewMode.GRID:
            main_layout = QVBoxLayout(content_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(4)
            main_layout.addWidget(cover_container)
        else:
            main_layout = QHBoxLayout(content_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(8)
            main_layout.addWidget(cover_container)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        display_title = self.title_text

        if self.view_mode == ViewMode.GRID:
            if len(display_title) > 33:
                display_title = display_title[:30] + "..."
        elif self.view_mode == ViewMode.TILE_BIG:
            if len(display_title) > 48:
                display_title = display_title[:45] + "..."

        if self.search_query:
            if self.view_mode == ViewMode.GRID:
                if len(display_title) > 33:
                    display_title = display_title[:30] + "..."
            elif self.view_mode == ViewMode.TILE_BIG:
                if len(display_title) > 48:
                    display_title = display_title[:45] + "..."
            elif self.view_mode == ViewMode.TILE_SMALL:
                if len(display_title) > 30:
                    display_title = display_title[:27] + "..."

            final_text = highlight_text(
                display_title, self.search_query, theme.COLORS["ACCENT"]
            )
            title_label = QLabel(final_text)
        else:
            final_text = display_title
            if self.view_mode == ViewMode.TILE_SMALL:
                title_label = ElidedLabel(final_text)
            else:
                title_label = QLabel(final_text)

        if isinstance(title_label, QLabel) and not isinstance(title_label, ElidedLabel):
            title_label.setWordWrap(True)

        set_custom_tooltip(
            title_label,
            title = self.title_text,
        )
        title_label.setProperty("class", "textSecondary textColorPrimary")

        title_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
            if self.view_mode == ViewMode.GRID
            else Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        info_layout.addWidget(title_label)

        if self.subtitle1_text:
            self.sub1_label = ElidedLabel(self.subtitle1_text)
            self.sub1_label.setProperty("class", "textTertiary textColorTertiary")
            if self.view_mode == ViewMode.GRID:
                self.sub1_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            info_layout.addWidget(self.sub1_label)

        if self.subtitle2_text:
            self.sub2_label = ElidedLabel(self.subtitle2_text)
            self.sub2_label.setProperty("class", "textTertiary textColorTertiary")
            info_layout.addWidget(self.sub2_label)

        if self.subtitle_extra_text:
            sub_extra_label = ElidedLabel(self.subtitle_extra_text)
            sub_extra_label.setProperty("class", "textTertiary textColorTertiary")
            if self.view_mode == ViewMode.GRID:
                sub_extra_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            info_layout.addWidget(sub_extra_label)

        info_layout.addStretch()
        main_layout.addWidget(info_widget)

        if self.view_mode == ViewMode.GRID:
            content_widget.setFixedWidth(pixmap_size)
            font_metrics = title_label.fontMetrics()
            max_height = font_metrics.height() * 4 + info_layout.spacing() * 2
            info_widget.setMaximumHeight(max_height)
        elif self.view_mode in [ViewMode.TILE_BIG, ViewMode.TILE_SMALL]:
            content_widget.setFixedHeight(cover_container_height)

    def set_subtitle(self, text):
        """Allows dynamic updating of the subtitle (e.g., to reflect track count)."""
        if hasattr(self, "sub1_label") and self.sub1_label:
            self.sub1_label.setText(text)
            self.subtitle1_text = text

    def dragEnterEvent(self, event):
        """Handles drag enter events, checking if data can be accepted."""
        if not self.is_playlist:
            super().dragEnterEvent(event)
            return

        mime = event.mimeData()
        if mime.hasUrls() or mime.hasFormat("application/x-vinyller-data"):
            event.acceptProposedAction()
            self._force_hover = True
            self._update_visuals()
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        """Handles drag leave events and removes hover state formatting."""
        if self.is_playlist:
            self._force_hover = False
            self._update_visuals()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """Handles the dropping of tracks onto the playlist card."""
        if self.is_playlist:
            self._force_hover = False
            self._update_visuals()

        if not self.is_playlist:
            super().dropEvent(event)
            return

        playlist_path = None
        if isinstance(self.data, str):
            playlist_path = self.data
        elif isinstance(self.data, dict):
            playlist_path = self.data.get('data') or self.data.get('path')

        if not playlist_path:
            return

        tracks = self._extract_tracks_from_event(event)

        if tracks:
            mw = self.window()
            if hasattr(mw, 'library_manager'):
                result = mw.library_manager.add_tracks_to_playlist(
                    playlist_path,
                    tracks,
                    mw.data_manager.path_to_track_map
                )

                if result:
                    new_count, total_seconds = result
                    print(f"Added {len(tracks)} tracks. New count: {new_count}, Duration: {total_seconds}s")

                    new_subtitle = translate("{count} tracks", count=new_count)
                    if hasattr(self, 'sub1_label') and self.sub1_label:
                        self.sub1_label.setText(new_subtitle)

                    if hasattr(self, 'sub2_label') and self.sub2_label:
                        time_str = format_time(total_seconds * 1000)
                        self.sub2_label.setText(time_str)

                    mw.playlists_need_refresh = True

            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _extract_tracks_from_event(self, event):
        """Helper method to extract file paths or valid URLs from a drop event."""
        mime = event.mimeData()
        tracks = []

        if mime.hasFormat("application/x-vinyller-data"):
            data = str(mime.data("application/x-vinyller-data"), encoding = "utf-8")
            for line in data.split('\n'):
                if line.startswith("track:"):
                    tracks.append(line.split("track:", 1)[1])

        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path.lower().endswith(('.mp3', '.flac', '.ogg', '.wav', '.m4a')):
                        tracks.append(path)
        return tracks

    def update_playback_state(self, is_current, is_playing):
        """Updates the playback state of the widget."""
        changed = self._is_current != is_current or self._is_playing != is_playing
        if changed:
            self._is_current = is_current
            self._is_playing = is_playing
            self._update_visuals()

    def _update_visuals(self):
        """Updates visibility of buttons based on state and hover."""
        try:
            is_hover = self.underMouse() or self._force_hover
            self.style().polish(self)
            if hasattr(self.cover_label, "setOverlayEnabled"):
                self.cover_label.setOverlayEnabled(is_hover)

            if is_hover:
                if self._is_current and self._is_playing:
                    self.pause_button.show()
                    if self.play_button:
                        self.play_button.hide()
                else:
                    if self.play_button:
                        self.play_button.show()
                    self.pause_button.hide()
            else:
                if self.play_button:
                    self.play_button.hide()
                self.pause_button.hide()
        except RuntimeError:
            pass

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Triggers hover state during context menu request."""
        self._force_hover = True
        self._update_visuals()

        super().contextMenuEvent(event)

        self._force_hover = False
        self._update_visuals()

    def _on_play_clicked(self):
        """Emits the play signal using the current card's data."""
        self.playClicked.emit(self.data)

    def enterEvent(self, event: QEvent):
        """Handles mouse hover enter to toggle visuals."""
        self._update_visuals()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        """Handles mouse hover leave to toggle visuals."""
        self._update_visuals()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        """Event filter to adjust opacity effects on play/pause buttons."""
        effect_to_change = None
        if self.play_button and obj == self.play_button:
            effect_to_change = self.opacity_effect
        elif obj == self.pause_button:
            effect_to_change = self.pause_opacity_effect

        if effect_to_change:
            if event.type() == QMouseEvent.Type.Enter:
                effect_to_change.setOpacity(1.0)
                return True
            elif event.type() == QMouseEvent.Type.Leave:
                effect_to_change.setOpacity(0.7)
                return True
        return super().eventFilter(obj, event)


class CardWidgetLyrics(QFrame):
    """
    Search result card for song lyrics.
    Shows the track and found text snippet.
    """
    playClicked = pyqtSignal(object)
    smartPlay = pyqtSignal(object)
    contextMenuRequested = pyqtSignal(object, QPoint)
    lyricsClicked = pyqtSignal(object)

    def __init__(self, track_data, snippet, pixmap, search_query, parent=None):
        """Initializes the lyrics card with track data, search snippet, and graphics."""
        super().__init__(parent)
        self.track_data = track_data
        self._pixmap = pixmap
        self.setMinimumWidth(360)

        self.setProperty("class", "contentWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 16, 8)
        layout.setSpacing(8)

        cover_data = track_data.get("path", "unknown_track")

        self.cover_widget = InteractiveCoverWidget(cover_data, pixmap, 64, parent=self)
        self.cover_widget.playClicked.connect(lambda: self.playClicked.emit(track_data))

        layout.addWidget(self.cover_widget, alignment=Qt.AlignmentFlag.AlignTop)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title = track_data.get("title", "Unknown Title")
        artist_list = track_data.get("artists", [])
        artist = (
            artist_list[0]
            if artist_list
            else track_data.get("artist", "Unknown Artist")
        )

        title_html = highlight_text(title, search_query, theme.COLORS["ACCENT"])

        lbl_title = QLabel(title_html)
        lbl_title.setProperty("class", "textSecondary bold textColorPrimary")
        lbl_title.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(lbl_title)

        lbl_artist = QLabel(artist)
        lbl_artist.setProperty("class", "textTertiary textColorTertiary")
        info_layout.addWidget(lbl_artist)

        snippet_html = highlight_text(snippet, search_query, theme.COLORS["ACCENT"])

        lbl_snippet = QLabel(f'<i>"{snippet_html}"</i>')
        lbl_snippet.setWordWrap(True)
        lbl_snippet.setTextFormat(Qt.TextFormat.RichText)
        lbl_snippet.setProperty("class", "textSecondary textColorPrimary")
        info_layout.addWidget(lbl_snippet)

        info_layout.addStretch()

        layout.addLayout(info_layout, stretch=1)

        btn_lyrics = QPushButton()
        set_custom_tooltip(
            btn_lyrics,
            title = translate("Show Lyrics"),
        )
        btn_lyrics.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_lyrics.setProperty("class", "btnTool")
        btn_lyrics.setIcon(
            create_svg_icon(
                "assets/control/lyrics.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        btn_lyrics.setIconSize(QSize(24, 24))
        btn_lyrics.setFixedSize(36, 36)
        apply_button_opacity_effect(btn_lyrics)

        btn_lyrics.clicked.connect(lambda: self.lyricsClicked.emit(self.track_data))

        layout.addWidget(btn_lyrics)

        btn_menu = QPushButton()
        set_custom_tooltip(
            btn_menu,
            title = translate("Actions"),
        )
        btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_menu.setProperty("class", "btnTool")
        btn_menu.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        btn_menu.setIconSize(QSize(24, 24))
        btn_menu.setFixedSize(36, 36)
        apply_button_opacity_effect(btn_menu)

        btn_menu.clicked.connect(self._on_menu_button_clicked)

        layout.addWidget(btn_menu)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Emits the context menu request signal mapped to a global position."""
        self.contextMenuRequested.emit(self.track_data, event.globalPos())
        super().contextMenuEvent(event)

    def _on_menu_button_clicked(self):
        """Handles context menu button clicks by calculating widget boundaries."""
        sender = self.sender()
        if sender:
            pos = sender.mapToGlobal(QPoint(0, sender.height()))
            self.contextMenuRequested.emit(self.track_data, pos)

    def leaveEvent(self, event: QEvent):
        """Handles mouse leave events to refresh QSS styling rules."""
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)


class DetailedAlbumCard(QWidget):
    """
    Detailed card view designed for albums, expanding to display cover art,
    album metadata, and a playable track list within a single widget.
    """
    playData = pyqtSignal(object)
    smartPlay = pyqtSignal(object)
    playTrack = pyqtSignal(object, int)
    pausePlayer = pyqtSignal()
    restartTrack = pyqtSignal(object, int)
    lyricsClicked = pyqtSignal(object)
    trackContextMenu = pyqtSignal(object, QPoint, object)
    albumContextMenu = pyqtSignal(object, QPoint)
    artistClicked = pyqtSignal(str)
    genreClicked = pyqtSignal(str)
    composerClicked = pyqtSignal(str)

    def __init__(
        self,
        album_key,
        album_data,
        tracks_to_show,
        main_window,
        icon_pixmap=None,
        disc_info_text=None,
        is_virtual=False,
        cue_icon_pixmap=None,
        parent=None,
        search_query=None,
    ):
        """Initializes the detailed album card with relevant track data and images."""
        super().__init__(parent)
        self.album_key = album_key
        self.album_data = album_data
        self.tracks_to_show = (
            tracks_to_show
            if tracks_to_show is not None
            else album_data.get("tracks", [])
        )
        self.main_window = main_window
        self.search_query = search_query

        self.icon_pixmap = icon_pixmap
        self.disc_info_text = disc_info_text
        self.is_virtual = is_virtual
        self.cue_icon_pixmap = cue_icon_pixmap

        self.pixmap_128 = self.album_data.get("pixmap_128")
        self.pixmap_96 = self.album_data.get("pixmap_96")
        self.track_list_widget = None
        self.art_widget = None
        self._is_narrow = False
        self.detailed_layout = None
        self.info_widget = None
        self.info_layout = None
        self.album_info_layout = None
        self.label_year = None
        self.label_track_count = None
        self.label_duration = None
        self.label_combined_details = None

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the layout, cover images, and populates the inner tracklist view."""
        self.setProperty("class", "backgroundPrimary")
        self.detailed_layout = QHBoxLayout(self)
        self.detailed_layout.setContentsMargins(0, 0, 0, 0)
        self.detailed_layout.setSpacing(24)

        self.info_layout = QVBoxLayout()
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(8)

        self.art_widget = InteractiveCoverWidget(
            self.album_key,
            self.pixmap_128,
            128,
            icon_pixmap=self.icon_pixmap,
            disc_info_text=self.disc_info_text,
            is_virtual=self.is_virtual,
            cue_icon_pixmap=self.cue_icon_pixmap,
            parent=self,
        )
        self.art_widget.playClicked.connect(lambda: self.smartPlay.emit(self.album_key))
        self.art_widget.pauseClicked.connect(self.pausePlayer)
        self.art_widget.contextMenuRequested.connect(self.albumContextMenu.emit)
        self.info_layout.addWidget(self.art_widget)

        self.album_info_layout = QVBoxLayout()
        self.album_info_layout.setContentsMargins(0, 0, 0, 0)
        self.album_info_layout.setSpacing(4)

        album_title = self.album_key[1]

        if self.search_query:
            highlighted_title = highlight_text(
                str(album_title), self.search_query, theme.COLORS["ACCENT"]
            )
            title_label = QLabel(highlighted_title)
        else:
            title_label = QLabel(f"{album_title}")

        title_label.setWordWrap(True)
        title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        title_label.setProperty("class", "textSecondary textColorPrimary")
        self.album_info_layout.addWidget(title_label, 1)

        artist_name = self.album_key[0]

        display_artist = artist_name
        if self.search_query:
            display_artist = highlight_text(
                artist_name, self.search_query, theme.COLORS["ACCENT"]
            )

        artist_label = ClickableWordWrapLabel(artist_name, display_artist, self)
        artist_label.clicked.connect(self.artistClicked.emit)
        artist_label.setWordWrap(True)
        artist_label.setProperty("class", "textSecondary textColorTertiary")
        set_custom_tooltip(
            artist_label,
            title = translate("Go to Album Artist"),
            text = artist_name
        )
        self.album_info_layout.addWidget(artist_label)

        raw_year = self.album_data.get("year", 0)

        year_str = str(raw_year) if raw_year > 0 else translate("Unknown year")

        display_year = year_str
        if self.search_query:
            display_year = highlight_text(
                year_str, self.search_query, theme.COLORS["ACCENT"]
            )

        self.label_year = ClickableWordWrapLabel(year_str, display_year, self)
        self.label_year.setProperty("class", "textSecondary textColorTertiary")

        if raw_year > 0:
            self.label_year.setCursor(Qt.CursorShape.PointingHandCursor)

            set_custom_tooltip(
                self.label_year,
                title = translate("Go to year"),
                text = f"{raw_year}"
            )
            self.label_year.clicked.connect(
                lambda: self.main_window.ui_manager.navigate_to_year(str(raw_year))
            )

        self.album_info_layout.addWidget(self.label_year)

        if genres := self.album_data.get("genre"):
            genres_widget = QWidget()
            genres_layout = FlowLayout(genres_widget)
            genres_layout.setContentsMargins(0, 0, 0, 0)
            genres_layout.setSpacing(4)

            num_genres = len(genres)
            for i, genre in enumerate(genres):
                display_genre = genre
                if self.search_query:
                    display_genre = highlight_text(
                        genre, self.search_query, theme.COLORS["ACCENT"]
                    )

                visual_text = display_genre
                if i < num_genres - 1:
                    visual_text += ","

                genre_label = ClickableWordWrapLabel(genre, visual_text, self)
                genre_label.setProperty("class", "textSecondary textColorTertiary")
                genre_label.setCursor(Qt.CursorShape.PointingHandCursor)
                genre_label.clicked.connect(partial(self.genreClicked.emit, genre))
                genre_label.setWordWrap(True)
                set_custom_tooltip(
                    genre_label,
                    title = translate("Go to genre"),
                    text = genre
                )
                genres_layout.addWidget(genre_label)

            self.album_info_layout.addWidget(genres_widget)

        raw_composer = None
        if self.tracks_to_show:
            raw_composer = self.tracks_to_show[0].get("composer")

        if raw_composer:
            composers_list = [
                c.strip() for c in re.split(r"[;/]", raw_composer) if c.strip()
            ]

            if composers_list:
                composers_widget = QWidget()
                composers_layout = FlowLayout(composers_widget)
                composers_layout.setContentsMargins(0, 0, 0, 0)
                composers_layout.setSpacing(4)

                num_comps = len(composers_list)
                for i, comp_name in enumerate(composers_list):
                    display_comp = comp_name
                    if self.search_query:
                        display_comp = highlight_text(
                            comp_name, self.search_query, theme.COLORS["ACCENT"]
                        )

                    visual_text = display_comp
                    if i < num_comps - 1:
                        visual_text += ","

                    comp_label = ClickableWordWrapLabel(comp_name, visual_text, self)
                    comp_label.setProperty("class", "textSecondary textColorTertiary")
                    comp_label.setCursor(Qt.CursorShape.PointingHandCursor)
                    comp_label.clicked.connect(self.composerClicked.emit)
                    comp_label.setWordWrap(True)
                    set_custom_tooltip(
                        comp_label,
                        title = translate("Go to composer"),
                        text = comp_name
                    )
                    composers_layout.addWidget(comp_label)

                self.album_info_layout.addWidget(composers_widget)

        counter = len(self.tracks_to_show)
        total_duration = format_time(
            sum(t.get("duration", 0) for t in self.tracks_to_show) * 1000
        )
        counter_value = translate("{count} track(s)", count=counter)

        display_counter = counter_value
        display_duration = total_duration

        if self.search_query:
            display_counter = highlight_text(
                counter_value, self.search_query, theme.COLORS["ACCENT"]
            )
            display_duration = highlight_text(
                total_duration, self.search_query, theme.COLORS["ACCENT"]
            )

        self.label_track_count = self._create_detail_label(display_counter)
        self.album_info_layout.addWidget(self.label_track_count)

        self.label_duration = self._create_detail_label(display_duration)
        self.album_info_layout.addWidget(self.label_duration)

        combined_details = f"{display_counter}, {display_duration}"
        self.label_combined_details = self._create_detail_label(combined_details)
        self.album_info_layout.addWidget(self.label_combined_details)
        self.label_combined_details.setVisible(False)

        self.album_info_layout.addStretch()
        self.info_layout.addLayout(self.album_info_layout)

        self.info_widget = QWidget()
        self.info_widget.setLayout(self.info_layout)
        self.info_widget.setFixedWidth(128)
        self.info_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum
        )
        self.detailed_layout.addWidget(self.info_widget, 0, Qt.AlignmentFlag.AlignTop)

        self.track_list_widget = TrackListWidget(
            self.main_window,
            parent_context=self.album_key,
            use_row_for_track_num=False,
            parent=self,
            search_query=self.search_query,
        )
        self.track_list_widget.setProperty("class", "backgroundPrimary")

        has_any_composer = any(
            t.get("composer") and t.get("composer").strip() for t in self.tracks_to_show
        )
        self.track_list_widget.delegate.setShowComposerColumn(has_any_composer)

        sorted_tracks = sorted(
            self.tracks_to_show,
            key=lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0)),
        )

        for i, track in enumerate(sorted_tracks):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, track)
            item.setData(CustomRoles.IsCurrentRole, False)
            item.setData(CustomRoles.IsPlayingRole, False)
            self.track_list_widget.addItem(item)

        self.track_list_widget.delegate.update_column_widths(
            self.track_list_widget.model()
        )

        self.track_list_widget.playTrackClicked.connect(self.playTrack)
        self.track_list_widget.pauseTrackClicked.connect(self.pausePlayer)
        self.track_list_widget.restartTrackClicked.connect(self.restartTrack)
        self.track_list_widget.trackContextMenuRequested.connect(self.trackContextMenu)
        self.track_list_widget.artistClicked.connect(self.artistClicked)
        self.track_list_widget.composerClicked.connect(self.composerClicked)
        self.track_list_widget.lyricsClicked.connect(self.lyricsClicked)

        self.detailed_layout.addWidget(
            self.track_list_widget, 1, Qt.AlignmentFlag.AlignTop
        )

    def _create_detail_label(self, text):
        """Creates a standardized generic label for displaying minor details."""
        label = QLabel(text)
        label.setProperty("class", "textSecondary textColorTertiary")
        return label

    def resizeEvent(self, event: QResizeEvent):
        """Catches resize events to trigger a responsive layout switch for narrow windows."""
        super().resizeEvent(event)
        width = event.size().width()
        is_narrow = width < 640

        if is_narrow != self._is_narrow:
            self._is_narrow = is_narrow
            self._update_layout(is_narrow)

    def _update_layout(self, is_narrow: bool):
        """Adjusts between vertical layout for narrow windows and horizontal for wide screens."""
        if (
            not self.detailed_layout
            or not self.info_widget
            or not self.info_layout
            or not self.art_widget
            or not self.album_info_layout
        ):
            return

        def _resize_art_widget(art_widget, size, pixmap):
            """Resizes the cover art widget and repositions its playback controls."""
            art_widget.setFixedSize(size, size)
            if pixmap:
                art_widget.cover_label.setPixmap(pixmap)
            art_widget.cover_label.setGeometry(0, 0, size, size)
            art_widget.overlay.setGeometry(0, 0, size, size)
            button_dim = 48
            new_pos = (size - button_dim) // 2
            art_widget.play_button.move(new_pos, new_pos)
            art_widget.pause_button.move(new_pos, new_pos)

        if is_narrow:
            self.detailed_layout.setDirection(QVBoxLayout.Direction.TopToBottom)
            self.detailed_layout.setSpacing(16)
            self.info_widget.setMinimumWidth(0)
            self.info_widget.setMaximumWidth(16777215)
            self.info_widget.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )
            self.info_widget.setMaximumHeight(16777215)
            self.info_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            self.info_layout.setContentsMargins(0, 0, 0, 0)
            self.info_layout.setSpacing(8)
            pix_96 = self.pixmap_96 if self.pixmap_96 else self.pixmap_128
            _resize_art_widget(self.art_widget, 96, pix_96)
            self.info_layout.setAlignment(self.art_widget, Qt.AlignmentFlag.AlignTop)
            self.info_layout.setAlignment(
                self.album_info_layout, Qt.AlignmentFlag.AlignTop
            )
            if self.label_track_count:
                self.label_track_count.setVisible(False)
            if self.label_duration:
                self.label_duration.setVisible(False)
            if self.label_combined_details:
                self.label_combined_details.setVisible(True)
            self.detailed_layout.setStretchFactor(self.info_widget, 0)
            self.detailed_layout.setStretchFactor(self.track_list_widget, 1)
        else:
            self.detailed_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            self.detailed_layout.setSpacing(24)
            self.info_widget.setFixedWidth(128)
            self.info_widget.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            self.info_widget.setMaximumHeight(16777215)
            self.info_layout.setDirection(QVBoxLayout.Direction.TopToBottom)
            self.info_layout.setContentsMargins(0, 0, 0, 0)
            self.info_layout.setSpacing(8)
            _resize_art_widget(self.art_widget, 128, self.pixmap_128)
            self.info_layout.setAlignment(self.art_widget, Qt.AlignmentFlag.AlignLeft)
            if self.label_track_count:
                self.label_track_count.setVisible(True)
            if self.label_duration:
                self.label_duration.setVisible(True)
            if self.label_combined_details:
                self.label_combined_details.setVisible(False)
            self.detailed_layout.setStretchFactor(self.info_widget, 0)
            self.detailed_layout.setStretchFactor(self.track_list_widget, 1)

    def get_art_widget(self):
        """Returns the cover art interactive widget instance."""
        return self.art_widget

    def get_track_list_widget(self):
        """Returns the inner tracklist widget tied to this album detailed card."""
        return self.track_list_widget


class DetailedPlaylistCard(QWidget):
    """
    Detailed card view explicitly tailored for playlists, allowing track reordering,
    drag-and-drop mechanics, and statistics tracking.
    """
    playData = pyqtSignal(object)
    smartPlay = pyqtSignal(object)
    playTrack = pyqtSignal(object, int)
    pausePlayer = pyqtSignal()
    restartTrack = pyqtSignal(object, int)
    lyricsClicked = pyqtSignal(object)
    trackContextMenu = pyqtSignal(object, QPoint, object)
    playlistContextMenu = pyqtSignal(object, QPoint)
    artistClicked = pyqtSignal(str)
    composerClicked = pyqtSignal(str)
    playlistReordered = pyqtSignal(str, list)

    playlistTracksInserted = pyqtSignal(str, list, int)

    def __init__(
        self,
        playlist_path,
        playlist_name,
        tracks,
        pixmap,
        main_window,
        show_score=False,
        parent=None,
        search_query=None,
    ):
        """Initializes the detailed playlist card with track and visual metadata."""
        super().__init__(parent)
        self.playlist_path = playlist_path
        self.playlist_name = playlist_name
        self.tracks = tracks
        self.pixmap = pixmap
        self.main_window = main_window
        self.show_score = show_score
        self.search_query = search_query

        self.track_list_widget = None
        self.art_widget = None
        self._is_narrow = False
        self.detailed_layout = None
        self.info_widget = None
        self.info_layout = None
        self.plist_info_layout = None
        self.label_track_count = None
        self.label_duration = None
        self.label_combined_details = None

        self.setAcceptDrops(True)

        self._setup_ui()

    def _setup_ui(self):
        """Builds and wires up the UI hierarchy specific to playlists."""
        self.setProperty("class", "backgroundPrimary")
        self.detailed_layout = QHBoxLayout(self)
        self.detailed_layout.setContentsMargins(0, 0, 0, 0)
        self.detailed_layout.setSpacing(24)

        self.info_layout = QVBoxLayout()
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(8)

        self.art_widget = InteractiveCoverWidget(self.playlist_path, self.pixmap, 128)
        self.art_widget.playClicked.connect(
            lambda: self.smartPlay.emit(self.playlist_path)
        )
        self.art_widget.pauseClicked.connect(self.pausePlayer.emit)
        self.art_widget.contextMenuRequested.connect(self.playlistContextMenu.emit)
        self.info_layout.addWidget(self.art_widget)

        self.plist_info_layout = QVBoxLayout()
        self.plist_info_layout.setContentsMargins(0, 0, 0, 0)
        self.plist_info_layout.setSpacing(4)

        title_label = QLabel(self.playlist_name)
        title_label.setWordWrap(True)
        title_label.setProperty("class", "textSecondary textColorPrimary")
        self.plist_info_layout.addWidget(title_label)

        total_duration = format_time(
            sum(t.get("duration", 0) for t in self.tracks) * 1000
        )
        counter = len(self.tracks)
        counter_value = translate("{count} track(s)", count=counter)

        self.label_track_count = self._create_detail_label(counter_value)
        self.plist_info_layout.addWidget(self.label_track_count)

        self.label_duration = self._create_detail_label(total_duration)
        self.plist_info_layout.addWidget(self.label_duration)

        combined_details = f"{counter_value}, {total_duration}"
        self.label_combined_details = self._create_detail_label(combined_details)
        self.plist_info_layout.addWidget(self.label_combined_details)
        self.label_combined_details.setVisible(False)

        self.plist_info_layout.addStretch()
        self.info_layout.addLayout(self.plist_info_layout)

        self.info_widget = QWidget()
        self.info_widget.setLayout(self.info_layout)
        self.info_widget.setFixedWidth(128)
        self.info_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum
        )
        self.detailed_layout.addWidget(self.info_widget, 0, Qt.AlignmentFlag.AlignTop)

        self.track_list_widget = TrackListWidget(
            self.main_window,
            parent_context = self.playlist_path,
            use_row_for_track_num = True,
            show_score = self.show_score,
            parent = self,
            search_query = self.search_query,
            allow_reorder = True
        )
        self.track_list_widget.setProperty("class", "backgroundPrimary")

        has_any_composer = any(
            t.get("composer") and t.get("composer").strip() for t in self.tracks
        )
        self.track_list_widget.delegate.setShowComposerColumn(has_any_composer)

        for i, track in enumerate(self.tracks):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, track)
            item.setData(CustomRoles.IsCurrentRole, False)
            item.setData(CustomRoles.IsPlayingRole, False)
            self.track_list_widget.addItem(item)

        self.track_list_widget.delegate.update_column_widths(
            self.track_list_widget.model()
        )

        self.track_list_widget.playTrackClicked.connect(self.playTrack)
        self.track_list_widget.pauseTrackClicked.connect(self.pausePlayer)
        self.track_list_widget.restartTrackClicked.connect(self.restartTrack)
        self.track_list_widget.trackContextMenuRequested.connect(self.trackContextMenu)
        self.track_list_widget.orderChanged.connect(self._on_list_reordered)
        self.track_list_widget.artistClicked.connect(self.artistClicked)
        self.track_list_widget.composerClicked.connect(self.composerClicked)
        self.track_list_widget.lyricsClicked.connect(self.lyricsClicked)
        self.track_list_widget.tracksDropped.connect(self._on_tracks_dropped_at_index)

        self.detailed_layout.addWidget(
            self.track_list_widget, 1, Qt.AlignmentFlag.AlignTop
        )

    def _on_tracks_dropped_at_index(self, track_paths, index):
        """Forwards the dropped tracks event to the LibraryManager via UiComponents."""
        self.playlistTracksInserted.emit(self.playlist_path, track_paths, index)

    def dragEnterEvent(self, event):
        """Handles drag enter to copy local items or accept external drop paths."""
        if event.source() == self:
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-vinyller-data"):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        """Extracts dropping paths and appends them to the playlist configuration."""
        if not getattr(self, 'playlist_path', None):
            return

        tracks = []
        mime = event.mimeData()

        if mime.hasFormat("application/x-vinyller-data"):
            data = str(mime.data("application/x-vinyller-data"), encoding = "utf-8")
            for line in data.split('\n'):
                if line.startswith("track:"):
                    tracks.append(line.split("track:", 1)[1])

        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path.lower().endswith(('.mp3', '.flac', '.ogg', '.wav', '.m4a')):
                        tracks.append(path)

        if tracks:
            mw = self.window()
            if hasattr(mw, 'library_manager'):
                result = mw.library_manager.add_tracks_to_playlist(
                    self.playlist_path,
                    tracks,
                    mw.data_manager.path_to_track_map
                )

                if result:
                    new_count, total_seconds = result
                    print(f"Added {len(tracks)} tracks via Header Card")

                    if hasattr(mw, 'ui_manager'):
                        mw.ui_manager.show_playlist_tracks(self.playlist_path)

                    if hasattr(self, 'label_track_count') and self.label_track_count:
                        self.label_track_count.setText(translate("{count} track(s)", count = new_count))

                    if hasattr(self, 'label_duration') and self.label_duration:
                        self.label_duration.setText(format_time(total_seconds * 1000))

                    mw.playlists_need_refresh = True

            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _on_list_reordered(self):
        """Reconstruct track list from UI order and emit save signal."""
        new_tracks = []
        for i in range(self.track_list_widget.count()):
            item = self.track_list_widget.item(i)
            track_data = item.data(Qt.ItemDataRole.UserRole)
            if track_data:
                new_tracks.append(track_data)

        self.tracks = new_tracks
        self.playlistReordered.emit(self.playlist_path, new_tracks)

    def _create_detail_label(self, text):
        """Creates a standardized generic label for displaying minor details."""
        label = QLabel(text)
        label.setProperty("class", "textSecondary textColorTertiary")
        return label

    def resizeEvent(self, event: QResizeEvent):
        """Monitors resizing to pivot the internal layout upon hitting standard breakpoint metrics."""
        super().resizeEvent(event)
        width = event.size().width()
        is_narrow = width < 640

        if is_narrow != self._is_narrow:
            self._is_narrow = is_narrow
            self._update_layout(is_narrow)

    def _update_layout(self, is_narrow: bool):
        """Reroutes info constraints to properly show either wide or narrow widget states."""
        if (
            not self.detailed_layout
            or not self.info_widget
            or not self.info_layout
            or not self.art_widget
            or not self.plist_info_layout
        ):
            return

        def _resize_art_widget(art_widget, size, pixmap):
            """Resizes the cover art widget and repositions its playback controls."""
            art_widget.setFixedSize(size, size)
            if pixmap:
                art_widget.cover_label.setPixmap(pixmap)
            art_widget.cover_label.setGeometry(0, 0, size, size)
            art_widget.overlay.setGeometry(0, 0, size, size)
            button_dim = 48
            new_pos = (size - button_dim) // 2
            art_widget.play_button.move(new_pos, new_pos)
            art_widget.pause_button.move(new_pos, new_pos)

        if is_narrow:
            self.detailed_layout.setDirection(QVBoxLayout.Direction.TopToBottom)
            self.detailed_layout.setSpacing(16)
            self.info_widget.setMinimumWidth(0)
            self.info_widget.setMaximumWidth(16777215)
            self.info_widget.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )
            self.info_widget.setMaximumHeight(16777215)
            self.info_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            self.info_layout.setContentsMargins(0, 0, 0, 0)
            _resize_art_widget(self.art_widget, 96, None)
            self.info_layout.setAlignment(self.art_widget, Qt.AlignmentFlag.AlignTop)
            if self.label_track_count:
                self.label_track_count.setVisible(True)
            if self.label_duration:
                self.label_duration.setVisible(True)
            if self.label_combined_details:
                self.label_combined_details.setVisible(False)
            self.detailed_layout.setStretchFactor(self.info_widget, 0)
            self.detailed_layout.setStretchFactor(self.track_list_widget, 1)
        else:
            self.detailed_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            self.detailed_layout.setSpacing(24)
            self.info_widget.setFixedWidth(128)
            self.info_widget.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            self.info_widget.setMaximumHeight(16777215)
            self.info_layout.setDirection(QVBoxLayout.Direction.TopToBottom)
            self.info_layout.setContentsMargins(0, 0, 0, 0)
            _resize_art_widget(self.art_widget, 128, self.pixmap)
            self.info_layout.setAlignment(self.art_widget, Qt.AlignmentFlag.AlignLeft)
            self.info_layout.setAlignment(
                self.plist_info_layout, Qt.AlignmentFlag.AlignLeft
            )
            self.detailed_layout.setStretchFactor(self.info_widget, 0)
            self.detailed_layout.setStretchFactor(self.track_list_widget, 1)

    def get_track_list_widget(self):
        """Returns the inner track list mapped to the playlist metadata."""
        return self.track_list_widget

    def get_art_widget(self):
        """Returns the cover art interactive widget tied to this view."""
        return self.art_widget