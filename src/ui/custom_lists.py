"""
Vinyller — Custom list widgets and delegates
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
from collections import defaultdict
from functools import partial

from PyQt6.QtCore import (
    pyqtSignal, QByteArray, QEvent, QMimeData, QModelIndex, QPoint, QRect, QRectF, QSize, Qt,
    QTimer, QUrl
)
from PyQt6.QtGui import (
    QAction, QColor, QFont, QFontMetrics, QIcon,
    QMouseEvent, QPainter, QPainterPath, QPen
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHBoxLayout, QLabel, QListWidgetItem, QPushButton,
    QStyle, QStyleOptionViewItem,
    QStyledItemDelegate, QWidget, QToolTip, QSizePolicy
)

from src.ui.custom_base_widgets import (
    StyledListWidget, TranslucentMenu, set_custom_tooltip, GlobalTooltipFilter
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ElidedLabel
)
from src.utils import theme
from src.utils.constants import ArtistSource
from src.utils.utils import (
    create_svg_icon, format_time
)
from src.utils.utils_translator import translate


class CustomRoles:
    """
    Defines custom item data roles used in the models.
    """
    IsCurrentRole = Qt.ItemDataRole.UserRole + 1
    IsPlayingRole = Qt.ItemDataRole.UserRole + 2
    IsPressedRole = Qt.ItemDataRole.UserRole + 3


class TrackListDelegate(QStyledItemDelegate):
    """
    Custom item delegate for rendering tracks in a QListWidget.
    Handles the custom painting of track details, including play/pause icons,
    titles, artists, composers, duration, and score.
    """
    def __init__(self, main_window, show_score=False, parent=None):
        """
        Initialize the TrackListDelegate.

        Args:
            main_window: Reference to the main application window.
            show_score (bool): Whether to display the track's rating/score column.
            parent (QWidget, optional): Parent widget.
        """
        super().__init__(parent)
        self.main_window = main_window
        self.show_score = show_score
        self.hovered_index = QModelIndex()
        self.mouse_pos = None
        self.search_query = None
        self.now_playing_icons = [
            create_svg_icon(
                f"assets/animation/track/now_playing_{i}.svg",
                theme.COLORS["ACCENT"],
                QSize(16, 16),
            )
            for i in range(1, 9)
        ]
        self.current_frame = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(120)
        self.animation_timer.timeout.connect(self._update_animation_frame)

        self.use_row_for_track_num = False
        self.show_composer_column = False

        self._icon_rects = defaultdict(QRect)
        self._artist_rects = defaultdict(
            lambda: {
                "title": QRect(),
                "artist": QRect(),
                "composer": QRect(),
                "lyrics": QRect(),
                "duration": QRect(),
                "duration_text": "",
                "actions": QRect(),
                "score": QRect(),
                "score_text": "",
            }
        )
        self.max_duration_width = 0
        self.max_score_width = 0

    def update_column_widths(self, model):
        """
        Calculates and caches the maximum widths needed for the duration
        and score columns based on the current model data.

        Args:
            model: The data model containing the tracks.
        """
        font = self.parent().font() if self.parent() else QFont()
        fm = QFontMetrics(font)
        max_d, max_s = 0, 0

        for i in range(model.rowCount()):
            track_data = model.index(i, 0).data(Qt.ItemDataRole.UserRole)
            if not track_data:
                continue

            d_text = format_time(track_data.get("duration", 0) * 1000)
            max_d = max(max_d, fm.horizontalAdvance(d_text))

            if self.show_score:
                s_text = translate(
                    "Rating: {count}", count=track_data.get("play_count", 0)
                )
                max_s = max(max_s, fm.horizontalAdvance(s_text))

        self.max_duration_width = max_d + 12
        self.max_score_width = max_s + 12
        self._artist_rects.clear()

    def setSearchQuery(self, query):
        """
        Set the current search query to highlight matching text in the delegate.

        Args:
            query (str): The search term to highlight.
        """
        self.search_query = query

    def helpEvent(self, event, view, option, index):
        """
        Handle tooltip events for track items, showing metadata on text elision
        or functional descriptions for interactive buttons and artist links.
        """
        if event.type() == QEvent.Type.ToolTip:
            rects = self._get_rects(option, index)
            title_rect = rects[1]
            artist_rect = rects[2]
            composer_rect = rects[3]
            lyrics_rect = rects[4]
            actions_rect = rects[7]

            pos = event.pos()
            track_data = index.data(Qt.ItemDataRole.UserRole)

            if not track_data:
                return super().helpEvent(event, view, option, index)

            if title_rect.contains(pos):
                title_text = track_data.get("title", "N/A")
                is_current = index.data(CustomRoles.IsCurrentRole)

                title_font = QFont(option.font)
                title_font.setBold(is_current)
                fm = QFontMetrics(title_font)

                if fm.horizontalAdvance(title_text) > title_rect.width():
                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": title_text},
                        rect = title_rect
                    )
                    return True

            if not artist_rect.isEmpty():
                artist_text = ", ".join(track_data.get("artists", ["..."]))

                font_metrics = QFontMetrics(option.font)
                text_width = font_metrics.horizontalAdvance(artist_text)
                precise_width = min(text_width, artist_rect.width())

                precise_rect = QRect(
                    artist_rect.left(),
                    artist_rect.top(),
                    precise_width,
                    artist_rect.height()
                )

                if precise_rect.contains(pos):
                    mw = self.main_window
                    if hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
                        target = track_data.get("album_artist") or track_data.get("artist") or "Unknown"
                        content = f"{translate('Go to Album Artist')}: {target}"
                    else:
                        content = translate("Go to artist")

                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": content},
                        rect = precise_rect
                    )
                    return True

            if not composer_rect.isEmpty():
                raw_comp = track_data.get("composer", "").strip()
                comps = [c.strip() for c in re.split(r"[;/]", raw_comp) if c.strip()]
                composer_text = ", ".join(comps)

                font_metrics = QFontMetrics(option.font)
                text_width = font_metrics.horizontalAdvance(composer_text)
                precise_width = min(text_width, composer_rect.width())

                precise_rect = QRect(
                    composer_rect.left(),
                    composer_rect.top(),
                    precise_width,
                    composer_rect.height()
                )

                if precise_rect.contains(pos):
                    content = translate("Go to composer")

                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": content},
                        rect = precise_rect
                    )
                    return True

            if not lyrics_rect.isEmpty() and lyrics_rect.contains(pos):
                if track_data.get("lyrics"):
                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": translate("Lyrics")},
                        rect = lyrics_rect
                    )
                    return True

            if not actions_rect.isEmpty() and actions_rect.contains(pos):
                GlobalTooltipFilter.show_rect_tooltip(
                    view,
                    data = {"title": translate("Actions")},
                    rect = actions_rect
                )
                return True

        return super().helpEvent(event, view, option, index)

    def _update_animation_frame(self):
        """
        Update the current animation frame for the 'now playing' icon indicator
        and schedule a viewport repaint.
        """
        self.current_frame = (self.current_frame + 1) % len(self.now_playing_icons)
        if self.parent() and hasattr(self.parent(), "viewport"):
            self.parent().viewport().update()

    def setUseRowForTrackNumber(self, use_row: bool):
        """
        Set whether to use the list row index instead of the track's metadata
        number for displaying the track number.
        """
        self.use_row_for_track_num = use_row

    def setHoveredIndex(self, index: QModelIndex, view: QWidget):
        """
        Set the currently hovered item index to apply hover styling.

        Args:
            index (QModelIndex): The index being hovered.
            view (QWidget): The view displaying the items.
        """
        if self.hovered_index != index:
            old_index = self.hovered_index
            self.hovered_index = index
            if view and view.viewport():
                if old_index.isValid():
                    view.viewport().update(view.visualRect(old_index))
                if index.isValid():
                    view.viewport().update(view.visualRect(index))

    def setMousePosition(self, pos: QPoint):
        """
        Update the cached mouse position to handle local hover effects
        (like highlighting specific text or buttons within an item).
        """
        if self.mouse_pos != pos:
            self.mouse_pos = pos
            parent_view = self.parent()
            if parent_view and hasattr(parent_view, "viewport"):
                parent_view.viewport().update()

    def setShowComposerColumn(self, show: bool):
        """
        Toggle the visibility of the composer column in the list.
        """
        if self.show_composer_column != show:
            self.show_composer_column = show
            self._artist_rects.clear()

    def _get_rects(self, option: QStyleOptionViewItem, index: QModelIndex):
        """
        Calculate and cache the geometries (QRects) for all the drawn elements
        (icon, title, artist, duration, etc.) for a specific item.
        """
        score_rect = QRect()
        score_text = ""

        if option.rect.width() <= 0:
            return (
                QRect(), QRect(), QRect(), QRect(), QRect(),
                QRect(), "", QRect(), score_rect, score_text,
            )

        track_data = index.data(Qt.ItemDataRole.UserRole)
        if not track_data:
            return (
                QRect(), QRect(), QRect(), QRect(), QRect(),
                QRect(), "", QRect(), score_rect, score_text,
            )

        cache_key = (track_data.get("path"), option.rect.y(), option.rect.width())

        if (
            cache_key in self._icon_rects
            and "composer" in self._artist_rects[cache_key]
        ):
            cached_artist = self._artist_rects[cache_key]
            return (
                self._icon_rects[cache_key],
                cached_artist.get("title"),
                cached_artist.get("artist"),
                cached_artist.get("composer"),
                cached_artist.get("lyrics"),
                cached_artist.get("duration"),
                cached_artist.get("duration_text"),
                cached_artist.get("actions"),
                cached_artist.get("score"),
                cached_artist.get("score_text"),
            )

        base_font = option.font

        left_margin = 8
        icon_size = 16

        icon_top = option.rect.center().y() - icon_size // 2
        icon_rect = QRect(left_margin, icon_top, icon_size + 8, icon_size)
        start_x = icon_rect.right() + 8

        duration_text = format_time(track_data.get("duration", 0) * 1000)
        duration_width = self.max_duration_width if self.max_duration_width > 0 else 50

        duration_rect = QRect(
            option.rect.right() - 12 - duration_width,
            option.rect.top(),
            duration_width,
            option.rect.height(),
        )

        actions_icon_size = 16
        actions_rect = QRect(
            duration_rect.center().x() + 6 - actions_icon_size // 2,
            duration_rect.center().y() - actions_icon_size // 2,
            actions_icon_size,
            actions_icon_size,
        )
        end_x = duration_rect.left() - 8

        if self.show_score:
            play_count = track_data.get("play_count", 0)
            if play_count > 0:
                score_text = translate("Rating: {count}", count=play_count)

            score_width = self.max_score_width if self.max_score_width > 0 else 70
            score_rect = QRect(
                duration_rect.left() - 16 - score_width,
                option.rect.top(),
                score_width,
                option.rect.height(),
            )
            end_x = score_rect.left() - 16

        total_available_width = end_x - start_x
        spacing_between = 8

        lyrics_icon_width = 16
        lyrics_icon_padding = 8
        total_available_width -= lyrics_icon_width + lyrics_icon_padding
        has_lyrics = bool(track_data.get("lyrics"))

        composer_name = track_data.get("composer", "").strip()
        has_composer = bool(composer_name)

        if self.show_composer_column:
            available_for_text = total_available_width - (2 * spacing_between)

            title_width = int(available_for_text * 0.40)
            artist_width = int(available_for_text * 0.30)
            composer_width = available_for_text - title_width - artist_width

            title_rect = QRect(
                start_x, option.rect.top(), title_width, option.rect.height()
            )
            artist_rect = QRect(
                title_rect.right() + spacing_between,
                option.rect.top(),
                artist_width,
                option.rect.height(),
            )
            composer_rect = QRect(
                artist_rect.right() + spacing_between,
                option.rect.top(),
                composer_width,
                option.rect.height(),
            )

            lyrics_anchor_rect = composer_rect
        else:
            available_for_text = total_available_width - spacing_between
            title_width = available_for_text // 2
            artist_width = available_for_text - title_width

            title_rect = QRect(
                start_x, option.rect.top(), title_width, option.rect.height()
            )
            artist_rect = QRect(
                title_rect.right() + spacing_between,
                option.rect.top(),
                artist_width,
                option.rect.height(),
            )
            composer_rect = QRect()

            lyrics_anchor_rect = artist_rect

        lyrics_rect = QRect()
        if has_lyrics:
            lyrics_rect = QRect(
                lyrics_anchor_rect.right() + lyrics_icon_padding,
                option.rect.center().y() - lyrics_icon_width // 2,
                lyrics_icon_width,
                lyrics_icon_width,
            )

        self._icon_rects[cache_key] = icon_rect
        self._artist_rects[cache_key] = {
            "title": title_rect,
            "artist": artist_rect,
            "composer": composer_rect,
            "lyrics": lyrics_rect,
            "duration": duration_rect,
            "duration_text": duration_text,
            "actions": actions_rect,
            "score": score_rect,
            "score_text": score_text,
        }

        return (
            icon_rect,
            title_rect,
            artist_rect,
            composer_rect,
            lyrics_rect,
            duration_rect,
            duration_text,
            actions_rect,
            score_rect,
            score_text,
        )

    def _draw_highlighted_text(
        self, painter, rect, text, font, default_color, align_flags
    ):
        """
        Draw elided text, highlighting the portion that matches the current search query.
        """
        painter.setFont(font)
        fm = QFontMetrics(font)

        safe_width = max(0, rect.width() - 4)
        elided_text = fm.elidedText(text, Qt.TextElideMode.ElideRight, safe_width)

        query = self.search_query
        if not query:
            painter.setPen(default_color)
            painter.drawText(rect, align_flags, elided_text)
            return

        idx = elided_text.lower().find(query.lower())

        if idx < 0:
            painter.setPen(default_color)
            painter.drawText(rect, align_flags, elided_text)
            return

        prefix = elided_text[:idx]
        match = elided_text[idx : idx + len(query)]
        suffix = elided_text[idx + len(query) :]

        x = rect.left()

        if prefix:
            painter.setPen(default_color)
            w = fm.horizontalAdvance(prefix)
            painter.drawText(
                QRect(x, rect.top(), w, rect.height()), align_flags, prefix
            )
            x += w

        match_w = fm.horizontalAdvance(match)
        bg_h = fm.height()
        bg_rect = QRect(x, rect.top() + (rect.height() - bg_h) // 2, match_w, bg_h)

        painter.fillRect(bg_rect, QColor(theme.COLORS["ACCENT"]))

        painter.setPen(QColor(theme.COLORS["WHITE"]))
        painter.drawText(
            QRect(x, rect.top(), match_w, rect.height()), align_flags, match
        )
        x += match_w

        if suffix:
            painter.setPen(default_color)
            rem_w = rect.right() - x + 1
            if rem_w > 0:
                painter.drawText(
                    QRect(x, rect.top(), rem_w, rect.height()), align_flags, suffix
                )

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ):
        """
        Custom paint routine for the track item list. Handles hover states,
        current playback state visuals, and custom layout of fields.
        """
        painter.save()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        is_current = index.data(CustomRoles.IsCurrentRole)
        is_playing = index.data(CustomRoles.IsPlayingRole)
        is_hovered = index == self.hovered_index
        is_pressed = index.data(CustomRoles.IsPressedRole)

        if is_hovered or is_pressed:
            painter.fillRect(option.rect, QColor(theme.COLORS["TRACK_HOVER_BG"]))
        if is_current:
            opt.state |= QStyle.StateFlag.State_Selected

        track_data = index.data(Qt.ItemDataRole.UserRole)
        if self.use_row_for_track_num:
            track_num_str = f"{index.row() + 1:02d}"
        else:
            track_num_str = f"{track_data.get('tracknumber', index.row() + 1):02d}"

        rects = self._get_rects(opt, index)
        (
            icon_rect,
            title_rect,
            artist_rect,
            composer_rect,
            lyrics_rect,
            duration_rect,
            duration_text,
            actions_rect,
            score_rect,
            score_text,
        ) = rects

        model = index.model()
        if model and index.row() < model.rowCount() - 1:
            painter.save()
            pen = QPen(QColor(0, 0, 0, int(255 * 0.08)))
            pen.setWidth(1)
            painter.setPen(pen)
            y = option.rect.bottom()
            x1 = option.rect.left()
            x2 = option.rect.right()
            painter.drawLine(x1, y, x2, y)
            painter.restore()

        is_mouse_over_icon = self.mouse_pos and icon_rect.contains(self.mouse_pos)
        icon_to_draw = None
        opacity = 1.0
        if is_current:
            if is_playing:
                if is_hovered:
                    icon_color = (
                        theme.COLORS["ACCENT"]
                        if is_mouse_over_icon
                        else theme.COLORS["PRIMARY"]
                    )
                    icon_to_draw = create_svg_icon(
                        "assets/control/pause.svg", icon_color, QSize(16, 16)
                    )
                    opacity = 1.0 if is_mouse_over_icon else 0.7
                else:
                    icon_to_draw = self.now_playing_icons[self.current_frame]
            else:
                icon_color = (
                    theme.COLORS["ACCENT"]
                    if is_mouse_over_icon
                    else theme.COLORS["PRIMARY"]
                )
                icon_to_draw = create_svg_icon(
                    "assets/control/play.svg", icon_color, QSize(16, 16)
                )
                opacity = 1.0 if is_mouse_over_icon else 0.7
        elif is_hovered:
            icon_color = (
                theme.COLORS["ACCENT"]
                if is_mouse_over_icon
                else theme.COLORS["PRIMARY"]
            )
            icon_to_draw = create_svg_icon(
                "assets/control/play.svg", icon_color, QSize(16, 16)
            )
            opacity = 1.0 if is_mouse_over_icon else 0.7

        if icon_to_draw:
            painter.save()
            if not (is_current and is_playing and not is_hovered):
                painter.setOpacity(opacity)
            icon_to_draw.paint(painter, icon_rect)
            painter.restore()
        else:
            painter.setPen(QColor(theme.COLORS["TERTIARY"]))
            number_rect = QRect(
                icon_rect.left(),
                option.rect.top(),
                icon_rect.width(),
                option.rect.height(),
            )
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, track_num_str)

        if is_hovered or is_pressed:
            is_mouse_over_actions = self.mouse_pos and duration_rect.contains(
                self.mouse_pos
            )
            icon_color = (
                theme.COLORS["ACCENT"]
                if is_mouse_over_actions
                else theme.COLORS["PRIMARY"]
            )
            actions_icon_to_draw = create_svg_icon(
                "assets/control/more_horiz.svg", icon_color, QSize(16, 16)
            )
            opacity = 1.0 if is_mouse_over_actions or is_pressed else 0.7
            painter.save()
            painter.setOpacity(opacity)
            actions_icon_to_draw.paint(painter, actions_rect)
            painter.restore()
        else:
            painter.setPen(QColor(theme.COLORS["PRIMARY"]))
            painter.drawText(
                duration_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                duration_text,
            )

        if self.show_score and score_rect and not score_rect.isEmpty() and score_text:
            painter.setPen(QColor(theme.COLORS["TERTIARY"]))
            painter.drawText(
                score_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                score_text,
            )

        artist_text = ", ".join(track_data.get("artists", ["..."]))
        is_mouse_over_artist = False
        if not artist_rect.isEmpty():
            font_metrics = QFontMetrics(option.font)
            actual_text_width = font_metrics.horizontalAdvance(artist_text)
            precise_artist_width = min(actual_text_width, artist_rect.width())
            precise_artist_rect = QRect(
                artist_rect.left(),
                artist_rect.top(),
                precise_artist_width,
                artist_rect.height(),
            )
            is_mouse_over_artist = self.mouse_pos and precise_artist_rect.contains(
                self.mouse_pos
            )

        artist_color = (
            QColor(theme.COLORS["ACCENT"])
            if is_mouse_over_artist
            else QColor(theme.COLORS["TERTIARY"])
        )
        self._draw_highlighted_text(
            painter,
            artist_rect,
            artist_text,
            option.font,
            artist_color,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        if not composer_rect.isEmpty():
            raw_comp = track_data.get("composer", "").strip()
            comps = [c.strip() for c in re.split(r"[;/]", raw_comp) if c.strip()]
            composer_text = ", ".join(comps)

            is_mouse_over_composer = False
            font_metrics = QFontMetrics(option.font)
            actual_comp_width = font_metrics.horizontalAdvance(composer_text)
            precise_comp_width = min(actual_comp_width, composer_rect.width())
            precise_comp_rect = QRect(
                composer_rect.left(),
                composer_rect.top(),
                precise_comp_width,
                composer_rect.height(),
            )
            is_mouse_over_composer = self.mouse_pos and precise_comp_rect.contains(
                self.mouse_pos
            )

            comp_color = (
                QColor(theme.COLORS["ACCENT"])
                if is_mouse_over_composer
                else QColor(theme.COLORS["TERTIARY"])
            )

            self._draw_highlighted_text(
                painter,
                composer_rect,
                composer_text,
                option.font,
                comp_color,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )

        if not lyrics_rect.isEmpty():
            painter.save()
            is_mouse_over_lyrics = self.mouse_pos and lyrics_rect.contains(
                self.mouse_pos
            )
            icon_color = (
                theme.COLORS["ACCENT"]
                if is_mouse_over_lyrics
                else theme.COLORS["PRIMARY"]
            )
            lyrics_icon_to_draw = create_svg_icon(
                "assets/control/lyrics.svg", icon_color, QSize(16, 16)
            )
            opacity = 1.0 if is_mouse_over_lyrics else 0.25
            painter.setOpacity(opacity)
            lyrics_icon_to_draw.paint(painter, lyrics_rect)
            painter.restore()

        title_font = QFont(option.font)
        title_font.setBold(is_current)
        title_color = QColor(theme.COLORS["PRIMARY"])

        self._draw_highlighted_text(
            painter,
            title_rect,
            track_data.get("title", "N/A"),
            title_font,
            title_color,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """
        Return the optimal size hint for a track list item.
        """
        return QSize(200, 32)


class TrackListWidget(StyledListWidget):
    """
    Custom QListWidget designed specifically for displaying lists of tracks.
    Implements drag-and-drop, custom context menus, double-click playback,
    and granular click handling within the item bounds.
    """
    playTrackClicked = pyqtSignal(object, int)
    pauseTrackClicked = pyqtSignal()
    restartTrackClicked = pyqtSignal(object, int)
    artistClicked = pyqtSignal(str)
    composerClicked = pyqtSignal(str)
    lyricsClicked = pyqtSignal(object)
    trackContextMenuRequested = pyqtSignal(object, QPoint, object)

    orderChanged = pyqtSignal()
    tracksDropped = pyqtSignal(list, int)

    def __init__(
        self,
        main_window,
        parent_context,
        use_row_for_track_num=False,
        show_score=False,
        search_query=None,
        parent=None,
        allow_reorder = False,
    ):
        """
        Initialize the TrackListWidget.

        Args:
            main_window: Main application window reference.
            parent_context: Context string/object describing where the widget is located.
            use_row_for_track_num (bool): Use visual row index instead of track metadata number.
            show_score (bool): Display track scores.
            search_query (str): Optional search query to highlight.
            parent (QWidget): Parent widget.
            allow_reorder (bool): Enable dragging to reorder tracks.
        """
        super().__init__(parent)
        self.parent_context = parent_context
        self.main_window = main_window
        self.delegate = TrackListDelegate(
            main_window, show_score=show_score, parent=self
        )
        self.delegate.setUseRowForTrackNumber(use_row_for_track_num)

        if search_query:
            self.delegate.setSearchQuery(search_query)

        self.setItemDelegate(self.delegate)
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(120)
        self.animation_timer.timeout.connect(self.delegate._update_animation_frame)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.drop_indicator_rect = QRect()

        if allow_reorder:
            self.setAcceptDrops(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            self.setDefaultDropAction(Qt.DropAction.MoveAction)
        else:
            self.setAcceptDrops(False)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemDoubleClicked.connect(self._on_double_clicked)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(10)
        self._resize_timer.timeout.connect(self._adjust_height_to_contents)
        self.model().rowsInserted.connect(self._schedule_resize)
        self.model().rowsRemoved.connect(self._schedule_resize)
        self.setProperty("class", "backgroundPrimary")

        self._drag_start_pos = None

    def dragEnterEvent(self, event):
        """Handle drag enter event, validating custom MIME data."""
        if event.source() == self:
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-vinyller-data"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event, clearing the drop indicator."""
        super().dragLeaveEvent(event)
        self.drop_indicator_rect = QRect()
        self.viewport().update()

    def dragMoveEvent(self, event):
        """Handle drag move event to visually indicate the drop target."""
        is_internal = (event.source() == self)
        has_data = event.mimeData().hasFormat("application/x-vinyller-data")

        if not is_internal and not has_data:
            event.ignore()
            return

        event.acceptProposedAction()

        pos = event.position().toPoint()
        index = self.indexAt(pos)

        if index.isValid():
            rect = self.visualRect(index)
            if pos.y() < rect.center().y():
                y = rect.top()
                self._drop_target_row = index.row()
            else:
                y = rect.bottom()
                self._drop_target_row = index.row() + 1

            self.drop_indicator_rect = QRect(rect.left(), y - 1, rect.width(), 2)
        else:
            if self.count() > 0:
                last_rect = self.visualRect(self.model().index(self.count() - 1, 0))
                if pos.y() > last_rect.bottom():
                    y = last_rect.bottom()
                    self.drop_indicator_rect = QRect(last_rect.left(), y, last_rect.width(), 2)
                    self._drop_target_row = self.count()
            else:
                self.drop_indicator_rect = QRect(0, 0, self.viewport().width(), 2)
                self._drop_target_row = 0

        self.viewport().update()

    def dropEvent(self, event):
        """Handle drop event, processing dropped items internally or from external lists."""
        self.drop_indicator_rect = QRect()
        self.viewport().update()

        if event.source() == self:
            super().dropEvent(event)
            self.orderChanged.emit()
            event.accept()

        elif event.mimeData().hasFormat("application/x-vinyller-data"):
            tracks = []
            data = str(event.mimeData().data("application/x-vinyller-data"), encoding = "utf-8")
            for line in data.split('\n'):
                if line.startswith("track:"):
                    tracks.append(line.split("track:", 1)[1])

            target_row = getattr(self, '_drop_target_row', self.count())

            if tracks:
                self.tracksDropped.emit(tracks, target_row)

            event.accept()
        else:
            event.ignore()

    def paintEvent(self, event):
        """Custom paint event to draw the drop indicator line."""
        super().paintEvent(event)

        if not self.drop_indicator_rect.isNull():
            painter = QPainter(self.viewport())
            color = QColor(theme.COLORS["ACCENT"])
            painter.fillRect(self.drop_indicator_rect, color)
            painter.end()

    def set_pressed_index(self, pressed_index: QModelIndex):
        """
        Set the visual 'pressed' state on a specific item, clearing it from the previous.
        """
        current_pressed_row = -1
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(CustomRoles.IsPressedRole):
                current_pressed_row = i
                item.setData(CustomRoles.IsPressedRole, False)
                break
        new_pressed_row = -1
        if pressed_index.isValid():
            item = self.item(pressed_index.row())
            if item:
                item.setData(CustomRoles.IsPressedRole, True)
                new_pressed_row = pressed_index.row()
        if current_pressed_row != -1:
            self.viewport().update(
                self.visualRect(self.model().index(current_pressed_row, 0))
            )
        if new_pressed_row != -1 and new_pressed_row != current_pressed_row:
            self.viewport().update(
                self.visualRect(self.model().index(new_pressed_row, 0))
            )

    def mousePressEvent(self, event: QMouseEvent):
        """Record start position to differentiate between a click and a drag."""
        self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Handle clicks on specific regions of a track item, triggering
        events like play, pause, artist info, or lyrics viewing.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if self._drag_start_pos:
            diff = event.pos() - self._drag_start_pos
            if diff.manhattanLength() > QApplication.startDragDistance():
                super().mouseReleaseEvent(event)
                return

        index = self.indexAt(event.pos())
        if index.isValid() and isinstance(self.delegate, TrackListDelegate):
            option = QStyleOptionViewItem()
            self.delegate.initStyleOption(option, index)
            option.rect = self.visualRect(index)
            try:
                rects = self.delegate._get_rects(option, index)
                (
                    icon_rect, _, artist_rect, composer_rect, lyrics_rect,
                    duration_rect, _, actions_rect, _, _
                ) = rects

                track_data = index.data(Qt.ItemDataRole.UserRole)

                if icon_rect.contains(event.pos()):
                    is_current = index.data(CustomRoles.IsCurrentRole)
                    is_playing = index.data(CustomRoles.IsPlayingRole)
                    if is_current and is_playing:
                        self.pauseTrackClicked.emit()
                    else:
                        self.playTrackClicked.emit(track_data, index.row())
                    return

                if not artist_rect.isEmpty():
                    artists_list = track_data.get("artists", [])
                    if not artists_list:
                        fallback = track_data.get("artist") or track_data.get("album_artist")
                        if fallback:
                            artists_list = [fallback]

                    artist_text = ", ".join(artists_list) if artists_list else "..."
                    font_metrics = QFontMetrics(option.font)
                    actual_text_width = font_metrics.horizontalAdvance(artist_text)
                    precise_artist_width = min(actual_text_width, artist_rect.width())

                    precise_artist_rect = QRect(
                        artist_rect.left(), artist_rect.top(),
                        precise_artist_width, artist_rect.height()
                    )

                    if precise_artist_rect.contains(event.pos()):
                        mw = self.main_window
                        if hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
                            target = track_data.get("album_artist") or track_data.get("artist")
                            if target:
                                self.artistClicked.emit(target)
                            return

                        if not artists_list:
                            return

                        if len(artists_list) == 1:
                            self.artistClicked.emit(artists_list[0])
                        else:
                            menu = TranslucentMenu(self)
                            for artist in artists_list:
                                action = QAction(artist, menu)
                                action.triggered.connect(partial(self.artistClicked.emit, artist))
                                menu.addAction(action)
                            menu.exec(event.globalPosition().toPoint())
                        return

                if not composer_rect.isEmpty():
                    raw_comp = track_data.get("composer", "").strip()

                    comps = [c.strip() for c in re.split(r"[;/]", raw_comp) if c.strip()]

                    display_text = ", ".join(comps)

                    if display_text:
                        font_metrics = QFontMetrics(option.font)
                        actual_comp_width = font_metrics.horizontalAdvance(display_text)

                        precise_comp_width = min(actual_comp_width, composer_rect.width())
                        precise_comp_rect = QRect(
                            composer_rect.left(), composer_rect.top(),
                            precise_comp_width, composer_rect.height()
                        )

                        if precise_comp_rect.contains(event.pos()):
                            if not comps:
                                return

                            if len(comps) == 1:
                                self.composerClicked.emit(comps[0])
                            else:
                                menu = TranslucentMenu(self)
                                for comp in comps:
                                    action = QAction(comp, menu)
                                    action.triggered.connect(partial(self.composerClicked.emit, comp))
                                    menu.addAction(action)
                                menu.exec(event.globalPosition().toPoint())
                            return

                if duration_rect and duration_rect.contains(event.pos()):
                    self._on_context_menu(event.pos())
                    return

                elif not lyrics_rect.isEmpty() and lyrics_rect.contains(event.pos()):
                    self.lyricsClicked.emit(track_data)
                    return

            except Exception as e:
                print(f"Error in TrackListWidget.mouseReleaseEvent: {e}")

        super().mouseReleaseEvent(event)

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:
        """Construct custom MIME data to support dragging tracks out of the widget."""
        mime_data = QMimeData()
        data_lines = []
        for item in items:
            track_data = item.data(Qt.ItemDataRole.UserRole)
            if track_data and "path" in track_data:
                data_lines.append(f"track:{track_data['path']}")
        if data_lines:
            data_str = "\n".join(data_lines)
            mime_data.setData(
                "application/x-vinyller-data", QByteArray(data_str.encode("utf-8"))
            )
        return mime_data

    def _schedule_resize(self):
        """Schedule a resize adjustment when the model changes."""
        self._resize_timer.start()

    def _adjust_height_to_contents(self):
        """Dynamically adjust widget height so it exactly fits its contents (avoiding scrollbars inside)."""
        try:
            count = self.model().rowCount()
            if count == 0:
                self.setMinimumHeight(0)
                self.setMaximumHeight(0)
                return
            item_height = self.sizeHintForRow(0)
            total_height = item_height * count

            total_height += 2
            self.setMinimumHeight(total_height)
            self.setMaximumHeight(total_height)
        except RuntimeError:
            pass

    def sizeHint(self) -> QSize:
        """Provide a size hint strictly bound by the content height."""
        self._adjust_height_to_contents()
        return QSize(super().sizeHint().width(), self.minimumHeight())

    def minimumSizeHint(self) -> QSize:
        """Provide a minimum size hint strictly bound by the content height."""
        self._adjust_height_to_contents()
        return QSize(super().minimumSizeHint().width(), self.minimumHeight())

    def updatePlaybackState(
            self,
            current_track_path: str | None,
            current_track_index: int,
            is_playing: bool,
            current_context: any,
    ):
        """
        Synchronize the visual state of the items to reflect global playback status,
        updating bolding and 'now playing' animations on the correct track.
        """
        orig_index = None
        if self.main_window.player.get_current_queue():
            idx = self.main_window.player.get_current_index()
            queue = self.main_window.player.get_current_queue()
            if 0 <= idx < len(queue):
                orig_index = queue[idx].get("__original_index")

        parent_ctx = self.parent_context
        current_ctx = current_context

        is_same_context = False
        if parent_ctx == current_ctx:
            is_same_context = True
        elif isinstance(current_ctx, dict) and "data" in current_ctx:
            if parent_ctx == current_ctx["data"]:
                is_same_context = True

        synced_by_queue = False
        if is_same_context and current_track_path and 0 <= current_track_index < self.count():
            item = self.item(current_track_index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get("path") == current_track_path:
                synced_by_queue = True

        synced_by_orig = False
        if not synced_by_queue and is_same_context and orig_index is not None and 0 <= orig_index < self.count():
            item = self.item(orig_index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get("path") == current_track_path:
                synced_by_orig = True

        fallback_found = False

        try:
            needs_update = False
            is_any_track_playing_in_this_list = False
            for i in range(self.count()):
                item = self.item(i)
                if not item:
                    continue
                track_data = item.data(Qt.ItemDataRole.UserRole)
                if not track_data:
                    continue

                is_correct_path = (
                        current_track_path is not None
                        and track_data["path"] == current_track_path
                )

                if not is_correct_path:
                    new_is_current = False
                else:
                    if is_same_context:
                        if synced_by_queue:
                            new_is_current = (i == current_track_index)
                        elif synced_by_orig:
                            new_is_current = (i == orig_index)
                        else:
                            if not fallback_found:
                                new_is_current = True
                                fallback_found = True
                            else:
                                new_is_current = False
                    else:
                        dashboard_contexts = [
                            "favorite_tracks",
                            "all_top_tracks",
                            "playback_history",
                        ]

                        if parent_ctx in dashboard_contexts:
                            new_is_current = False
                        else:
                            if not fallback_found:
                                new_is_current = True
                                fallback_found = True
                            else:
                                new_is_current = False

                old_is_current = item.data(CustomRoles.IsCurrentRole)
                old_is_playing = item.data(CustomRoles.IsPlayingRole)
                new_is_playing = new_is_current and is_playing

                if old_is_current != new_is_current or old_is_playing != new_is_playing:
                    item.setData(CustomRoles.IsCurrentRole, new_is_current)
                    item.setData(CustomRoles.IsPlayingRole, new_is_playing)
                    needs_update = True
                if new_is_playing:
                    is_any_track_playing_in_this_list = True

            if is_any_track_playing_in_this_list:
                if not self.animation_timer.isActive():
                    self.animation_timer.start()
            else:
                if self.animation_timer.isActive():
                    self.animation_timer.stop()
            if needs_update:
                self.viewport().update()
        except RuntimeError:
            if self.animation_timer.isActive():
                self.animation_timer.stop()

    def _on_double_clicked(self, item: QListWidgetItem):
        """Emit signal to restart the track when an item is double-clicked."""
        index = self.indexFromItem(item)
        track_data = item.data(Qt.ItemDataRole.UserRole)
        self.restartTrackClicked.emit(track_data, index.row())

    def _on_context_menu(self, pos: QPoint):
        """Handle custom context menu request, providing the item context."""
        index = self.indexAt(pos)
        if not index.isValid():
            return
        item = self.itemAt(pos)
        if not item:
            return

        track_data = item.data(Qt.ItemDataRole.UserRole)
        if not track_data:
            return

        context = {
            "source": "tracklist",
            "parent_context": self.parent_context,
            "widget": self,
            "index": index,
        }

        try:
            self.trackContextMenuRequested.emit(track_data, self.mapToGlobal(pos), context)
        except Exception as e:
            print(f"Error showing context menu: {e}")

    def mouseMoveEvent(self, event: QMouseEvent):
        """Update cursor shape and hover state dynamically based on the sub-element hovered over."""
        index = self.indexAt(event.pos())
        self.delegate.setHoveredIndex(index, self)
        self.delegate.setMousePosition(event.pos())
        cursor_is_hand = False

        if index.isValid() and isinstance(self.delegate, TrackListDelegate):
            option = QStyleOptionViewItem()
            self.delegate.initStyleOption(option, index)
            option.rect = self.visualRect(index)
            try:
                rects = self.delegate._get_rects(option, index)
                (
                    icon_rect,
                    _,
                    artist_rect,
                    composer_rect,
                    lyrics_rect,
                    duration_rect,
                    _,
                    actions_rect,
                    _,
                    _,
                ) = rects

                precise_artist_rect = QRect()
                if artist_rect and not artist_rect.isEmpty():
                    track_data = index.data(Qt.ItemDataRole.UserRole)
                    artist_text = ", ".join(track_data.get("artists", ["..."]))
                    font_metrics = QFontMetrics(option.font)
                    actual_text_width = font_metrics.horizontalAdvance(artist_text)
                    precise_artist_width = min(actual_text_width, artist_rect.width())
                    precise_artist_rect = QRect(
                        artist_rect.left(),
                        artist_rect.top(),
                        precise_artist_width,
                        artist_rect.height(),
                    )

                precise_composer_rect = QRect()
                if composer_rect and not composer_rect.isEmpty():
                    track_data = index.data(Qt.ItemDataRole.UserRole)

                    raw_comp = track_data.get("composer", "").strip()
                    comps_list = [c.strip() for c in re.split(r"[;/]", raw_comp) if c.strip()]
                    composer_text = ", ".join(comps_list)

                    font_metrics = QFontMetrics(option.font)
                    actual_comp_width = font_metrics.horizontalAdvance(composer_text)
                    precise_comp_width = min(actual_comp_width, composer_rect.width())
                    precise_composer_rect = QRect(
                        composer_rect.left(),
                        composer_rect.top(),
                        precise_comp_width,
                        composer_rect.height(),
                    )

                if icon_rect and icon_rect.contains(event.pos()):
                    cursor_is_hand = True
                elif precise_artist_rect and precise_artist_rect.contains(event.pos()):
                    cursor_is_hand = True
                elif precise_composer_rect and precise_composer_rect.contains(
                        event.pos()
                ):
                    cursor_is_hand = True
                elif duration_rect and duration_rect.contains(event.pos()):
                    cursor_is_hand = True
                elif (
                        lyrics_rect
                        and not lyrics_rect.isEmpty()
                        and lyrics_rect.contains(event.pos())
                ):
                    cursor_is_hand = True
            except Exception as e:
                pass
        if cursor_is_hand:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        if event.buttons() & Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if self._drag_start_pos and (
                    event.pos() - self._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                if self.dragEnabled() and (self.currentItem() or self.selectedItems()):
                    self.startDrag(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
            return

        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent):
        """Clear hover effects and cursors when the mouse leaves the widget."""
        self.delegate.setHoveredIndex(QModelIndex(), self)
        self.delegate.setMousePosition(None)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


class QueueDelegate(QStyledItemDelegate):
    """
    Custom delegate for drawing playback queue items. Supports normal and
    compact visual modes, optional cover art display, and distinct hover actions.
    """
    playButtonClicked = pyqtSignal(QModelIndex)
    playTrack = pyqtSignal(object, int)
    pausePlayer = pyqtSignal()
    restartTrack = pyqtSignal(object, int)

    def __init__(self, parent=None):
        """Initialize QueueDelegate."""
        super().__init__(parent)
        self.hovered_index = QModelIndex()
        self.mouse_pos = None
        self._rect_cache = defaultdict(dict)

        self.now_playing_icons = [
            create_svg_icon(
                f"assets/animation/track/now_playing_{i}.svg",
                theme.COLORS["ACCENT"],
                QSize(16, 16),
            )
            for i in range(1, 9)
        ]
        self.compact_mode = False
        self.hide_artist_in_compact = False
        self.show_cover = False
        self.current_frame = 0

    def set_animation_frame(self, frame_index: int):
        """Sync animation frame from an external timer."""
        if self.current_frame != frame_index:
            self.current_frame = frame_index

    def set_compact_mode(self, compact: bool):
        """Toggle compact view mode on or off, clearing layout cache."""
        if self.compact_mode != compact:
            self.compact_mode = compact
            self._rect_cache.clear()

    def set_hide_artist_in_compact(self, hide):
        """Determine if artist text is hidden to save space in compact mode."""
        if self.hide_artist_in_compact != hide:
            self.hide_artist_in_compact = hide
            self._rect_cache.clear()

    def set_show_cover(self, show: bool):
        """Toggle the display of the track's album cover thumbnail."""
        if self.show_cover != show:
            self.show_cover = show
            self._rect_cache.clear()

    def setHoveredIndex(self, index: QModelIndex):
        """Update the currently hovered item index."""
        if self.hovered_index != index:
            old_index = self.hovered_index
            self.hovered_index = index
            if self.parent() and hasattr(self.parent(), "viewport"):
                if old_index.isValid():
                    self.parent().viewport().update(self.parent().visualRect(old_index))
                if index.isValid():
                    self.parent().viewport().update(self.parent().visualRect(index))

    def setMousePosition(self, pos):
        """Cache mouse position to trigger local component hover effects."""
        if self.mouse_pos != pos:
            self.mouse_pos = pos
            if self.parent() and hasattr(self.parent(), "viewport"):
                self.parent().viewport().update()

    def get_play_button_rect(self, option, left_margin: int) -> QRect:
        """Calculate the geometry for the play/pause button icon."""
        icon_size = 16
        icon_top = option.rect.center().y() - icon_size // 2
        return QRect(left_margin, icon_top, icon_size, icon_size)

    def _get_rects(self, option, index):
        """Calculate and cache all visual element geometries for a specific queue item."""
        if option.rect.width() <= 0:
            return {
                "play": QRect(),
                "cover": QRect(),
                "text_left": 0,
                "duration": QRect(),
                "duration_text": "",
                "actions": QRect(),
                "lyrics": QRect(),
                "text_right": 0,
                "artist": QRect(),
            }

        track_data = index.data(Qt.ItemDataRole.UserRole)
        if not track_data:
            return {
                "play": QRect(),
                "cover": QRect(),
                "text_left": 0,
                "duration": QRect(),
                "duration_text": "",
                "actions": QRect(),
                "lyrics": QRect(),
                "text_right": 0,
                "artist": QRect(),
            }

        cache_key = (
            track_data.get("path"),
            option.rect.y(),
            option.rect.width(),
            track_data.get("title"),
            tuple(track_data.get("artists", [])),
            track_data.get("duration"),
            bool(track_data.get("lyrics"))
        )

        if cache_key in self._rect_cache:
            return self._rect_cache[cache_key]

        current_left_margin = option.rect.left() + 8
        play_button_rect = self.get_play_button_rect(option, current_left_margin)

        cover_rect = QRect()
        if self.show_cover:
            cover_size = 32 if not self.compact_mode else 24
            cover_left = play_button_rect.right() + 8
            cover_rect = QRect(
                cover_left,
                option.rect.center().y() - cover_size // 2,
                cover_size,
                cover_size,
            )

        text_left_margin = play_button_rect.right() + 8
        if self.show_cover:
            text_left_margin = cover_rect.right() + 8

        duration_text = format_time(track_data.get("duration", 0) * 1000)
        duration_font = QFont(option.font)
        duration_font.setBold(False)
        duration_font.setPixelSize(12)
        duration_metrics = QFontMetrics(duration_font)
        duration_width = duration_metrics.horizontalAdvance(duration_text)

        right_margin = 12
        current_right = option.rect.right() - right_margin

        duration_rect = QRect(
            current_right - duration_width,
            option.rect.top(),
            duration_width,
            option.rect.height(),
        )
        current_right = duration_rect.left()

        actions_icon_size = 16
        actions_rect = QRect(
            duration_rect.center().x() - actions_icon_size // 2,
            duration_rect.center().y() - actions_icon_size // 2,
            actions_icon_size,
            actions_icon_size,
        )

        lyrics_icon_width = 16
        lyrics_icon_padding = 8
        lyrics_left = current_right - lyrics_icon_padding - lyrics_icon_width
        lyrics_rect = QRect(
            lyrics_left,
            option.rect.center().y() - lyrics_icon_width // 2,
            lyrics_icon_width,
            lyrics_icon_width,
        )
        current_right = lyrics_rect.left()

        text_right_margin = current_right - 8
        main_text_rect_width = text_right_margin - text_left_margin

        artist_rect = QRect()

        artist_font = QFont(option.font)
        artist_font.setBold(False)
        artist_font.setPixelSize(10)
        artist_metrics = QFontMetrics(artist_font)

        artist_str = ", ".join(track_data.get("artists", ["N/A"]))

        if self.compact_mode:
            if not self.hide_artist_in_compact:
                main_text_rect = QRect(
                    text_left_margin,
                    option.rect.top(),
                    main_text_rect_width,
                    option.rect.height(),
                )

                title_font = QFont(option.font)
                title_font.setBold(True)
                title_metrics = QFontMetrics(title_font)

                artist_text_with_sep = f"  {artist_str}"

                full_artist_width = artist_metrics.horizontalAdvance(
                    artist_text_with_sep
                )
                max_artist_share = int(main_text_rect.width() * 0.5)

                title_text = track_data.get("title", "N/A")
                title_width_available = main_text_rect.width() - min(
                    full_artist_width, max_artist_share
                )
                elided_title = title_metrics.elidedText(
                    title_text, Qt.TextElideMode.ElideRight, title_width_available
                )
                drawn_title_width = title_metrics.horizontalAdvance(elided_title) + 4

                artist_x = main_text_rect.left() + drawn_title_width

                remaining_space = main_text_rect.width() - drawn_title_width

                remaining_space = max(0, remaining_space)

                final_artist_width = min(full_artist_width, remaining_space)

                if final_artist_width > 0:
                    artist_rect = QRect(
                        artist_x,
                        main_text_rect.top(),
                        final_artist_width,
                        main_text_rect.height(),
                    )

        else:
            padding_top = 6 if self.show_cover else 4

            title_font = QFont(option.font)
            title_font.setBold(True)
            title_metrics = QFontMetrics(title_font)
            title_height = title_metrics.height()

            title_bottom = option.rect.top() + padding_top + title_height

            artist_width = artist_metrics.horizontalAdvance(artist_str)

            final_artist_width = min(artist_width + 4, main_text_rect_width)

            artist_rect = QRect(
                text_left_margin,
                title_bottom + 4,
                final_artist_width,
                artist_metrics.height(),
            )

        rects = {
            "play": play_button_rect,
            "cover": cover_rect,
            "text_left": text_left_margin,
            "duration": duration_rect,
            "duration_text": duration_text,
            "actions": actions_rect,
            "lyrics": lyrics_rect,
            "text_right": text_right_margin,
            "artist": artist_rect,
        }
        self._rect_cache[cache_key] = rects
        return rects

    def helpEvent(self, event, view, option, index):
        """
        Handle tooltip events for queue items, calculating dynamic text bounds
        to detect elision and labeling functional icons and artists.
        """
        if event.type() == QEvent.Type.ToolTip:
            rects = self._get_rects(option, index)
            pos = event.pos()
            track_data = index.data(Qt.ItemDataRole.UserRole)

            if not track_data:
                return super().helpEvent(event, view, option, index)

            is_current = index.data(CustomRoles.IsCurrentRole)
            title_font = QFont(option.font)
            title_font.setBold(is_current)
            title_metrics = QFontMetrics(title_font)

            text_left = rects["text_left"]
            text_right = rects["text_right"]
            available_width = text_right - text_left

            if self.compact_mode:
                artist_rect = rects.get("artist")
                title_width = (
                            artist_rect.left() - text_left) if artist_rect and not artist_rect.isEmpty() else available_width
                title_rect = QRect(text_left, option.rect.top(), title_width, option.rect.height())
            else:
                padding_top = 6 if self.show_cover else 4
                title_rect = QRect(text_left, option.rect.top() + padding_top, available_width, title_metrics.height())

            if title_rect.contains(pos):
                full_title = track_data.get("title", "N/A")
                if title_metrics.horizontalAdvance(full_title) > title_rect.width():
                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": full_title},
                        rect = title_rect
                    )
                    return True

            artist_rect = rects.get("artist")
            if artist_rect and not artist_rect.isEmpty():
                artists = track_data.get("artists", ["N/A"])
                artist_text = ", ".join(artists)

                font = QFont(option.font)
                font.setPixelSize(10)
                fm = QFontMetrics(font)

                text_width = fm.horizontalAdvance(artist_text)
                precise_width = min(text_width, artist_rect.width())

                precise_rect = QRect(
                    artist_rect.left(),
                    artist_rect.top(),
                    precise_width,
                    artist_rect.height()
                )

                if precise_rect.contains(pos):
                    mw = view.window()
                    if hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
                        target = track_data.get("album_artist") or track_data.get("artist") or "Unknown"
                        content = f"{translate('Go to Album Artist')}: {target}"
                    else:
                        content = translate("Go to artist")

                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": content},
                        rect = precise_rect
                    )
                    return True

            lyrics_rect = rects.get("lyrics")
            if lyrics_rect and not lyrics_rect.isEmpty() and lyrics_rect.contains(pos):
                if track_data.get("lyrics"):
                    GlobalTooltipFilter.show_rect_tooltip(
                        view,
                        data = {"title": translate("Lyrics")},
                        rect = lyrics_rect
                    )
                    return True

            actions_rect = rects.get("actions")
            if actions_rect and not actions_rect.isEmpty() and actions_rect.contains(pos):
                GlobalTooltipFilter.show_rect_tooltip(
                    view,
                    data = {"title": translate("Actions")},
                    rect = actions_rect
                )
                return True

        return super().helpEvent(event, view, option, index)

    def paint(self, painter, option, index):
        """Main rendering pipeline for painting a queue item with covers, text, and icons."""
        painter.save()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        if opt.state & QStyle.StateFlag.State_HasFocus:
            opt.state = opt.state & ~QStyle.StateFlag.State_HasFocus

        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget
        )

        is_current = index.data(CustomRoles.IsCurrentRole)
        is_playing = index.data(CustomRoles.IsPlayingRole)
        is_hovered = index == self.hovered_index
        is_pressed = index.data(CustomRoles.IsPressedRole)

        rects = self._get_rects(opt, index)
        play_button_rect = rects["play"]
        cover_rect = rects["cover"]
        text_left_margin = rects["text_left"]
        duration_rect = rects["duration"]
        duration_text = rects["duration_text"]
        actions_rect = rects["actions"]
        lyrics_rect = rects["lyrics"]
        text_right_margin = rects["text_right"]

        if self.show_cover:
            main_win = self.parent().window()
            if main_win and hasattr(main_win, "ui_manager"):
                track_data = index.data(Qt.ItemDataRole.UserRole)
                artwork_data = track_data.get("artwork")
                pixmap = main_win.ui_manager.components.get_pixmap(
                    artwork_data, cover_rect.width()
                )

                if pixmap and not pixmap.isNull():
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(cover_rect), 3, 3)
                    painter.save()
                    painter.setClipPath(path)
                    painter.drawPixmap(cover_rect, pixmap)
                    pen = QPen(QColor(0, 0, 0, int(255 * 0.05)))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    border_rect = QRectF(cover_rect).adjusted(0.5, 0.5, -0.5, -0.5)
                    painter.drawRoundedRect(border_rect, 3, 3)
                    painter.restore()

        is_mouse_over_button = self.mouse_pos is not None and play_button_rect.contains(
            self.mouse_pos
        )
        icon_to_draw = None
        opacity = 1.0

        icon_color = (
            theme.COLORS["ACCENT"] if is_mouse_over_button else theme.COLORS["PRIMARY"]
        )

        if is_current:
            if is_playing:
                if is_hovered:
                    icon_to_draw = create_svg_icon(
                        "assets/control/pause.svg", icon_color, QSize(16, 16)
                    )
                    opacity = 1.0 if is_mouse_over_button else 0.7
                else:
                    icon_to_draw = self.now_playing_icons[self.current_frame]
            else:
                icon_to_draw = create_svg_icon(
                    "assets/control/play.svg", icon_color, QSize(16, 16)
                )
                opacity = 1.0 if is_mouse_over_button else 0.7
        elif is_hovered:
            icon_to_draw = create_svg_icon(
                "assets/control/play.svg", icon_color, QSize(16, 16)
            )
            opacity = 1.0 if is_mouse_over_button else 0.7

        if icon_to_draw:
            painter.save()
            if not (is_current and is_playing and not is_hovered):
                painter.setOpacity(opacity)
            icon_to_draw.paint(painter, play_button_rect)
            painter.restore()

        if self.compact_mode:
            self._paint_compact_text(
                painter,
                opt,
                index,
                is_current,
                text_left_margin,
                text_right_margin,
                rects["artist"],
            )
        else:
            self._paint_normal_text(
                painter,
                opt,
                index,
                is_current,
                text_left_margin,
                text_right_margin,
                rects["artist"],
            )

        track_data = index.data(Qt.ItemDataRole.UserRole)
        has_lyrics = bool(track_data.get("lyrics"))

        if has_lyrics and not lyrics_rect.isEmpty():
            painter.save()
            is_mouse_over_lyrics = self.mouse_pos and lyrics_rect.contains(
                self.mouse_pos
            )

            icon_color = (
                theme.COLORS["ACCENT"]
                if is_mouse_over_lyrics
                else theme.COLORS["PRIMARY"]
            )
            lyrics_icon_to_draw = create_svg_icon(
                "assets/control/lyrics.svg", icon_color, QSize(16, 16)
            )

            opacity = 1.0 if is_mouse_over_lyrics else 0.25
            painter.setOpacity(opacity)
            lyrics_icon_to_draw.paint(painter, lyrics_rect)
            painter.restore()

        if is_hovered or is_pressed:
            is_mouse_over_actions = self.mouse_pos and duration_rect.contains(
                self.mouse_pos
            )
            icon_color = (
                theme.COLORS["ACCENT"]
                if is_mouse_over_actions
                else theme.COLORS["PRIMARY"]
            )
            actions_icon_to_draw = create_svg_icon(
                "assets/control/more_horiz.svg", icon_color, QSize(16, 16)
            )
            opacity = 1.0 if is_mouse_over_actions or is_pressed else 0.7

            painter.save()
            painter.setOpacity(opacity)
            actions_icon_to_draw.paint(painter, actions_rect)
            painter.restore()
        else:
            duration_font = QFont(painter.font())
            duration_font.setBold(False)
            duration_font.setPixelSize(12)
            painter.setFont(duration_font)
            painter.setPen(QColor(theme.COLORS["PRIMARY"]))
            painter.drawText(
                duration_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                duration_text,
            )

        painter.restore()

    def _paint_normal_text(
        self,
        painter,
        option,
        index,
        is_current,
        text_left_margin,
        text_right_margin,
        artist_rect,
    ):
        """Paint title and artist data on distinct lines (standard view)."""
        track_data = index.data(Qt.ItemDataRole.UserRole)

        title_font = painter.font()
        title_font.setBold(is_current)
        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        if self.show_cover:
            padding_top = 6
        else:
            padding_top = 4

        title_rect_width = text_right_margin - text_left_margin
        title_rect = QRect(
            text_left_margin,
            option.rect.top() + padding_top,
            title_rect_width,
            title_metrics.height(),
        )

        painter.setPen(QColor(theme.COLORS["PRIMARY"]))
        elided_title = title_metrics.elidedText(
            track_data.get("title", "N/A"),
            Qt.TextElideMode.ElideRight,
            title_rect.width(),
        )
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_title,
        )

        artist_font = painter.font()
        artist_font.setBold(False)
        artist_font.setPixelSize(10)
        painter.setFont(artist_font)
        artist_metrics = QFontMetrics(artist_font)

        is_mouse_over_artist = self.mouse_pos is not None and artist_rect.contains(
            self.mouse_pos
        )

        if is_mouse_over_artist:
            painter.setPen(QColor(theme.COLORS["ACCENT"]))
        else:
            painter.setPen(QColor(theme.COLORS["TERTIARY"]))

        elided_artist = artist_metrics.elidedText(
            ", ".join(track_data.get("artists", ["N/A"])),
            Qt.TextElideMode.ElideRight,
            artist_rect.width(),
        )

        painter.drawText(
            artist_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            elided_artist,
        )

    def _paint_compact_text(
        self,
        painter,
        option,
        index,
        is_current,
        text_left_margin,
        text_right_margin,
        artist_rect,
    ):
        """Paint title and artist side by side for a dense layout."""
        track_data = index.data(Qt.ItemDataRole.UserRole)

        main_text_rect_width = text_right_margin - text_left_margin
        main_text_rect = QRect(
            text_left_margin,
            option.rect.top(),
            main_text_rect_width,
            option.rect.height(),
        )

        title_font = painter.font()
        title_font.setBold(is_current)
        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        title_text = track_data.get("title", "N/A")

        artist_text_only = ", ".join(track_data.get("artists", ["N/A"]))

        if self.hide_artist_in_compact:
            elided_title = title_metrics.elidedText(
                title_text, Qt.TextElideMode.ElideRight, main_text_rect.width()
            )
            painter.setPen(QColor(theme.COLORS["PRIMARY"]))
            painter.drawText(
                main_text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_title,
            )
        else:
            artist_font = painter.font()
            artist_font.setBold(False)
            artist_font.setPixelSize(10)
            artist_metrics = QFontMetrics(artist_font)

            title_width = artist_rect.left() - main_text_rect.left()

            elided_title = title_metrics.elidedText(
                title_text, Qt.TextElideMode.ElideRight, title_width
            )
            painter.setPen(QColor(theme.COLORS["PRIMARY"]))
            title_rect = QRect(
                main_text_rect.left(),
                main_text_rect.top(),
                title_width,
                main_text_rect.height(),
            )
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_title,
            )

            if artist_rect.width() > 0:
                painter.setFont(artist_font)

                is_mouse_over_artist = (
                    self.mouse_pos is not None and artist_rect.contains(self.mouse_pos)
                )
                if is_mouse_over_artist:
                    painter.setPen(QColor(theme.COLORS["ACCENT"]))
                else:
                    painter.setPen(QColor(theme.COLORS["TERTIARY"]))

                artist_text_with_sep = f"  {artist_text_only}"
                elided_artist = artist_metrics.elidedText(
                    artist_text_with_sep,
                    Qt.TextElideMode.ElideRight,
                    artist_rect.width(),
                )
                painter.drawText(
                    artist_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    elided_artist,
                )

    def sizeHint(self, option, index):
        """Provide a size hint adjusting for compact and cover view states."""
        if self.compact_mode:
            return QSize(200, 40 if self.show_cover else 32)
        return QSize(200, 48 if self.show_cover else 44)

    def editorEvent(self, event, model, option, index):
        """Handle UI events locally (e.g. clicking the play button overlay)."""
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            try:
                rects = self._get_rects(option, index)
                if rects["play"].contains(event.pos()):
                    self.playButtonClicked.emit(index)
                    return True
            except Exception as e:
                pass

        return super().editorEvent(event, model, option, index)


