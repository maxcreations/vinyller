"""
Vinyller — Settings window
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
from pathlib import Path

from PyQt6.QtCore import (
    pyqtSignal, QEvent, QSize, Qt,
    QTimer, QPoint, QUrl
)
from PyQt6.QtGui import (
    QColor, QIcon,
    QPainter, QPixmap, QAction, QDesktopServices
)
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QFormLayout, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QListWidgetItem, QPushButton,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QDialogButtonBox, QGridLayout
)

from src.core.hotkey_manager import HotkeyManager
from src.encyclopedia.encyclopedia_dialogs import EncyclopediaCleanupDialog
from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledListWidget, StyledScrollArea,
    TranslucentCombo, TranslucentMenu, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ElidedLabel
)
from src.ui.custom_dialogs import (
    BlacklistDialog, CustomConfirmDialog, UnavailableFavoritesDialog, NavOrderDialog, LicenseDialog
)
from src.ui.search_services_tools import AddSearchLinkDialog
from src.utils import theme
from src.utils.constants import (
    APP_VERSION, ArtistSource, SUPPORTED_LANGUAGES, FAVORITE_ICONS, ARTICLES_TO_IGNORE
)
from src.utils.constants_linux import IS_LINUX
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_color_picker import ColorPickerPopup
from src.utils.utils_translator import translate


class PathListItemWidget(QWidget):
    """
    A custom widget used to display a directory path within a QListWidget.
    Includes a label for the path and a button to remove the item from the list.
    """
    remove_requested = pyqtSignal(QListWidgetItem)

    def __init__(self, path_text, list_widget_item, parent=None):
        """
        Initializes the path list item widget.

        Args:
            path_text (str): The directory path to display.
            list_widget_item (QListWidgetItem): The parent item in the list widget.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.list_widget_item = list_widget_item
        self.path = path_text
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setFixedHeight(36)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(8)

        path_label = ElidedLabel(path_text, show_tooltip=False)
        path_label.setProperty("class", "textColorPrimary")
        path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        set_custom_tooltip(
            path_label,
            title = translate("Folder Path"),
            text = f"{path_text}",
        )
        self.remove_button = QPushButton()
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        self.remove_button.setFixedSize(24, 24)
        self.remove_button.setIconSize(QSize(16, 16))
        self.remove_button.setProperty("class", "btnListAction")
        set_custom_tooltip(
            self.remove_button,
            title = translate("Remove folder"),
        )
        apply_button_opacity_effect(self.remove_button)
        self.remove_button.clicked.connect(self._on_remove_clicked)

        self.remove_button.hide()

        layout.addWidget(path_label, 1)
        layout.addWidget(self.remove_button)

        main_layout.addWidget(self.container)

    def _on_remove_clicked(self):
        """Emits a signal requesting the removal of this item from the parent list."""
        self.remove_requested.emit(self.list_widget_item)

    def enterEvent(self, event):
        """Shows the remove button when the mouse cursor enters the widget area."""
        self.remove_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the remove button when the mouse cursor leaves the widget area."""
        self.remove_button.hide()
        super().leaveEvent(event)


class SearchLinkItemWidget(QWidget):
    """
    A custom widget used to display an external search service link within a QListWidget.
    Includes controls to toggle visibility, edit (if custom), and remove the link.
    """
    remove_requested = pyqtSignal(QListWidgetItem)
    edit_requested = pyqtSignal(QListWidgetItem)
    toggle_requested = pyqtSignal(QListWidgetItem)

    def __init__(self, link_data, list_widget_item, parent=None):
        """
        Initializes the search link item widget.

        Args:
            link_data (dict): Dictionary containing link details ('name', 'url', 'enabled', 'lyrics', 'is_custom').
            list_widget_item (QListWidgetItem): The parent item in the list widget.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.list_widget_item = list_widget_item
        self.link_data = link_data

        is_enabled = link_data.get("enabled", True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        name_label = ElidedLabel(link_data["name"], show_tooltip=False)
        name_label.setProperty("class", "textColorPrimary")
        name_label.installEventFilter(self)
        set_custom_tooltip(
            name_label,
            title = f"{link_data["name"]}",
            text = f"{link_data["url"]}",
        )
        if not is_enabled:
            opacity = QGraphicsOpacityEffect(name_label)
            opacity.setOpacity(0.5)
            name_label.setGraphicsEffect(opacity)

        layout.addWidget(name_label, 1)

        if link_data.get("lyrics"):
            lyrics_icon = QLabel()
            pix = create_svg_icon(
                "assets/control/lyrics.svg", theme.COLORS["TERTIARY"], QSize(16, 16)
            ).pixmap(16, 16)
            lyrics_icon.setPixmap(pix)
            set_custom_tooltip(
                lyrics_icon,
                title = translate("Supports lyrics search"),
            )
            if not is_enabled:
                op_eff = QGraphicsOpacityEffect(lyrics_icon)
                op_eff.setOpacity(0.5)
                lyrics_icon.setGraphicsEffect(op_eff)
            layout.addWidget(lyrics_icon)

        toggle_btn = QToolButton()
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        icon_name = "visible.svg" if is_enabled else "invisible.svg"
        icon_color = theme.COLORS["PRIMARY"] if is_enabled else theme.COLORS["PRIMARY"]

        toggle_btn.setIcon(
            create_svg_icon(f"assets/control/{icon_name}", icon_color, QSize(16, 16))
        )
        toggle_btn.setFixedSize(24, 24)
        toggle_btn.setIconSize(QSize(16, 16))
        toggle_btn.setProperty("class", "btnListAction")
        set_custom_tooltip(
            toggle_btn,
            title = translate("Show in menu") if not is_enabled else translate("Hide from menu"),
        )
        apply_button_opacity_effect(toggle_btn)

        toggle_btn.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(toggle_btn)

        if link_data.get("is_custom", False):
            edit_button = QPushButton()
            edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_button.setIcon(
                create_svg_icon(
                    "assets/control/edit.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
                )
            )
            edit_button.setFixedSize(24, 24)
            edit_button.setIconSize(QSize(16, 16))
            edit_button.setProperty("class", "btnListAction")
            set_custom_tooltip(
                edit_button,
                title = translate("Edit"),
            )
            apply_button_opacity_effect(edit_button)
            edit_button.clicked.connect(self._on_edit_clicked)
            layout.addWidget(edit_button)

            remove_button = QPushButton()
            remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_button.setIcon(
                create_svg_icon(
                    "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
                )
            )
            remove_button.setFixedSize(24, 24)
            remove_button.setIconSize(QSize(16, 16))
            remove_button.setProperty("class", "btnPathRemove")
            set_custom_tooltip(
                remove_button,
                title = translate("Remove"),
            )
            apply_button_opacity_effect(remove_button)
            remove_button.clicked.connect(self._on_remove_clicked)
            layout.addWidget(remove_button)
        else:
            pass

    def _on_remove_clicked(self):
        """Emits a signal requesting the removal of this custom search link."""
        self.remove_requested.emit(self.list_widget_item)

    def _on_edit_clicked(self):
        """Emits a signal requesting the editing of this custom search link."""
        self.edit_requested.emit(self.list_widget_item)

    def _on_toggle_clicked(self):
        """Emits a signal requesting to toggle the enabled/disabled state of this link."""
        self.toggle_requested.emit(self.list_widget_item)


class SettingsWindow(StyledDialog):
    """
    The main settings dialog window, providing tabs for general preferences,
    library paths, statistics, hotkeys, and application details.
    """
    rescan_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    clear_stats_requested = pyqtSignal()
    theme_change_requires_restart = pyqtSignal()
    deferred_rescan_requested = pyqtSignal()

    def __init__(self, settings, parent=None, start_tab_index=0, title=""):
        """
        Initializes the settings dialog, layouts, side navigation, and content pages.

        Args:
            settings (dict): The current application settings dictionary.
            parent (QWidget, optional): The parent widget (MainWindow).
            start_tab_index (int, optional): The index of the tab to display upon opening.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Settings"))
        self.resize(800, 600)

        self.settings = settings
        self.initial_paths = list(self.settings.get("musicLibraryPaths", []))
        self.initial_theme = self.settings.get("theme", "Light")
        self.initial_accent = self.settings.get("accent_color", "Crimson")

        self.nav_tab_order = []

        mw = self.parent()
        self.local_blacklist = mw.library_manager.load_blacklist()
        self.local_unavailable = mw.library_manager.load_unavailable_favorites()
        self.local_search_links = mw.library_manager.load_search_links()

        self.setProperty("class", "backgroundPrimary")

        self.icon_label = None
        self.icon_click_count = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation_frame)
        self.animation_frames = []
        self.current_frame_index = 0
        self.original_pixmap = None
        self.icon_size = QSize(256, 86)
        self.animation_loop_count = 0
        self.animation_total_loops = 3

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(0)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        nav_widget = QWidget()
        nav_widget.setContentsMargins(16, 16, 16, 16)
        nav_widget.setProperty("class", "navBar")

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setSpacing(24)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidgetNav")
        self.list_widget.setFixedWidth(200)
        self.list_widget.setSpacing(2)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setContentsMargins(0, 0, 0, 0)

        nav_layout.addWidget(self.list_widget)
        settings_layout.addWidget(nav_widget)
        settings_layout.addWidget(self.stacked_widget, 1)

        self.main_layout.addLayout(settings_layout, 1)

        self.setup_general_tab()
        self.setup_preferences_tab()
        self.setup_library_tab()
        self.setup_statistics_tab()
        self.setup_encyclopedia_tab()
        self.setup_search_resources_tab()
        self.setup_hotkeys_tab()
        self.setup_about_tab()
        self.setup_credits_tab()

        self._add_settings_page(self.general_tab, translate("General"))
        self._add_settings_page(self.preferences_tab, translate("Preferences"))
        self._add_settings_page(self.library_tab, translate("Library"))
        self._add_settings_page(self.statistics_tab, translate("Charts and Rating"))
        self._add_settings_page(self.encyclopedia_tab, translate("Encyclopedia"))
        self._add_settings_page(self.search_resources_tab, translate("Search Services"))
        self._add_settings_page(self.hotkeys_tab, translate("Hotkeys"))
        self._add_settings_page(self.about_tab, translate("About"))
        self._add_settings_page(self.credits_tab, translate("Credits"))

        self.list_widget.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.list_widget.setCurrentRow(start_tab_index)

        self._setup_mappings()
        self.load_initial_settings()

        dialog_buttons_widget = QWidget()
        dialog_buttons_widget.setContentsMargins(0, 0, 0, 0)
        dialog_buttons_widget.setProperty("class", "controlPanel")

        dialog_buttons_layout = QHBoxLayout(dialog_buttons_widget)
        dialog_buttons_layout.setContentsMargins(24, 16, 24, 16)
        dialog_buttons_layout.setSpacing(16)

        self.reset_button = QPushButton(translate("Reset Settings"))
        set_custom_tooltip(
            self.reset_button,
            title = translate("Reset Settings"),
            text = translate("Reset all settings and preferences"),
        )
        self.reset_button.setProperty("class", "btnText")
        self.reset_button.setFixedHeight(36)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self.reset_requested.emit)

        self.rescan_button = QPushButton(translate("Update library"))
        set_custom_tooltip(
            self.rescan_button,
            title = translate("Update library"),
            text = translate("Launch full library rescan"),

        )
        self.rescan_button.setProperty("class", "btnText")
        self.rescan_button.setFixedHeight(36)
        self.rescan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rescan_button.clicked.connect(self.rescan_requested.emit)

        self.button_box = QDialogButtonBox(self)

        self.apply_button = self.button_box.addButton(
            translate("Apply"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.apply_button.clicked.connect(self.accept)
        self.apply_button.setEnabled(False)

        cancel_button = self.button_box.addButton(
            translate("Cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        cancel_button.clicked.connect(self.reject)

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        dialog_buttons_layout.addWidget(self.reset_button)
        dialog_buttons_layout.addWidget(self.rescan_button)
        dialog_buttons_layout.addStretch(1)
        dialog_buttons_layout.addWidget(self.button_box)

        self.main_layout.addWidget(dialog_buttons_widget)
        self._connect_signals()

    def _add_settings_page(self, widget, name):
        """
        Adds a new settings page to the stacked widget and a corresponding entry to the sidebar list.

        Args:
            widget (QWidget): The content widget for this settings page.
            name (str): The localized name to display in the list.
        """
        self.stacked_widget.addWidget(widget)
        item = QListWidgetItem(name)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        item.setSizeHint(QSize(item.sizeHint().width(), 40))
        self.list_widget.addItem(item)

    def accept(self):
        """Handles the 'Apply/Accept' action of the dialog."""
        super().accept()

    def setup_general_tab(self):
        """Creates and layouts the 'General' settings tab."""
        self.general_tab = QWidget()
        self.general_tab.setContentsMargins(24, 24, 24, 24)
        general_layout = QVBoxLayout(self.general_tab)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(24)

        general_header_layout = QHBoxLayout()
        general_header_layout.setContentsMargins(0, 0, 0, 0)
        general_header_layout.setSpacing(16)

        general_text_layout = QVBoxLayout()
        general_text_layout.setContentsMargins(0, 0, 0, 0)
        general_text_layout.setSpacing(8)

        general_header_label = QLabel(translate("General settings"))
        general_header_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        general_text_layout.addWidget(general_header_label)

        general_tex_label = QLabel(translate("General settings description text..."))
        general_tex_label.setWordWrap(True)
        general_tex_label.setProperty("class", "textSecondary textColorPrimary")
        general_text_layout.addWidget(general_tex_label)

        general_header_layout.addLayout(general_text_layout, stretch = 1)

        general_layout.addLayout(general_header_layout)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setFixedHeight(36)
            return lbl

        self.language_combo = TranslucentCombo()
        self.language_combo.setFixedHeight(36)
        for name, (code, icon_path) in SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(name, code)

        self.theme_combo = TranslucentCombo()
        self.theme_combo.setFixedHeight(36)
        for theme_name in theme.THEMES.keys():
            self.theme_combo.addItem(translate(theme_name), theme_name)

        self.accent_container = QWidget()
        self.accent_container.setFixedHeight(36)
        self.accent_layout = QHBoxLayout(self.accent_container)
        self.accent_layout.setContentsMargins(0, 0, 0, 0)
        self.accent_layout.setSpacing(8)

        self.accent_combo = TranslucentCombo()
        self.accent_combo.setFixedHeight(36)

        for color_name, hex_code in theme.ACCENT_PALETTE.items():
            color = theme.get_qcolor(hex_code)
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 16, 16, 3, 3)
            painter.end()
            self.accent_combo.addItem(QIcon(pixmap), translate(color_name), color_name)

        self.accent_combo.addItem(create_svg_icon(
            "assets/control/paint.svg",
            theme.COLORS["PRIMARY"]), translate("Custom color..."), "CUSTOM_USER_DEFINED")

        self.custom_color_btn = QPushButton()
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.setProperty("class", "btnText")
        self.custom_color_btn.clicked.connect(self._open_color_picker)
        self.custom_color_btn.hide()

        self.accent_combo.currentIndexChanged.connect(self._on_accent_combo_changed)

        self.accent_layout.addWidget(self.accent_combo, 1)
        self.accent_layout.addWidget(self.custom_color_btn)

        self.remember_queue_combo = TranslucentCombo()
        self.remember_queue_combo.setFixedHeight(36)
        self.remember_queue_combo.addItem(translate("Do not remember queue"), 0)
        self.remember_queue_combo.addItem(translate("Remember queue"), 1)
        self.remember_queue_combo.addItem(translate("Remember last played track"), 2)
        self.remember_queue_combo.addItem(translate("Remember track position"), 3)

        self.playback_history_combo = TranslucentCombo()
        self.playback_history_combo.setFixedHeight(36)
        self.playback_history_combo.addItem(translate("Do not remember history"), 0)
        self.playback_history_combo.addItem(translate("Remember for current session"), 1)
        self.playback_history_combo.addItem(translate("Remember last 1000 tracks"), 2)

        self.history_store_unique_checkbox = QCheckBox()
        self.history_store_unique_checkbox.setMinimumHeight(18)
        self.history_store_unique_checkbox.setText(
            translate("Store only unique tracks in history")
        )
        set_custom_tooltip(
            self.history_store_unique_checkbox,
            title = translate("Store only unique tracks in history"),
            text = translate("Unique tracks in history tooltip..."),
        )
        self.history_store_unique_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.playback_history_combo.currentIndexChanged.connect(
            self._update_history_checkbox_state
        )

        self.remember_last_view_checkbox = QCheckBox()
        self.remember_last_view_checkbox.setMinimumHeight(18)
        self.remember_last_view_checkbox.setText(
            translate("Remember last viewed page")
        )
        set_custom_tooltip(
            self.remember_last_view_checkbox,
            title = translate("Remember last viewed page"),
            text = translate("Restore the last viewed page on startup."),
        )
        self.remember_last_view_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.remember_window_size_checkbox = QCheckBox()
        self.remember_window_size_checkbox.setMinimumHeight(18)
        self.remember_window_size_checkbox.setText(
            translate("Remember window size")
        )
        set_custom_tooltip(
            self.remember_window_size_checkbox,
            title = translate("Remember window size"),
            text = translate("Remember the size of the window for all window modes"),
        )
        self.remember_window_size_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.show_separators_checkbox = QCheckBox()
        self.show_separators_checkbox.setMinimumHeight(18)
        self.show_separators_checkbox.setText(translate("Show navigation separators on the main pages of tabs"))

        set_custom_tooltip(
            self.show_separators_checkbox,
            title = translate("Show navigation separators on the main pages of tabs"),
            text = translate(
                "The main pages of each tab will display navigation separators. Clicking them allows you to quickly "
                "jump to any other separator on the current page — for example, to reach artists or albums starting with M."),
        )
        self.show_separators_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.show_favorites_separators_checkbox = QCheckBox()
        self.show_favorites_separators_checkbox.setMinimumHeight(18)
        self.show_favorites_separators_checkbox.setText(
            translate('Show navigation separators on "All Favorites..." and "All Popular..." pages')
        )
        set_custom_tooltip(
            self.show_favorites_separators_checkbox,
            title = translate('Show navigation separators on "All Favorites..." and "All Popular..." pages'),
            text = translate(
                "The pages for all favorite and popular artists, albums, genres, etc., will display navigation separators. "
                "Clicking them allows you to quickly skip to any other section on the page — for example, to reach artists or albums starting with M."),
        )
        self.show_favorites_separators_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.allow_drag_export_checkbox = QCheckBox()
        self.allow_drag_export_checkbox.setMinimumHeight(18)
        self.allow_drag_export_checkbox.setText(
            translate("Allow file export via drag-and-drop")
        )
        set_custom_tooltip(
            self.allow_drag_export_checkbox,
            title = translate("Allow file export via drag-and-drop"),
            text = translate(
                "Allows you to drag and drop tracks directly from the playback queue into your file manager (e.g., File Explorer or Finder) to copy them."),
        )
        self.allow_drag_export_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.check_updates_at_startup_checkbox = QCheckBox()
        self.check_updates_at_startup_checkbox.setMinimumHeight(18)
        self.check_updates_at_startup_checkbox.setText(
            translate("Automatically check for Vinyller updates at startup")
        )
        set_custom_tooltip(
            self.check_updates_at_startup_checkbox,
            title = translate("Check for Updates"),
            text = translate("Automatically check for new versions of Vinyller on GitHub when the program starts."),
        )
        self.check_updates_at_startup_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(16)
        grid_layout.setVerticalSpacing(16)
        grid_layout.setColumnStretch(1, 1)

        grid_layout.addWidget(make_label(translate("Language") + ":"), 0, 0)
        grid_layout.addWidget(self.language_combo, 0, 1)

        grid_layout.addWidget(make_label(translate("Color theme") + ":"), 1, 0)
        grid_layout.addWidget(self.theme_combo, 1, 1)

        grid_layout.addWidget(make_label(translate("Accent color") + ":"), 2, 0)
        grid_layout.addWidget(self.accent_container, 2, 1)

        grid_layout.addWidget(make_label(translate("On program close") + ":"), 3, 0)
        grid_layout.addWidget(self.remember_queue_combo, 3, 1)

        grid_layout.addWidget(make_label(translate("Playback history") + ":"), 4, 0)
        grid_layout.addWidget(self.playback_history_combo, 4, 1)

        checkboxes_layout = QVBoxLayout()
        checkboxes_layout.setContentsMargins(0, 0, 0, 0)
        checkboxes_layout.setSpacing(16)

        checkboxes_layout.addWidget(self.history_store_unique_checkbox)
        checkboxes_layout.addWidget(self.remember_last_view_checkbox)
        checkboxes_layout.addWidget(self.remember_window_size_checkbox)
        checkboxes_layout.addWidget(self.show_separators_checkbox)
        checkboxes_layout.addWidget(self.show_favorites_separators_checkbox)
        checkboxes_layout.addWidget(self.allow_drag_export_checkbox)
        checkboxes_layout.addWidget(self.check_updates_at_startup_checkbox)

        general_layout.addLayout(grid_layout)
        general_layout.addLayout(checkboxes_layout)

        general_layout.addStretch()

    def _open_color_picker(self):
        """Opens the color picker popup to define a custom accent color."""
        current_hex = self.custom_color_btn.text() or "#FF0000"

        self.color_picker = ColorPickerPopup(initial_color=current_hex, parent=self)

        self.color_picker.colorChanged.connect(self._update_custom_color_btn)

        btn_pos = self.custom_color_btn.mapToGlobal(QPoint(0, 0))

        margins = self.color_picker.layout.contentsMargins()

        x = btn_pos.x() + self.custom_color_btn.width() - self.color_picker.width() + margins.right()

        y = btn_pos.y() + self.custom_color_btn.height() - margins.top() + 4

        screen_geo = self.custom_color_btn.screen().geometry()
        if x + self.color_picker.width() > screen_geo.right():
            x = screen_geo.right() - self.color_picker.width() - 10

        self.color_picker.move(x, y)
        self.color_picker.show()

    def _update_custom_color_btn(self, hex_color):
        """
        Updates the custom color button's background and text color based on the selected hex value.

        Args:
            hex_color (str): The hexadecimal representation of the selected color.
        """
        bg_color = QColor(hex_color)

        r, g, b = bg_color.red(), bg_color.green(), bg_color.blue()

        brightness = (r * 299 + g * 587 + b * 114) / 1000

        text_color = "black" if brightness > 160 else "white"

        border_color = "rgba(0, 0, 0, 0.15)" if text_color == "black" else "rgba(255, 255, 255, 0.15)"

        self.custom_color_btn.setText(hex_color.upper())

        self.custom_color_btn.setText(hex_color)
        self.custom_color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_color};
                color: {text_color};
            }}
        """)
        self.custom_color_btn.setFixedSize(96, 36)
        self._check_for_changes()

    def setup_preferences_tab(self):
        """Creates and layouts the 'Preferences' settings tab, including behavioral and UI toggles."""
        self.preferences_tab = QWidget()
        self.preferences_tab.setContentsMargins(24, 24, 24, 24)
        preferences_layout = QVBoxLayout(self.preferences_tab)
        preferences_layout.setContentsMargins(0, 0, 0, 0)
        preferences_layout.setSpacing(24)

        preferences_header_layout = QHBoxLayout()
        preferences_header_layout.setContentsMargins(0, 0, 0, 0)
        preferences_header_layout.setSpacing(16)

        preferences_text_layout = QVBoxLayout()
        preferences_text_layout.setContentsMargins(0, 0, 0, 0)
        preferences_text_layout.setSpacing(8)

        preferences_header_label = QLabel(translate("Preferences"))
        preferences_header_label.setProperty(
            "class", "textHeaderPrimary textColorPrimary"
        )
        preferences_text_layout.addWidget(preferences_header_label)

        preferences_tex_label = QLabel(translate("Preferences description text..."))
        preferences_tex_label.setWordWrap(True)
        preferences_tex_label.setProperty("class", "textSecondary textColorPrimary")
        preferences_text_layout.addWidget(preferences_tex_label)

        preferences_header_layout.addLayout(preferences_text_layout, stretch=1)

        preferences_layout.addLayout(preferences_header_layout)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setFixedHeight(36)
            return lbl

        self.artist_source_combo = TranslucentCombo()
        self.artist_source_combo.setFixedHeight(36)
        self.artist_source_combo.addItem(
            translate("By Artist tag"), ArtistSource.ARTIST
        )
        self.artist_source_combo.addItem(
            translate("By Album Artist tag"), ArtistSource.ALBUM_ARTIST
        )

        self.ignore_articles_checkbox = QCheckBox()
        self.ignore_articles_checkbox.setMinimumHeight(18)
        self.ignore_articles_checkbox.setText(translate("Ignore articles (A, The, etc.) when sorting"))
        articles_str = ", ".join(ARTICLES_TO_IGNORE)
        set_custom_tooltip(
            self.ignore_articles_checkbox,
            title = translate("Articles to ignore"),
            text = articles_str,
        )
        self.ignore_articles_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.ignore_genre_case_checkbox = QCheckBox()
        self.ignore_genre_case_checkbox.setMinimumHeight(18)
        self.ignore_genre_case_checkbox.setText(translate('Ignore the case of the "Genre" tag'))
        set_custom_tooltip(
            self.ignore_genre_case_checkbox,
            title = translate('Ignore the case of the "Genre" tag'),
            text = translate("If enabled, genre tags with different capitalization will be logically merged and unified (e.g., ROCK and rock will be combined into Rock)."),
        )
        self.ignore_genre_case_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.treat_folders_as_unique_checkbox = QCheckBox()
        self.treat_folders_as_unique_checkbox.setMinimumHeight(18)
        self.treat_folders_as_unique_checkbox.setText(
            translate("Treat the same albums in different folders as separate")
        )
        set_custom_tooltip(
            self.treat_folders_as_unique_checkbox,
            title = translate("Treat the same albums in different folders as separate"),
            text = translate(
                "If enabled, albums with the same artist, title, and year, but located in different folders (e.g., releases for different regions), will be displayed as separate albums. They will be marked with a disc badge and a sequence number."
            ),
        )
        self.treat_folders_as_unique_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.show_random_suggestions_checkbox = QCheckBox()
        self.show_random_suggestions_checkbox.setMinimumHeight(18)
        self.show_random_suggestions_checkbox.setText(
            translate("Show suggestions of random music from your collection")
        )
        set_custom_tooltip(
            self.show_random_suggestions_checkbox,
            title = translate("Show suggestions of random music from your collection"),
            text = translate("Suggestions appear rules tooltip...")
        )
        self.show_random_suggestions_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.stylize_vinyl_covers_checkbox = QCheckBox()
        self.stylize_vinyl_covers_checkbox.setMinimumHeight(18)
        self.stylize_vinyl_covers_checkbox.setText(
            translate("Styled album artworks in Vinyl mode")
        )
        set_custom_tooltip(
            self.stylize_vinyl_covers_checkbox,
            title = translate("Styled album artworks in Vinyl mode"),
            text = translate("Adds a styled texture overlay to album covers in Vinyl mode"),
        )
        self.stylize_vinyl_covers_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.mini_opacity_checkbox = QCheckBox()
        self.mini_opacity_checkbox.setMinimumHeight(18)
        self.mini_opacity_checkbox.setText(
            translate("Enable window transparency in Mini mode")
        )
        set_custom_tooltip(
            self.mini_opacity_checkbox,
            title = translate("Enable window transparency in Mini mode"),
            text = translate("Makes the Mini window semi-transparent when it is not active"),
        )
        self.mini_opacity_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        if IS_LINUX:
            self.mini_opacity_checkbox.hide()

        self.warm_sound_checkbox = QCheckBox()
        self.warm_sound_checkbox.setMinimumHeight(18)
        self.warm_sound_checkbox.setText(translate("Vinyl background sound"))
        set_custom_tooltip(
            self.warm_sound_checkbox,
            title = translate("Vinyl background sound"),
            text = translate("Adds a classic vinyl background noise"),
        )
        self.warm_sound_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.scratch_sound_checkbox = QCheckBox()
        self.scratch_sound_checkbox.setMinimumHeight(18)
        self.scratch_sound_checkbox.setText(translate("Vinyl rewind effect"))
        set_custom_tooltip(
            self.scratch_sound_checkbox,
            title = translate("Vinyl rewind effect"),
            text = translate("Don't try this..."),
        )
        self.scratch_sound_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.autoplay_on_queue_checkbox = QCheckBox()
        self.autoplay_on_queue_checkbox.setMinimumHeight(18)
        self.autoplay_on_queue_checkbox.setText(
            translate("Auto-play when adding to queue")
        )
        set_custom_tooltip(
            self.autoplay_on_queue_checkbox,
            title = translate("Auto-play when adding to queue"),
            text = translate("Start playback automatically when adding tracks to an empty queue"),
        )
        self.autoplay_on_queue_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.favorite_icon_combo = TranslucentCombo()
        self.favorite_icon_combo.setFixedHeight(36)
        for display_name, data_name in FAVORITE_ICONS:
            icon = create_svg_icon(
                f"assets/control/{data_name}.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
            self.favorite_icon_combo.addItem(icon, translate(display_name), data_name)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(16)
        grid_layout.setVerticalSpacing(16)
        grid_layout.setColumnStretch(1, 1)

        grid_layout.addWidget(make_label(translate("Favorite icon") + ":"), 0, 0)
        grid_layout.addWidget(self.favorite_icon_combo, 0, 1)

        grid_layout.addWidget(make_label(translate("Group artists") + ":"), 1, 0)
        grid_layout.addWidget(self.artist_source_combo, 1, 1)

        checkboxes_layout = QVBoxLayout()
        checkboxes_layout.setContentsMargins(0, 0, 0, 0)
        checkboxes_layout.setSpacing(16)

        checkboxes_layout.addWidget(self.ignore_articles_checkbox)
        checkboxes_layout.addWidget(self.ignore_genre_case_checkbox)
        checkboxes_layout.addWidget(self.treat_folders_as_unique_checkbox)
        checkboxes_layout.addWidget(self.show_random_suggestions_checkbox)
        checkboxes_layout.addWidget(self.autoplay_on_queue_checkbox)
        checkboxes_layout.addWidget(self.stylize_vinyl_covers_checkbox)
        checkboxes_layout.addWidget(self.warm_sound_checkbox)
        checkboxes_layout.addWidget(self.scratch_sound_checkbox)
        checkboxes_layout.addWidget(self.mini_opacity_checkbox)

        preferences_layout.addLayout(grid_layout)
        preferences_layout.addLayout(checkboxes_layout)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setProperty("class", "separator")
        preferences_layout.addWidget(separator)

        nav_order_layout = QHBoxLayout()
        nav_order_text_layout = QVBoxLayout()
        nav_order_text_layout.setSpacing(4)

        nav_order_label = QLabel(translate("Navigation Tab Order"))
        nav_order_label.setProperty("class", "textHeaderSecondary textColorPrimary")

        nav_order_hint = QLabel(translate("Manage navigation bar tabs: reorder your main tabs and set your own custom order."))
        nav_order_hint.setWordWrap(True)
        nav_order_hint.setProperty("class", "textSecondary textColorPrimary")

        nav_order_text_layout.addWidget(nav_order_label)
        nav_order_text_layout.addWidget(nav_order_hint)

        self.manage_nav_btn = QPushButton(translate("Reorder"))
        self.manage_nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manage_nav_btn.setProperty("class", "btnText")
        self.manage_nav_btn.setFixedHeight(36)
        self.manage_nav_btn.clicked.connect(self._open_nav_order_dialog)

        nav_order_layout.addLayout(nav_order_text_layout, 1)
        nav_order_layout.addWidget(self.manage_nav_btn)

        preferences_layout.addLayout(nav_order_layout)

        preferences_layout.addStretch()

    def _open_nav_order_dialog(self):
        """Opens the dialog to manage navigation tab order."""
        dialog = NavOrderDialog(self.nav_tab_order, self)
        if dialog.exec():
            new_order = dialog.get_order()
            if new_order != self.nav_tab_order:
                self.nav_tab_order = new_order
        self._check_for_changes()

    def setup_library_tab(self):
        """Creates and layouts the 'Library' settings tab, covering folder paths, blacklist, and unavailable favorites."""
        self.library_tab = QWidget()
        self.library_tab.setContentsMargins(24, 24, 24, 24)
        library_layout = QVBoxLayout(self.library_tab)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(24)

        folders_layout = QVBoxLayout()
        folders_layout.setContentsMargins(0, 0, 0, 0)
        folders_layout.setSpacing(16)

        folders_header_layout = QHBoxLayout()
        folders_header_layout.setContentsMargins(0, 0, 0, 0)
        folders_header_layout.setSpacing(16)

        folders_text_layout = QVBoxLayout()
        folders_text_layout.setContentsMargins(0, 0, 0, 0)
        folders_text_layout.setSpacing(8)

        folders_header_label = QLabel(translate("Music folders"))
        folders_header_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        folders_text_layout.addWidget(folders_header_label)

        folders_tex_label = QLabel(
            translate("Add folders with music to build your library.")
        )
        folders_tex_label.setWordWrap(True)
        folders_tex_label.setProperty("class", "textSecondary textColorPrimary")
        folders_text_layout.addWidget(folders_tex_label)

        folders_header_layout.addLayout(folders_text_layout, stretch=1)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)

        add_button = QPushButton(translate("Add"))
        set_custom_tooltip(
            add_button,
            title = translate("Add folder"),
        )
        add_button.setProperty("class", "btnText inputBorderMultiLeft inputBorderPaddingButton")
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self.add_folder)
        buttons_layout.addWidget(add_button)
        folders_header_layout.addLayout(buttons_layout)

        self.more_button = QPushButton("")
        set_custom_tooltip(
            self.more_button,
            title = translate("Optimize Path List"),
            text = translate("Automatically removes subfolders if the parent folder is already listed"),
        )
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.setProperty("class", "inputBorderMultiRight")
        self.more_button.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.more_button.setIconSize(QSize(24, 24))
        apply_button_opacity_effect(self.more_button)
        self.more_button.clicked.connect(self.show_path_header_menu)
        buttons_layout.addWidget(self.more_button)

        folders_layout.addLayout(folders_header_layout)

        self.folder_list_widget = StyledListWidget()
        self.folder_list_widget.setSpacing(2)
        self.folder_list_widget.setProperty("class", "listWidget")
        self.populate_folder_list()
        folders_layout.addWidget(self.folder_list_widget)

        library_layout.addLayout(folders_layout, 1)

        blacklist_layout = QVBoxLayout()
        blacklist_layout.setContentsMargins(0, 0, 0, 0)
        blacklist_layout.setSpacing(16)

        blacklist_header_layout = QHBoxLayout()
        blacklist_header_layout.setContentsMargins(0, 0, 0, 0)
        blacklist_header_layout.setSpacing(16)

        blacklist_text_layout = QVBoxLayout()
        blacklist_text_layout.setContentsMargins(0, 0, 0, 0)
        blacklist_text_layout.setSpacing(8)

        blacklist_header_label = QLabel(translate("Blacklist"))
        blacklist_header_label.setProperty(
            "class", "textHeaderSecondary textColorPrimary"
        )
        blacklist_text_layout.addWidget(blacklist_header_label)

        blacklist_desc_label = QLabel(
            translate("Blacklist sections description text...")
        )
        blacklist_desc_label.setWordWrap(True)
        blacklist_desc_label.setProperty("class", "textSecondary textColorPrimary")
        blacklist_text_layout.addWidget(blacklist_desc_label)

        self.blacklist_count_label = QLabel()
        self.blacklist_count_label.setWordWrap(True)
        self.blacklist_count_label.setProperty(
            "class", "textSecondary textColorPrimary"
        )
        self._update_blacklist_count_label()
        blacklist_text_layout.addWidget(self.blacklist_count_label)

        blacklist_header_layout.addLayout(blacklist_text_layout, stretch=1)

        blacklist_button_layout = QHBoxLayout()
        blacklist_button = QPushButton(translate("Blacklist"))
        set_custom_tooltip(
            blacklist_button,
            title = translate("Manage blacklist"),
        )
        blacklist_button.setProperty("class", "btnText")
        blacklist_button.setCursor(Qt.CursorShape.PointingHandCursor)
        blacklist_button.clicked.connect(self._open_blacklist_dialog)
        blacklist_button_layout.addWidget(blacklist_button)
        blacklist_header_layout.addLayout(blacklist_button_layout)

        blacklist_layout.addLayout(blacklist_header_layout)

        library_layout.addLayout(blacklist_layout)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setProperty("class", "separator")
        library_layout.addWidget(separator)

        unavailable_layout = QVBoxLayout()
        unavailable_layout.setContentsMargins(0, 0, 0, 0)
        unavailable_layout.setSpacing(16)

        unavailable_header_layout = QHBoxLayout()
        unavailable_header_layout.setContentsMargins(0, 0, 0, 0)
        unavailable_header_layout.setSpacing(16)

        unavailable_text_layout = QVBoxLayout()
        unavailable_text_layout.setContentsMargins(0, 0, 0, 0)
        unavailable_text_layout.setSpacing(8)

        unavailable_header_label = QLabel(translate("Unavailable Favorites"))
        unavailable_header_label.setProperty(
            "class", "textHeaderSecondary textColorPrimary"
        )
        unavailable_text_layout.addWidget(unavailable_header_label)

        unavailable_desc_label = QLabel(
            translate("Unavailable sections description text...")
        )
        unavailable_desc_label.setWordWrap(True)
        unavailable_desc_label.setProperty("class", "textSecondary textColorPrimary")
        unavailable_text_layout.addWidget(unavailable_desc_label)

        self.unavailable_count_label = QLabel()
        self.unavailable_count_label.setWordWrap(True)
        self.unavailable_count_label.setProperty(
            "class", "textSecondary textColorPrimary"
        )
        self._update_unavailable_count_label()
        unavailable_text_layout.addWidget(self.unavailable_count_label)

        unavailable_header_layout.addLayout(unavailable_text_layout, stretch=1)

        unavailable_button_layout = QHBoxLayout()
        unavailable_button = QPushButton(translate("Unavailable list"))
        set_custom_tooltip(
            unavailable_button,
            title = translate("Manage unavailable favorites list"),
        )
        unavailable_button.setProperty("class", "btnText")
        unavailable_button.setCursor(Qt.CursorShape.PointingHandCursor)
        unavailable_button.clicked.connect(self._open_unavailable_dialog)
        unavailable_button_layout.addWidget(unavailable_button)
        unavailable_header_layout.addLayout(unavailable_button_layout)

        unavailable_layout.addLayout(unavailable_header_layout)

        library_layout.addLayout(unavailable_layout)

    def show_path_header_menu(self):
        """Shows the context menu for the queue header allowing path optimization."""
        menu = TranslucentMenu(self)

        optimize_action = QAction(translate("Optimize Path List"), self)
        optimize_action.triggered.connect(self.optimize_paths)
        menu.addAction(optimize_action)

        self.more_button.setProperty("active", True)
        self.more_button.style().unpolish(self.more_button)
        self.more_button.style().polish(self.more_button)

        menu.exec(self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))

        self.more_button.setProperty("active", False)
        self.more_button.style().unpolish(self.more_button)
        self.more_button.style().polish(self.more_button)

    def setup_search_resources_tab(self):
        """Creates and layouts the 'Search Services' settings tab."""
        self.search_resources_tab = QWidget()
        self.search_resources_tab.setContentsMargins(24, 24, 24, 24)

        main_layout = QVBoxLayout(self.search_resources_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(24)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        title_label = QLabel(translate("Manage Search Services"))
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        text_layout.addWidget(title_label)

        desc_label = QLabel(
            translate(
                "Add your favorite stores, video/audio hosts, and music info websites as search services..."
            )
        )
        desc_label.setWordWrap(True)
        desc_label.setProperty("class", "textSecondary textColorPrimary")
        text_layout.addWidget(desc_label)

        header_layout.addLayout(text_layout, stretch=1)

        buttons_layout = QHBoxLayout()
        add_button = QPushButton(translate("Add"))
        set_custom_tooltip(
            add_button,
            title = translate("Add search service"),
        )
        add_button.setProperty("class", "btnText")
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self.add_search_resource)
        buttons_layout.addWidget(add_button)
        header_layout.addLayout(buttons_layout)

        main_layout.addLayout(header_layout)

        self.search_links_list_widget = StyledListWidget()
        self.search_links_list_widget.setSpacing(2)
        self.search_links_list_widget.setProperty("class", "listWidget")

        self.populate_search_links_list()

        main_layout.addWidget(self.search_links_list_widget, 1)

    def populate_search_links_list(self):
        """Clears and populates the list of search links based on the saved data."""
        self.search_links_list_widget.clear()
        mw = self.parent()
        if not mw:
            return

        links = mw.library_manager.load_search_links()

        for link in links:
            self._add_search_link_item(link)

    def _add_search_link_item(self, link_data):
        """
        Instantiates and adds a SearchLinkItemWidget to the links list.

        Args:
            link_data (dict): The link dictionary containing details.
        """
        item = QListWidgetItem(self.search_links_list_widget)

        widget = SearchLinkItemWidget(link_data, item, self)
        widget.remove_requested.connect(self.remove_search_link)
        widget.edit_requested.connect(self.edit_search_link)
        widget.toggle_requested.connect(self.toggle_search_link)

        item.setSizeHint(widget.sizeHint())
        self.search_links_list_widget.addItem(item)

        self.search_links_list_widget.setItemWidget(item, widget)

    def toggle_search_link(self, item):
        """
        Toggles the enabled/disabled state of a search link via the LibraryManager.

        Args:
            item (QListWidgetItem): The list item bound to the search link.
        """
        mw = self.parent()
        if not mw:
            return

        widget = self.search_links_list_widget.itemWidget(item)
        name = widget.link_data["name"]

        mw.library_manager.toggle_search_provider_visibility(name)

        self.populate_search_links_list()

    def add_search_resource(self):
        """Opens a dialog to define and add a new custom search link."""
        mw = self.parent()
        if not mw:
            return

        dlg = AddSearchLinkDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                mw.library_manager.add_custom_search_link(
                    data["name"], data["url"], is_lyrics_suitable=data["lyrics"]
                )
                self.populate_search_links_list()

    def remove_search_link(self, item):
        """
        Prompts for confirmation and removes a custom search link if confirmed.

        Args:
            item (QListWidgetItem): The item representing the link to remove.
        """
        mw = self.parent()
        if not mw:
            return

        widget = self.search_links_list_widget.itemWidget(item)
        name = widget.link_data["name"]

        confirmed = CustomConfirmDialog.confirm(
            self,
            title=translate("Remove Service"),
            label=translate("Are you sure you want to remove '{name}'?", name=name),
            ok_text=translate("Remove"),
            cancel_text=translate("Cancel"),
        )

        if confirmed:
            if mw.library_manager.remove_custom_search_link(name):
                self.populate_search_links_list()

    def edit_search_link(self, item):
        """
        Opens a dialog to edit an existing custom search link.

        Args:
            item (QListWidgetItem): The item representing the link to edit.
        """
        mw = self.parent()
        if not mw:
            return

        widget = self.search_links_list_widget.itemWidget(item)
        old_data = widget.link_data

        dlg = AddSearchLinkDialog(
            self,
            edit_name=old_data["name"],
            edit_url=old_data["url"],
            edit_lyrics=old_data.get("lyrics", False),
        )

        if dlg.exec():
            new_data = dlg.get_data()
            if new_data:
                if hasattr(mw.library_manager, "edit_custom_search_link"):
                    mw.library_manager.edit_custom_search_link(
                        old_data["name"],
                        new_data["name"],
                        new_data["url"],
                        new_data["lyrics"],
                    )
                else:
                    mw.library_manager.remove_custom_search_link(old_data["name"])
                    mw.library_manager.add_custom_search_link(
                        new_data["name"],
                        new_data["url"],
                        is_lyrics_suitable=new_data["lyrics"],
                    )

                self.populate_search_links_list()

    def setup_statistics_tab(self):
        """Creates and layouts the 'Charts & Playback Rating' settings tab."""
        self.statistics_tab = QWidget()
        self.statistics_tab.setContentsMargins(24, 24, 24, 24)
        statistics_layout = QVBoxLayout(self.statistics_tab)
        statistics_layout.setContentsMargins(0, 0, 0, 0)
        statistics_layout.setSpacing(24)

        statistics_header_layout = QHBoxLayout()
        statistics_header_layout.setContentsMargins(0, 0, 0, 0)
        statistics_header_layout.setSpacing(16)

        statistics_text_layout = QVBoxLayout()
        statistics_text_layout.setContentsMargins(0, 0, 0, 0)
        statistics_text_layout.setSpacing(8)

        statistics_header_label = QLabel(translate("Charts & Playback Rating"))
        statistics_header_label.setProperty(
            "class", "textHeaderPrimary textColorPrimary"
        )
        statistics_text_layout.addWidget(statistics_header_label)

        statistics_desc_label = QLabel(translate("Charts tab description text..."))
        statistics_desc_label.setWordWrap(True)
        statistics_desc_label.setProperty("class", "textSecondary textColorPrimary")
        statistics_text_layout.addWidget(statistics_desc_label)

        statistics_header_layout.addLayout(statistics_text_layout, stretch=1)

        statistics_layout.addLayout(statistics_header_layout)

        rating_info_layout = QVBoxLayout()
        rating_info_layout.setContentsMargins(0, 0, 0, 0)
        rating_info_layout.setSpacing(8)

        rating_info_header_label = QLabel(translate("How rating is formed"))
        rating_info_header_label.setProperty("class", "textPrimary textColorPrimary")
        rating_info_layout.addWidget(rating_info_header_label)

        for i in range(1, 6):
            stats_rule_label_x = QLabel(translate(f"Rating rule {i}..."))
            stats_rule_label_x.setProperty("class", "textSecondary textColorPrimary")
            stats_rule_label_x.setWordWrap(True)
            rating_info_layout.addWidget(stats_rule_label_x)

        statistics_layout.addLayout(rating_info_layout)

        checkboxes_layout = QVBoxLayout()
        checkboxes_layout.setContentsMargins(0, 0, 0, 0)
        checkboxes_layout.setSpacing(16)

        self.collect_statistics_checkbox = QCheckBox()
        self.collect_statistics_checkbox.setMinimumHeight(18)
        self.collect_statistics_checkbox.setText(translate("Toggle charts"))

        checkboxes_layout.addWidget(self.collect_statistics_checkbox)
        statistics_layout.addLayout(checkboxes_layout)

        stats_separator = QWidget()
        stats_separator.setFixedHeight(1)
        stats_separator.setProperty("class", "separator")
        statistics_layout.addWidget(stats_separator)

        stats_layout = QVBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(16)

        stats_header_layout = QHBoxLayout()
        stats_header_layout.setContentsMargins(0, 0, 0, 0)
        stats_header_layout.setSpacing(16)

        stats_text_layout = QVBoxLayout()
        stats_text_layout.setContentsMargins(0, 0, 0, 0)
        stats_text_layout.setSpacing(8)

        stats_header_label = QLabel(translate("Reset Playback Rating"))
        stats_header_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        stats_text_layout.addWidget(stats_header_label)

        stats_desc_label = QLabel(translate("Reset playback rating text..."))
        stats_desc_label.setWordWrap(True)
        stats_desc_label.setProperty("class", "textSecondary textColorPrimary")
        stats_text_layout.addWidget(stats_desc_label)

        stats_header_layout.addLayout(stats_text_layout, stretch=1)

        stats_button_layout = QHBoxLayout()
        self.clear_stats_button = QPushButton(translate("Reset"))
        set_custom_tooltip(
            self.clear_stats_button,
            title = translate("Reset rating"),
        )
        self.clear_stats_button.setProperty("class", "btnText")
        self.clear_stats_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_stats_button.clicked.connect(self.clear_stats_requested.emit)
        stats_button_layout.addWidget(self.clear_stats_button)
        stats_header_layout.addLayout(stats_button_layout)

        stats_layout.addLayout(stats_header_layout)

        statistics_layout.addLayout(stats_layout)

        statistics_layout.addStretch()

        self.collect_statistics_checkbox.toggled.connect(
            self.clear_stats_button.setEnabled
        )

    def setup_encyclopedia_tab(self):
        """Creates and layouts the 'Encyclopedia' settings tab."""
        self.encyclopedia_tab = QWidget()
        self.encyclopedia_tab.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(self.encyclopedia_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(24)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        title_label = QLabel(translate("Music Encyclopedia"))
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        text_layout.addWidget(title_label)

        desc_label = QLabel(
            translate(
                "Supplement your music collection with background information about albums, artists, composers, and genres."
            )
        )
        desc_label.setWordWrap(True)
        desc_label.setProperty("class", "textSecondary textColorPrimary")
        text_layout.addWidget(desc_label)

        header_layout.addLayout(text_layout, stretch=1)
        main_layout.addLayout(header_layout)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)

        info1 = QLabel(
            translate(
                "Add descriptions, write your own album reviews, attach images and links to online resources — create your own music encyclopedia exactly how you want it."
            )
        )
        info1.setWordWrap(True)
        info1.setProperty("class", "textSecondary textColorPrimary")
        info_layout.addWidget(info1)

        info2 = QLabel(
            translate(
                "By the way, an image added to the description for an artist, composer, or genre can be set as the main card cover."
            )
        )
        info2.setWordWrap(True)
        info2.setProperty("class", "textSecondary textColorTertiary")
        info_layout.addWidget(info2)

        main_layout.addLayout(info_layout)

        sep1 = QWidget()
        sep1.setFixedHeight(1)
        sep1.setProperty("class", "separator")
        main_layout.addWidget(sep1)

        mgmt_layout = QVBoxLayout()
        mgmt_layout.setSpacing(16)

        mgmt_header_layout = QHBoxLayout()
        mgmt_text_layout = QVBoxLayout()
        mgmt_text_layout.setSpacing(8)

        mgmt_title = QLabel(translate("Encyclopedia Management"))
        mgmt_title.setProperty("class", "textHeaderSecondary textColorPrimary")
        mgmt_text_layout.addWidget(mgmt_title)

        mgmt_desc = QLabel(
            translate(
                "Backup your encyclopedia or transfer it to another device. Export saves the encyclopedia file and images to an archive. Import allows you to restore from a previously saved archive."
            )
        )
        mgmt_desc.setWordWrap(True)
        mgmt_desc.setProperty("class", "textSecondary textColorPrimary")
        mgmt_text_layout.addWidget(mgmt_desc)

        mgmt_header_layout.addLayout(mgmt_text_layout, 1)

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(16)

        import_btn = QPushButton(translate("Import"))
        set_custom_tooltip(
            import_btn,
            title = translate("Import encyclopedia"),
        )
        import_btn.setProperty("class", "btnText")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_encyclopedia)

        export_btn = QPushButton(translate("Export"))
        set_custom_tooltip(
            export_btn,
            title = translate("Export encyclopedia"),
        )
        export_btn.setProperty("class", "btnText")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_encyclopedia)

        btns_layout.addWidget(import_btn)
        btns_layout.addWidget(export_btn)

        mgmt_header_layout.addLayout(btns_layout)

        mgmt_layout.addLayout(mgmt_header_layout)
        main_layout.addLayout(mgmt_layout)

        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setProperty("class", "separator")
        main_layout.addWidget(sep2)

        cleanup_layout = QVBoxLayout()
        cleanup_layout.setSpacing(16)

        cleanup_header_layout = QHBoxLayout()
        cleanup_text_layout = QVBoxLayout()
        cleanup_text_layout.setSpacing(8)

        cleanup_title = QLabel(translate("Encyclopedia Cleanup"))
        cleanup_title.setProperty("class", "textHeaderSecondary textColorPrimary")
        cleanup_text_layout.addWidget(cleanup_title)

        cleanup_desc = QLabel(
            translate(
                "If unused images accidentally get into the encyclopedia folder, you can clean it up."
            )
        )
        cleanup_desc.setWordWrap(True)
        cleanup_desc.setProperty("class", "textSecondary textColorPrimary")
        cleanup_text_layout.addWidget(cleanup_desc)

        cleanup_header_layout.addLayout(cleanup_text_layout, 1)

        clean_btn = QPushButton(translate("Clean"))
        set_custom_tooltip(
            clean_btn,
            title = translate("Delete unused images"),
        )
        clean_btn.setProperty("class", "btnText")
        clean_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clean_btn.clicked.connect(self._open_encyclopedia_cleanup_dialog)
        cleanup_header_layout.addWidget(clean_btn)

        cleanup_layout.addLayout(cleanup_header_layout)
        main_layout.addLayout(cleanup_layout)

        main_layout.addStretch()

    def _import_encyclopedia(self):
        """Delegates the encyclopedia import action to the main window's UIManager."""
        self.parent().ui_manager.handle_encyclopedia_import(self)

    def _export_encyclopedia(self):
        """Delegates the encyclopedia export action to the main window's UIManager."""
        self.parent().ui_manager.handle_encyclopedia_export(self)

    def _open_encyclopedia_cleanup_dialog(self):
        """
        Opens a dialog to identify and clean up unreferenced encyclopedia images.
        Delegates the scanning and deletion logic to the EncyclopediaManager to keep the UI layer clean.
        """
        mw = self.parent()
        if not mw:
            return

        em = mw.encyclopedia_manager

        if not em.images_dir.exists():
            CustomConfirmDialog.confirm(
                self,
                translate("Cleanup"),
                translate("Encyclopedia folder is empty or does not exist."),
                ok_text=translate("OK"),
                cancel_text=None,
            )
            return

        orphans = em.get_orphaned_images()

        if not orphans:
            CustomConfirmDialog.confirm(
                self,
                translate("Cleanup"),
                translate("No unused images found."),
                ok_text=translate("OK"),
                cancel_text=None,
            )
            return

        dialog = EncyclopediaCleanupDialog(orphans, str(em.images_dir), self)
        if dialog.exec():
            deleted_count = em.remove_images(orphans)
            print(f"Cleanup finished. Deleted {deleted_count} files.")

    def setup_hotkeys_tab(self):
        """Creates and layouts the 'Hotkeys' settings tab."""
        self.hotkeys_tab = QWidget()
        self.hotkeys_tab.setContentsMargins(24, 0, 0, 0)
        hotkeys_layout = QVBoxLayout(self.hotkeys_tab)
        hotkeys_layout.setContentsMargins(0, 0, 0, 0)
        hotkeys_layout.setSpacing(16)

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        hotkeys_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        scroll_content.setProperty("class", "backgroundPrimary")
        scroll_area.setWidget(scroll_content)

        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 24, 24, 24)
        scroll_layout.setSpacing(16)

        header_label = QLabel(translate("Application Hotkeys"))
        header_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        scroll_layout.addWidget(header_label)

        desc_label = QLabel(
            translate(
                "Here is a list of keyboard shortcuts for quick access to application features."
            )
        )
        desc_label.setWordWrap(True)
        desc_label.setProperty("class", "textSecondary textColorPrimary")
        scroll_layout.addWidget(desc_label)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 8, 0, 0)
        form_layout.setSpacing(16)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        hotkeys = HotkeyManager.get_hotkey_list()

        for keys, description in hotkeys:
            desc_label = QLabel(description)
            desc_label.setProperty("class", "textColorPrimary")
            keys_label = QLabel(f"<b>{keys}</b>")
            keys_label.setProperty("class", "textColorPrimary")

            form_layout.addRow(keys_label, desc_label)

        scroll_layout.addLayout(form_layout)
        scroll_layout.addStretch()

    def _open_blacklist_dialog(self):
        """Opens a dialog allowing the user to manage the blacklist."""
        main_window = self.parent()
        if not main_window:
            return

        current_blacklist = main_window.library_manager.load_blacklist()
        dialog = BlacklistDialog(current_blacklist, main_window, self)
        if dialog.exec():
            new_blacklist = dialog.get_blacklist_data()
            if new_blacklist != current_blacklist:
                main_window.library_manager.save_blacklist(new_blacklist)
                self._update_blacklist_count_label()
                confirmed = CustomConfirmDialog.confirm(
                    self,
                    title=translate("Blacklist Updated"),
                    label=translate(
                        "The blacklist has been updated. A library rescan is required for the changes to take effect."
                    ),
                    ok_text=translate("Rescan Now"),
                    cancel_text=translate("Later"),
                )
                if confirmed:
                    self.rescan_requested.emit()
                else:
                    self.deferred_rescan_requested.emit()

    def _open_unavailable_dialog(self):
        """Opens a dialog allowing the user to manage unavailable favorite items."""
        main_window = self.parent()
        if not main_window:
            return

        current_unavailable = main_window.library_manager.load_unavailable_favorites()
        dialog = UnavailableFavoritesDialog(current_unavailable, self)
        if dialog.exec():
            new_unavailable = dialog.get_unavailable_data()
            if new_unavailable != current_unavailable:
                main_window.library_manager.save_unavailable_favorites(new_unavailable)
                self._update_unavailable_count_label()

                confirmed = CustomConfirmDialog.confirm(
                    self,
                    title=translate("List Updated"),
                    label=translate(
                        "The unavailable list has been updated. A library rescan is required to restore items."
                    ),
                    ok_text=translate("Rescan Now"),
                    cancel_text=translate("Later"),
                )
                if confirmed:
                    self.rescan_requested.emit()
                else:
                    self.deferred_rescan_requested.emit()

    def setup_about_tab(self):
        """Creates and layouts the 'About' settings tab containing app info and easter eggs."""
        self.about_tab = QWidget()
        self.about_tab.setContentsMargins(24, 0, 0, 0)
        about_layout = QVBoxLayout(self.about_tab)
        about_layout.setContentsMargins(0, 0, 0, 0)
        about_layout.setSpacing(24)

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        about_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        scroll_content.setProperty("class", "backgroundPrimary")
        scroll_area.setWidget(scroll_content)

        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 24, 24, 24)
        scroll_layout.setSpacing(32)

        text_icon_layout = QVBoxLayout()
        text_icon_layout.setContentsMargins(0, 0, 0, 0)
        text_icon_layout.setSpacing(16)

        easter_layout = QHBoxLayout()
        easter_layout.setContentsMargins(0, 0, 0, 0)
        easter_layout.setSpacing(0)

        self.icon_label = QLabel()

        is_dark = theme.COLORS.get("IS_DARK", False)
        suffix = "_dk" if is_dark else ""

        if self.settings.get("language") == 'ru':
            self.original_pixmap = QPixmap(resource_path(f"assets/logo/vinyller_logo_full_ru{suffix}.png"))
        else:
            self.original_pixmap = QPixmap(resource_path(f"assets/logo/vinyller_logo_full_en{suffix}.png"))

        set_custom_tooltip(
            self.icon_label,
            title = translate("Awa-waka-aw?"),
        )
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.icon_label.setFixedSize(self.icon_size)

        ratio = self.devicePixelRatioF()
        target_size = QSize(
            int(self.icon_size.width() * ratio),
            int(self.icon_size.height() * ratio)
        )

        self.scaled_original_pixmap = self.original_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.scaled_original_pixmap.setDevicePixelRatio(ratio)

        self.icon_label.setPixmap(self.scaled_original_pixmap)

        self.icon_label.installEventFilter(self)

        easter_layout.addWidget(self.icon_label)
        text_icon_layout.addLayout(easter_layout)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        app_ver_label = QLabel(translate("Version") + f" {APP_VERSION}")
        app_ver_label.setProperty("class", "textTertiary textColorTertiary")
        text_layout.addWidget(app_ver_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        main_desc_label = QLabel(translate("Vinyller main description..."))
        main_desc_label.setProperty("class", "textSecondary textColorPrimary")
        main_desc_label.setWordWrap(True)
        main_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_layout.addWidget(main_desc_label)

        text_icon_layout.addLayout(text_layout)

        links_layout = QHBoxLayout()
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.setSpacing(16)
        links_layout.addStretch()

        license_type_btn = QPushButton(translate("License type") + " " + "GPL-3.0+")
        license_type_btn.setProperty("class", "btnLink")
        license_type_btn.setFixedHeight(16)
        license_type_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            license_type_btn,
            title = translate("Read License"),
        )
        license_type_btn.clicked.connect(self.show_license_dialog)
        links_layout.addWidget(license_type_btn)

        github_link = "https://github.com/maxcreations/Vinyller"
        github_btn = QPushButton(translate("Vinyller on GitHub"))
        github_btn.setProperty("class", "btnLink")
        github_btn.setFixedHeight(16)
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            github_btn,
            title = translate("Open in browser"),
            text = github_link,
            activity_type = "external",
        )
        github_btn.setProperty("url", github_link)
        github_btn.clicked.connect(self._on_link_clicked)
        links_layout.addWidget(github_btn)

        manual_link = "https://github.com/maxcreations/Vinyller/docs/MANUAL.en.md"
        manual_btn = QPushButton(translate("User Manual"))
        manual_btn.setProperty("class", "btnLink")
        manual_btn.setFixedHeight(16)
        manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            manual_btn,
            title = translate("Open in browser"),
            text = manual_link + "\n\n" + translate("Available in English and Russian."),
            activity_type = "external",
        )
        manual_btn.setProperty("url", manual_link)
        manual_btn.clicked.connect(self._on_link_clicked)
        links_layout.addWidget(manual_btn)
        links_layout.addStretch()

        text_icon_layout.addLayout(links_layout)

        scroll_layout.addLayout(text_icon_layout)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setProperty("class", "separator")
        scroll_layout.addWidget(sep)

        description_layout = QVBoxLayout()
        description_layout.setContentsMargins(0, 0, 0, 0)
        description_layout.setSpacing(16)
        description_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        adv_header = QLabel(translate("Advantages main header..."))
        adv_header.setProperty("class", "textHeaderSecondary textColorPrimary")
        adv_header.setWordWrap(True)
        description_layout.addWidget(adv_header)

        for i in range(1, 9):
            adv_layout_x = QVBoxLayout()
            adv_layout_x.setContentsMargins(0, 0, 0, 0)
            adv_layout_x.setSpacing(2)

            adv_header_label_x = QLabel(translate(f"Advantages header {i}..."))
            adv_header_label_x.setProperty("class", "textPrimary textColorPrimary")
            adv_header_label_x.setWordWrap(True)
            adv_layout_x.addWidget(adv_header_label_x)

            adv_label_x = QLabel(translate(f"Advantages description {i}..."))
            adv_label_x.setProperty("class", "textSecondary textColorPrimary")
            adv_label_x.setWordWrap(True)
            adv_layout_x.addWidget(adv_label_x)

            description_layout.addLayout(adv_layout_x)

        description_layout.addLayout(scroll_layout)

        made_by_label = QLabel(
            translate("Created by Maxim Moshkin in 2026. Complex functions, methods, and multilingual translations were implemented with AI support.")
        )
        made_by_label.setProperty("class", "textSecondary textColorPrimary")
        made_by_label.setWordWrap(True)
        description_layout.addWidget(made_by_label)

        memory_label = QLabel(
            translate(
                "In memory of my father, who loved spinning records, winding tape reels, and taking notes "
                "about his collection in his notebook."
            )
        )
        memory_label.setProperty("class", "textSecondary textColorPrimary")
        memory_label.setWordWrap(True)
        description_layout.addWidget(memory_label)

        description_layout.addStretch()
        scroll_layout.addLayout(description_layout)

    def show_license_dialog(self):
        """Displays a dialog showing the application's software license."""
        dialog = LicenseDialog(self)
        dialog.exec()

    def _on_link_clicked(self):
        """Opens the associated URL in the system's default browser when a link button is clicked."""
        btn = self.sender()
        url = btn.property("url")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def setup_credits_tab(self):
        """Creates and layouts the 'Credits' settings tab."""
        self.credits_tab = QWidget()
        self.credits_tab.setContentsMargins(24, 24, 24, 24)
        credits_layout = QVBoxLayout(self.credits_tab)
        credits_layout.setContentsMargins(0, 0, 0, 0)
        credits_layout.setSpacing(24)

        header_label = QLabel(translate("Credits"))
        header_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        credits_layout.addWidget(header_label)

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setProperty("class", "backgroundPrimary")

        content_widget = QWidget()
        content_widget.setProperty("class", "backgroundPrimary")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        libs_header = QLabel(translate("Open Source Libraries"))
        libs_header.setProperty("class", "textHeaderSecondary textColorPrimary")
        content_layout.addWidget(libs_header)

        libraries_list = [
            ("PyQt6", "https://pypi.org/project/PyQt6", translate("Python Bindings for Qt"), "GPL-3.0-only"),
            ("Mutagen", "https://github.com/quodlibet/mutagen", translate("audio metadata handling"), "GPLv2 or later"),
            ("Pillow", "https://github.com/python-pillow/Pillow", translate("Python Imaging Library"), "MIT-CMU"),
            ("Requests", "https://github.com/psf/requests", translate("lyrics and article descriptions download handling"), "Apache 2.0"),
            ("Send2Trash", "https://github.com/arsenetar/send2trash", translate("a package that sends files to the Trash instead of permanent deletion"), "BSD License"),
            ("urllib3", "https://github.com/urllib3/urllib3", translate("to handle external links and wikipedia data"), "MIT License"),
            ("PyObjC", "https://pyobjc.readthedocs.io/", translate("for integration with native macOS media buttons and MPRemoteCommandCenter"),
             "MIT License"),
        ]

        for name, url, desc, license_type in libraries_list:
            lib_layout = QHBoxLayout()
            lib_layout.setContentsMargins(0, 0, 0, 0)
            lib_layout.setSpacing(6)

            btn = QPushButton(name)
            btn.setProperty("class", "btnLink")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                btn,
                title = translate("Open in browser"),
                text = url,
                activity_type = "external",
            )
            btn.setProperty("url", url)
            btn.clicked.connect(self._on_link_clicked)

            desc_label = QLabel(f" — {desc} <i>({license_type})</i>.")
            desc_label.setProperty("class", "textSecondary textColorPrimary")
            desc_label.setWordWrap(True)

            lib_layout.addWidget(btn, alignment = Qt.AlignmentFlag.AlignTop)
            lib_layout.addWidget(desc_label, 1, alignment = Qt.AlignmentFlag.AlignTop)

            content_layout.addLayout(lib_layout)

        content_layout.addSpacing(16)

        services_header = QLabel(translate("External Services"))
        services_header.setProperty("class", "textHeaderSecondary textColorPrimary")
        content_layout.addWidget(services_header)

        services_list = [
            ("Apple Music", translate("metadata search and cover art"), "https://music.apple.com"),
            ("LRCLIB", translate("lyrics search"), "https://lrclib.net"),
            ("Wikipedia", translate("brief descriptions for the encyclopedia articles"), "https://www.wikipedia.org/")
        ]

        for link_name, desc_text, link_url in services_list:
            srv_layout = QHBoxLayout()
            srv_layout.setContentsMargins(0, 0, 0, 0)
            srv_layout.setSpacing(0)

            btn = QPushButton(link_name)
            btn.setProperty("class", "btnLink")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                btn,
                title = translate("Open in browser"),
                text = link_url,
                activity_type = "external",
            )
            btn.setProperty("url", link_url)
            btn.clicked.connect(self._on_link_clicked)

            desc_label = QLabel(f" — " + desc_text)
            desc_label.setProperty("class", "textSecondary textColorPrimary")

            srv_layout.addWidget(btn, alignment = Qt.AlignmentFlag.AlignTop)
            srv_layout.addWidget(desc_label, alignment = Qt.AlignmentFlag.AlignTop)
            srv_layout.addStretch()

            content_layout.addLayout(srv_layout)

        content_layout.addSpacing(16)



        thanks_header = QLabel(translate("Special Thanks"))
        thanks_header.setProperty("class", "textHeaderSecondary textColorPrimary")
        content_layout.addWidget(thanks_header)

        thanks_text = (
            f"{translate("Huge thanks and respect to the guys who took the time to test Vinyller:")}<br>"
            f"TuneLow<br>"
            f"StarSwarschik<br>"
            f"{translate("As well as to everyone who has supported me along the way!")}<br>"
        )
        thanks_label = QLabel(thanks_text)
        thanks_label.setWordWrap(True)
        thanks_label.setProperty("class", "textSecondary textColorPrimary")
        content_layout.addWidget(thanks_label)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        credits_layout.addWidget(scroll_area)

    def eventFilter(self, obj, event):
        """
        Intercepts events to detect secret multiple clicks (easter egg).

        Args:
            obj (QObject): The target object.
            event (QEvent): The intercepted event.
        """
        if obj == self.icon_label and event.type() == QEvent.Type.MouseButtonPress:
            if (
                not self.animation_timer.isActive()
            ):
                self.icon_click_count += 1

                if self.icon_click_count == 3:
                    self.icon_click_count = 0
                    self._start_animation()
            return True

        return super().eventFilter(obj, event)

    def _prepare_animation_frames(self):
        """Loads easter egg animation frames from the resources into memory."""
        if self.animation_frames:
            return

        self.animation_frames = []

        is_dark = theme.COLORS.get("IS_DARK", False)
        suffix = "_dk" if is_dark else ""

        ratio = self.devicePixelRatioF()
        target_size = QSize(
            int(self.icon_size.width() * ratio),
            int(self.icon_size.height() * ratio)
        )

        for i in range(1, 49):
            if self.settings.get("language") == 'ru':
                frame_path = resource_path(f"assets/animation/vinyller/ru/frame_ru_{i}{suffix}.png")
            else:
                frame_path = resource_path(f"assets/animation/vinyller/en/frame_{i}{suffix}.png")
            pixmap = QPixmap(frame_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                scaled_pixmap.setDevicePixelRatio(ratio)
                self.animation_frames.append(scaled_pixmap)
            else:
                print(f"Easter egg: Could not find frame {i}. Halting frame load.")
                break

    def _start_animation(self):
        """Starts the easter egg icon animation."""
        if self.animation_timer.isActive():
            return

        if not self.animation_frames:
            self._prepare_animation_frames()

        if len(self.animation_frames) < 2:
            print(
                "Easter egg: Not enough animation frames found in 'assets/animation/vinyller/en'."
            )
            self.animation_frames = []
            return

        self.current_frame_index = 0
        self.animation_loop_count = 0

        self.animation_timer.start(42)
        self._update_animation_frame()

    def _update_animation_frame(self):
        """Loops through animation frames and stops when the target loops count is reached."""
        if not self.animation_frames:
            self.animation_timer.stop()
            return

        if self.current_frame_index >= len(self.animation_frames):
            self.animation_loop_count += 1
            self.current_frame_index = 0

            if self.animation_loop_count >= self.animation_total_loops:
                self.animation_timer.stop()

                if hasattr(self, 'scaled_original_pixmap'):
                    self.icon_label.setPixmap(self.scaled_original_pixmap)

                self.icon_click_count = 0
                self.animation_loop_count = 0
                self.current_frame_index = 0
                return

        pixmap = self.animation_frames[self.current_frame_index]
        self.icon_label.setPixmap(pixmap)
        self.current_frame_index += 1

    def _update_history_checkbox_state(self, index):
        """Disables the 'store unique tracks only' option if history recording is disabled."""
        is_disabled = index == 0
        self.history_store_unique_checkbox.setDisabled(is_disabled)

    def _update_blacklist_count_label(self):
        """Updates the text describing how many items are in the blacklist."""
        main_window = self.parent()
        if not main_window:
            return

        blacklist = main_window.library_manager.load_blacklist()
        count = sum(len(v) for v in blacklist.values())

        if count > 0:
            text = translate("The blacklist contains {count} items.", count=count)
        else:
            text = translate("The blacklist is empty.")
        self.blacklist_count_label.setText(text)

    def _update_unavailable_count_label(self):
        """Updates the text describing how many items are marked as unavailable."""
        main_window = self.parent()
        if not main_window:
            return

        unavailable = main_window.library_manager.load_unavailable_favorites()
        count = sum(len(v) for v in unavailable.values())

        if count > 0:
            text = translate("The list contains {count} items.", count=count)
        else:
            text = translate("The list of unavailable favorites is empty.")
        self.unavailable_count_label.setText(text)

    def populate_folder_list(self):
        """Loads and visualizes all registered library paths into the UI list widget."""
        self.folder_list_widget.clear()
        for path in self.initial_paths:
            self._add_path_item(path)

    def _add_path_item(self, path_text):
        """
        Creates and adds a PathListItemWidget for a given path string.

        Args:
            path_text (str): The folder path string.
        """
        list_item = QListWidgetItem(self.folder_list_widget)
        item_widget = PathListItemWidget(path_text, list_item, self)
        item_widget.remove_requested.connect(self.remove_path_item)

        size_hint = item_widget.sizeHint()
        size_hint.setWidth(0)
        list_item.setSizeHint(size_hint)

        self.folder_list_widget.addItem(list_item)
        self.folder_list_widget.setItemWidget(list_item, item_widget)

    def remove_path_item(self, list_item_to_remove):
        """
        Removes the specified path item widget from the list.

        Args:
            list_item_to_remove (QListWidgetItem): The item to remove.
        """
        row = self.folder_list_widget.row(list_item_to_remove)
        if row >= 0:
            self.folder_list_widget.takeItem(row)
        self._check_for_changes()

    def _on_accent_combo_changed(self):
        """Handles enabling the custom color selection button if the user chose the 'Custom' combo box item."""
        data = self.accent_combo.currentData()
        if data == "CUSTOM_USER_DEFINED":
            self.custom_color_btn.show()
            if not self.custom_color_btn.text():
                init_color = self.initial_accent if self.initial_accent.startswith("#") else theme.COLORS["PRIMARY"]
                self._update_custom_color_btn(init_color)
        else:
            self.custom_color_btn.hide()

    def _setup_mappings(self):
        """
        Initializes declarative mappings linking core configuration keys directly
        to their corresponding UI widgets.

        This declarative approach prevents logic duplication during setting loads,
        saves, and signal connection. Format: "setting_key": (widget_instance, default_value)
        """
        self.checkbox_mapping = {
            "show_separators": (self.show_separators_checkbox, True),
            "show_favorites_separators": (self.show_favorites_separators_checkbox, False),
            "ignore_articles": (self.ignore_articles_checkbox, True),
            "ignore_genre_case": (self.ignore_genre_case_checkbox, True),
            "treat_folders_as_unique": (self.treat_folders_as_unique_checkbox, False),
            "allow_drag_export": (self.allow_drag_export_checkbox, False),
            "check_updates_at_startup": (self.check_updates_at_startup_checkbox, True),
            "history_store_unique_only": (self.history_store_unique_checkbox, True),
            "remember_last_view": (self.remember_last_view_checkbox, False),
            "remember_window_size": (self.remember_window_size_checkbox, True),
            "show_random_suggestions": (self.show_random_suggestions_checkbox, True),
            "stylize_vinyl_covers": (self.stylize_vinyl_covers_checkbox, False),
            "warm_sound": (self.warm_sound_checkbox, False),
            "scratch_sound": (self.scratch_sound_checkbox, False),
            "mini_opacity": (self.mini_opacity_checkbox, True),
            "collect_statistics": (self.collect_statistics_checkbox, True),
            "autoplay_on_queue": (self.autoplay_on_queue_checkbox, False),
        }

        self.combo_mapping = {
            "remember_queue_mode": (self.remember_queue_combo, 3),
            "playback_history_mode": (self.playback_history_combo, 2),
            "artist_source_tag": (self.artist_source_combo, ArtistSource.ARTIST),
            "language": (self.language_combo, "en"),
            "favorite_icon_name": (self.favorite_icon_combo, "favorite_heart"),
            "theme": (self.theme_combo, "Light"),
        }

    def load_initial_settings(self):
        """
        Parses the injected settings dictionary and populates all tabs' controls accordingly.

        Leverages the declarative mappings for standard widgets to automatically assign
        states. Also processes complex logic that requires manual initialization (like
        color pickers and navigation order arrays).
        """
        # --- 1. Dynamic standard widgets load ---
        for key, (checkbox, default) in self.checkbox_mapping.items():
            value = self.settings.get(key, default)
            # Linux specific override
            if key == "mini_opacity" and IS_LINUX:
                value = False
            checkbox.setChecked(value)

        for key, (combo, default) in self.combo_mapping.items():
            value = self.settings.get(key, default)
            index = combo.findData(value)
            if index != -1:
                combo.setCurrentIndex(index)

        # --- 2. Custom logical elements ---
        # Accent color custom logic
        current_accent = self.settings.get("accent_color", "Crimson")
        self.initial_accent = current_accent
        idx = self.accent_combo.findData(current_accent)

        if idx != -1:
            self.accent_combo.setCurrentIndex(idx)
            self.custom_color_btn.hide()
        else:
            custom_idx = self.accent_combo.findData("CUSTOM_USER_DEFINED")
            if custom_idx != -1:
                self.accent_combo.setCurrentIndex(custom_idx)
                self._update_custom_color_btn(current_accent)
                self.custom_color_btn.show()

        # Nav tab order logic
        default_keys = ["artist", "album", "genre", "composer", "track", "playlist", "folder", "charts"]
        saved_order = self.settings.get("nav_tab_order", default_keys)
        self.nav_tab_order = []
        known_keys = set(default_keys)

        for key in saved_order:
            if key in known_keys:
                self.nav_tab_order.append(key)
        for key in default_keys:
            if key not in self.nav_tab_order:
                self.nav_tab_order.append(key)

        # Triggers
        self._update_history_checkbox_state(self.playback_history_combo.currentIndex())
        self.clear_stats_button.setEnabled(self.collect_statistics_checkbox.isChecked())

    def get_settings(self) -> dict:
        """
        Compiles and returns the dictionary of finalized UI settings.

        Iterates over the mapped UI elements to extract their current values,
        fetches library paths from the custom list widget, and assembles the
        final state structure required by MainWindow.

        Returns:
            dict: The settings payload ready to be processed and applied.
        """
        result = {}

        # 1. Dynamic standard widget extraction
        for key, (checkbox, _) in self.checkbox_mapping.items():
            result[key] = checkbox.isChecked()

        for key, (combo, _) in self.combo_mapping.items():
            result[key] = combo.currentData()

        # 2. Extract library paths
        paths = []
        for i in range(self.folder_list_widget.count()):
            item = self.folder_list_widget.item(i)
            widget = self.folder_list_widget.itemWidget(item)
            if widget and hasattr(widget, "path"):
                paths.append(widget.path)
        result["musicLibraryPaths"] = paths

        # 3. Handle custom fields
        selected_accent_data = self.accent_combo.currentData()
        final_accent = selected_accent_data

        if selected_accent_data == "CUSTOM_USER_DEFINED":
            custom_hex = self.custom_color_btn.text().strip()
            if custom_hex and custom_hex.startswith("#"):
                final_accent = custom_hex
            else:
                final_accent = self.initial_accent

        result["accent_color"] = final_accent
        result["nav_tab_order"] = self.nav_tab_order
        result["view_modes"] = self.settings.get("view_modes", {})
        result["sort_modes"] = self.settings.get("sort_modes", {})

        return result

    def _connect_signals(self):
        """
        Connects UI interaction events to the change-detection mechanism.

        Dynamically binds all standard widgets defined in the mappings
        so that modifying them enables the "Apply" button.
        """
        # Custom elements
        self.accent_combo.currentIndexChanged.connect(self._check_for_changes)

        # Auto-connect mapped elements
        for checkbox, _ in self.checkbox_mapping.values():
            checkbox.toggled.connect(self._check_for_changes)

        for combo, _ in self.combo_mapping.values():
            combo.currentIndexChanged.connect(self._check_for_changes)


    def optimize_paths(self):
        """Checks for and removes redundant subfolders nested inside other library paths."""
        paths_in_widget = []
        for i in range(self.folder_list_widget.count()):
            item = self.folder_list_widget.item(i)
            widget = self.folder_list_widget.itemWidget(item)
            if widget and hasattr(widget, "path"):
                paths_in_widget.append(widget.path)

        if not paths_in_widget:
            return

        resolved_paths = [Path(p).resolve() for p in paths_in_widget]
        optimized_paths = []

        for i, p1 in enumerate(resolved_paths):
            is_subfolder = False
            parent_path = None

            for j, p2 in enumerate(resolved_paths):
                if i != j and p1.is_relative_to(p2):
                    is_subfolder = True
                    parent_path = paths_in_widget[j]
                    break

            if not is_subfolder:
                optimized_paths.append(paths_in_widget[i])
            else:
                print(f"Optimization: path '{paths_in_widget[i]}' removed (nested in '{parent_path}')")

        if len(optimized_paths) < len(paths_in_widget):
            removed_count = len(paths_in_widget) - len(optimized_paths)

            self.folder_list_widget.clear()
            for path in optimized_paths:
                self._add_path_item(path)

            CustomConfirmDialog.confirm(
                self,
                title = translate("Optimization Complete"),
                label = translate("Removed {count} nested folder(s).", count = removed_count),
                ok_text = translate("OK"),
                cancel_text = None,
            )
        else:
            CustomConfirmDialog.confirm(
                self,
                title = translate("Optimization Complete"),
                label = translate("No nested folders found. The list is already optimized."),
                ok_text = translate("OK"),
                cancel_text = None,
            )
        self._check_for_changes()

    def add_folder(self):
        """Spawns a folder selection dialog to add new music paths."""
        directory = QFileDialog.getExistingDirectory(
            self, translate("Select music folder"), str(Path.home())
        )
        if directory:
            norm_directory = os.path.normcase(os.path.normpath(directory))

            paths_in_widget = []
            for i in range(self.folder_list_widget.count()):
                item = self.folder_list_widget.item(i)
                widget = self.folder_list_widget.itemWidget(item)
                if widget and hasattr(widget, "path"):
                    paths_in_widget.append(
                        os.path.normcase(os.path.normpath(widget.path))
                    )

            if norm_directory not in paths_in_widget:
                self._add_path_item(directory)
        self._check_for_changes()


    def _check_for_changes(self, *args):
        """Compares current UI settings with the original ones and toggles the 'Apply' button state."""
        current_settings = self.get_settings()

        has_changes = False
        for key, current_val in current_settings.items():
            original_val = self.settings.get(key)
            if current_val != original_val:
                has_changes = True
                break

        self.apply_button.setEnabled(has_changes)

