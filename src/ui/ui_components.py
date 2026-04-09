"""
Vinyller — Main window components
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
from functools import partial

from PyQt6.QtCore import (
    QEvent, QEasingCurve, QObject, QPoint, QPropertyAnimation, QSize, Qt, QTimer
)
from PyQt6.QtGui import (
    QAction, QPalette, QPixmap
)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QSizePolicy, QLayout
)

from src.core.hotkey_manager import HotkeyManager
from src.ui.control_panel import ControlPanel
from src.ui.custom_base_widgets import (
    IconSpaceButton, StyledLineEdit, StyledScrollArea,
    TranslucentMenu, StyledToolButton, ShadowPopup, set_custom_tooltip
)
from src.ui.custom_cards import CardWidget, CardWidgetLyrics, DetailedAlbumCard, DetailedPlaylistCard
from src.ui.custom_classes import (
    AccentIconFactory, apply_button_opacity_effect,
    ClickableSeparatorLabel,
    ElidedLabel, OverlayWidget, RadialProgressButton,
    RotatingIconLabel, ViewMode, apply_label_opacity_effect
)
from src.ui.custom_dialogs import (
    CoverViewerWidget, ChangedFilesDialog
)
from src.ui.mode_vinyl import VinylWidget
from src.ui.ui_right_panel import RightPanel
from src.ui.ui_tabs import TabFactory
from src.utils import theme
from src.utils.random_greetings import get_random_greeting, get_random_waiting
from src.utils.utils import (
    create_svg_icon, format_time,
    resource_path
)
from src.utils.utils_translator import translate


class PendingUpdatesPopup(ShadowPopup):
    """
    A popup widget that notifies the user when library updates, metadata changes,
    or new application versions are available.
    """
    def __init__(self, parent = None, update_callback = None, hide_callback = None, postpone_callback = None):
        """
        Initializes the pending updates popup.

        Args:
            parent (QWidget, optional): The parent widget.
            update_callback (callable, optional): Invoked when the 'Update' button is clicked.
            hide_callback (callable, optional): Invoked when the popup is hidden or closed.
            postpone_callback (callable, optional): Invoked when the 'Later' button is clicked to defer the update.
        """
        super().__init__(parent)
        self.hide_callback = hide_callback
        self.update_callback = update_callback
        self.postpone_callback = postpone_callback

        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        if parent:
            parent.removeEventFilter(self)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        content_container = QWidget()
        content_container.setProperty("class", "pendingUpdatesWidget")
        content_container.setFixedWidth(
            352 - self.layout.contentsMargins().left() - self.layout.contentsMargins().right())

        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        layout = QVBoxLayout(content_container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.title_label = QLabel(translate("Library update required"))
        self.title_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        self.title_label.setWordWrap(True)
        self.title_label.setMargin(0)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header_layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignTop)

        close_button = QPushButton()
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setIcon(
            create_svg_icon("assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16))
        )
        close_button.setFixedSize(24, 24)
        close_button.setIconSize(QSize(16, 16))
        close_button.setProperty("class", "btnListAction")
        set_custom_tooltip(
            close_button,
            title = translate("Close"),
        )
        apply_button_opacity_effect(close_button)

        close_button.clicked.connect(self.hide)

        header_layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_layout)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.message_label.setProperty("class", "textSecondary textColorPrimary")
        layout.addWidget(self.message_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        self.update_btn = QPushButton(translate("Update"))
        self.update_btn.setProperty("class", "btnText")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.clicked.connect(self._on_update_clicked)
        buttons_layout.addWidget(self.update_btn)

        self.changes_btn = QPushButton(translate("Changes"))
        self.changes_btn.setProperty("class", "btnText")
        self.changes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.changes_btn.clicked.connect(self._show_changes_dialog)
        self.changes_btn.hide()
        buttons_layout.addWidget(self.changes_btn)

        self.later_btn = QPushButton(translate("Later"))
        self.later_btn.setProperty("class", "btnText")
        self.later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.later_btn.clicked.connect(self._on_later_clicked)
        self.later_btn.hide()
        buttons_layout.addWidget(self.later_btn)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        self.layout.addWidget(content_container)

    def set_title(self, text):
        """
        Sets the primary title of the popup window.
        """
        self.title_label.setText(text)

    def set_changes_button_visible(self, visible):
        """
        Toggles the visibility of the changes details button.
        """
        self.changes_btn.setVisible(visible)

    def set_later_button_visible(self, visible):
        """
        Toggles the visibility of the 'Later' button, used for deferring app updates.
        """
        self.later_btn.setVisible(visible)

    def _on_update_clicked(self):
        """
        Handles the update button click, hiding the popup and triggering the update callback.
        """
        self.hide()
        if self.update_callback:
            self.update_callback()

    def _show_changes_dialog(self):
        """
        Hides the popup and displays the detailed dialog showing modified or removed files.
        """
        self.hide()

        parent = self.parent()
        if not parent:
            return

        changed_files = getattr(parent, "pending_added_modified_paths", [])
        removed_files = getattr(parent, "pending_removed_paths", [])

        dialog = ChangedFilesDialog(changed_files, removed_files, parent)
        dialog.exec()

    def _on_later_clicked(self):
        """
        Handles the 'Later' button click event. Hides the popup and triggers the postpone callback.
        """
        self.hide()
        if self.postpone_callback:
            self.postpone_callback()

    def set_message(self, text):
        """
        Sets the main text message displayed in the popup.
        """
        self.message_label.setText(text)

    def set_app_update_mode(self, is_app_update, github_link = ""):
        """
        Configures the primary action button for either an app download or a library update.
        """
        if is_app_update:
            self.update_btn.setText(translate("Go to GitHub"))
            set_custom_tooltip(
                self.update_btn,
                title = translate("Open in browser"),
                text = github_link,
                activity_type = "external",
            )
        else:
            self.update_btn.setText(translate("Update"))
            set_custom_tooltip(
                self.update_btn,
                title = translate("Update library")
            )

    def hideEvent(self, event):
        """
        Handles the hide event, invoking the hide callback if defined.
        """
        if self.hide_callback:
            self.hide_callback()
        super().hideEvent(event)


class ToastNotification(ShadowPopup):
    """
    Semi-transparent floating notification widget with an icon and text.
    Inherits ShadowPopup for consistent shadow and styling.
    """

    def __init__(self, parent = None):
        """
        Initializes the toast notification widget.

        Args:
            parent (QWidget, optional): The parent widget to overlay the toast on.
        """
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.setWindowModality(Qt.WindowModality.NonModal)
        if parent:
            self.setParent(parent)

        content_container = QWidget()
        content_container.setStyleSheet("background: transparent;")

        inner_layout = QHBoxLayout(content_container)
        inner_layout.setContentsMargins(16, 16, 16, 16)
        inner_layout.setSpacing(16)
        inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        icon_pixmap = create_svg_icon(
            "assets/control/search_album.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24)
        ).pixmap(24, 24)
        self.icon_label.setPixmap(icon_pixmap)
        inner_layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(12)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_label = QLabel(translate("Sorting records..."))
        header_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        text_layout.addWidget(header_label)

        self.wow_label = QLabel(get_random_waiting())
        self.wow_label.setProperty("class", "textSecondary textColorPrimary")
        self.wow_label.setMinimumWidth(400)
        self.wow_label.setWordWrap(True)
        self.wow_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_layout.addWidget(self.wow_label)

        self.text_label = QLabel()
        self.text_label.setProperty("class", "textPrimary textColorPrimary")
        text_layout.addWidget(self.text_label)

        inner_layout.addLayout(text_layout)
        self.layout.addWidget(content_container)
        self.hide()

    def show_message(self, text, duration = 2000):
        """
        Displays the toast notification with the given text for a specified duration.
        """
        if hasattr(self, 'wow_label'):
            self.wow_label.setText(get_random_waiting())

        self.text_label.setText(text)

        self.setProperty("should_be_visible", True)

        self.layout.activate()
        self.wow_label.adjustSize()
        self.adjustSize()
        self.update_position()

        self.show()
        self.raise_()

        if duration:
            QTimer.singleShot(duration, self._on_timeout)

    def hide(self):
        """
        Overrides the hide method to reset the visibility flag for the event filter.
        """
        self.setProperty("should_be_visible", False)
        super().hide()

    def _on_timeout(self):
        """
        Automatically conceals the toast after the configured duration elapses.
        """
        self.hide()

    def update_position(self):
        """
        Calculates and applies the position of the toast relative to its parent window.
        """
        if self.parent():
            parent_pos = self.parent().mapToGlobal(QPoint(0, 0))

            margins = self.layout.contentsMargins()

            x = parent_pos.x() + 72 - margins.left()
            y = parent_pos.y() + 72 - margins.top()

            self.move(x, y)


class SearchInteractionFilter(QObject):
    """
    Event filter to manage opacity effects based on hover and focus states for search interaction.
    """
    def __init__(self, target_effect, parent=None):
        """
        Initializes the search interaction filter.

        Args:
            target_effect (QGraphicsOpacityEffect): The opacity effect to modify.
            parent (QObject, optional): The parent object.
        """
        super().__init__(parent)
        self.target_effect = target_effect
        self.is_hovered = False
        self.is_focused = False

    def _update_opacity(self):
        """
        Updates the target effect's opacity based on the current hover and focus states.
        """
        if self.is_hovered or self.is_focused:
            self.target_effect.setOpacity(1.0)
        else:
            self.target_effect.setOpacity(0.5)

    def eventFilter(self, obj, event):
        """
        Intercepts events to track hover and focus changes, updating opacity accordingly.
        """
        if event.type() == QEvent.Type.Enter:
            self.is_hovered = True
            self._update_opacity()
        elif event.type() == QEvent.Type.Leave:
            self.is_hovered = False
            self._update_opacity()
        elif event.type() == QEvent.Type.FocusIn:
            self.is_focused = True
            self._update_opacity()
        elif event.type() == QEvent.Type.FocusOut:
            self.is_focused = False
            self._update_opacity()

        return super().eventFilter(obj, event)


class NavBarResizeFilter(QObject):
    """
    Tracks resizing of the navigation panel and hides buttons
    that don't fit in height into the 'More' menu.
    """

    def __init__(
        self,
        nav_bar,
        collapsible_buttons,
        more_button,
        fixed_top_widgets,
        fixed_bottom_widgets,
        mw,
    ):
        """
        Initializes the navigation bar resize filter with required layout elements.
        """
        super().__init__(nav_bar)
        self.nav_bar = nav_bar
        self.collapsible_buttons = collapsible_buttons
        self.more_button = more_button
        self.fixed_top_widgets = fixed_top_widgets
        self.fixed_bottom_widgets = fixed_bottom_widgets
        self.mw = mw
        self.button_height = 50

        self.nav_bar.setMinimumHeight(0)

    def eventFilter(self, obj, event):
        """
        Intercepts resize events on the navigation bar to trigger layout recalculation.
        """
        if obj == self.nav_bar and event.type() == QEvent.Type.Resize:
            self.recalc_layout(event.size().height())
        return super().eventFilter(obj, event)

    def recalc_layout(self, total_height=None):
        """
        Recalculates the visibility of navigation buttons based on available vertical space.
        """
        if total_height is None:
            total_height = self.nav_bar.height()

        if total_height <= 0:
            return

        fixed_height = 0
        for w in self.fixed_top_widgets:
            if not w.isHidden():
                fixed_height += w.height()

        bottom_height = 0
        for w in self.fixed_bottom_widgets:
            if not w.isHidden():
                bottom_height += w.height()

        allowed_buttons = []
        for btn in self.collapsible_buttons:
            if btn == self.mw.history_button and self.mw.playback_history_mode == 0:
                btn.hide()
                continue
            if btn == self.mw.charts_button and not self.mw.collect_statistics:
                btn.hide()
                continue
            allowed_buttons.append(btn)

        available_space = total_height - fixed_height - bottom_height - 20
        total_needed = len(allowed_buttons) * self.button_height

        if total_needed <= available_space:
            self.more_button.hide()
            for btn in allowed_buttons:
                btn.show()
            self._update_more_button_state(has_hidden_active=False)
        else:
            available_for_buttons = available_space - self.button_height
            count_visible = max(0, int(available_for_buttons // self.button_height))

            hidden_buttons = []
            has_hidden_active = False

            for i, btn in enumerate(allowed_buttons):
                if i < count_visible:
                    btn.show()
                else:
                    btn.hide()
                    hidden_buttons.append(btn)
                    if btn.isChecked():
                        has_hidden_active = True

            self.more_button.show()
            self._update_more_button_state(has_hidden_active)
            self.more_button.hidden_buttons = hidden_buttons

        if self.nav_bar.layout():
            self.nav_bar.layout().activate()

        if self.mw and self.mw.isVisible():
            self.mw.updateGeometry()

    def _update_more_button_state(self, has_hidden_active):
        """
        Updates the appearance and active state of the 'More' button.
        """
        self.more_button.setChecked(has_hidden_active)

        accent_color = theme.get_qcolor(theme.COLORS["ACCENT"])
        r, g, b = accent_color.red(), accent_color.green(), accent_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        is_dark_theme = theme.COLORS.get("IS_DARK", False)

        if brightness > 160 and is_dark_theme:
            nav_icon_active = theme.COLORS["SECONDARY"]
        elif brightness > 220:
            nav_icon_active = theme.COLORS["PRIMARY"]
        elif brightness > 160:
            nav_icon_active = theme.COLORS["PRIMARY"]
        elif brightness < 160 and is_dark_theme:
            nav_icon_active = theme.COLORS["WHITE"]
        else:
            nav_icon_active = theme.COLORS["ACCENT"]

        color = nav_icon_active if has_hidden_active else theme.COLORS["PRIMARY"]

        self.more_button.setIcon(
            create_svg_icon("assets/control/more_horiz.svg", color, QSize(24, 24))
        )


class UiComponents:
    """
    Class responsible for creating and configuring
    user interface components.
    """

    def __init__(self, main_window, manager):
        """
        Initializes the UI components manager and preloads common resources like icons and pixmaps.
        """
        self.main_window = main_window
        self.manager = manager

        self.charts_tab_index = -1
        self.search_tab_index = -1

        default_missing_cover = "assets/view/missing_cover.png"
        missing_cover_path = theme.COLORS.get("MISSING_COVER", default_missing_cover)
        self.missing_cover_pixmap = QPixmap(resource_path(missing_cover_path))

        self.favorite_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/favorite_big.png"), 128
        )

        self.playlist_pixmap = AccentIconFactory.create(
            resource_path("assets/view/playlist_big.png"), 128
        )
        self.history_pixmap_128 = AccentIconFactory.create(
            resource_path("assets/view/history_big.png"), 128
        )

        self.favorite_playlist_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/playlist_big.png"), 128
        )
        self.favorite_artist_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/artist_big.png"), 128
        )
        self.favorite_album_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/album_big.png"), 128
        )
        self.favorite_genre_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/genre_big.png"), 128
        )
        self.favorite_composer_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/composer_big.png"), 128
        )
        self.favorite_folder_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/folder_big.png"), 128
        )

        self.top_track_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/track_big.png"), 128
        )
        self.top_artist_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/artist_big.png"), 128
        )
        self.top_album_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/album_big.png"), 128
        )
        self.top_archive_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/archive_big.png"), 128
        )
        self.top_genre_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/genre_big.png"), 128
        )
        self.top_folder_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/folder_big.png"), 128
        )
        self.top_playlist_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/playlist_big.png"), 128
        )
        self.top_composer_cover_pixmap = AccentIconFactory.create(
            resource_path("assets/view/composer_big.png"), 128
        )

        dpr = self.main_window.devicePixelRatio()
        base_size = 16

        def get_retina_icon_pixmap(svg_path):
            """
            Generates a high-resolution (retina) pixmap from an SVG icon path
            based on the current device pixel ratio.
            """
            icon_size = QSize(base_size, base_size)
            icon = create_svg_icon(svg_path, theme.COLORS["WHITE"], icon_size)

            phy_w = int(base_size * dpr)
            phy_h = int(base_size * dpr)
            pixmap = icon.pixmap(QSize(phy_w, phy_h))

            pixmap.setDevicePixelRatio(dpr)
            return pixmap

        self.artist_icon_pixmap = get_retina_icon_pixmap(
            "assets/control/artist_inverted.svg"
        )
        self.genre_icon_pixmap = get_retina_icon_pixmap(
            "assets/control/genre_inverted.svg"
        )
        self.playlist_icon_pixmap = get_retina_icon_pixmap(
            "assets/control/playlist_inverted.svg"
        )
        self.folder_icon_pixmap = get_retina_icon_pixmap(
            "assets/control/folder_inverted.svg"
        )
        self.album_icon_pixmap = get_retina_icon_pixmap(
            "assets/control/album_inverted.svg"
        )
        self.composer_icon_pixmap = get_retina_icon_pixmap(
            "assets/control/composer_inverted.svg"
        )
        self.cue_icon_pixmap = get_retina_icon_pixmap("assets/control/cue_inverted.svg")

        self.my_wave_animation_frames = [
            create_svg_icon(
                f"assets/animation/track/now_playing_{i}.svg",
                theme.COLORS["ACCENT"],
                QSize(20, 20),
            ).pixmap(20, 20)
            for i in range(1, 9)
        ]

    def create_lyrics_card(self, track_data, snippet, pixmap, search_query):
        """
        Creates and returns a card widget specifically designed to show lyrics search results.
        """
        return CardWidgetLyrics(
            track_data, snippet, pixmap, search_query, self.main_window
        )

    def create_navigable_section(
        self, title, content_widget, on_see_all_slot=None, header_icon_name=None
    ):
        """
        Creates a section with title, navigation buttons (left/right) and a hidden scrollbar.
        Repeats the suggestion_block design.
        """

        container = QWidget()
        container.setProperty("class", "suggestionBlock")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(1, 8, 1, 8)
        layout.setSpacing(8)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 0, 7, 0)
        header_layout.setSpacing(8)

        if header_icon_name:
            icon_label = QLabel()
            if not header_icon_name.endswith(".svg"):
                header_icon_name += ".svg"

            icon_path = f"assets/control/{header_icon_name}"
            icon_pixmap = create_svg_icon(
                icon_path, theme.COLORS["PRIMARY"], QSize(24, 24)
            ).pixmap(24, 24)
            icon_label.setPixmap(icon_pixmap)

            header_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        scroll_left_button = QPushButton("")
        scroll_left_button.setCursor(Qt.CursorShape.PointingHandCursor)
        scroll_left_button.setIcon(
            create_svg_icon(
                "assets/control/arrow_left.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        scroll_left_button.setIconSize(QSize(24, 24))
        scroll_left_button.setFixedHeight(36)
        scroll_left_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(scroll_left_button)
        header_layout.addWidget(scroll_left_button)

        scroll_right_button = QPushButton("")
        scroll_right_button.setCursor(Qt.CursorShape.PointingHandCursor)
        scroll_right_button.setIcon(
            create_svg_icon(
                "assets/control/arrow_right.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        scroll_right_button.setIconSize(QSize(24, 24))
        scroll_right_button.setFixedHeight(36)
        scroll_right_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(scroll_right_button)
        header_layout.addWidget(scroll_right_button)

        if on_see_all_slot:
            see_all_button = QPushButton(translate("See all"))
            see_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                see_all_button,
                title = translate("Go to"),
                text = title,
            )
            see_all_button.setFixedHeight(36)
            see_all_button.setProperty("class", "btnToolText")
            see_all_button.clicked.connect(on_see_all_slot)
            apply_button_opacity_effect(see_all_button)
            header_layout.addWidget(see_all_button)

        layout.addWidget(header_widget)

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setProperty("class", "backgroundPrimary")

        content_widget.setProperty("class", "backgroundPrimary")
        scroll_area.setWidget(content_widget)

        scroll_area.setFixedHeight(content_widget.sizeHint().height())

        layout.addWidget(scroll_area)

        scrollbar = scroll_area.horizontalScrollBar()
        scroll_area.animation = None

        def scroll(direction):
            """
            Animates the horizontal scrollbar to smoothly scroll the area in the given direction.
            """
            try:
                step = 300
                current_value = scrollbar.value()
                target_value = current_value + (step * direction)

                scroll_area.animation = QPropertyAnimation(scrollbar, b"value")
                scroll_area.animation.setDuration(300)
                scroll_area.animation.setStartValue(current_value)
                scroll_area.animation.setEndValue(target_value)
                scroll_area.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
                scroll_area.animation.start()
            except RuntimeError:
                pass

        def update_button_states():
            """
            Updates the enabled state of the left and right scroll buttons
            based on the current scrollbar position.
            """
            try:
                scroll_left_button.setEnabled(scrollbar.value() > scrollbar.minimum())
                scroll_right_button.setEnabled(scrollbar.value() < scrollbar.maximum())
            except RuntimeError:
                pass

        scroll_left_button.clicked.connect(lambda: scroll(-1))
        scroll_right_button.clicked.connect(lambda: scroll(1))

        scrollbar.rangeChanged.connect(update_button_states)
        scrollbar.valueChanged.connect(update_button_states)

        QTimer.singleShot(0, update_button_states)

        return container

    def create_suggestion_block(self, suggestion_type, refresh_callback):
        """
        Generates a horizontal block containing a selection of random items (artists, albums, etc.) as suggestions.
        """
        mw = self.main_window
        if mw.data_manager.is_empty():
            return None

        block = QWidget()
        block.setProperty("class", "suggestionBlock")
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(1, 8, 1, 8)
        block_layout.setSpacing(8)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 0, 7, 0)
        header_layout.setSpacing(8)

        title_label = QLabel(translate("Have you heard this?!"))
        title_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        scroll_left_button = QPushButton("")
        scroll_left_button.setCursor(Qt.CursorShape.PointingHandCursor)
        scroll_left_button.setIcon(
            create_svg_icon(
                "assets/control/arrow_left.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        scroll_left_button.setFixedHeight(36)
        scroll_left_button.setIconSize(QSize(24, 24))
        scroll_left_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(scroll_left_button)
        header_layout.addWidget(scroll_left_button)

        scroll_right_button = QPushButton("")
        scroll_right_button.setCursor(Qt.CursorShape.PointingHandCursor)
        scroll_right_button.setIcon(
            create_svg_icon(
                "assets/control/arrow_right.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        scroll_right_button.setFixedHeight(36)
        scroll_right_button.setIconSize(QSize(24, 24))
        scroll_right_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(scroll_right_button)
        header_layout.addWidget(scroll_right_button)

        refresh_button = QPushButton("")
        refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            refresh_button,
            title = translate("Other options"),
            text = translate("Update the list and show new suggestions"),
        )
        refresh_button.setIcon(
            create_svg_icon(
                "assets/control/reload.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        refresh_button.setFixedHeight(36)
        refresh_button.setIconSize(QSize(24, 24))
        refresh_button.setProperty("class", "btnTool")
        refresh_button.clicked.connect(refresh_callback)
        apply_button_opacity_effect(refresh_button)
        header_layout.addWidget(refresh_button)

        block_layout.addWidget(header_widget)

        items_to_show = []
        source_list = []
        card_creation_type = suggestion_type

        if suggestion_type == "artist":
            source_list = mw.data_manager.sorted_artists
        elif suggestion_type == "album":
            source_list = mw.data_manager.sorted_albums
        elif suggestion_type == "genre":
            source_list = mw.data_manager.sorted_genres
        elif suggestion_type == "composer":
            source_list = mw.data_manager.sorted_composers
        elif suggestion_type == "track":
            source_list = mw.data_manager.sorted_albums
            card_creation_type = "album"

        if source_list:
            items_to_show = random.sample(source_list, k=min(10, len(source_list)))

        if not items_to_show:
            return None

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFixedHeight(72)
        scroll_area.setProperty("class", "backgroundPrimary")

        scroll_content = QWidget()
        scroll_content.setProperty("class", "backgroundPrimary")
        suggestions_layout = QHBoxLayout(scroll_content)
        suggestions_layout.setContentsMargins(8, 0, 8, 0)
        suggestions_layout.setSpacing(8)

        for item_data, data_dict in items_to_show:
            card_widget = None
            suggestion_data = data_dict.copy()

            if card_creation_type == "artist":
                if "artworks" in suggestion_data and suggestion_data["artworks"]:
                    suggestion_data["artworks"] = [suggestion_data["artworks"][0]]
                card_widget = self.create_artist_widget(
                    item_data, suggestion_data, ViewMode.TILE_SMALL
                )
                card_widget.activated.connect(self.manager.show_artist_albums)

            elif card_creation_type == "album":
                card_widget = self.create_album_widget(
                    item_data, data_dict, ViewMode.TILE_SMALL
                )
                card_widget.activated.connect(
                    self.manager.navigate_to_album_tab_and_show
                )

            elif card_creation_type == "genre":
                if "artworks" in suggestion_data and suggestion_data["artworks"]:
                    suggestion_data["artworks"] = [suggestion_data["artworks"][0]]
                card_widget = self.create_genre_widget(
                    item_data, suggestion_data, ViewMode.TILE_SMALL
                )
                card_widget.activated.connect(self.manager.show_genre_albums)

            elif card_creation_type == "composer":
                if "artworks" in suggestion_data and suggestion_data["artworks"]:
                    suggestion_data["artworks"] = [suggestion_data["artworks"][0]]
                card_widget = self.create_composer_widget(
                    item_data, suggestion_data, ViewMode.TILE_SMALL
                )
                card_widget.activated.connect(self.manager.show_composer_albums)

            if card_widget:
                card_widget.playClicked.connect(mw.player_controller.smart_play)
                card_widget.contextMenuRequested.connect(
                    mw.action_handler.show_context_menu
                )
                suggestions_layout.addWidget(card_widget, 0, Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(scroll_content)
        block_layout.addWidget(scroll_area)

        scrollbar = scroll_area.horizontalScrollBar()
        scroll_area.animation = None

        def scroll(direction):
            try:
                step = 280 + 24
                current_value = scrollbar.value()
                target_value = current_value + (step * direction)

                scroll_area.animation = QPropertyAnimation(scrollbar, b"value")
                scroll_area.animation.setDuration(300)
                scroll_area.animation.setStartValue(current_value)
                scroll_area.animation.setEndValue(target_value)
                scroll_area.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
                scroll_area.animation.start()
            except RuntimeError:
                pass

        def update_button_states():
            try:
                scroll_left_button.setEnabled(scrollbar.value() > scrollbar.minimum())
                scroll_right_button.setEnabled(scrollbar.value() < scrollbar.maximum())
            except RuntimeError:
                pass

        scroll_left_button.clicked.connect(lambda: scroll(-1))
        scroll_right_button.clicked.connect(lambda: scroll(1))
        scrollbar.rangeChanged.connect(update_button_states)
        scrollbar.valueChanged.connect(update_button_states)

        QTimer.singleShot(0, update_button_states)

        return block

    def setup_ui(self):
        """
        Creates and configures all foundational user interface layouts and widgets.
        """
        mw = self.main_window

        central_widget = QWidget()
        mw.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        mw.overlay_widget = OverlayWidget(central_widget)
        mw.vinyl_widget = VinylWidget(mw.player)

        main_view_container = QWidget()
        main_view_layout = QHBoxLayout(main_view_container)
        main_view_layout.setContentsMargins(0, 0, 0, 0)
        main_view_layout.setSpacing(0)

        right_block_widget = QWidget()
        right_block_layout = QVBoxLayout(right_block_widget)
        right_block_layout.setContentsMargins(0, 0, 0, 0)
        right_block_layout.setSpacing(0)

        top_bar_widget = QWidget()
        top_bar_widget.setFixedHeight(56)
        top_bar_widget.setProperty("class", "headerBackground headerBorder")
        top_bar_layout = QHBoxLayout(top_bar_widget)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(16)

        mw.header_stack = QStackedWidget()
        mw.header_stack.setFixedHeight(56)
        top_bar_layout.addWidget(mw.header_stack, 1)

        mw.search_container = QWidget()
        mw.search_container.setContentsMargins(0, 0, 0, 0)

        mw.search_container.setFixedWidth(320)

        search_bar_layout = QHBoxLayout(mw.search_container)
        search_bar_layout.setContentsMargins(0, 0, 16, 0)
        search_bar_layout.setSpacing(8)

        search_divider = QFrame()
        search_divider.setFrameShape(QFrame.Shape.VLine)
        search_divider.setFixedWidth(1)
        search_divider.setProperty("class", "headerDivider")
        search_bar_layout.addWidget(search_divider)

        search_icon_label = QLabel()
        search_icon_pixmap = create_svg_icon(
            "assets/control/search.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
        ).pixmap(20, 20)
        search_icon_label.setPixmap(search_icon_pixmap)
        search_icon_label.setContentsMargins(4, 0, 0, 0)

        opacity_effect = QGraphicsOpacityEffect(search_icon_label)
        opacity_effect.setOpacity(0.3)
        search_icon_label.setGraphicsEffect(opacity_effect)

        search_bar_layout.addWidget(search_icon_label)

        mw.search_interaction_filter = SearchInteractionFilter(opacity_effect, mw)

        mw.search_container.installEventFilter(mw.search_interaction_filter)

        mw.global_search_bar = StyledLineEdit()
        mw.global_search_bar.setClearButtonEnabled(True)
        mw.global_search_bar.findChild(QAction).setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.global_search_bar.setProperty("class", "filterInput")
        mw.global_search_bar.setPlaceholderText(translate("Search..."))

        palette = mw.global_search_bar.palette()

        primary_str = theme.COLORS["PRIMARY"]
        text_color = theme.get_qcolor(primary_str)

        text_color.setAlphaF(0.5)
        palette.setColor(QPalette.ColorRole.PlaceholderText, text_color)

        palette.setColor(QPalette.ColorRole.Text, text_color)

        mw.global_search_bar.setPalette(palette)

        mw.global_search_bar.installEventFilter(mw.search_interaction_filter)

        search_bar_layout.addWidget(mw.global_search_bar)

        top_bar_layout.addWidget(mw.search_container)

        right_block_layout.addWidget(top_bar_widget)

        mw.splitter = QSplitter(Qt.Orientation.Horizontal)
        mw.splitter.setHandleWidth(1)

        mw.main_stack = QStackedWidget()
        mw.main_stack.currentChanged.connect(self.manager.on_main_stack_changed)

        mw.main_stack.currentChanged.connect(mw.header_stack.setCurrentIndex)

        mw.splitter.addWidget(mw.main_stack)

        mw.right_panel = RightPanel(mw)
        mw.splitter.addWidget(mw.right_panel)
        mw.splitter.setSizes([680, 320])
        for i in range(mw.splitter.count()):
            mw.splitter.setCollapsible(i, False)

        right_block_layout.addWidget(mw.splitter)
        main_view_layout.addWidget(right_block_widget)

        mw.main_view_stack = QStackedWidget()
        mw.main_view_stack.addWidget(main_view_container)
        mw.main_view_stack.addWidget(mw.vinyl_widget)
        main_layout.addWidget(mw.main_view_stack, 1)

        self.setup_left_panel(main_view_layout)

        mw.control_panel = ControlPanel(mw)
        main_layout.addWidget(mw.control_panel)


    def create_page_header(
        self,
        title,
        details_text=None,
        back_slot=None,
        control_widgets=None,
        play_slot_data=None,
        context_menu_data=None,
    ):
        """
        Constructs a standardized page header consisting of a title, optional details,
        a back navigation button, and supplementary action controls.
        """
        header = QWidget()
        header.setContentsMargins(16, 0, 0, 0)
        header.setFixedHeight(56)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        if back_slot:
            back_button = QPushButton("")
            back_button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                back_button,
                title = translate("Back"),
            )
            back_button.setIcon(
                create_svg_icon(
                    "assets/control/arrow_back.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
            back_button.setIconSize(QSize(24, 24))
            back_button.setFixedHeight(36)
            back_button.setProperty("class", "btnTool")
            back_button.clicked.connect(back_slot)
            apply_button_opacity_effect(back_button)
            layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

        title_container = QWidget()
        title_hbox = QVBoxLayout(title_container)
        title_hbox.setContentsMargins(0, 0, 0, 0)
        title_hbox.setSpacing(2)
        title_hbox.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        title_label = ElidedLabel(f"{title}")
        title_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        title_hbox.addWidget(title_label)

        details_label = QLabel(details_text or "")
        details_label.setProperty("class", "textSecondary textColorTertiary")
        title_hbox.addWidget(details_label)
        details_label.setVisible(bool(details_text))

        layout.addWidget(title_container)
        layout.addStretch()

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        play_button = None
        shake_button = None
        if play_slot_data:
            play_button = QPushButton("")
            play_button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                play_button,
                title = translate("Play"),
            )
            play_button.setIcon(
                create_svg_icon(
                    "assets/control/play_outline.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
            play_button.setFixedHeight(36)
            play_button.setIconSize(QSize(24, 24))
            play_button.setProperty("class", "btnTool")
            apply_button_opacity_effect(play_button)
            actions_layout.addWidget(
                play_button, alignment=Qt.AlignmentFlag.AlignCenter
            )

            shake_button = QPushButton("")
            shake_button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                shake_button,
                title = translate("Shake and Play"),
                text = translate("This action will mix all tracks and add them to the playback queue in a random order"),
            )
            shake_button.setIcon(
                create_svg_icon(
                    "assets/control/shake_queue.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
            shake_button.setFixedHeight(36)
            shake_button.setIconSize(QSize(24, 24))
            shake_button.setProperty("class", "btnTool")
            shake_button.clicked.connect(
                lambda: self.main_window.player_controller.play_data_shuffled(
                    play_slot_data
                )
            )
            apply_button_opacity_effect(shake_button)
            actions_layout.addWidget(
                shake_button, alignment=Qt.AlignmentFlag.AlignCenter
            )

        if control_widgets:
            controls_container = QWidget()
            controls_layout = QHBoxLayout(controls_container)
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(8)
            for widget in control_widgets:
                controls_layout.addWidget(widget)
            actions_layout.addWidget(
                controls_container, alignment=Qt.AlignmentFlag.AlignCenter
            )

        actions_button = None
        if context_menu_data:
            item_data, item_type = context_menu_data
            actions_button = QPushButton("")
            actions_button.setFixedSize(36, 36)
            set_custom_tooltip(
                actions_button,
                title = translate("Actions"),
            )
            actions_button.setCursor(Qt.CursorShape.PointingHandCursor)
            actions_button.setProperty("class", "btnTool")
            actions_button.setIcon(
                create_svg_icon(
                    "assets/control/more_horiz.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
            actions_button.setIconSize(QSize(24, 24))
            apply_button_opacity_effect(actions_button)

            actions_button.clicked.connect(
                lambda: self._show_header_context_menu(
                    actions_button, item_data, item_type
                )
            )
            actions_layout.addWidget(
                actions_button, alignment=Qt.AlignmentFlag.AlignCenter
            )

        layout.addLayout(actions_layout)

        return {
            "header": header,
            "title": title_label,
            "details": details_label,
            "play_button": play_button,
            "shake_button": shake_button,
            "actions_button": actions_button,
            "divider": None,
        }

    def _show_header_context_menu(self, button, item_data, item_type):
        """
        Displays a context menu for the page header's action button based on the item type.
        """
        mw = self.main_window
        button.setProperty("active", True)
        button.style().unpolish(button)
        button.style().polish(button)

        global_pos = button.mapToGlobal(QPoint(0, button.height()))

        context = {"forced_type": item_type}

        if item_type == "favorite_tracks" or item_type == "system_list":
            mw.action_handler.show_favorite_tracks_card_context_menu(
                item_data, global_pos
            )

        elif item_type == "playlist":
            mw.action_handler.show_playlist_card_context_menu(item_data, global_pos)

        else:
            mw.action_handler.show_context_menu(item_data, global_pos, context=context)

        button.setProperty("active", False)
        button.style().unpolish(button)
        button.style().polish(button)

    def create_tool_button_with_menu(
            self, options, current_mode_data, icon_size = QSize(24, 24)
    ):
        """
        Creates a tool button with an attached dropdown menu for selecting from multiple options.
        """
        tool_button = StyledToolButton()

        tool_button.setCursor(Qt.CursorShape.PointingHandCursor)
        tool_button.setProperty("class", "btnToolMenu")
        tool_button.setFixedHeight(36)
        tool_button.setIconSize(icon_size)
        tool_button.setAutoRaise(True)

        menu = tool_button.menu()

        current_action = None
        for text, icon_path, data in options:
            action = QAction(icon_path, text, tool_button)
            action.setData(data)
            action.setCheckable(True)
            menu.addAction(action)
            if data == current_mode_data:
                current_action = action
                action.setChecked(True)

        def on_triggered(triggered_action):
            """
            Handles menu item selection by updating the button's icon
            and the checked state of the actions.
            """
            tool_button.setIcon(triggered_action.icon())
            for a in menu.actions():
                a.setChecked(a == triggered_action)

        menu.triggered.connect(on_triggered)

        if current_action:
            tool_button.setIcon(current_action.icon())
        elif options:
            tool_button.setIcon(options[0][1])

        apply_button_opacity_effect(tool_button)
        return tool_button

    def update_tool_button_icon(self, button, current_data):
        """
        Updates the icon of a tool button based on the currently selected action data.
        """
        if not button or not button.menu():
            return
        for action in button.menu().actions():
            is_active = (action.data() == current_data)
            action.setChecked(is_active)

            if is_active:
                button.setIcon(action.icon())

    def setup_left_panel(self, parent_layout):
        """
        Sets up the main left navigation panel and its associated buttons and layout.
        """
        mw = self.main_window

        mw.nav_bar = QWidget()
        mw.nav_bar.setProperty("class", "navBar")
        mw.nav_bar.setFixedWidth(56)

        nav_layout = QVBoxLayout(mw.nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        mw.nav_buttons_group = QButtonGroup()
        mw.nav_buttons_group.setExclusive(True)

        mw.nav_button_icon_names = ["favorite"]

        mw.nav_buttons = []
        mw.collapsible_nav_buttons = []
        fixed_top_widgets = []
        fixed_bottom_widgets = []

        tab_factory = TabFactory(mw)

        pages_containers = {
            "artist": tab_factory.create_artists_tab(),
            "album": tab_factory.create_albums_tab(),
            "track": tab_factory.create_songs_tab(),
            "genre": tab_factory.create_genres_tab(),
            "composer": tab_factory.create_composers_tab(),
            "folder": tab_factory.create_folder_tab(),
            "playlist": tab_factory.create_playlists_tab(),
            "favorite": tab_factory.create_favorites_tab(),
            "charts": tab_factory.create_charts_tab(),
        }
        history_container = tab_factory.create_history_tab()

        def unpack_and_add(container):
            """
            Extracts the header and content widgets from the tab container
            and appends them to their respective stacked widgets.
            """
            layout = container.layout()
            if layout.count() >= 2:
                header_sub = layout.itemAt(0).widget()
                content_sub = layout.itemAt(1).widget()
                mw.header_stack.addWidget(header_sub)
                mw.main_stack.addWidget(content_sub)

        mw.favorite_nav_button = QToolButton()
        mw.favorite_nav_button.setCursor(Qt.CursorShape.PointingHandCursor)
        mw.favorite_nav_button.setProperty("class", "navButtonFavorite")
        set_custom_tooltip(
            mw.favorite_nav_button,
            title = translate("Favorites"),
        )
        mw.favorite_nav_button.setIcon(
            create_svg_icon(
                f"assets/control/vinyller.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.favorite_nav_button.setIconSize(QSize(24, 24))
        mw.favorite_nav_button.setCheckable(True)
        mw.favorite_nav_button.setFixedHeight(56)
        apply_button_opacity_effect(mw.favorite_nav_button)

        nav_layout.addWidget(mw.favorite_nav_button)
        mw.nav_buttons_group.addButton(mw.favorite_nav_button)
        mw.nav_buttons.append(mw.favorite_nav_button)
        fixed_top_widgets.append(mw.favorite_nav_button)

        unpack_and_add(pages_containers["favorite"])


        definitions = {
            "artist": (translate("Artists"), None),
            "album": (translate("Albums"), None),
            "genre": (translate("Genres"), None),
            "composer": (translate("Composers"), None),
            "track": (translate("All tracks"), None),
            "playlist": (translate("Playlists"), None),
            "folder": (translate("Folders"), None),
            "charts": (translate("Charts"), None),
        }

        default_order = [
            "artist", "album", "genre", "composer",
            "track", "playlist", "folder", "charts"
        ]
        order_keys = getattr(mw, "nav_tab_order", default_order)

        for k in default_order:
            if k not in order_keys:
                order_keys.append(k)

        for key in order_keys:
            if key in definitions:
                title, icon_override = definitions[key]
                icon_name = icon_override if icon_override else key

                btn = self.create_and_add_nav_button(
                    mw, nav_layout, icon_name, title, pages_containers, key = key
                )
                mw.collapsible_nav_buttons.append(btn)

                if key == "charts":
                    mw.charts_button = btn

                mw.nav_button_icon_names.append(key)

        mw.history_button = QToolButton()
        mw.history_button.setCursor(Qt.CursorShape.PointingHandCursor)
        mw.history_button.setProperty("class", "navButton")
        set_custom_tooltip(
            mw.history_button,
            title = translate("Playback history"),
        )
        mw.history_button.setProperty("original_tooltip", translate("Playback history"))
        mw.history_button.setIcon(
            create_svg_icon(
                "assets/control/history.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.history_button.setIconSize(QSize(24, 24))
        mw.history_button.setCheckable(True)
        mw.history_button.setFixedHeight(50)
        apply_button_opacity_effect(mw.history_button)
        mw.nav_buttons_group.addButton(mw.history_button)

        nav_layout.addWidget(mw.history_button)
        mw.nav_buttons.append(mw.history_button)

        mw.nav_button_icon_names.append("history")
        mw.collapsible_nav_buttons.append(mw.history_button)
        unpack_and_add(history_container)

        mw.history_button.hide()

        mw.nav_more_button = QToolButton()
        mw.nav_more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        mw.nav_more_button.setProperty("class", "navButton")
        set_custom_tooltip(
            mw.nav_more_button,
            title = translate("Show more"),
        )
        mw.nav_more_button.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.nav_more_button.setIconSize(QSize(24, 24))
        mw.nav_more_button.setCheckable(True)
        mw.nav_more_button.setFixedHeight(50)

        mw.nav_more_button.clicked.connect(
            lambda: self._show_nav_more_menu(mw.nav_more_button)
        )

        nav_layout.addWidget(mw.nav_more_button)
        mw.nav_more_button.hide()

        mw.search_results_container, mw.search_header_stack, mw.search_stack = (
            tab_factory.create_search_results_page()
        )
        s_layout = mw.search_results_container.layout()
        if s_layout.count() >= 2:
            mw.search_header_widget = s_layout.itemAt(0).widget()
            mw.search_content_widget = s_layout.itemAt(1).widget()
            mw.header_stack.addWidget(mw.search_header_widget)
            mw.main_stack.addWidget(mw.search_content_widget)
            mw.global_search_page_index = mw.main_stack.indexOf(
                mw.search_content_widget
            )
            mw.search_tab_index = mw.global_search_page_index

        if "charts" in pages_containers:
            c_layout = pages_containers["charts"].layout()
            if c_layout.count() > 1:
                c_content = c_layout.itemAt(1).widget()
                mw.charts_tab_index = mw.main_stack.indexOf(c_content)

        self.manager.update_nav_button_icons()

        nav_layout.addStretch()

        mw.notification_toggle_button = QToolButton()
        mw.notification_toggle_button.setProperty("class", "navButtonSettings")
        set_custom_tooltip(
            mw.notification_toggle_button,
            title = translate("Library update required"),
        )
        mw.notification_toggle_button.setIcon(
            create_svg_icon(
                "assets/control/warning.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.notification_toggle_button.setIconSize(QSize(24, 24))
        mw.notification_toggle_button.setCheckable(True)
        mw.notification_toggle_button.setFixedHeight(56)
        apply_button_opacity_effect(mw.notification_toggle_button)
        nav_layout.addWidget(mw.notification_toggle_button)
        mw.notification_toggle_button.hide()
        fixed_bottom_widgets.append(mw.notification_toggle_button)

        mw.vinyl_toggle_button = QToolButton()
        mw.vinyl_toggle_button.setProperty("class", "navButtonSettings")
        set_custom_tooltip(
            mw.vinyl_toggle_button,
            title = translate("Enter Vinyl mode"),
        )
        mw.vinyl_toggle_button.setIcon(
            create_svg_icon(
                "assets/control/view_vinny.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.vinyl_toggle_button.setIconSize(QSize(24, 24))
        mw.vinyl_toggle_button.setCheckable(True)
        mw.vinyl_toggle_button.setFixedHeight(56)
        apply_button_opacity_effect(mw.vinyl_toggle_button)
        nav_layout.addWidget(mw.vinyl_toggle_button)
        fixed_bottom_widgets.append(mw.vinyl_toggle_button)

        mw.settings_button = RadialProgressButton()
        mw.settings_button.setProperty("class", "navButtonSettings")
        set_custom_tooltip(
            mw.settings_button,
            title = translate("Settings"),
        )
        mw.settings_button.setIcon(mw.settings_icon)
        mw.settings_button.setIconSize(QSize(24, 24))
        mw.settings_button.setFixedHeight(56)
        apply_button_opacity_effect(mw.settings_button)
        nav_layout.addWidget(mw.settings_button)
        fixed_bottom_widgets.append(mw.settings_button)

        parent_layout.insertWidget(0, mw.nav_bar)

        self.resize_filter = NavBarResizeFilter(
            mw.nav_bar,
            mw.collapsible_nav_buttons,
            mw.nav_more_button,
            fixed_top_widgets,
            fixed_bottom_widgets,
            mw,
        )
        mw.nav_bar.installEventFilter(self.resize_filter)

        QTimer.singleShot(0, lambda: self.resize_filter.recalc_layout())

    def _show_nav_more_menu(self, button):
        """
        Displays a drop-down menu containing navigation buttons that are hidden due to insufficient space.
        """
        mw = self.main_window
        hidden_buttons = getattr(button, "hidden_buttons", [])

        if not hidden_buttons:
            return

        menu = TranslucentMenu(button)
        menu.setProperty("class", "popMenu")

        for btn in hidden_buttons:
            if btn == mw.history_button and mw.playback_history_mode == 0:
                continue

            text = btn.property("original_tooltip") or btn.toolTip()
            icon = btn.icon()

            action = QAction(icon, text, menu)
            action.setCheckable(True)
            action.setChecked(btn.isChecked())

            action.triggered.connect(btn.click)

            menu.addAction(action)

        global_pos = button.mapToGlobal(QPoint(button.width(), 0))
        menu.exec(global_pos)

        self.manager.update_nav_button_icons()

    def create_and_add_nav_button(
        self, mw, layout, icon_name, tooltip, pages_containers, key=None
    ):
        """
        Creates a new navigation button, sets its properties, and connects it to the corresponding tab view.
        """
        if key is None:
            key = icon_name

        button = QToolButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("class", "navButton")
        set_custom_tooltip(
            button,
            title = tooltip,
        )
        button.setProperty("original_tooltip", tooltip)
        button.setIcon(
            create_svg_icon(
                f"assets/control/{icon_name}.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        button.setIconSize(QSize(24, 24))
        button.setCheckable(True)
        button.setFixedHeight(50)
        apply_button_opacity_effect(button)
        layout.addWidget(button)
        mw.nav_buttons_group.addButton(button)
        mw.nav_buttons.append(button)

        def unpack_and_add(container):
            layout = container.layout()
            if layout.count() >= 2:
                header_sub = layout.itemAt(0).widget()
                content_sub = layout.itemAt(1).widget()

                mw.header_stack.addWidget(header_sub)
                mw.main_stack.addWidget(content_sub)
            else:
                print("Error: Invalid tab container structure")

        if key in pages_containers:
            unpack_and_add(pages_containers[key])

        return button

    def _create_favorite_button(self, item_data, item_type):
        """
        Creates a toggle button to add or remove a specific item from the user's favorites.
        """
        mw = self.main_window
        button = QPushButton("")
        set_custom_tooltip(
            button,
            title = translate("Add to favorites"),
            hotkey = HotkeyManager.get_hotkey_str("favorite")
        )
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("class", "btnTool")
        button.setFixedHeight(36)
        button.setIconSize(QSize(24, 24))
        apply_button_opacity_effect(button)

        def update_icon():
            """
            Updates the button's icon, tooltip, and active state based
            on whether the item is currently in favorites.
            """
            key = list(item_data) if isinstance(item_data, tuple) else item_data
            is_fav = mw.library_manager.is_favorite(key, item_type)
            button.setProperty("active", is_fav)
            if button.graphicsEffect():
                button.graphicsEffect().setEnabled(not is_fav)
            button.setIcon(mw.favorite_filled_icon if is_fav else mw.favorite_icon)
            if is_fav:
                set_custom_tooltip(
                    button,
                    title = translate("Remove from favorites"),
                    hotkey = HotkeyManager.get_hotkey_str("favorite")
                )
            else:
                set_custom_tooltip(
                    button,
                    title = translate("Add to favorites"),
                    hotkey = HotkeyManager.get_hotkey_str("favorite")
                )
            button.style().polish(button)

        def on_click():
            """
            Toggles the favorite status of the item and refreshes the button UI.
            """
            mw.action_handler.toggle_favorite(item_data, item_type)
            update_icon()

        button.clicked.connect(on_click)
        update_icon()
        return button

    def get_pixmap(self, artwork_data, target_size):
        """
        Retrieves a cached pixmap for the given artwork data and target size. Generates and caches it if it doesn't exist.
        """
        mw = self.main_window
        artwork_path = None
        if isinstance(artwork_data, dict):
            available_sizes = sorted([int(s) for s in artwork_data.keys()])
            best_size = None
            for size in available_sizes:
                if size >= target_size:
                    best_size = size
                    break
            if best_size is None and available_sizes:
                best_size = available_sizes[-1]
            if best_size:
                artwork_path = artwork_data.get(str(best_size))
        elif isinstance(artwork_data, str):
            artwork_path = artwork_data

        cache_key = (artwork_path, target_size)
        if cache_key in mw.pixmap_cache:
            return mw.pixmap_cache[cache_key]

        if artwork_path and os.path.exists(artwork_path):
            pixmap = QPixmap(artwork_path)
        else:
            pixmap = self.missing_cover_pixmap

        if pixmap.width() != target_size or pixmap.height() != target_size:
            scaled_pixmap = pixmap.scaled(
                target_size,
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            scaled_pixmap = pixmap

        mw.pixmap_cache[cache_key] = scaled_pixmap
        return scaled_pixmap

    def create_artist_widget(
        self, artist, data, mode, subtitle_extra=None, search_query=None
    ):
        """
        Creates a customized CardWidget instance designed for artist data.
        """
        mw = self.main_window
        size = 128
        artwork_dicts = data.get("artworks", [])
        pixmaps = [self.get_pixmap(p, size) for p in artwork_dicts]
        if not pixmaps:
            pixmaps.append(self.get_pixmap(None, size))

        album_count = data.get("album_count", 0)
        track_count = data.get("track_count", 0)
        album_text = translate("{count} album(s)", count=album_count)
        track_text = translate("{count} track(s)", count=track_count)
        subtitle1 = f"{album_text}, {track_text}"

        subtitle2_text = translate(
            "Total time: {duration}",
            duration=format_time(data.get("total_duration", 0) * 1000),
        )

        widget = CardWidget(
            data=artist,
            view_mode=mode,
            pixmaps=pixmaps,
            title=artist,
            subtitle1=subtitle1 if mode != ViewMode.GRID else None,
            subtitle2=(
                subtitle2_text
                if mode in [ViewMode.TILE_BIG, ViewMode.TILE_SMALL]
                else None
            ),
            subtitle_extra=subtitle_extra,
            is_artist_card=True,
            icon_pixmap=self.artist_icon_pixmap,
            disc_info_text=None,
            search_query=search_query,
        )
        widget.pauseClicked.connect(mw.player.pause)
        mw.main_view_card_widgets[artist].append(widget)
        return widget

    def create_composer_widget(
        self, composer, data, mode, subtitle_extra=None, search_query=None
    ):
        """
        Creates a customized CardWidget instance designed for composer data.
        """
        mw = self.main_window
        size = 128
        artwork_dicts = data.get("artworks", [])
        pixmaps = [self.get_pixmap(p, size) for p in artwork_dicts]
        if not pixmaps:
            pixmaps.append(self.get_pixmap(None, size))

        album_count = data.get("album_count", 0)
        track_count = data.get("track_count", 0)
        album_text = translate("{count} album(s)", count=album_count)
        track_text = translate("{count} track(s)", count=track_count)
        subtitle1 = f"{album_text}, {track_text}"

        subtitle2_text = translate(
            "Total time: {duration}",
            duration=format_time(data.get("total_duration", 0) * 1000),
        )

        widget = CardWidget(
            data=composer,
            view_mode=mode,
            pixmaps=pixmaps,
            title=composer,
            subtitle1=subtitle1 if mode != ViewMode.GRID else None,
            subtitle2=(
                subtitle2_text
                if mode in [ViewMode.TILE_BIG, ViewMode.TILE_SMALL]
                else None
            ),
            subtitle_extra=subtitle_extra,
            is_artist_card=True,
            icon_pixmap=self.composer_icon_pixmap,
            disc_info_text=None,
            search_query=search_query,
        )
        widget.pauseClicked.connect(mw.player.pause)
        mw.main_view_card_widgets[composer].append(widget)
        return widget

    def create_genre_widget(
        self, genre, data, mode, subtitle_extra=None, search_query=None
    ):
        """
        Creates a customized CardWidget instance designed for genre data.
        """
        mw = self.main_window
        size = 128
        artwork_dicts = data.get("artworks", [])
        pixmaps = [self.get_pixmap(p, size) for p in artwork_dicts]
        if not pixmaps:
            pixmaps.append(self.get_pixmap(None, size))

        album_count = data.get("album_count", 0)
        track_count = data.get("track_count", 0)
        album_text = translate("{count} album(s)", count=album_count)
        track_text = translate("{count} track(s)", count=track_count)
        subtitle1 = f"{album_text}, {track_text}"
        subtitle2_text = translate(
            "Total time: {duration}",
            duration=format_time(data.get("total_duration", 0) * 1000),
        )

        widget = CardWidget(
            data=genre,
            view_mode=mode,
            pixmaps=pixmaps,
            title=genre,
            subtitle1=subtitle1 if mode != ViewMode.GRID else None,
            subtitle2=(
                subtitle2_text
                if mode in [ViewMode.TILE_BIG, ViewMode.TILE_SMALL]
                else None
            ),
            subtitle_extra=subtitle_extra,
            is_artist_card=False,
            icon_pixmap=self.genre_icon_pixmap,
            disc_info_text=None,
            search_query=search_query,
        )
        widget.pauseClicked.connect(mw.player.pause)
        mw.main_view_card_widgets[genre].append(widget)
        return widget

    def create_album_widget(
        self,
        album_key,
        data,
        mode,
        show_artist=True,
        subtitle_extra=None,
        search_query=None,
    ):
        """
        Creates a customized CardWidget instance designed for album data, including logic for disc markers.
        """
        mw = self.main_window

        disc_info_text = None
        icon_pixmap = None
        disc_num, total_discs = self._get_disc_info(album_key)

        if disc_num is not None:
            disc_info_text = str(disc_num)
            icon_pixmap = self.album_icon_pixmap

        tracks = data.get("tracks", [])
        is_virtual = any(t.get("is_virtual", False) for t in tracks)

        album_title = album_key[1]

        artist_name = data.get("album_artist", translate("Unknown"))
        pixmap = self.get_pixmap(data.get("artwork"), 128)
        year_str = str(data.get("year")) if data.get("year", 0) > 0 else ""

        if mode == ViewMode.GRID:
            subtitle2_text = None
        elif mode == ViewMode.TILE_SMALL:
            count = data.get("track_count", 0)
            duration = format_time(data.get("total_duration", 0) * 1000)
            details = translate(
                "{count} track(s) - {duration}", count=count, duration=duration
            )
            subtitle2_text = details
        else:
            subtitle2_text = translate(
                "{count} track(s) - {duration}",
                count=data.get("track_count", 0),
                duration=format_time(data.get("total_duration", 0) * 1000),
            )

        widget = CardWidget(
            data=album_key,
            view_mode=mode,
            pixmaps=[pixmap] if pixmap else [],
            title=album_title,
            subtitle1=artist_name if show_artist else year_str,
            artist_name_for_nav=artist_name if show_artist else None,
            subtitle2=subtitle2_text,
            subtitle_extra=subtitle_extra,
            icon_pixmap=icon_pixmap,
            disc_info_text=disc_info_text,
            search_query=search_query,
            is_virtual=is_virtual,
            cue_icon_pixmap=self.cue_icon_pixmap,
        )
        widget.pauseClicked.connect(mw.player.pause)
        mw.main_view_card_widgets[album_key].append(widget)
        if show_artist:
            widget.artistClicked.connect(self.manager.navigate_to_artist)
        return widget

    def _create_detailed_album_widget(
        self, album_key, album_data, tracks_to_show=None, search_query=None
    ):
        """
        Creates a detailed, multi-element widget explicitly representing an album with its tracklist.
        """
        mw = self.main_window
        pixmap_128 = self.get_pixmap(album_data.get("artwork"), 128)

        disc_info_text = None
        icon_pixmap = None

        disc_num, total_discs = self._get_disc_info(album_key)
        if disc_num is not None:
            disc_info_text = str(disc_num)
            icon_pixmap = self.album_icon_pixmap

        tracks = (
            tracks_to_show
            if tracks_to_show is not None
            else album_data.get("tracks", [])
        )
        is_virtual = any(t.get("is_virtual", False) for t in tracks)

        card = DetailedAlbumCard(
            album_key,
            {**album_data, "pixmap_128": pixmap_128},
            tracks_to_show,
            mw,
            icon_pixmap=icon_pixmap,
            disc_info_text=disc_info_text,
            is_virtual=is_virtual,
            cue_icon_pixmap=self.cue_icon_pixmap,
            search_query=search_query,
        )

        card.smartPlay.connect(mw.player_controller.smart_play)
        card.playData.connect(mw.player_controller.play_data)
        card.playTrack.connect(mw.player_controller.play_or_pause_track_universal)
        card.pausePlayer.connect(mw.player.pause)
        card.restartTrack.connect(mw.player_controller.play_track_from_start_universal)
        card.trackContextMenu.connect(
            lambda track, pos, context: mw.action_handler.show_context_menu(
                track, pos, context=context
            )
        )
        card.albumContextMenu.connect(mw.action_handler.show_context_menu)
        card.artistClicked.connect(self.manager.navigate_to_artist)
        card.genreClicked.connect(self.manager.navigate_to_genre)
        card.composerClicked.connect(self.manager.navigate_to_composer)
        card.lyricsClicked.connect(mw.action_handler.show_lyrics)

        if track_list_widget := card.get_track_list_widget():
            mw.main_view_track_lists.append(track_list_widget)

        mw.main_view_cover_widgets[album_key].append(card.get_art_widget())
        return card

    def create_directory_widget(self, name, path, view_mode, artwork_dicts):
        """
        Creates a customized CardWidget instance designed to represent a local directory folder.
        """
        mw = self.main_window

        if artwork_dicts is None:
            artwork_dicts = []

        pixmaps = [self.get_pixmap(p, 128) for p in artwork_dicts]
        if not pixmaps:
            pixmaps.append(mw.folder_pixmap)
        widget = CardWidget(
            data=path,
            view_mode=view_mode,
            pixmaps=pixmaps,
            title=name,
            subtitle1=path if view_mode != ViewMode.GRID else None,
            is_artist_card=False,
            icon_pixmap=self.folder_icon_pixmap,
        )
        widget.pauseClicked.connect(mw.player.pause)
        mw.main_view_card_widgets[path].append(widget)
        return widget

    def _create_separator_widget(self, text, source_view, letters):
        """
        Creates a separator widget with an optional clickable alphabetic label to facilitate easy navigation.
        """
        separator_widget = QWidget()
        separator_widget.setContentsMargins(0, 0, 0, 0)
        separator_widget.setFixedHeight(16)
        separator_layout = QHBoxLayout(separator_widget)
        separator_layout.setContentsMargins(0, 0, 0, 0)
        separator_layout.setSpacing(16)

        if source_view:
            separator_alpha = ClickableSeparatorLabel(text)
            separator_alpha.clicked.connect(
                partial(
                    self.manager._on_separator_clicked,
                    source_view,
                    letters,
                    separator_alpha,
                )
            )
        else:
            separator_alpha = QLabel(text)

        separator_alpha.setProperty("class", "separatorAlpha")
        separator_alpha.setFixedHeight(16)
        separator_layout.addWidget(separator_alpha)

        separator_line = QWidget()
        separator_line.setProperty("class", "separator")
        separator_line.setFixedHeight(2)
        separator_layout.addWidget(separator_line, stretch=1)
        return separator_widget

    def _create_detailed_playlist_widget(
        self, playlist_path, playlist_name, tracks, pixmap=None, show_score=False
    ):
        """
        Creates a detailed, multi-element widget specifically designed for playlists, supporting track ordering.
        """
        mw = self.main_window
        if pixmap is None:
            first_track_artwork_dict = tracks[0].get("artwork") if tracks else None
            pixmap = (
                self.get_pixmap(first_track_artwork_dict, 128)
                if first_track_artwork_dict
                else self.playlist_pixmap.scaled(
                    128,
                    128,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        card = DetailedPlaylistCard(
            playlist_path, playlist_name, tracks, pixmap, mw, show_score = show_score
        )
        card.playData.connect(mw.player_controller.play_data)
        card.smartPlay.connect(mw.player_controller.smart_play)

        is_system_list = playlist_path in [
            "favorite_tracks",
            "playback_history",
            "all_top_tracks",
        ]
        is_archive_list = isinstance(playlist_path, str) and playlist_path.startswith(
            "archive_"
        )
        if not (is_system_list or is_archive_list):
            card.playlistReordered.connect(
                lambda path, new_tracks: mw.library_manager.save_playlist(path, new_tracks)
            )

        if is_system_list or is_archive_list:
            card.playTrack.connect(mw.player_controller.play_or_pause_track_universal)
            card.restartTrack.connect(
                mw.player_controller.play_track_from_start_universal
            )
        else:
            card.playlistReordered.connect(
                lambda path, new_tracks: mw.library_manager.save_playlist(path, new_tracks)
            )

            card.playlistTracksInserted.connect(
                lambda path, tracks, index: self._handle_playlist_insert(path, tracks, index)
            )

            card.playTrack.connect(
                lambda track_data, track_index: mw.player_controller.play_track_from_playlist_context(
                    track_data, playlist_path, track_index = track_index
                )
            )
            card.restartTrack.connect(
                lambda track_data, track_index: mw.player_controller.play_track_from_playlist_context(
                    track_data,
                    playlist_path,
                    force_restart = True,
                    track_index = track_index,
                )
            )

        card.pausePlayer.connect(mw.player.pause)

        context = {"playlist_path": playlist_path}
        if playlist_path == "all_top_tracks":
            context["source"] = "charts"
        elif playlist_path == "playback_history":
            context["source"] = "history"

        card.trackContextMenu.connect(
            lambda track, pos: mw.action_handler.show_context_menu(
                track, pos, context=context
            )
        )

        card.playlistContextMenu.connect(
            mw.action_handler.show_playlist_card_context_menu
        )
        card.artistClicked.connect(self.manager.navigate_to_artist)
        card.composerClicked.connect(self.manager.navigate_to_composer)
        card.lyricsClicked.connect(mw.action_handler.show_lyrics)

        if track_list_widget := card.get_track_list_widget():
            mw.main_view_track_lists.append(track_list_widget)

        mw.main_view_cover_widgets[playlist_path].append(card.get_art_widget())

        return card

    def _handle_playlist_insert(self, path, tracks, index):
        """
        Handles the logical update when tracks are inserted into a custom playlist.
        """
        mw = self.main_window
        if mw.library_manager.insert_tracks_into_playlist(path, tracks, index):
            mw.ui_manager.show_playlist_tracks(path)

    def show_cover_viewer(
            self,
            pixmap,
            use_global_context = False,
            parent = None,
            image_list = None,
            current_index = 0,
    ):
        """
        Spawns the CoverViewerWidget, attempting to display the highest available resolution for the requested image.
        """
        mw = self.main_window
        target_parent = parent if parent else mw

        full_pixmap = None

        if not image_list and use_global_context:
            artwork_dict = (
                mw.current_artwork_path
                if isinstance(mw.current_artwork_path, dict)
                else None
            )
            if artwork_dict:
                try:
                    numeric_keys = [int(s) for s in artwork_dict.keys() if s.isdigit()]
                    if numeric_keys:
                        largest_size = sorted(numeric_keys)[-1]
                        path_hq = artwork_dict.get(str(largest_size))
                        if path_hq and os.path.exists(path_hq):
                            full_pixmap = QPixmap(path_hq)
                except Exception:
                    pass

        if (
                (not image_list)
                and (not full_pixmap or full_pixmap.isNull())
                and not pixmap.isNull()
        ):
            full_pixmap = pixmap

        if not image_list and (full_pixmap is None or full_pixmap.isNull()):
            return

        if getattr(mw, 'current_cover_viewer', None) is not None:
            mw.current_cover_viewer.hide()
            mw.current_cover_viewer.deleteLater()

        viewer = CoverViewerWidget(
            full_pixmap,
            target_parent,
            image_list = image_list,
            current_index = current_index,
        )

        mw.current_cover_viewer = viewer

        def on_viewer_closed():
            """
            Handles cleanup and restores UI states when the cover viewer is closed.
            """
            if target_parent == mw:
                mw.overlay_widget.setVisible(False)

            viewer.deleteLater()
            mw.current_cover_viewer = None

        viewer.closed.connect(on_viewer_closed)

        if target_parent == mw:
            mw.overlay_widget.setVisible(True)
            mw.overlay_widget.raise_()

        viewer.show()
        viewer.raise_()
        viewer.activateWindow()

    def _show_loading_library_message(self, layout):
        """
        Displays an animated loading message indicating library processing is underway.
        """
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(24)

        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        loading_icon = RotatingIconLabel("assets/control/scan.svg", QSize(64, 64))
        op_eff = QGraphicsOpacityEffect(loading_icon)
        op_eff.setOpacity(0.5)
        container_layout.addWidget(loading_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        container_layout.addSpacing(24)

        title_label = QLabel(translate("Spinning up the records"))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        container_layout.addWidget(title_label)

        text_layout = QHBoxLayout()
        text_label = QLabel(
            translate("Please wait while Vinyller warms up and loads your library.")
        )
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setMaximumWidth(512)
        text_layout.addWidget(text_label, 1)
        container_layout.addLayout(text_layout)

        layout.addStretch(1)
        layout.addWidget(container)
        layout.addStretch(1)

    def _show_no_library_message(self, layout):
        """
        Displays a centered message indicating that the library is currently empty, prompting the user to add folders.
        """
        mw = self.main_window
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(24)

        icon_label = QLabel()
        icon_pixmap = create_svg_icon(
            "assets/control/search_all.svg", theme.COLORS["TERTIARY"], QSize(64, 64)
        ).pixmap(QSize(64, 64))
        icon_label.setPixmap(icon_pixmap)
        op_eff = QGraphicsOpacityEffect(icon_label)
        op_eff.setOpacity(0.5)
        icon_label.setGraphicsEffect(op_eff)
        container_layout.addWidget(icon_label, alignment = Qt.AlignmentFlag.AlignCenter)
        container_layout.addSpacing(24)

        title_label = QLabel(translate("Library is empty"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        container_layout.addWidget(title_label)

        text_layout = QHBoxLayout()
        text_label = QLabel(translate("Specify a folder with your music collection..."))
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setMaximumWidth(512)
        text_layout.addWidget(text_label, 1)
        container_layout.addLayout(text_layout)

        button = QPushButton(translate("Select Folder"))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("class", "btnText")
        button.setFixedHeight(36)

        def handle_select_folder():
            old_paths = set(getattr(mw, "music_library_paths", []))

            result = mw.select_folder_and_scan()

            target_path = None
            if isinstance(result, str) and os.path.exists(result):
                target_path = result
            else:
                new_paths = set(getattr(mw, "music_library_paths", []))
                added = list(new_paths - old_paths)
                if added:
                    target_path = added[0]

            if target_path:
                if os.path.isfile(target_path):
                    target_path = os.path.dirname(target_path)
                try:
                    folder_tab_index = mw.nav_button_icon_names.index("folder")
                    mw.main_stack.setCurrentIndex(folder_tab_index)

                    for btn in mw.nav_buttons:
                        btn.setChecked(False)
                    if folder_tab_index < len(mw.nav_buttons):
                        mw.nav_buttons[folder_tab_index].setChecked(True)
                    mw.ui_manager.update_nav_button_icons()

                    mw.ui_manager.navigate_to_directory(target_path)
                except ValueError:
                    pass

        button.clicked.connect(handle_select_folder)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(button)
        button_layout.addStretch()
        container_layout.addLayout(button_layout)
        container_layout.addStretch(1)
        layout.addStretch(1)

        layout.addWidget(container)
        layout.addStretch(1)

    def _show_no_favorites_message(self, layout):
        """
        Displays a centered message indicating that there are no favorite items in the current view yet.
        """
        mw = self.main_window

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(24)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel()
        icon_pixmap = mw.favorite_icon.pixmap(QSize(64, 64))
        icon_label.setPixmap(icon_pixmap)
        op_eff = QGraphicsOpacityEffect(icon_label)
        op_eff.setOpacity(0.5)
        icon_label.setGraphicsEffect(op_eff)
        container_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        container_layout.addSpacing(24)

        title_label = QLabel(translate("Favorites is empty yet"))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        container_layout.addWidget(title_label)

        text_layout = QHBoxLayout()
        desc_text = translate(
            "Add your favorite tracks, albums, artists, composers and genres to favorites using the context menu or buttons in the control panel."
        )
        text_label = QLabel(desc_text)
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setMaximumWidth(512)
        text_layout.addWidget(text_label, 1)
        container_layout.addLayout(text_layout)

        layout.addStretch()
        layout.addWidget(container)
        layout.addStretch()

    def _show_no_metadata_results_message(self, layout, category_text):
        """
        Displays a generic 'not found' message targeted towards specific missing metadata categories (like composers or genres).
        """
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(24)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel()
        icon_pixmap = create_svg_icon(
            "assets/control/search.svg", theme.COLORS["TERTIARY"], QSize(64, 64)
        ).pixmap(QSize(64, 64))
        icon_label.setPixmap(icon_pixmap)
        op_eff = QGraphicsOpacityEffect(icon_label)
        op_eff.setOpacity(0.5)
        icon_label.setGraphicsEffect(op_eff)
        container_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        container_layout.addSpacing(24)

        title_label = QLabel(translate("Hmm..."))
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        container_layout.addWidget(title_label)

        text_layout = QHBoxLayout()
        category = category_text
        if category == "composers":
            desc_text = translate(
                "Music data contains no mentions of composers. You can open the metadata editor from the context menu of albums or tracks to fill in missing information about your music."
            )
        elif category == "genres":
            desc_text = translate(
                "Music data contains no mentions of genres. You can open the metadata editor from the context menu of albums or tracks to fill in missing information about your music."
            )

        text_label = QLabel(desc_text)
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setMaximumWidth(512)
        text_layout.addWidget(text_label, 1)
        container_layout.addLayout(text_layout)

        layout.addStretch(1)
        layout.addWidget(container)
        layout.addStretch(1)

    def create_album_merge_warning_widget(self):
        """
        Creates an informational notification widget suggesting the user activate the "Treat folders as unique" setting.
        """
        mw = self.main_window

        warning_frame = QFrame()
        warning_frame.setContentsMargins(0, 0, 0, 0)
        warning_frame.setProperty("class", "backgroundPrimary")

        warning_frame_layout = QHBoxLayout(warning_frame)
        warning_frame_layout.setContentsMargins(24, 0, 24, 0)
        warning_frame_layout.setSpacing(24)

        warning_widget = QWidget()
        warning_widget.setContentsMargins(16, 12, 16, 12)
        warning_widget.setProperty("class", "notificationWidget")

        w_layout = QHBoxLayout(warning_widget)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_layout.setSpacing(16)

        icon_label = QLabel()
        icon_pixmap = create_svg_icon(
            "assets/control/album.svg", theme.COLORS["TERTIARY"], QSize(24, 24)
        ).pixmap(QSize(24, 24))
        icon_label.setPixmap(icon_pixmap)
        apply_label_opacity_effect(icon_label)
        w_layout.addWidget(icon_label, alignment = Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        header_text = translate(
            "Several albums from different folders mixed into one?"
        )

        header_label = QLabel()
        header_label.setText(header_text)
        header_label.setWordWrap(True)
        header_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header_label.setProperty("class", "textHeaderSecondary")
        text_layout.addWidget(header_label)
        msg_text = translate(
            "Try enabling 'Treat the same albums in different folders as separate' in preferences."
        )

        info_label = QLabel()
        info_label.setText(msg_text)
        info_label.setWordWrap(True)
        info_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        info_label.setProperty("class", "textSecondary")
        text_layout.addWidget(info_label)
        w_layout.addLayout(text_layout, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_open_settings = QPushButton(translate("Settings"))
        set_custom_tooltip(
            btn_open_settings,
            title = translate("Open settings"),
        )
        btn_open_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_settings.setFixedHeight(36)
        btn_open_settings.setProperty("class", "btnText")

        btn_dismiss = QPushButton(translate("Hide"))
        set_custom_tooltip(
            btn_dismiss,
            title = translate("Hide until next launch"),
        )
        btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_dismiss.setFixedHeight(36)
        btn_dismiss.setProperty("class", "btnText")

        btn_layout.addWidget(btn_open_settings)
        btn_layout.addWidget(btn_dismiss)

        w_layout.addLayout(btn_layout)

        def open_settings_action():
            """
            Opens the application settings navigated to the general tab.
            """
            mw.open_settings(tab_index=1)

        def dismiss_action():
            """
            Hides the warning message and saves the dismissal state to settings.
            """
            mw.dismissed_album_merge_warning = True
            mw.save_current_settings()
            warning_frame.hide()

        btn_open_settings.clicked.connect(open_settings_action)
        btn_dismiss.clicked.connect(dismiss_action)

        warning_frame_layout.addWidget(warning_widget)

        return warning_frame

    def create_library_hint_widget(self):
        """
        Creates an informational hint widget explaining how to add music via drag-and-drop.
        """
        mw = self.main_window

        hint_frame = QFrame()
        hint_frame.setContentsMargins(0, 0, 0, 0)
        hint_frame.setProperty("class", "backgroundPrimary")

        hint_frame_layout = QHBoxLayout(hint_frame)
        hint_frame_layout.setContentsMargins(0, 0, 0, 0)
        hint_frame_layout.setSpacing(0)

        hint_widget = QWidget()
        hint_widget.setContentsMargins(16, 12, 16, 12)
        hint_widget.setProperty("class", "notificationWidget")

        w_layout = QHBoxLayout(hint_widget)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_layout.setSpacing(16)

        icon_label = QLabel()
        icon_pixmap = create_svg_icon(
            "assets/control/folder_add.svg", theme.COLORS["TERTIARY"], QSize(24, 24)
        ).pixmap(QSize(24, 24))
        icon_label.setPixmap(icon_pixmap)
        w_layout.addWidget(icon_label, alignment = Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        header_label = QLabel(translate("Add new music easily!"))
        header_label.setWordWrap(True)
        header_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header_label.setProperty("class", "textHeaderSecondary")
        text_layout.addWidget(header_label)

        msg_text = translate(
            "Drag and drop a music folder or files into the Vinyller window to add them to the library. You can manage your library in the settings window under the 'Library' tab."
        )
        info_label = QLabel(msg_text)
        info_label.setWordWrap(True)
        info_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        info_label.setProperty("class", "textSecondary")
        text_layout.addWidget(info_label)
        w_layout.addLayout(text_layout, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_open_settings = QPushButton(translate("Settings"))
        set_custom_tooltip(
            btn_open_settings,
            title = translate("Open settings"),
        )
        btn_open_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_settings.setFixedHeight(36)
        btn_open_settings.setProperty("class", "btnText")

        btn_dismiss = QPushButton(translate("Hide"))
        set_custom_tooltip(
            btn_dismiss,
            title = translate("Hide until next launch"),
        )
        btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_dismiss.setFixedHeight(36)
        btn_dismiss.setProperty("class", "btnText")

        btn_layout.addWidget(btn_open_settings)
        btn_layout.addWidget(btn_dismiss)

        w_layout.addLayout(btn_layout)

        def open_settings_action():
            """
            Opens the application settings navigated to the library tab.
            """
            mw.open_settings(tab_index=2)

        def dismiss_action():
            """
            Hides the hint message and saves the dismissal state to settings.
            """
            mw.dismissed_add_folder_hint = True
            mw.save_current_settings()
            hint_frame.hide()

        btn_open_settings.clicked.connect(open_settings_action)
        btn_dismiss.clicked.connect(dismiss_action)

        hint_frame_layout.addWidget(hint_widget)

        return hint_frame

    def _get_disc_info(self, album_key):
        """
        Calculates the internal disc number sequence if there are multiple parts of the same album.
        """
        mw = self.main_window

        if (
            not mw.treat_folders_as_unique
            or not isinstance(album_key, tuple)
            or len(album_key) < 4
        ):
            return None, None

        artist = album_key[0]
        title = album_key[1]
        year = album_key[2]

        all_discs = []

        for key in mw.data_manager.albums_data.keys():
            if isinstance(key, tuple) and len(key) >= 4:
                if key[0] == artist and key[1] == title and key[2] == year:
                    all_discs.append(key)

        if len(all_discs) <= 1:
            return None, None

        all_discs.sort(key=lambda k: k[3])

        try:
            disc_index = all_discs.index(album_key)
            return disc_index + 1, len(all_discs)
        except ValueError:
            return None, None

    def _show_no_search_results_message(self, layout):
        """
        Displays a centered message indicating that no items matched the active search query.
        """
        layout.addStretch(1)

        title_label = QLabel(translate("Hmm..."))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        text_label = QLabel(translate("Nothing found. Time to expand the library?"))
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        reset_button = QPushButton(translate("Reset filter"))
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.setFixedHeight(36)
        reset_button.setProperty("class", "btnText")
        reset_button.clicked.connect(self._clear_active_filter)
        layout.addWidget(reset_button, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

    def _show_no_history_results_message(self, layout):
        """
        Displays a centered message indicating that the user's playback history is currently empty.
        """
        layout.addStretch(1)

        title_label = QLabel(translate("Hmm..."))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        text_label = QLabel(translate("Playback history is empty."))
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        layout.addStretch(1)

    def _clear_active_filter(self):
        """
        Clears the text in the main window's global search input field.
        """
        mw = self.main_window

        if hasattr(mw, "global_search_bar") and mw.global_search_bar.isVisible():
            mw.global_search_bar.clear()
            return

    def _show_no_playlists_message(self, layout):
        """
        Displays a simple message indicating that there are no saved playlists found.
        """
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setSpacing(16)

        title_label = QLabel(translate("No saved playlists"))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        container_layout.addWidget(title_label)

        text_label = QLabel(translate("Create your own playlists..."))
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        container_layout.addWidget(text_label)

        container_layout.addStretch(1)

        layout.addWidget(container)

    def create_my_wave_banner(self, on_play_wave, on_play_random_album):
        """
        Creates a large visual banner block for the 'My Wave' and 'Random Album' play features.
        """

        mw = self.main_window

        accent_color = theme.get_qcolor(theme.COLORS["ACCENT"])

        r, g, b = accent_color.red(), accent_color.green(), accent_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        is_dark_theme = theme.COLORS.get("IS_DARK", False)

        if brightness > 160 and not is_dark_theme:
            text_color_class = "textColorPrimary"
            btn_text_color_class = "textColorPrimary"
            icon_color = theme.COLORS["PRIMARY"]
        elif brightness > 160:
            text_color_class = "textColorSecondary"
            btn_text_color_class = "textColorSecondary"
            icon_color = theme.COLORS["SECONDARY"]
        else:
            text_color_class = "textColorWhite"
            btn_text_color_class = "textColorAccent"
            icon_color = theme.COLORS["ACCENT"]

        self.my_wave_animation_frames = [
            create_svg_icon(
                f"assets/animation/track/now_playing_{i}.svg",
                icon_color,
                QSize(20, 20),
            ).pixmap(20, 20)
            for i in range(1, 9)
        ]

        banner = QWidget()
        banner.setProperty("class", "bannerMyWave")

        layout = QVBoxLayout(banner)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(16)

        title = QLabel(get_random_greeting())
        title.setProperty("class", f"textBannerPrimary {text_color_class}")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        subtitle = QLabel(translate("Play random music based on your interests..."))
        subtitle.setProperty("class", f"textBannerSecondary {text_color_class}")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)

        btns_layout = QHBoxLayout()
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.setSpacing(16)

        btn_wave = IconSpaceButton(spacing = 8)
        btn_wave.setText(translate("My Wave"))
        set_custom_tooltip(
            btn_wave,
            title = translate("Listen to the Wave"),
            text = translate("Vinyller will create a playback queue based on your preferences: your favorite music and music charts"),
        )
        btn_wave.setCursor(Qt.CursorShape.PointingHandCursor)

        static_icon_pix = create_svg_icon(
            "assets/control/wave.svg", icon_color, QSize(20, 20)
        ).pixmap(20, 20)

        if (
                mw.current_queue_name == translate("My Wave")
                and mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState
        ):
            current_frame = getattr(mw, "now_playing_animation_frame", 0)
            btn_wave.setCustomIcon(self.my_wave_animation_frames[current_frame])
        else:
            btn_wave.setCustomIcon(static_icon_pix)

        mw.my_wave_btn = btn_wave
        mw.my_wave_static_pixmap = static_icon_pix

        btn_wave.destroyed.connect(lambda: setattr(mw, "my_wave_btn", None))
        btn_wave.setProperty("class", f"btnBanner {btn_text_color_class}")
        btn_wave.setTextColorClass(btn_text_color_class)

        btn_wave.setFixedHeight(36)
        btn_wave.clicked.connect(on_play_wave)

        btn_random = QPushButton(translate("Random Album"))
        set_custom_tooltip(
            btn_random,
            title = translate("Spin up random album"),
            text = translate(
                "Vinyller will pick and play random album from your library"),
        )
        btn_random.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_random.setProperty("class", f"btnBanner {btn_text_color_class}")
        btn_random.setFixedHeight(36)
        btn_random.clicked.connect(on_play_random_album)

        btns_layout.addWidget(btn_wave)
        btns_layout.addWidget(btn_random)
        btns_layout.addStretch()

        layout.addLayout(text_layout)
        layout.addLayout(btns_layout)

        return banner

    def create_horizontal_section(self, title, items_widget, on_see_all):
        """
        Creates a section block with a title and an embedded horizontal scroll area containing cards.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 8, 0)

        lbl_title = QLabel(title)
        lbl_title.setProperty("class", "textHeaderSecondary textColorPrimary")

        btn_see_all = QPushButton(translate("See all"))
        btn_see_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_see_all.setFixedHeight(36)
        btn_see_all.setProperty("class", "btnText")
        btn_see_all.clicked.connect(on_see_all)

        h_layout.addWidget(lbl_title)
        h_layout.addStretch()
        h_layout.addWidget(btn_see_all)

        layout.addWidget(header)

        scroll = StyledScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setProperty("class", "backgroundPrimary")

        items_widget.setProperty("class", "backgroundPrimary")
        scroll.setWidget(items_widget)
        scroll.setFixedHeight(items_widget.sizeHint().height() + 20)

        layout.addWidget(scroll)

        return container