class QueueWidget(StyledListWidget):
    """
    QListWidget subclass for managing the playback queue.
    Features robust drag and drop for reordering, drag export to system files,
    and customized mouse event handling mapping.
    """
    tracksDropped = pyqtSignal(list, int)
    orderChanged = pyqtSignal()
    playActionRequested = pyqtSignal(QModelIndex)
    lyricsClicked = pyqtSignal(object)
    artistClicked = pyqtSignal(str)
    trackContextMenuRequested = pyqtSignal(object, QPoint, object)

    def __init__(self, parent=None):
        """Initialize the QueueWidget."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.allow_drag_export = False
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setProperty("class", "queueWidget")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.drop_indicator_rect = QRect()

        self._drag_start_pos = None

    def startDrag(self, supportedActions):
        """Override startDrag to support copy action when drag export is enabled."""
        if self.allow_drag_export:
            super().startDrag(Qt.DropAction.CopyAction)
        else:
            super().startDrag(supportedActions)

    def set_drag_export_enabled(self, enabled: bool):
        """Toggle dragging out of the widget to copy tracks globally."""
        self.allow_drag_export = enabled
        if enabled:
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        else:
            self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:
        """Construct standard QMimeData with optional file URLs for exporting."""
        mime_data = super().mimeData(items)

        data_lines = []
        urls = []

        for item in items:
            track_data = item.data(Qt.ItemDataRole.UserRole)
            if track_data and "path" in track_data:
                path = track_data['path']
                data_lines.append(f"track:{path}")

                if self.allow_drag_export:
                    urls.append(QUrl.fromLocalFile(path))

        if data_lines:
            data_str = "\n".join(data_lines)
            mime_data.setData(
                "application/x-vinyller-data", QByteArray(data_str.encode("utf-8"))
            )

        if self.allow_drag_export and urls:
            mime_data.setUrls(urls)

        return mime_data

    def paintEvent(self, event):
        """Draw custom drop indicator line during drag and drop."""
        super().paintEvent(event)
        if self.drop_indicator_rect.isValid():
            painter = QPainter(self.viewport())
            pen = QPen(QColor(theme.COLORS["ACCENT"]), 2)
            painter.setPen(pen)
            painter.drawLine(
                self.drop_indicator_rect.topLeft(), self.drop_indicator_rect.topRight()
            )

    def dragEnterEvent(self, event):
        """Handle items entering the widget during a drag operation."""
        if (
            event.mimeData().hasFormat("application/x-vinyller-data")
            or event.source() == self
        ):
            if event.source() != self:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Position drop indicator line while an item is dragged over the widget."""
        if (
            event.mimeData().hasFormat("application/x-vinyller-data")
            or event.source() == self
        ):
            pos = event.position().toPoint()
            index = self.indexAt(pos)
            if index.isValid():
                rect = self.visualRect(index)
                if pos.y() - rect.top() < rect.height() / 2:
                    self.drop_indicator_rect = QRect(
                        rect.left(), rect.top(), rect.width(), 1
                    )
                else:
                    self.drop_indicator_rect = QRect(
                        rect.left(), rect.bottom(), rect.width(), 1
                    )
            else:
                last_index = self.count() - 1
                if last_index >= 0:
                    rect = self.visualRect(self.indexFromItem(self.item(last_index)))
                    self.drop_indicator_rect = QRect(
                        rect.left(), rect.bottom(), rect.width(), 1
                    )
                else:
                    self.drop_indicator_rect = QRect(
                        self.viewport().rect().left(),
                        self.viewport().rect().top(),
                        self.viewport().rect().width(),
                        1,
                    )
            self.viewport().update()

            if event.source() == self:
                if self.allow_drag_export:
                    event.setDropAction(Qt.DropAction.CopyAction)
                    event.accept()
                else:
                    event.setDropAction(Qt.DropAction.MoveAction)
                    event.accept()
            else:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
        else:
            self.drop_indicator_rect = QRect()
            self.viewport().update()
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        """Clear visual indicators when drag leaves the widget."""
        self.drop_indicator_rect = QRect()
        self.viewport().update()
        super().dragLeaveEvent(event)

    def _on_context_menu(self, pos: QPoint, index=None):
        """Invoke context menu emitting specifically for the queue widget."""
        if index is None:
            index = self.indexAt(pos)

        if not index.isValid():
            return

        item = self.item(index.row())
        if not item:
            return

        if not item.isSelected():
            self.clearSelection()
            item.setSelected(True)
            self.setCurrentItem(item)

        selected_items = self.selectedItems()
        if len(selected_items) > 1:
            track_data = [
                i.data(Qt.ItemDataRole.UserRole)
                for i in selected_items
                if i.data(Qt.ItemDataRole.UserRole)
            ]
        else:
            track_data = item.data(Qt.ItemDataRole.UserRole)

        if not track_data:
            return

        context = {
            "source": "queue",
            "parent_context": "queue",
            "widget": self,
            "index": index,
        }
        self.trackContextMenuRequested.emit(track_data, self.mapToGlobal(pos), context)

    def set_pressed_index(self, pressed_index: QModelIndex):
        """Persist visual pressed state for a specific item index."""
        current_pressed_row = -1
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(CustomRoles.IsPressedRole):
                current_pressed_row = i
                item.setData(CustomRoles.IsPressedRole, False)
                break

        new_pressed_row = -1
        if pressed_index.isValid():
            item = self.item(pressed_index.row())
            if item:
                item.setData(CustomRoles.IsPressedRole, True)
                new_pressed_row = pressed_index.row()

        if current_pressed_row != -1:
            self.viewport().update(
                self.visualRect(self.model().index(current_pressed_row, 0))
            )

        if new_pressed_row != -1 and new_pressed_row != current_pressed_row:
            self.viewport().update(
                self.visualRect(self.model().index(new_pressed_row, 0))
            )

    def mousePressEvent(self, event):
        """Manage basic mouse press layout/selection updates."""
        self._drag_start_pos = event.pos()
        index = self.indexAt(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            if index.isValid() and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                if not self.selectionModel().isSelected(index):
                    self.clearSelection()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Determine what sub-component was clicked in the queue list and trigger it."""
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            diff = event.pos() - self._drag_start_pos
            if diff.manhattanLength() > QApplication.startDragDistance():
                super().mouseReleaseEvent(event)
                return

        index = self.indexAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if index.isValid() and isinstance(self.itemDelegate(), QueueDelegate):
                delegate = self.itemDelegate()
                option = QStyleOptionViewItem()
                delegate.initStyleOption(option, index)
                option.rect = self.visualRect(index)

                try:
                    rects = delegate._get_rects(option, index)
                    track_data = index.data(Qt.ItemDataRole.UserRole)

                    if (rects["lyrics"] and not rects["lyrics"].isEmpty()
                            and rects["lyrics"].contains(event.pos())):
                        if track_data.get("lyrics"):
                            self.lyricsClicked.emit(track_data)
                            return

                    elif rects.get("artist") and not rects["artist"].isEmpty():
                        if rects["artist"].contains(event.pos()):

                            mw = self.window()
                            if hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
                                target = track_data.get("album_artist") or track_data.get("artist")
                                if target:
                                    self.artistClicked.emit(target)
                                return

                            artists_list = track_data.get("artists", [])
                            if not artists_list:
                                fallback = track_data.get("artist") or track_data.get("album_artist")
                                if fallback:
                                    artists_list = [fallback]

                            if not artists_list:
                                return

                            if len(artists_list) == 1:
                                self.artistClicked.emit(artists_list[0])
                            else:
                                menu = TranslucentMenu(self)
                                for artist in artists_list:
                                    action = QAction(artist, menu)
                                    action.triggered.connect(partial(self.artistClicked.emit, artist))
                                    menu.addAction(action)
                                menu.exec(event.globalPosition().toPoint())
                            return

                    if rects["duration"].contains(event.pos()):
                        self.setCurrentIndex(index)
                        self._on_context_menu(event.pos(), index = index)
                        return

                except Exception as e:
                    print(f"Error in QueueWidget.mouseReleaseEvent: {e}")

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Set pointers and delegate hover states based on cursor overlap."""
        index = self.indexAt(event.pos())
        delegate = self.itemDelegate()

        if isinstance(delegate, QueueDelegate):
            delegate.setHoveredIndex(index)
            delegate.setMousePosition(event.pos())

            cursor_is_hand = False
            if index.isValid():
                option = QStyleOptionViewItem()
                delegate.initStyleOption(option, index)
                option.rect = self.visualRect(index)

                try:
                    rects = delegate._get_rects(option, index)

                    if rects["play"].contains(event.pos()):
                        cursor_is_hand = True
                    elif (
                        rects["lyrics"]
                        and not rects["lyrics"].isEmpty()
                        and rects["lyrics"].contains(event.pos())
                    ):
                        track_data = index.data(Qt.ItemDataRole.UserRole)
                        if track_data.get("lyrics"):
                            cursor_is_hand = True

                    elif rects.get("artist") and not rects["artist"].isEmpty():
                        if rects["artist"].contains(event.pos()):
                            cursor_is_hand = True

                    elif rects["duration"].contains(event.pos()):
                        cursor_is_hand = True
                except Exception as e:
                    pass

            if cursor_is_hand:
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
                if hasattr(self, '_custom_tooltip') and self._custom_tooltip:
                    set_custom_tooltip(self)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        if event.buttons() & Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if self._drag_start_pos and (event.pos() - self._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                if self.currentItem() or self.selectedItems():
                    self.startDrag(self.defaultDropAction())
            return

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Clear delegate hover indices when leaving the viewport."""
        delegate = self.itemDelegate()
        if isinstance(delegate, QueueDelegate):
            delegate.setHoveredIndex(QModelIndex())
            delegate.setMousePosition(None)

        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        super().leaveEvent(event)

    def dropEvent(self, event):
        """Process finalized drop operations for sorting or external data dropping."""
        drop_index = -1
        if self.drop_indicator_rect.isValid():
            pos = self.drop_indicator_rect.center()
            index_at_pos = self.indexAt(pos)

            if index_at_pos.isValid():
                rect = self.visualRect(index_at_pos)
                if self.drop_indicator_rect.y() == rect.top():
                    drop_index = index_at_pos.row()
                else:
                    drop_index = index_at_pos.row() + 1
            else:
                drop_index = self.count()

        self.drop_indicator_rect = QRect()
        self.viewport().update()

        if event.source() == self:
            if self.allow_drag_export:
                source_items = self.selectedItems()
                super().dropEvent(event)
                for item in source_items:
                    row = self.row(item)
                    if row >= 0:
                        self.takeItem(row)
            else:
                super().dropEvent(event)

            for i in range(self.count()):
                item = self.item(i)
                if item.data(CustomRoles.IsCurrentRole):
                    mw = self.window()
                    if hasattr(mw, "player") and hasattr(mw.player, "current_index"):
                        if mw.player.current_index != i:
                            mw.player.current_index = i
                    break

            self.orderChanged.emit()

        elif event.mimeData().hasFormat("application/x-vinyller-data"):
            data = (
                event.mimeData()
                .data("application/x-vinyller-data")
                .data()
                .decode("utf-8")
            )
            data_list = data.split("\n")
            self.tracksDropped.emit(data_list, drop_index)

            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            super().dropEvent(event)

    def resizeEvent(self, event):
        """Clear layout caches upon resizing and update."""
        if delegate := self.itemDelegate():
            if isinstance(delegate, QueueDelegate):
                delegate._rect_cache.clear()

        super().resizeEvent(event)
        self.scheduleDelayedItemsLayout()


class NavCategoryItem(QWidget):
    """
    A simple composite widget for navigation sidebars representing a category
    with a name and a count indicator.
    """
    def __init__(self, name, count, parent=None):
        """
        Initialize NavCategoryItem.

        Args:
            name (str): The string name of the category.
            count (int): The current count to display next to it.
            parent (QWidget): Parent widget.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.name_label = QLabel(name)
        self.name_label.setProperty("class", "textColorPrimary")

        self.count_label = QLabel(str(count))
        self.count_label.setProperty("class", "textSecondary textColorTertiary")

        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.count_label)

    def set_count(self, count):
        """Update the item count displayed on the label."""
        self.count_label.setText(str(count))


class BlacklistItemWidget(QWidget):
    """
    A widget representing an item in the blacklist, providing inline actions
    to restore the item to the library or open it in the file explorer.
    """
    restore_requested = pyqtSignal(QListWidgetItem)
    show_in_explorer_requested = pyqtSignal(object)

    def __init__(
        self, item_data, display_text, list_widget_item, has_path, parent=None
    ):
        """
        Initialize the BlacklistItemWidget.

        Args:
            item_data: Underlying data corresponding to the item.
            display_text (str): Name/text representation of the item.
            list_widget_item (QListWidgetItem): The parent item containing this widget.
            has_path (bool): Indicates if the item has an explorer path.
            parent (QWidget): Parent widget.
        """
        super().__init__(parent)
        self.item_data = item_data
        self.list_widget_item = list_widget_item

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        item_label = ElidedLabel(display_text)
        item_label.setProperty("class", "textColorPrimary")
        set_custom_tooltip(
            item_label,
            title = display_text,
        )

        restore_button = QPushButton()
        restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_button.setIcon(
            create_svg_icon(
                "assets/control/undo.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        restore_button.setFixedSize(24, 24)
        restore_button.setIconSize(QSize(16, 16))
        restore_button.setProperty("class", "btnListAction")
        set_custom_tooltip(
            restore_button,
            title = translate("Restore to library"),
        )
        apply_button_opacity_effect(restore_button)
        restore_button.clicked.connect(self._on_restore_clicked)

        explorer_button = QPushButton()
        explorer_button.setCursor(Qt.CursorShape.PointingHandCursor)
        explorer_button.setIcon(
            create_svg_icon(
                "assets/control/folder.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        explorer_button.setFixedSize(24, 24)
        explorer_button.setIconSize(QSize(16, 16))
        explorer_button.setProperty("class", "btnListAction")
        set_custom_tooltip(
            explorer_button,
            title = translate("Show file location"),
        )
        apply_button_opacity_effect(explorer_button)
        explorer_button.clicked.connect(self._on_explorer_clicked)
        explorer_button.setVisible(has_path)

        layout.addWidget(item_label, 1)
        layout.addWidget(restore_button)
        layout.addWidget(explorer_button)

    def _on_restore_clicked(self):
        """Emit restore request signal for this item."""
        self.restore_requested.emit(self.list_widget_item)

    def _on_explorer_clicked(self):
        """Emit explorer view request signal for this item."""
        self.show_in_explorer_requested.emit(self.item_data)


class UnavailableItemWidget(QWidget):
    """
    A widget representing an item that is currently unavailable (e.g., deleted file).
    Provides an inline action to remove it from the list.
    """
    remove_requested = pyqtSignal(QListWidgetItem)

    def __init__(self, item_key_str, display_text, list_widget_item, parent=None):
        """
        Initialize the UnavailableItemWidget.

        Args:
            item_key_str (str): A unique key string identifying the missing item.
            display_text (str): The text to display.
            list_widget_item (QListWidgetItem): The parent QListWidgetItem.
            parent (QWidget): Parent widget.
        """
        super().__init__(parent)
        self.item_key_str = item_key_str
        self.list_widget_item = list_widget_item

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        item_label = ElidedLabel(display_text)
        item_label.setProperty("class", "textColorPrimary")
        item_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        set_custom_tooltip(
            item_label,
            title = translate("File Path"),
            text = display_text,
        )

        remove_button = QPushButton()
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        remove_button.setFixedSize(24, 24)
        remove_button.setIconSize(QSize(16, 16))
        remove_button.setProperty("class", "btnListAction")
        set_custom_tooltip(
            remove_button,
            title = translate("Remove from list"),
        )
        apply_button_opacity_effect(remove_button)
        remove_button.clicked.connect(self._on_remove_clicked)

        layout.addWidget(item_label, 1)
        layout.addWidget(remove_button)

    def _on_remove_clicked(self):
        """Emit the remove request signal for this item."""
        self.remove_requested.emit(self.list_widget_item)


class EncyclopediaListDelegate(QStyledItemDelegate):
    """
    Delegate for drawing lists of Encyclopedia entries.
    Handles icon positioning and custom search highlighting.
    """
    def __init__(self, parent=None):
        """Initialize EncyclopediaListDelegate."""
        super().__init__(parent)
        self.search_query = ""

    def setSearchQuery(self, query):
        """
        Store the current search query to highlight matched text.

        Args:
            query (str): The string query to be highlighted.
        """
        self.search_query = query

    def paint(self, painter, option, index):
        """Custom paint implementation for encyclopedia list items."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        item_data = index.data(Qt.ItemDataRole.UserRole)
        has_entry = item_data.get("has_entry", False) if item_data else False

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = QIcon()

        style = opt.widget.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget
        )

        rect = opt.rect
        content_rect = rect.adjusted(12, 0, -12, 0)

        icon_size = 16
        main_icon = index.data(Qt.ItemDataRole.DecorationRole)
        text_x = content_rect.left()

        if main_icon and not main_icon.isNull():
            icon_rect = QRect(
                content_rect.left(),
                content_rect.top() + (content_rect.height() - icon_size) // 2,
                icon_size,
                icon_size,
            )
            main_icon.paint(painter, icon_rect)
            text_x = icon_rect.right() + 12

        check_icon_size = 14
        if has_entry:
            check_rect = QRect(
                content_rect.right() - check_icon_size,
                content_rect.top() + (content_rect.height() - check_icon_size) // 2,
                check_icon_size,
                check_icon_size,
            )
            check_svg = create_svg_icon(
                "assets/control/check.svg",
                theme.COLORS["ACCENT"],
                QSize(check_icon_size, check_icon_size),
            )
            check_svg.paint(painter, check_rect)

            text_width_limit = check_rect.left() - text_x - 8
        else:
            text_width_limit = content_rect.right() - text_x

        text_rect = QRect(
            text_x, content_rect.top(), text_width_limit, content_rect.height()
        )
        text = index.data(Qt.ItemDataRole.DisplayRole)
        text_color = QColor(theme.COLORS["PRIMARY"])

        self._draw_highlighted_text(
            painter,
            text_rect,
            text,
            opt.font,
            text_color,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        painter.restore()

    def _draw_highlighted_text(
        self, painter, rect, text, font, default_color, align_flags
    ):
        """Draw text string within item rect, highlighting matching search text."""
        painter.setFont(font)
        fm = QFontMetrics(font)

        safe_width = max(0, rect.width() - 4)
        elided_text = fm.elidedText(text, Qt.TextElideMode.ElideRight, safe_width)

        query = self.search_query.lower()
        text_lower = elided_text.lower()

        if not query or query not in text_lower:
            painter.setPen(default_color)
            painter.drawText(rect, align_flags, elided_text)
            return

        idx = text_lower.find(query)

        prefix = elided_text[:idx]
        match = elided_text[idx : idx + len(query)]
        suffix = elided_text[idx + len(query) :]

        current_x = rect.left()

        if prefix:
            painter.setPen(default_color)
            prefix_width = fm.horizontalAdvance(prefix)
            painter.drawText(
                QRect(current_x, rect.top(), prefix_width, rect.height()),
                align_flags,
                prefix,
            )
            current_x += prefix_width

        match_width = fm.horizontalAdvance(match)
        if match:
            text_height = fm.height()
            bg_rect = QRect(
                current_x,
                rect.top() + (rect.height() - text_height) // 2,
                match_width,
                text_height,
            )

            painter.fillRect(bg_rect, QColor(theme.COLORS["ACCENT"]))

            painter.setPen(QColor(theme.COLORS["WHITE"]))
            painter.drawText(
                QRect(current_x, rect.top(), match_width, rect.height()),
                align_flags,
                match,
            )
            current_x += match_width

        if suffix:
            painter.setPen(default_color)
            suffix_width = rect.right() - current_x + 1
            if suffix_width > 0:
                painter.drawText(
                    QRect(current_x, rect.top(), suffix_width, rect.height()),
                    align_flags,
                    suffix,
                )