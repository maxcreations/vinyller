"""
Vinyller — Queue and lyrics panel widget
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

from PyQt6.QtCore import (
    pyqtSignal, QModelIndex, QPoint, QSize, Qt, QTimer
)
from PyQt6.QtGui import (
    QAction, QIcon
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidgetItem, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget, QSizePolicy
)

from src.ui.custom_base_widgets import (
    StyledScrollArea,
    TranslucentMenu, StyledLabel, set_custom_tooltip
)
from src.ui.custom_classes import (
    AccentIconFactory, apply_button_opacity_effect,
    ElidedLabel, RoundedCoverLabel
)
from src.ui.custom_lists import (
    CustomRoles, QueueDelegate, QueueWidget
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate


class RightPanel(QWidget):
    """
    A widget that encapsulates the entire right panel, including the
    queue header and the queue widget.
    """

    queuePopulated = pyqtSignal()
    clearQueueRequested = pyqtSignal()
    saveQueueRequested = pyqtSignal()
    createMixtapeRequested = pyqtSignal()
    deletePlaylistRequested = pyqtSignal(str)
    toggleCompactModeRequested = pyqtSignal()
    toggleShowCoverRequested = pyqtSignal()
    toggleHideArtistRequested = pyqtSignal()
    itemDoubleClicked = pyqtSignal(QListWidgetItem)
    playActionRequested = pyqtSignal(QModelIndex)
    customContextMenuRequested = pyqtSignal(QPoint)
    tracksDropped = pyqtSignal(list, int)
    orderChanged = pyqtSignal()
    lyricsCloseRequested = pyqtSignal()
    vinylLyricsCloseRequested = pyqtSignal()
    lyricsClicked = pyqtSignal(object)
    toggleAutoplayOnQueueRequested = pyqtSignal()
    shakeQueueRequested = pyqtSignal()
    artistClicked = pyqtSignal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.current_queue_context_path = None
        self.is_compact_mode = False
        self.is_showing_cover = False
        self.is_hiding_artist = False
        self.cover_pixmaps = {
            "default": AccentIconFactory.create(
                resource_path("assets/view/music_small.png"), 48
            ),
            "artist": AccentIconFactory.create(
                resource_path("assets/view/artist_small.png"), 48
            ),
            "album": AccentIconFactory.create(
                resource_path("assets/view/album_small.png"), 48
            ),
            "favorite": AccentIconFactory.create(
                resource_path("assets/view/favorite_small.png"), 48
            ),
            "folder": AccentIconFactory.create(
                resource_path("assets/view/folder_small.png"), 48
            ),
            "genre": AccentIconFactory.create(
                resource_path("assets/view/genre_small.png"), 48
            ),
            "composer": AccentIconFactory.create(
                resource_path("assets/view/composer_small.png"), 48
            ),
            "playlist": AccentIconFactory.create(
                resource_path("assets/view/playlist_small.png"), 48
            ),
            "fav_artist": AccentIconFactory.create(
                resource_path("assets/view/artist_small.png"), 48
            ),
            "fav_album": AccentIconFactory.create(
                resource_path("assets/view/album_small.png"), 48
            ),
            "fav_folder": AccentIconFactory.create(
                resource_path("assets/view/folder_small.png"), 48
            ),
            "fav_genre": AccentIconFactory.create(
                resource_path("assets/view/genre_small.png"), 48
            ),
            "fav_playlist": AccentIconFactory.create(
                resource_path("assets/view/playlist_small.png"), 48
            ),
            "fav_composer": AccentIconFactory.create(
                resource_path("assets/view/composer_small.png"), 48
            ),
            "history": AccentIconFactory.create(
                resource_path("assets/view/history_small.png"), 48
            ),
            "top_track": AccentIconFactory.create(
                resource_path("assets/view/track_small.png"), 48
            ),
            "top_artist": AccentIconFactory.create(
                resource_path("assets/view/artist_small.png"), 48
            ),
            "top_album": AccentIconFactory.create(
                resource_path("assets/view/album_small.png"), 48
            ),
            "top_genre": AccentIconFactory.create(
                resource_path("assets/view/genre_small.png"), 48
            ),
        }
        self.check_icon = QIcon(
            create_svg_icon(
                "assets/control/check.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )

        self.lyrics_base_font_size = 12
        self.lyrics_font_level = 0
        self.max_lyrics_font_level = 4

        self.queue_populate_timer = QTimer(self)
        self.queue_populate_timer.timeout.connect(self._populate_queue_batch)
        self.queue_append_timer = QTimer(self)
        self.queue_append_timer.timeout.connect(self._append_queue_batch)

        self.vinyl_queue_populate_timer = QTimer(self)
        self.vinyl_queue_populate_timer.timeout.connect(
            self._populate_vinyl_queue_batch
        )
        self.vinyl_queue_tracks_generator = None

        self._setup_ui()
        self.setup_vinyl_queue_view()
        self.setup_vinyl_lyrics_view()
        self._connect_signals()

    def _setup_ui(self):
        """Sets up the widgets for the right panel."""
        self.setMinimumWidth(256)
        self.setMaximumWidth(640)
        self.setProperty("class", "backgroundPrimary")
        right_layout = QVBoxLayout(self)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.right_stack = QStackedWidget(self)

        self.queue_page = QWidget()
        self.queue_page.setProperty("class", "backgroundPrimary")
        queue_page_layout = QVBoxLayout(self.queue_page)
        queue_page_layout.setContentsMargins(0, 0, 0, 0)
        queue_page_layout.setSpacing(0)

        queue_header_widget = QWidget()
        queue_header_widget.setProperty("class", "backgroundPrimary headerBorder")
        queue_header_layout = QHBoxLayout(queue_header_widget)
        queue_header_layout.setContentsMargins(16, 16, 16, 16)
        queue_header_layout.setSpacing(8)

        self.queue_header_icon = RoundedCoverLabel(self.cover_pixmaps["default"], 3)
        self.queue_header_icon.setFixedSize(48, 48)

        text_vbox = QVBoxLayout()
        text_vbox.setContentsMargins(0, 0, 0, 0)
        text_vbox.setSpacing(2)

        self.queue_context_label = ElidedLabel("")
        self.queue_context_label.setProperty("class", "textTertiary textColorTertiary")
        self.queue_name_label = ElidedLabel(translate("Playback Queue"))
        self.queue_name_label.setProperty("class", "textSecondary textColorPrimary")
        self.queue_details_label = ElidedLabel(
            translate("{count} track(s) - {duration}", count=0, duration="00:00")
        )
        self.queue_details_label.setProperty("class", "textTertiary textColorPrimary")
        text_vbox.addWidget(self.queue_context_label)
        text_vbox.addWidget(self.queue_name_label)
        text_vbox.addWidget(self.queue_details_label)

        queue_header_layout.addWidget(self.queue_header_icon)
        queue_header_layout.addLayout(text_vbox)
        queue_header_layout.addStretch()

        self.more_button = QPushButton("")
        set_custom_tooltip(
            self.more_button,
            title = translate("Actions"),
        )
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.setProperty("class", "btnTool")
        self.more_button.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.more_button.setIconSize(QSize(24, 24))
        apply_button_opacity_effect(self.more_button)
        queue_header_layout.addWidget(self.more_button)

        queue_page_layout.addWidget(queue_header_widget)

        self.queue_widget = QueueWidget(self)
        self.queue_widget.setItemDelegate(QueueDelegate(self.queue_widget))
        self.queue_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.queue_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        queue_page_layout.addWidget(self.queue_widget)

        self.right_stack.addWidget(self.queue_page)

        self.lyrics_page = QWidget()
        self.lyrics_page.setProperty("class", "backgroundPrimary")
        lyrics_page_layout = QVBoxLayout(self.lyrics_page)
        lyrics_page_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_page_layout.setSpacing(0)

        lyrics_header_widget = QWidget()
        lyrics_header_widget.setProperty("class", "backgroundPrimary headerBorder")
        lyrics_header_layout = QHBoxLayout(lyrics_header_widget)
        lyrics_header_layout.setContentsMargins(16, 16, 16, 16)
        lyrics_header_layout.setSpacing(8)

        self.lyrics_header_icon = RoundedCoverLabel(self.cover_pixmaps["default"], 3)
        self.lyrics_header_icon.setFixedSize(48, 48)

        lyrics_text_vbox = QVBoxLayout()
        lyrics_text_vbox.setContentsMargins(0, 0, 0, 0)
        lyrics_text_vbox.setSpacing(2)

        self.lyrics_context_label = ElidedLabel(translate("Lyrics"))
        self.lyrics_context_label.setProperty("class", "textTertiary textColorTertiary")
        self.lyrics_name_label = ElidedLabel(translate("Track Title"))
        self.lyrics_name_label.setProperty("class", "textSecondary textColorPrimary")
        self.lyrics_artist_label = ElidedLabel(translate("Artist"))
        self.lyrics_artist_label.setProperty("class", "textTertiary textColorPrimary")

        lyrics_text_vbox.addWidget(self.lyrics_context_label)
        lyrics_text_vbox.addWidget(self.lyrics_name_label)
        lyrics_text_vbox.addWidget(self.lyrics_artist_label)

        lyrics_header_layout.addWidget(self.lyrics_header_icon)
        lyrics_header_layout.addLayout(lyrics_text_vbox)
        lyrics_header_layout.addStretch()

        self.btn_lyrics_dec = QPushButton()
        self.btn_lyrics_dec.setIcon(
            create_svg_icon(
                "assets/control/text_size_smaller.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.btn_lyrics_dec.setIconSize(QSize(24, 24))
        self.btn_lyrics_dec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics_dec.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_lyrics_dec,
            title = translate("Decrease font size"),
        )
        self.btn_lyrics_dec.clicked.connect(lambda: self._change_lyrics_font_size(-1))
        apply_button_opacity_effect(self.btn_lyrics_dec)
        lyrics_header_layout.addWidget(self.btn_lyrics_dec)

        self.btn_lyrics_inc = QPushButton()
        self.btn_lyrics_inc.setIcon(
            create_svg_icon(
                "assets/control/text_size_bigger.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.btn_lyrics_inc.setIconSize(QSize(24, 24))
        self.btn_lyrics_inc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics_inc.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_lyrics_inc,
            title = translate("Increase font size"),
        )
        self.btn_lyrics_inc.clicked.connect(lambda: self._change_lyrics_font_size(1))
        apply_button_opacity_effect(self.btn_lyrics_inc)
        lyrics_header_layout.addWidget(self.btn_lyrics_inc)

        self.lyrics_close_button = QPushButton("")
        set_custom_tooltip(
            self.lyrics_close_button,
            title = translate("Close"),
        )
        self.lyrics_close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lyrics_close_button.setProperty("class", "btnTool")
        self.lyrics_close_button.setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.lyrics_close_button.setIconSize(QSize(24, 24))
        apply_button_opacity_effect(self.lyrics_close_button)
        lyrics_header_layout.addWidget(self.lyrics_close_button)

        lyrics_page_layout.addWidget(lyrics_header_widget)

        self.lyrics_scroll_area = StyledScrollArea(self)
        self.lyrics_scroll_area.setWidgetResizable(True)
        self.lyrics_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.lyrics_scroll_area.setProperty("class", "backgroundPrimary")

        lyrics_scroll_widget = QWidget()
        lyrics_scroll_widget.setProperty("class", "backgroundPrimary")

        lyrics_text_layout = QVBoxLayout(lyrics_scroll_widget)
        lyrics_text_layout.setContentsMargins(24, 24, 24, 24)
        lyrics_text_layout.setSpacing(8)

        self.lyrics_text_label = StyledLabel(translate("Lyrics not found"))
        self.lyrics_text_label.setProperty("class", "textColorPrimary")
        self.lyrics_text_label.setWordWrap(True)
        self.lyrics_text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.lyrics_text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.lyrics_text_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        lyrics_text_layout.addWidget(self.lyrics_text_label)
        lyrics_text_layout.addStretch()

        self.lyrics_scroll_area.setWidget(lyrics_scroll_widget)
        lyrics_page_layout.addWidget(self.lyrics_scroll_area)

        self.right_stack.addWidget(self.lyrics_page)

        right_layout.addWidget(self.right_stack)

    def setup_vinyl_queue_view(self):
        mw = self.main_window
        self.vinyl_queue_container = QWidget(mw.vinyl_widget)
        self.vinyl_queue_container.setProperty("class", "backgroundPrimary")
        self.vinyl_queue_container.hide()

        layout = QVBoxLayout(self.vinyl_queue_container)
        layout.setContentsMargins(0, 0, 0, 198)
        layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setProperty("class", "backgroundPrimary headerBorder")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(8)

        back_button = QPushButton()
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            back_button,
            title = translate("Back"),
        )
        back_button.setIcon(
            create_svg_icon(
                "assets/control/arrow_back.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        back_button.setIconSize(QSize(24, 24))
        back_button.setFixedSize(36, 36)
        back_button.setProperty("class", "btnTool")
        back_button.clicked.connect(mw._vinyl_queue_go_back)
        apply_button_opacity_effect(back_button)

        title_label = QLabel(translate("Playback Queue"))
        title_label.setProperty("class", "textHeaderSecondary textColorPrimary")

        header_layout.addWidget(back_button)
        header_layout.addWidget(title_label, 1)
        layout.addWidget(header_widget)

        self.vinyl_queue_widget = QueueWidget(mw)
        delegate = QueueDelegate(self.vinyl_queue_widget)
        delegate.set_compact_mode(True)
        delegate.set_hide_artist_in_compact(True)
        self.vinyl_queue_widget.setItemDelegate(delegate)
        self.vinyl_queue_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.vinyl_queue_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        layout.addWidget(self.vinyl_queue_widget)

        mw.vinyl_widget.add_queue_page(self.vinyl_queue_container)

        delegate.playButtonClicked.connect(mw.player_controller.play_from_queue_action)
        self.vinyl_queue_widget.itemDoubleClicked.connect(
            mw.player_controller.play_from_queue_double_click
        )
        self.vinyl_queue_widget.playActionRequested.connect(
            mw.player_controller.play_from_queue_action
        )
        self.vinyl_queue_widget.customContextMenuRequested.connect(
            lambda pos: mw.action_handler.show_queue_context_menu(pos, self.vinyl_queue_widget)
        )
        self.vinyl_queue_widget.tracksDropped.connect(
            mw.action_handler.handle_tracks_dropped
        )
        self.vinyl_queue_widget.orderChanged.connect(
            lambda: mw.action_handler.handle_queue_reordered(self.vinyl_queue_widget)
        )
        self.vinyl_queue_widget.lyricsClicked.connect(self.lyricsClicked)
        self.vinyl_queue_widget.artistClicked.connect(self.artistClicked)

    def setup_vinyl_lyrics_view(self):
        """Creates a lyrics page for VinylWidget."""
        mw = self.main_window

        self.vinyl_lyrics_container = QWidget(mw.vinyl_widget)
        self.vinyl_lyrics_container.setProperty("class", "backgroundPrimary  borderBottom")
        self.vinyl_lyrics_container.hide()

        layout = QVBoxLayout(self.vinyl_lyrics_container)
        layout.setContentsMargins(0, 0, 0, 198)
        layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setProperty("class", "backgroundPrimary headerBorder")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(8)

        self.vinyl_lyrics_back_button = QPushButton()
        self.vinyl_lyrics_back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self.vinyl_lyrics_back_button,
            title = translate("Back"),
        )
        self.vinyl_lyrics_back_button.setIcon(
            create_svg_icon(
                "assets/control/arrow_back.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.vinyl_lyrics_back_button.setIconSize(QSize(24, 24))
        self.vinyl_lyrics_back_button.setFixedSize(36, 36)
        self.vinyl_lyrics_back_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.vinyl_lyrics_back_button)

        title_label = QLabel(translate("Lyrics"))
        title_label.setProperty("class", "textHeaderSecondary textColorPrimary")

        header_layout.addWidget(self.vinyl_lyrics_back_button)
        header_layout.addWidget(title_label, 1)

        self.btn_vinyl_lyrics_dec = QPushButton()
        self.btn_vinyl_lyrics_dec.setIcon(
            create_svg_icon(
                "assets/control/text_size_smaller.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.btn_vinyl_lyrics_dec.setIconSize(QSize(24, 24))
        self.btn_vinyl_lyrics_dec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_vinyl_lyrics_dec.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_vinyl_lyrics_dec,
            title = translate("Decrease font size"),
        )
        self.btn_vinyl_lyrics_dec.clicked.connect(
            lambda: self._change_lyrics_font_size(-1)
        )
        apply_button_opacity_effect(self.btn_vinyl_lyrics_dec)
        header_layout.addWidget(self.btn_vinyl_lyrics_dec)

        self.btn_vinyl_lyrics_inc = QPushButton()
        self.btn_vinyl_lyrics_inc.setIcon(
            create_svg_icon(
                "assets/control/text_size_bigger.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.btn_vinyl_lyrics_inc.setIconSize(QSize(24, 24))
        self.btn_vinyl_lyrics_inc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_vinyl_lyrics_inc.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_vinyl_lyrics_inc,
            title = translate("Increase font size"),
        )
        self.btn_vinyl_lyrics_inc.clicked.connect(
            lambda: self._change_lyrics_font_size(1)
        )
        apply_button_opacity_effect(self.btn_vinyl_lyrics_inc)
        header_layout.addWidget(self.btn_vinyl_lyrics_inc)

        self._update_lyrics_font_ui()

        layout.addWidget(header_widget)

        self.vinyl_lyrics_scroll_area = StyledScrollArea(self.vinyl_lyrics_container)
        self.vinyl_lyrics_scroll_area.setWidgetResizable(True)
        self.vinyl_lyrics_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.vinyl_lyrics_scroll_area.setProperty("class", "backgroundPrimary")

        lyrics_scroll_widget = QWidget()
        lyrics_scroll_widget.setProperty("class", "backgroundPrimary")
        lyrics_text_layout = QVBoxLayout(lyrics_scroll_widget)
        lyrics_text_layout.setContentsMargins(24, 24, 24, 24)
        lyrics_text_layout.setSpacing(8)

        self.vinyl_lyrics_text_label = StyledLabel(translate("Lyrics not found"))
        self.vinyl_lyrics_text_label.setProperty("class", "textColorPrimary")
        self.vinyl_lyrics_text_label.setWordWrap(True)
        self.vinyl_lyrics_text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.vinyl_lyrics_text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.vinyl_lyrics_text_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        lyrics_text_layout.addWidget(self.vinyl_lyrics_text_label)
        lyrics_text_layout.addStretch()
        self.vinyl_lyrics_scroll_area.setWidget(lyrics_scroll_widget)

        layout.addWidget(self.vinyl_lyrics_scroll_area)

        mw.vinyl_widget.add_lyrics_page(self.vinyl_lyrics_container)

    def update_vinyl_margins(self, is_panel_visible: bool):
        """
        Dynamically updates the bottom margin of vinyl queue and lyrics containers.
        Use this when toggling the control panel visibility.
        """
        bottom_margin = 198 if is_panel_visible else 0

        if hasattr(self, "vinyl_queue_container"):
            self.vinyl_queue_container.layout().setContentsMargins(0, 0, 0, bottom_margin)

        if hasattr(self, "vinyl_lyrics_container"):
            self.vinyl_lyrics_container.layout().setContentsMargins(0, 0, 0, bottom_margin)

    def _connect_signals(self):
        """Connects internal signals and forwards others."""
        self.more_button.clicked.connect(self.show_queue_header_menu)

        self.lyrics_close_button.clicked.connect(self.lyricsCloseRequested)
        self.vinyl_lyrics_back_button.clicked.connect(self.vinylLyricsCloseRequested)

        self.queue_widget.itemDelegate().playButtonClicked.connect(
            self.playActionRequested
        )
        self.queue_widget.itemDoubleClicked.connect(self.itemDoubleClicked)
        self.queue_widget.playActionRequested.connect(self.playActionRequested)
        self.queue_widget.customContextMenuRequested.connect(
            self.customContextMenuRequested
        )
        self.queue_widget.tracksDropped.connect(self.tracksDropped)
        self.queue_widget.orderChanged.connect(self.orderChanged)
        self.queue_widget.lyricsClicked.connect(self.lyricsClicked)

        self.queue_widget.artistClicked.connect(self.artistClicked)

        if hasattr(self, "vinyl_queue_widget"):
            self.vinyl_queue_widget.artistClicked.connect(self.artistClicked)

    def update_queue_header(
            self, name, context_text, details, pixmap_key, current_path
    ):
        """Updates the header with new information."""
        self.current_queue_context_path = current_path
        pixmap_to_show = self.cover_pixmaps.get(
            pixmap_key, self.cover_pixmaps["default"]
        )
        self.queue_header_icon.setPixmap(pixmap_to_show)

        if context_text:
            self.queue_context_label.setText(context_text)
            set_custom_tooltip(
                self.queue_context_label,
                title = context_text,
            )
            self.queue_context_label.show()

            self.queue_name_label.setText(name)
            set_custom_tooltip(
                self.queue_name_label,
                title = name,
            )
        else:
            self.queue_context_label.hide()
            self.queue_name_label.setText(name)
            set_custom_tooltip(
                self.queue_name_label,
                title = name,
            )

        self.queue_details_label.setText(details)
        set_custom_tooltip(
            self.queue_details_label,
            title = details,
        )

    def update_right_queue(self, tracks):
        """Clears and repopulates the queue widget."""
        self.queue_populate_timer.stop()
        self.queue_widget.clear()
        if not tracks:
            return
        self.queue_tracks_generator = (track for track in tracks)
        self.queue_populate_timer.start(0)

    def update_vinyl_queue(self, tracks):
        """Clears and repopulates the vinyl queue widget."""
        self.vinyl_queue_populate_timer.stop()
        self.vinyl_queue_widget.clear()
        if not tracks:
            return
        self.vinyl_queue_tracks_generator = (track for track in tracks)
        self.vinyl_queue_populate_timer.start(0)

    def _populate_queue_batch(self):
        """Populates the queue in batches to avoid freezing the UI."""
        for _ in range(50):
            try:
                track = next(self.queue_tracks_generator)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, track)
                item.setData(CustomRoles.IsCurrentRole, False)
                item.setData(CustomRoles.IsPlayingRole, False)
                self.queue_widget.addItem(item)
            except StopIteration:
                self.queue_populate_timer.stop()
                self.queuePopulated.emit()
                return

    def _populate_vinyl_queue_batch(self):
        """Populates the vinyl queue in batches."""
        for _ in range(50):
            try:
                track = next(self.vinyl_queue_tracks_generator)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, track)
                item.setData(CustomRoles.IsCurrentRole, False)
                item.setData(CustomRoles.IsPlayingRole, False)
                self.vinyl_queue_widget.addItem(item)
            except (StopIteration, TypeError):
                self.vinyl_queue_populate_timer.stop()
                self.vinyl_queue_tracks_generator = None
                self.queuePopulated.emit()
                return

    def _append_queue_batch(self):
        """Appends tracks to the queue in batches."""
        for _ in range(50):
            try:
                track = next(self.tracks_to_append_generator)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, track)
                item.setData(CustomRoles.IsCurrentRole, False)
                item.setData(CustomRoles.IsPlayingRole, False)
                self.queue_widget.addItem(item)
            except StopIteration:
                self.queue_append_timer.stop()
                self.queuePopulated.emit()
                return

    def append_tracks_to_queue_ui(self, tracks_to_add):
        """Starts the process of appending tracks to the UI."""
        self.queue_append_timer.stop()
        self.tracks_to_append_generator = (track for track in tracks_to_add)
        self.queue_append_timer.start(0)

    def show_queue_header_menu(self):
        """Shows the context menu for the queue header."""
        menu = TranslucentMenu(self)
        is_queue_empty = self.queue_widget.count() == 0

        compact_action = QAction(translate("Compact List"), self)
        compact_action.setCheckable(True)
        compact_action.setChecked(self.is_compact_mode)
        if self.is_compact_mode:
            compact_action.setIcon(self.check_icon)
        compact_action.triggered.connect(self.toggleCompactModeRequested)
        menu.addAction(compact_action)

        hide_artist_action = QAction(translate("Hide Artist Name"), self)
        hide_artist_action.setCheckable(True)
        hide_artist_action.setChecked(self.is_hiding_artist)
        if self.is_hiding_artist:
            hide_artist_action.setIcon(self.check_icon)
        hide_artist_action.triggered.connect(self.toggleHideArtistRequested)
        hide_artist_action.setEnabled(self.is_compact_mode)
        menu.addAction(hide_artist_action)

        show_cover_action = QAction(translate("Show Cover Art"), self)
        show_cover_action.setCheckable(True)
        show_cover_action.setChecked(self.is_showing_cover)
        if self.is_showing_cover:
            show_cover_action.setIcon(self.check_icon)
        show_cover_action.triggered.connect(self.toggleShowCoverRequested)
        menu.addAction(show_cover_action)

        autoplay_action = QAction(translate("Autoplay on Add"), self)
        autoplay_action.setCheckable(True)
        autoplay_action.setChecked(self.main_window.autoplay_on_queue)
        if self.main_window.autoplay_on_queue:
            autoplay_action.setIcon(self.check_icon)
        autoplay_action.triggered.connect(self.toggleAutoplayOnQueueRequested.emit)
        menu.addAction(autoplay_action)

        menu.addSeparator()

        shake_action = QAction(translate("Shake Queue"), self)
        shake_action.setIcon(
            QIcon(
                create_svg_icon(
                    "assets/control/shake_queue.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
        )
        shake_action.triggered.connect(self.shakeQueueRequested.emit)
        shake_action.setEnabled(self.queue_widget.count() > 1)
        menu.addAction(shake_action)

        menu.addSeparator()

        clear_action = QAction(translate("Clear Queue"), self)
        clear_action.triggered.connect(self.clearQueueRequested)
        menu.addAction(clear_action)

        save_action = QAction(translate("Save as Playlist"), self)
        save_action.triggered.connect(self.saveQueueRequested)
        menu.addAction(save_action)

        mixtape_action = QAction(translate("Create Mixtape"), self)
        if hasattr(self.main_window, 'mixtape_icon'):
            mixtape_action.setIcon(self.main_window.mixtape_icon)
        mixtape_action.triggered.connect(self.createMixtapeRequested.emit)
        menu.addAction(mixtape_action)

        clear_action.setEnabled(not is_queue_empty)
        save_action.setEnabled(not is_queue_empty)

        if self.current_queue_context_path:
            menu.addSeparator()
            delete_action = QAction(translate("Delete Playlist"), self)
            delete_action.triggered.connect(
                lambda: self.deletePlaylistRequested.emit(
                    self.current_queue_context_path
                )
            )
            menu.addAction(delete_action)

        self.more_button.setProperty("active", True)
        self.more_button.style().unpolish(self.more_button)
        self.more_button.style().polish(self.more_button)

        menu.exec(self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))

        self.more_button.setProperty("active", False)
        self.more_button.style().unpolish(self.more_button)
        self.more_button.style().polish(self.more_button)

    def apply_view_options(self, is_compact, hide_artist, show_cover):
        """Applies visual styles to the delegate."""
        self.is_compact_mode = is_compact
        self.is_hiding_artist = hide_artist
        self.is_showing_cover = show_cover

        delegate = self.queue_widget.itemDelegate()
        if isinstance(delegate, QueueDelegate):
            delegate.set_compact_mode(is_compact)
            delegate.set_hide_artist_in_compact(hide_artist)
            delegate.set_show_cover(show_cover)
            self.queue_widget.scheduleDelayedItemsLayout()
            self.queue_widget.viewport().update()

        vinyl_delegate = self.vinyl_queue_widget.itemDelegate()
        if isinstance(vinyl_delegate, QueueDelegate):
            vinyl_delegate.set_compact_mode(True)
            vinyl_delegate.set_hide_artist_in_compact(hide_artist)
            vinyl_delegate.set_show_cover(show_cover)
            self.vinyl_queue_widget.scheduleDelayedItemsLayout()
            self.vinyl_queue_widget.viewport().update()

    def apply_compact_mode(self, is_compact, hide_artist):
        """
        This method is now a wrapper for apply_view_options for backward compatibility.
        """
        self.apply_view_options(is_compact, hide_artist, self.is_showing_cover)

    def updateVinylLyricsPage(self, track_data):
        """
        Updates the lyrics widget in "Vinyl" mode with track data.
        """
        if not track_data:
            lyrics = translate("Lyrics not found")
        else:
            lyrics = track_data.get("lyrics")
            if not lyrics:
                lyrics = translate("Lyrics not found")

        self.vinyl_lyrics_text_label.setText(lyrics.replace("\n", "<br>"))
        self.vinyl_lyrics_scroll_area.verticalScrollBar().setValue(0)

    def toggleLyricsView(self, show, track_data=None):
        """
        Switches the QStackedWidget to the lyrics or queue widget.
        """
        if show and track_data:
            self.updateLyricsPage(track_data)
            self.right_stack.setCurrentIndex(1)
        else:
            self.right_stack.setCurrentIndex(0)

    def updateLyricsPage(self, track_data):
        """
        Updates the lyrics widget with current track data.
        """
        if not track_data:
            return

        artwork_data = track_data.get("artwork")
        pixmap_to_show = self.main_window.ui_manager.components.get_pixmap(
            artwork_data, 48
        )
        self.lyrics_header_icon.setPixmap(pixmap_to_show)

        track_title = track_data.get("title", translate("Track Title"))
        artist_name = track_data.get("artist", translate("Artist"))

        self.lyrics_name_label.setText(track_title)
        set_custom_tooltip(
            self.lyrics_name_label,
            title = track_title,
        )

        self.lyrics_artist_label.setText(artist_name)
        set_custom_tooltip(
            self.lyrics_artist_label,
            title = artist_name,
        )

        lyrics = track_data.get("lyrics")
        if lyrics:
            self.lyrics_text_label.setText(lyrics.replace("\n", "<br>"))
        else:
            self.lyrics_text_label.setText(translate("Lyrics not found"))

        self.lyrics_scroll_area.verticalScrollBar().setValue(0)

    def _change_lyrics_font_size(self, delta):
        """
        Changes the font size level by delta (+1 or -1).
        """
        new_level = self.lyrics_font_level + delta
        if 0 <= new_level <= self.max_lyrics_font_level:
            self.lyrics_font_level = new_level
            self._update_lyrics_font_ui()

    def _update_lyrics_font_ui(self):
        """
        Applies font size to labels and updates button states.
        """
        new_size = self.lyrics_base_font_size + (self.lyrics_font_level * 2)
        style = f"font-size: {new_size}px;"

        if hasattr(self, "lyrics_text_label"):
            self.lyrics_text_label.setStyleSheet(style)

        if hasattr(self, "vinyl_lyrics_text_label"):
            self.vinyl_lyrics_text_label.setStyleSheet(style)

        can_decrease = self.lyrics_font_level > 0
        if hasattr(self, "btn_lyrics_dec"):
            self.btn_lyrics_dec.setEnabled(can_decrease)
        if hasattr(self, "btn_vinyl_lyrics_dec"):
            self.btn_vinyl_lyrics_dec.setEnabled(can_decrease)

        can_increase = self.lyrics_font_level < self.max_lyrics_font_level
        if hasattr(self, "btn_lyrics_inc"):
            self.btn_lyrics_inc.setEnabled(can_increase)
        if hasattr(self, "btn_vinyl_lyrics_inc"):
            self.btn_vinyl_lyrics_inc.setEnabled(can_increase)

    def refresh_queue_data(self):
        """
        Updates metadata (UserRole) for all items in queue widgets.
        This ensures that if lyrics have been added or titles changed,
        the queue list will reflect the changes immediately.
        """
        mw = self.main_window

        def _refresh_list_widget(widget):
            """
            Iterates through a given QListWidget, fetches fresh metadata
            for each track from the DataManager, updates the item's UserRole,
            and forces a UI repaint to reflect any changes.
            """
            for i in range(widget.count()):
                item = widget.item(i)
                track_data = item.data(Qt.ItemDataRole.UserRole)
                if not track_data:
                    continue

                path = track_data.get("path")
                fresh_data = mw.data_manager.get_track_by_path(path)

                if fresh_data:
                    item.setData(Qt.ItemDataRole.UserRole, fresh_data)

            if hasattr(widget.itemDelegate(), "_rect_cache"):
                widget.itemDelegate()._rect_cache.clear()

            widget.viewport().update()

        if hasattr(self, "queue_widget"):
            _refresh_list_widget(self.queue_widget)

        if hasattr(self, "vinyl_queue_widget"):
            _refresh_list_widget(self.vinyl_queue_widget)