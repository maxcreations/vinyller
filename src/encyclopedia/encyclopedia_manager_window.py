"""
Vinyller — Main encyclopedia window
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

import json

from PyQt6.QtCore import (
    QPoint, QSize, Qt,
    QTimer, QEvent
)
from PyQt6.QtGui import (
    QAction, QIcon, QPalette, QPixmap
)
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QListWidgetItem, QPushButton,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget, QSizePolicy
)

from src.encyclopedia.encyclopedia_components import LocalSearchInteractionFilter
from src.encyclopedia.encyclopedia_injects import EncyclopediaFullViewer
from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledListWidget, TranslucentCombo, TranslucentMenu, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ElidedLabel
)
from src.ui.custom_dialogs import (
    CustomConfirmDialog
)
from src.ui.custom_lists import EncyclopediaListDelegate
from src.utils import theme
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate


class EncyclopediaWindow(StyledDialog):
    """
    Main window for managing and viewing encyclopedia entries.
    Provides a split interface with a filterable list on the left and an article viewer on the right.
    """

    def __init__(self, main_window):
        """
        Initializes the encyclopedia manager window.
        """
        super().__init__()
        self.mw = main_window
        self.setWindowTitle(translate("Encyclopedia Manager"))
        self.resize(1280, 720)

        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )

        self.setProperty("class", "backgroundPrimary")
        self.setWindowIcon(QIcon(resource_path("assets/logo/app_icon.png")))

        self.all_items_cache = []

        self.current_type_idx = 0
        self.current_status_idx = 0
        self.current_avail_idx = 0
        self.current_sort_idx = 0

        self._load_settings()

        self.history_stack = []
        self._is_navigating = False

        self.current_viewer = None

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """
        Sets up the user interface layout, widgets, and connections.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)

        left_panel_widget = QWidget()
        left_panel_widget.setContentsMargins(0, 0, 0, 0)

        left_layout = QVBoxLayout(left_panel_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        control_header = QWidget(self)
        control_header.setContentsMargins(16, 8, 16, 8)
        control_header.setProperty("class", "headerBorder")

        control_layout = QVBoxLayout(control_header)
        control_layout.setSpacing(16)
        control_layout.setContentsMargins(0, 0, 0, 0)

        self.search_container = QWidget()
        self.search_container.setContentsMargins(0, 0, 0, 0)

        search_layout = QHBoxLayout(self.search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        search_icon_label = QLabel()
        search_icon_pixmap = create_svg_icon(
            "assets/control/search.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
        ).pixmap(20, 20)
        search_icon_label.setPixmap(search_icon_pixmap)

        opacity_effect = QGraphicsOpacityEffect(search_icon_label)
        opacity_effect.setOpacity(0.3)
        search_icon_label.setGraphicsEffect(opacity_effect)

        self.search_filter = LocalSearchInteractionFilter(opacity_effect, self)

        self.search_input = StyledLineEdit()
        self.search_input.setFixedHeight(36)
        self.search_input.setPlaceholderText(translate("Search articles..."))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.findChild(QAction).setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.search_input.setProperty("class", "filterInput")

        palette = self.search_input.palette()
        primary_str = theme.COLORS["PRIMARY"]
        text_color = theme.get_qcolor(primary_str)
        text_color.setAlphaF(0.5)
        palette.setColor(QPalette.ColorRole.PlaceholderText, text_color)
        palette.setColor(QPalette.ColorRole.Text, theme.get_qcolor(primary_str))
        self.search_input.setPalette(palette)

        self.search_input.installEventFilter(self.search_filter)
        self.search_input.textChanged.connect(self._apply_filters)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.setContentsMargins(12, 0, 0, 0)

        icon_wrapper = QWidget()
        iw_layout = QVBoxLayout(icon_wrapper)
        iw_layout.setContentsMargins(0, 0, 0, 0)
        iw_layout.addWidget(search_icon_label)

        search_row.addWidget(icon_wrapper)
        search_row.addWidget(self.search_input)

        self.more_btn = QPushButton()
        self.more_btn.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.more_btn.setFixedSize(36, 36)
        self.more_btn.setIconSize(QSize(24, 24))
        self.more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_btn.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.more_btn)
        self.more_btn.clicked.connect(self._show_more_menu)

        search_row.addWidget(self.more_btn)
        control_layout.addLayout(search_row)

        filters_layout = QHBoxLayout()
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)

        type_options = [
            (
                translate("All Types"),
                create_svg_icon(
                    "assets/control/encyclopedia.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                0,
            ),
            (
                translate("Artists"),
                create_svg_icon(
                    "assets/control/artist.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                ),
                1,
            ),
            (
                translate("Albums"),
                create_svg_icon(
                    "assets/control/album.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                ),
                2,
            ),
            (
                translate("Genres"),
                create_svg_icon(
                    "assets/control/genre.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                ),
                3,
            ),
            (
                translate("Composers"),
                create_svg_icon(
                    "assets/control/composer.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                4,
            ),
        ]
        self.type_btn = self.mw.ui_manager.components.create_tool_button_with_menu(
            type_options, self.current_type_idx
        )
        set_custom_tooltip(
            self.type_btn,
            title = translate("Filter by Type"),
        )
        self.type_btn.menu().triggered.connect(
            lambda action: self._set_filter_state("type", action.data())
        )
        filters_layout.addWidget(self.type_btn)

        avail_options = [
            (
                translate("All"),
                create_svg_icon(
                    "assets/control/library_all.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                0,
            ),
            (
                translate("In Library"),
                create_svg_icon(
                    "assets/control/library_present.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                1,
            ),
            (
                translate("Missing"),
                create_svg_icon(
                    "assets/control/library_missing.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                2,
            ),
        ]
        self.avail_btn = self.mw.ui_manager.components.create_tool_button_with_menu(
            avail_options, self.current_avail_idx
        )
        set_custom_tooltip(
            self.avail_btn,
            title = translate("Filter by Availability"),
        )
        self.avail_btn.menu().triggered.connect(
            lambda action: self._set_filter_state("avail", action.data())
        )
        filters_layout.addWidget(self.avail_btn)

        status_options = [
            (
                translate("All Statuses"),
                create_svg_icon(
                    "assets/control/article_all.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                0,
            ),
            (
                translate("Filled Only"),
                create_svg_icon(
                    "assets/control/article_present.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                1,
            ),
            (
                translate("Empty Only"),
                create_svg_icon(
                    "assets/control/article_missing.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                2,
            ),
        ]
        self.status_btn = self.mw.ui_manager.components.create_tool_button_with_menu(
            status_options, self.current_status_idx
        )
        set_custom_tooltip(
            self.status_btn,
            title = translate("Filter by Status"),
        )
        self.status_btn.menu().triggered.connect(
            lambda action: self._set_filter_state("status", action.data())
        )
        filters_layout.addWidget(self.status_btn)

        sort_options = [
            (
                translate("Name (A-Z)"),
                create_svg_icon(
                    "assets/control/sort_alpha_asc.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                0,
            ),
            (
                translate("Name (Z-A)"),
                create_svg_icon(
                    "assets/control/sort_alpha_desc.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                1,
            ),
            (
                translate("Date Modified (Newest)"),
                create_svg_icon(
                    "assets/control/sort_date_desc.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                2,
            ),
            (
                translate("Date Modified (Oldest)"),
                create_svg_icon(
                    "assets/control/sort_date_asc.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                ),
                3,
            ),
        ]
        self.sort_btn = self.mw.ui_manager.components.create_tool_button_with_menu(
            sort_options, self.current_sort_idx
        )
        set_custom_tooltip(
            self.sort_btn,
            title = translate("Sort Options"),
        )
        self.sort_btn.menu().triggered.connect(
            lambda action: self._set_filter_state("sort", action.data())
        )
        filters_layout.addWidget(self.sort_btn)

        filters_layout.addStretch()
        control_layout.addLayout(filters_layout)
        left_layout.addWidget(control_header)

        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(16, 8, 0, 8)
        list_layout.setSpacing(0)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidgetNav")
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.list_delegate = EncyclopediaListDelegate(self.list_widget)
        self.list_widget.setItemDelegate(self.list_delegate)

        list_layout.addWidget(self.list_widget)
        left_layout.addLayout(list_layout)

        self.count_label = QLabel("0 items")
        self.count_label.setContentsMargins(16, 8, 16, 8)
        self.count_label.setProperty("class", "textSecondary textColorTertiary")
        left_layout.addWidget(self.count_label)

        self.splitter.addWidget(left_panel_widget)

        right_panel_widget = QWidget()
        right_panel_widget.setContentsMargins(0, 0, 0, 0)

        right_layout = QVBoxLayout(right_panel_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.right_toolbar = QWidget()
        self.right_toolbar.setProperty("class", "backgroundPrimary headerBorder")
        self.right_toolbar.setFixedHeight(56)

        tb_layout = QHBoxLayout(self.right_toolbar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(16)

        self.back_btn = QPushButton()
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setIcon(
            create_svg_icon(
                "assets/control/arrow_back.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.back_btn.setIconSize(QSize(24, 24))
        self.back_btn.setFixedHeight(36)
        self.back_btn.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.back_btn)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.hide()
        set_custom_tooltip(
            self.back_btn,
            title = translate("Back"),
        )
        tb_layout.addWidget(self.back_btn)

        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.current_item_label = ElidedLabel("")
        self.current_item_label.setProperty(
            "class", "textHeaderSecondary textColorPrimary"
        )

        self.current_item_type_label = QLabel("")
        self.current_item_type_label.setProperty(
            "class", "textSecondary textColorTertiary"
        )

        title_layout.addWidget(self.current_item_label)
        title_layout.addWidget(self.current_item_type_label)

        tb_layout.addWidget(title_container, 1)

        self.btn_dec = QPushButton()
        self.btn_dec.setIcon(
            create_svg_icon(
                "assets/control/text_size_smaller.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.btn_dec.setIconSize(QSize(24, 24))
        self.btn_dec.setFixedHeight(36)
        self.btn_dec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dec.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_dec,
            title = translate("Decrease font size"),
        )
        self.btn_dec.clicked.connect(lambda: self._change_viewer_font_size(-1))
        apply_button_opacity_effect(self.btn_dec)
        self.btn_dec.hide()
        tb_layout.addWidget(self.btn_dec)

        self.btn_inc = QPushButton()
        self.btn_inc.setIcon(
            create_svg_icon(
                "assets/control/text_size_bigger.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.btn_inc.setIconSize(QSize(24, 24))
        self.btn_inc.setFixedHeight(36)
        self.btn_inc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inc.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_inc,
            title = translate("Increase font size"),
        )
        self.btn_inc.clicked.connect(lambda: self._change_viewer_font_size(1))
        apply_button_opacity_effect(self.btn_inc)
        self.btn_inc.hide()
        tb_layout.addWidget(self.btn_inc)

        self.edit_btn = QPushButton()
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setIcon(
            QIcon(
                create_svg_icon(
                    "assets/control/article_edit.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
        )
        self.edit_btn.setIconSize(QSize(24, 24))
        self.edit_btn.setFixedHeight(36)
        self.edit_btn.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.edit_btn,
            title = translate("Edit"),
        )
        self.edit_btn.clicked.connect(self._open_editor)
        self.edit_btn.hide()

        tb_layout.addWidget(self.edit_btn)

        right_layout.addWidget(self.right_toolbar)

        self.stack = QStackedWidget()

        self.welcome_page = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_page)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        welcome_icon = QLabel()
        welcome_icon.setPixmap(
            create_svg_icon(
                "assets/control/article_edit.svg",
                theme.COLORS["TERTIARY"],
                QSize(64, 64),
            ).pixmap(64, 64)
        )
        welcome_layout.addWidget(welcome_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        welcome_layout.addSpacing(16)

        welcome_title = QLabel(translate("Vinyller Encyclopedia"))
        welcome_title.setProperty("class", "textHeaderPrimary textColorPrimary")
        welcome_desc = QLabel(
            translate("Select an item from the list to view or edit details.")
        )
        welcome_desc.setProperty("class", "textSecondary textColorPrimary")

        welcome_layout.addWidget(welcome_title, 0, Qt.AlignmentFlag.AlignHCenter)
        welcome_layout.addWidget(welcome_desc, 0, Qt.AlignmentFlag.AlignHCenter)

        self.stack.addWidget(self.welcome_page)

        self.viewer_container = QWidget()
        self.viewer_layout = QVBoxLayout(self.viewer_container)
        self.viewer_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.viewer_container)

        right_layout.addWidget(self.stack, 1)
        self.splitter.addWidget(right_panel_widget)

        sizes = getattr(self, "_saved_splitter_sizes", [350, 750])
        self.splitter.setSizes(sizes)

        self.splitter.setCollapsible(0, False)

        main_layout.addWidget(self.splitter)
        self.stack.setCurrentIndex(0)

    def _change_viewer_font_size(self, delta):
        """
        Changes the font size in the current encyclopedia viewer.
        """
        if self.current_viewer:
            self.current_viewer.change_font_size(delta)
            self._update_manager_font_buttons()

    def _update_manager_font_buttons(self):
        """
        Updates the enabled state of the font size adjustment buttons based on the viewer limits.
        """
        if self.current_viewer:
            has_content = len(self.current_viewer.body_labels) > 0

            can_decrease = has_content and (
                    self.current_viewer.font_level > self.current_viewer.min_font_level
            )
            can_increase = has_content and (
                    self.current_viewer.font_level < self.current_viewer.max_font_level
            )

            self.btn_dec.setEnabled(can_decrease)
            self.btn_inc.setEnabled(can_increase)
        else:
            self.btn_dec.setEnabled(False)
            self.btn_inc.setEnabled(False)

    def _show_more_menu(self):
        """
        Displays the context menu with options for new articles, import, export, and closing the window.
        """
        menu = TranslucentMenu(self.more_btn)
        menu.setProperty("class", "popMenu")

        act_new = QAction(translate("New Article"), menu)
        act_new.triggered.connect(self._create_new_entry)
        menu.addAction(act_new)

        menu.addSeparator()

        act_import = QAction(translate("Import"), menu)
        act_import.triggered.connect(self._import_encyclopedia)
        menu.addAction(act_import)

        act_export = QAction(translate("Export"), menu)
        act_export.triggered.connect(self._export_encyclopedia)
        menu.addAction(act_export)

        menu.addSeparator()

        act_close = QAction(translate("Close"), menu)
        act_close.triggered.connect(self.close)
        menu.addAction(act_close)

        self.more_btn.setProperty("active", True)
        self.more_btn.style().unpolish(self.more_btn)
        self.more_btn.style().polish(self.more_btn)

        menu.exec(self.more_btn.mapToGlobal(QPoint(0, self.more_btn.height())))

        self.more_btn.setProperty("active", False)
        self.more_btn.style().unpolish(self.more_btn)
        self.more_btn.style().polish(self.more_btn)

    def _get_settings_path(self):
        """Returns the path to the encyclopedia settings JSON file."""
        return self.mw.encyclopedia_manager.app_data_dir / "encyclopedia_settings.json"

    def _load_settings(self):
        """Loads filter and sort settings from the settings file."""
        settings_path = self._get_settings_path()

        self._saved_splitter_sizes = [350, 750]

        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding = "utf-8") as f:
                    settings = json.load(f)
                    self.current_type_idx = settings.get("type_idx", 0)
                    self.current_status_idx = settings.get("status_idx", 0)
                    self.current_avail_idx = settings.get("avail_idx", 0)
                    self.current_sort_idx = settings.get("sort_idx", 0)
                    self._saved_splitter_sizes = settings.get("splitter_sizes", [350, 750])
            except Exception as e:
                print(f"Error loading encyclopedia settings: {e}")

    def _save_settings(self):
        """Saves current filter, sort settings, and splitter layout to the settings file."""
        settings_path = self._get_settings_path()

        splitter_sizes = [350, 750]
        if hasattr(self, "splitter"):
            splitter_sizes = self.splitter.sizes()

        settings = {
            "type_idx": self.current_type_idx,
            "status_idx": self.current_status_idx,
            "avail_idx": self.current_avail_idx,
            "sort_idx": self.current_sort_idx,
            "splitter_sizes": splitter_sizes
        }
        try:
            with open(settings_path, "w", encoding = "utf-8") as f:
                json.dump(settings, f, ensure_ascii = False, indent = 4)
        except Exception as e:
            print(f"Error saving encyclopedia settings: {e}")

    def _set_filter_state(self, filter_type, value):
        """
        Updates the specified filter state and applies the changes to the list.
        """
        if filter_type == "type":
            self.current_type_idx = value
        elif filter_type == "status":
            self.current_status_idx = value
        elif filter_type == "avail":
            self.current_avail_idx = value
        elif filter_type == "sort":
            self.current_sort_idx = value

        self._save_settings()
        self._apply_filters()

    def changeEvent(self, event):
        """
        Intercepts the event when the window becomes active (gains focus).
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self._check_external_updates()

    def _check_external_updates(self):
        """
        Checks if the encyclopedia file was modified externally (e.g., by other windows).
        If so, it silently reloads the data.
        """
        json_path = self.mw.encyclopedia_manager.json_path
        if json_path.exists():
            try:
                mtime = json_path.stat().st_mtime
                if not hasattr(self, "_last_db_mtime") or self._last_db_mtime < mtime:
                    self._last_db_mtime = mtime
                    self._load_data()
            except Exception:
                pass
        elif hasattr(self, "_last_db_mtime") and self._last_db_mtime > 0:
            self._last_db_mtime = 0
            self._load_data()

    def _load_data(self):
        """
        Loads data from the library and encyclopedia into the manager's cache.
        All album keys are passed through em.normalize_album_key for unification.
        """
        self.all_items_cache.clear()
        dm = self.mw.data_manager
        em = self.mw.encyclopedia_manager

        enc_data = em.load_data()
        processed_keys = set()

        def get_entry_status(key, type_str):
            section = enc_data.get(type_str, {})
            norm_key = em.normalize_album_key(key) if type_str == "album" else key
            key_str = (
                json.dumps(list(norm_key))
                if isinstance(norm_key, (list, tuple))
                else str(norm_key)
            )

            entry = section.get(key_str)
            if not entry and type_str == "genre":
                target_lower = key_str.lower()
                for k, v in section.items():
                    if k.lower() == target_lower:
                        entry = v
                        break

            return bool(entry), entry.get("last_modified", 0) if entry else 0

        for artist in dm.artists_data.keys():
            exists, mod = get_entry_status(artist, "artist")
            self.all_items_cache.append(
                {
                    "key": artist,
                    "type": "artist",
                    "name": artist,
                    "has_entry": exists,
                    "modified": mod,
                    "in_library": True,
                }
            )
            processed_keys.add(("artist", str(artist)))

        for album_key in dm.albums_data.keys():
            short_key = em.normalize_album_key(album_key)
            canon_str = json.dumps(list(short_key))

            if ("album", canon_str) in processed_keys:
                continue
            processed_keys.add(("album", canon_str))

            exists, mod = get_entry_status(short_key, "album")

            self.all_items_cache.append(
                {
                    "key": short_key,
                    "type": "album",
                    "name": short_key[1],
                    "has_entry": exists,
                    "modified": mod,
                    "in_library": True,
                    "subtitle": f"{short_key[0]}, {short_key[2]}",
                }
            )

        for genre in dm.genres_data.keys():
            exists, mod = get_entry_status(genre, "genre")
            self.all_items_cache.append(
                {
                    "key": genre,
                    "type": "genre",
                    "name": genre,
                    "has_entry": exists,
                    "modified": mod,
                    "in_library": True,
                }
            )
            processed_keys.add(("genre", str(genre)))

        for comp in dm.composers_data.keys():
            exists, mod = get_entry_status(comp, "composer")
            self.all_items_cache.append(
                {
                    "key": comp,
                    "type": "composer",
                    "name": comp,
                    "has_entry": exists,
                    "modified": mod,
                    "in_library": True,
                }
            )
            processed_keys.add(("composer", str(comp)))

        for cat, items in enc_data.items():
            if cat not in ["artist", "album", "genre", "composer"]:
                continue

            for key_str, entry in items.items():
                try:
                    raw_key = (
                        json.loads(key_str) if (cat == "album" and key_str) else key_str
                    )
                except (json.JSONDecodeError, TypeError):
                    continue

                norm_key = (
                    em.normalize_album_key(raw_key) if cat == "album" else raw_key
                )
                canon_str = (
                    json.dumps(list(norm_key)) if cat == "album" else str(norm_key)
                )

                if (cat, canon_str) in processed_keys:
                    continue

                name = entry.get("title", str(norm_key))
                subtitle = ""
                if cat == "album" and isinstance(norm_key, (list, tuple)):
                    name = norm_key[1]
                    subtitle = f"{norm_key[0]}, {norm_key[2]}"

                self.all_items_cache.append(
                    {
                        "key": norm_key,
                        "type": cat,
                        "name": name,
                        "has_entry": True,
                        "modified": entry.get("last_modified", 0),
                        "in_library": False,
                        "subtitle": subtitle,
                    }
                )
                processed_keys.add((cat, canon_str))

        self._apply_filters()

    def _apply_filters(self):
        """
        Filters the cached items based on the active search and filter constraints, then repopulates the UI list.
        """
        v_scroll = self.list_widget.verticalScrollBar()
        scroll_pos = v_scroll.value()
        query = self.search_input.text().lower()

        selected_key = None
        selected_type = None
        current_item = self.list_widget.currentItem()
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            selected_key = data["key"]
            selected_type = data["type"]

        type_idx = self.current_type_idx
        status_idx = self.current_status_idx
        avail_idx = self.current_avail_idx
        sort_idx = self.current_sort_idx

        filtered = []
        type_map = {1: "artist", 2: "album", 3: "genre", 4: "composer"}

        for item in self.all_items_cache:
            if query and query not in item["name"].lower():
                if item["type"] == "album":
                    if query not in item.get("subtitle", "").lower():
                        continue
                else:
                    continue

            if type_idx > 0:
                if item["type"] != type_map[type_idx]:
                    continue

            if status_idx == 1 and not item["has_entry"]:
                continue
            if status_idx == 2 and item["has_entry"]:
                continue

            if avail_idx == 1 and not item["in_library"]:
                continue
            if avail_idx == 2 and item["in_library"]:
                continue

            filtered.append(item)

        sort_func = self.mw.data_manager.get_sort_key

        if sort_idx == 0:
            filtered.sort(key=lambda x: sort_func(x["name"]))
        elif sort_idx == 1:
            filtered.sort(key=lambda x: sort_func(x["name"]), reverse=True)
        elif sort_idx == 2:
            filtered.sort(key=lambda x: x["modified"], reverse=True)
        elif sort_idx == 3:
            filtered.sort(key=lambda x: x["modified"])

        self.list_widget.clear()

        icon_map = {
            "artist": "artist",
            "album": "album",
            "genre": "genre",
            "composer": "composer",
        }

        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.clear()

        item_to_select = None

        for item in filtered:
            display_text = item["name"]
            if item["type"] == "album":
                display_text = f"{item['name']} ({item.get('subtitle', '')})"

            list_item = QListWidgetItem(display_text)

            svg_name = icon_map.get(item["type"], "file")

            is_real = item.get("in_library", False)
            has_entry = item.get("has_entry", False)

            color = theme.COLORS["ACCENT"] if is_real else theme.COLORS["TERTIARY"]
            icon = QIcon(
                create_svg_icon(f"assets/control/{svg_name}.svg", color, QSize(16, 16))
            )

            lib_status = translate("Present in library") if is_real else translate(
                "Missing from library or not bound to library object")
            art_status = translate("Article created") if has_entry else translate("Article missing")

            set_custom_tooltip(
                list_item,
                title = translate("Status"),
                text = f"{lib_status}\n{art_status}"
            )

            list_item.setIcon(icon)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            list_item.setData(Qt.ItemDataRole.DisplayRole, display_text)
            list_item.setSizeHint(QSize(0, 36))

            self.list_widget.addItem(list_item)

            if selected_key is not None and item["key"] == selected_key and item["type"] == selected_type:
                item_to_select = list_item

        if item_to_select:
            self.list_widget.setCurrentItem(item_to_select)

        self.list_widget.setUpdatesEnabled(True)

        QTimer.singleShot(0, lambda: v_scroll.setValue(scroll_pos))
        self.count_label.setText(translate("{count} items found", count = len(filtered)))

    def _on_item_clicked(self, list_item):
        """
        Handles clicks on list items to display their encyclopedia entry details.
        """
        if not self._is_navigating:
            self.history_stack.clear()
            self.back_btn.hide()

        item_data = list_item.data(Qt.ItemDataRole.UserRole)
        self._show_item_details(item_data)

    def _on_item_double_clicked(self, list_item):
        """
        Handles double-clicks on list items to open them directly in the editor.
        """
        self._open_editor()

    def _show_item_details(self, item_data):
        """
        Populates the right-hand view area with the encyclopedia entry of the selected item.
        """
        key = item_data["key"]
        typ = item_data["type"]
        name = item_data["name"]

        self.current_item_label.setText(name)

        type_map = {
            "artist": translate("Artist"),
            "album": translate("Album"),
            "genre": translate("Genre"),
            "composer": translate("Composer"),
        }
        type_str = type_map.get(typ, typ)
        self.current_item_type_label.setText(type_str)

        self.edit_btn.show()

        while self.viewer_layout.count():
            child = self.viewer_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        enc_entry = self.mw.encyclopedia_manager.get_entry(key, typ)
        is_missing = enc_entry is None

        self.current_viewer = EncyclopediaFullViewer(
            enc_entry,
            name,
            item_type=typ,
            parent=self,
            show_header=False,
            is_missing=is_missing,
        )

        self.current_viewer.galleryNavigationRequested.connect(
            lambda img_list, idx: self.mw.ui_manager.components.show_cover_viewer(
                QPixmap(), parent=self, image_list=img_list, current_index=idx
            )
        )

        self.current_viewer.libraryNavigationRequested.connect(
            self._handle_library_navigation
        )

        self.current_viewer.relationNavigationRequested.connect(
            self._navigate_to_relation_internal
        )

        self.current_viewer.editRequested.connect(self._open_editor)

        self.current_viewer.header_widget.hide()
        self.viewer_layout.addWidget(self.current_viewer.scroll_area)

        if is_missing:
            self.btn_dec.hide()
            self.btn_inc.hide()
        else:
            self.btn_dec.show()
            self.btn_inc.show()
            self._update_manager_font_buttons()

        self.stack.setCurrentIndex(1)

    def _handle_library_navigation(self, key, typ):
        """
        Navigates to the given item within the main app's local library.
        """
        if typ == "artist":
            self.mw.ui_manager.navigate_to_artist(key)
        elif typ == "genre":
            self.mw.ui_manager.navigate_to_genre(key)
        elif typ == "composer":
            self.mw.ui_manager.navigate_to_composer(key)
        elif typ == "album":
            self.mw.ui_manager.navigate_to_album(key)

        self.showMinimized()

    def _navigate_to_relation_internal(self, key, typ, extra_data = None):
        """
        Handles clicks on relationship links within an article.
        If the article exists, navigates to it.
        If not, prompts the user to create it using the common Helper.
        """
        current_item_widget = self.list_widget.currentItem()
        if current_item_widget:
            current_data = current_item_widget.data(Qt.ItemDataRole.UserRole)
            self.history_stack.append(current_data)
            self.back_btn.show()

        target_item = None
        em = self.mw.encyclopedia_manager

        target_key_norm = em.normalize_album_key(key) if typ == "album" else key
        target_tuple = (
            tuple(target_key_norm)
            if isinstance(target_key_norm, (list, tuple))
            else target_key_norm
        )

        for item in self.all_items_cache:
            if item["type"] != typ:
                continue

            cache_key = item["key"]
            cache_tuple = (
                tuple(cache_key) if isinstance(cache_key, (list, tuple)) else cache_key
            )

            if cache_tuple == target_tuple:
                target_item = item
                break

        if not target_item:
            item_name = str(target_key_norm)
            if (
                    typ == "album"
                    and isinstance(target_key_norm, (tuple, list))
                    and len(target_key_norm) >= 2
            ):
                item_name = target_key_norm[1]

            msg = translate(
                "This entry does not exist in the encyclopedia yet.\nWould you like to create it now?"
            )

            if CustomConfirmDialog.confirm(
                    self,
                    translate("Create Article"),
                    msg,
                    ok_text = translate("Create"),
                    cancel_text = translate("Cancel"),
            ):
                self.mw.ui_manager.open_encyclopedia_editor(
                    item_key = target_key_norm,
                    item_type = typ,
                    on_success = self._on_editor_success,
                    initial_meta = extra_data,
                    parent = self
                )
            return

        need_refresh = False

        if self.current_type_idx != 0:
            self.current_type_idx = 0
            self.type_btn.setIcon(
                create_svg_icon(
                    "assets/control/filter.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                )
            )
            need_refresh = True

        if self.search_input.text():
            self.search_input.clear()
            need_refresh = False

        if self.current_status_idx != 0:
            self.current_status_idx = 0
            self.status_btn.setIcon(
                create_svg_icon(
                    "assets/control/view_list.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
            need_refresh = True

        if need_refresh:
            self._apply_filters()

        for i in range(self.list_widget.count()):
            list_item = self.list_widget.item(i)
            data = list_item.data(Qt.ItemDataRole.UserRole)

            data_key = data["key"]
            data_tuple = (
                tuple(data_key) if isinstance(data_key, (list, tuple)) else data_key
            )

            if data["type"] == typ and data_tuple == target_tuple:
                self._is_navigating = True
                self.list_widget.setCurrentItem(list_item)
                self.list_widget.scrollToItem(list_item)
                self._on_item_clicked(list_item)
                self._is_navigating = False
                return

    def navigate_to_item(self, target_key, target_type):
        """
        Programmatically navigates the list to the specified item and opens it, clearing conflicting filters if needed.
        """
        need_refresh = False
        if self.current_type_idx != 0:
            self.current_type_idx = 0
            self.type_btn.setIcon(
                create_svg_icon(
                    "assets/control/filter.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                )
            )
            need_refresh = True

        if self.search_input.text():
            self.search_input.clear()
            need_refresh = False

        if self.current_status_idx != 0:
            self.current_status_idx = 0
            self.status_btn.setIcon(
                create_svg_icon(
                    "assets/control/view_list.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(24, 24),
                )
            )
            need_refresh = True

        if need_refresh:
            self._apply_filters()

        em = self.mw.encyclopedia_manager
        search_key = (
            em.normalize_album_key(target_key) if target_type == "album" else target_key
        )

        search_tuple = (
            tuple(search_key) if isinstance(search_key, (list, tuple)) else search_key
        )

        found_item = None
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)

            data_key = data["key"]
            data_tuple = (
                tuple(data_key) if isinstance(data_key, (list, tuple)) else data_key
            )

            if data["type"] == target_type and data_tuple == search_tuple:
                found_item = item
                break

        if found_item:
            self.list_widget.setCurrentItem(found_item)
            self.list_widget.scrollToItem(found_item)
            self._on_item_clicked(found_item)
        else:
            print(
                f"Encyclopedia Manager: Item not found: {target_type} - {search_tuple}"
            )

    def _go_back(self):
        """
        Navigates back to the previously viewed item using the history stack.
        """
        if not self.history_stack:
            self.back_btn.hide()
            return

        prev_data = self.history_stack.pop()

        if not self.history_stack:
            self.back_btn.hide()

        found = False
        for i in range(self.list_widget.count()):
            list_item = self.list_widget.item(i)
            data = list_item.data(Qt.ItemDataRole.UserRole)

            if data["key"] == prev_data["key"] and data["type"] == prev_data["type"]:
                self._is_navigating = True
                self.list_widget.setCurrentItem(list_item)
                self.list_widget.scrollToItem(list_item)
                self._on_item_clicked(list_item)
                self._is_navigating = False
                found = True
                break

        if not found:
            print("History item not currently visible in list")

    def _on_editor_success(self, new_key, new_type, moved = False):
        """
        Callback triggered by the Helper after successfully saving an article.
        Refreshes the list and navigates to the modified or newly created item.
        """
        self._load_data()

        if new_key:
            self.navigate_to_item(new_key, new_type)

        if hasattr(self.mw, "refresh_current_view"):
            self.mw.refresh_current_view()

        self.activateWindow()
        self.raise_()

    def _open_editor(self):
        """
        Opens the editor for the currently selected item.
        All dialog logic, image caching, and saving are delegated to the UI Manager.
        """
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        item_data = current_item.data(Qt.ItemDataRole.UserRole)
        key = item_data["key"]
        typ = item_data["type"]


        self.mw.ui_manager.open_encyclopedia_editor(
            item_key = key,
            item_type = typ,
            on_success = self._on_editor_success,
            parent = self
        )

    def _create_new_entry(self):
        """
        Shows a pre-dialog to input the title and type for a new article, then opens the main editor.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("New Article"))
        dlg.setFixedWidth(400)
        dlg.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)
        form = QFormLayout()
        form.setSpacing(16)

        combo = TranslucentCombo()
        combo.addItem(translate("Artist"), "artist")
        combo.addItem(translate("Composer"), "composer")
        combo.addItem(translate("Album"), "album")
        combo.addItem(translate("Genre"), "genre")

        name_edit = StyledLineEdit()
        name_edit.setFixedHeight(36)
        name_edit.setPlaceholderText(translate("Enter title..."))
        name_edit.setProperty("class", "inputBorderSinglePadding")

        artist_edit = StyledLineEdit()
        artist_edit.setFixedHeight(36)
        artist_edit.setPlaceholderText(translate("Artist"))
        artist_edit.setProperty("class", "inputBorderSinglePadding")

        year_edit = StyledLineEdit()
        year_edit.setFixedHeight(36)
        year_edit.setPlaceholderText("1877")
        year_edit.setProperty("class", "inputBorderSinglePadding")

        error_label = QLabel("")
        error_label.setProperty("class", "textPrimary textColorAccent")
        error_label.setWordWrap(True)
        error_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        error_label.hide()

        for edit in [name_edit, artist_edit, year_edit]:
            edit.textChanged.connect(error_label.hide)
        combo.currentIndexChanged.connect(error_label.hide)

        def update_fields():
            is_album = combo.currentData() == "album"
            artist_edit.setVisible(is_album)
            year_edit.setVisible(is_album)
            form.labelForField(artist_edit).setVisible(is_album)
            form.labelForField(year_edit).setVisible(is_album)

        combo.currentIndexChanged.connect(update_fields)

        form.addRow(translate("Type:"), combo)
        form.addRow(translate("Title:"), name_edit)
        form.addRow(translate("Artist:"), artist_edit)
        form.addRow(translate("Year:"), year_edit)

        content_layout.addLayout(form)
        content_layout.addWidget(error_label)
        main_layout.addLayout(content_layout)
        main_layout.addStretch()

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        def validate():
            typ = combo.currentData()
            name = name_edit.text().strip()

            if not name:
                error_label.setText(translate("All fields are required!"))
                error_label.show()
                return

            if typ == "album":
                artist = artist_edit.text().strip()
                year = year_edit.text().strip()

                if not artist or not year:
                    error_label.setText(translate("All fields are required!"))
                    error_label.show()
                    return

                if not (year.isdigit() and len(year) == 4):
                    error_label.setText(translate("Enter a valid year (4 digits)!"))
                    error_label.show()
                    return

            dlg.accept()

        button_box.accepted.connect(validate)
        button_box.rejected.connect(dlg.reject)

        if button_box.layout():
            button_box.layout().setSpacing(16)
        for btn in button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        bottom_layout.addStretch()
        bottom_layout.addWidget(button_box)
        main_layout.addWidget(bottom_panel)
        update_fields()

        if dlg.exec():
            name = name_edit.text().strip()
            typ = combo.currentData()
            initial_meta = {}
            key = name

            if typ == "album":
                artist = artist_edit.text().strip()
                year = int(year_edit.text().strip())
                key = (artist, name, year)
                initial_meta = {"title": name, "artist": artist, "album_artist": artist, "year": year}

            self.mw.ui_manager.open_encyclopedia_editor(
                item_key = key,
                item_type = typ,
                on_success = self._on_editor_success,
                initial_meta = initial_meta,
                parent = self
            )

    def _import_encyclopedia(self):
        """
        Triggers the encyclopedia import functionality and repopulates data upon completion.
        """
        current_item = self.list_widget.currentItem()
        saved_state = None
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            saved_state = (data["key"], data["type"])

        self.mw.ui_manager.handle_encyclopedia_import(self)

        self._load_data()

        if saved_state:
            key, typ = saved_state
            self.navigate_to_item(key, typ)

    def _export_encyclopedia(self):
        """
        Triggers the encyclopedia export functionality to save data externally.
        """
        current_item = self.list_widget.currentItem()
        saved_state = None
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            saved_state = (data["key"], data["type"])

        self.mw.ui_manager.handle_encyclopedia_export(self)

        if saved_state:
            self.navigate_to_item(saved_state[0], saved_state[1])

    def bring_to_front(self):
        """
        Restores the window if it is minimized and forcefully brings it to the foreground.
        """
        if self.isMinimized():
            self.showNormal()

        self.show()

        self.activateWindow()

        self.raise_()

    def closeEvent(self, event):
        """
        Intercepts the window close event to guarantee saving of splitter width and current filters.
        """
        self._save_settings()
        super().closeEvent(event)