"""
Vinyller — Encyclopedia inject widgets
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
from functools import partial

from PyQt6.QtCore import (
    pyqtSignal, QPoint, QSize, Qt, QUrl
)
from PyQt6.QtGui import (
    QAction, QIcon, QPixmap, QTextDocument, QDesktopServices
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget
)

from src.encyclopedia.encyclopedia_components import (
    EncyclopediaTextBrowser, LinksOverflowWidget
)
from src.ui.custom_base_widgets import (
    IconSpaceButton, StyledScrollArea,
    TranslucentMenu, StyledLabel, StyledToolButton, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ClickableWidget, ElidedLabel, FlowLayout, InteractiveCoverWidget,
    RoundedCoverLabel, ZoomableCoverLabel
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class EncyclopediaWidget(QFrame):
    """
    Compact description card for the top of the page.
    Supports collapsed and expanded modes.
    """

    fullViewRequested = pyqtSignal()
    editRequested = pyqtSignal()

    def __init__(self, data, item_type, parent=None, main_window=None):
        """
        Initialize the compact encyclopedia widget.

        Args:
            data (dict): The encyclopedia entry data to display.
            item_type (str): The type of the item (e.g., 'album', 'artist', 'genre').
            parent (QWidget, optional): The parent widget. Defaults to None.
            main_window (QMainWindow, optional): Reference to the main application window. Defaults to None.
        """
        super().__init__(parent)
        self.setProperty("class", "encyclopediaCompact")
        self.data = data
        self.item_type = item_type
        self.mw = main_window

        self.is_collapsed = False
        if self.mw:
            self.is_collapsed = getattr(self.mw, "encyclopedia_collapsed", False)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        self.expanded_widget = QWidget()
        self._setup_expanded_ui(self.expanded_widget)
        self.stack.addWidget(self.expanded_widget)

        self.collapsed_widget = QWidget()
        self._setup_collapsed_ui(self.collapsed_widget)
        self.stack.addWidget(self.collapsed_widget)

        self._update_view_mode()

    def mouseReleaseEvent(self, event):
        """
        Handle mouse release events to expand the widget if it is collapsed.

        Args:
            event (QMouseEvent): The mouse event.
        """
        if self.is_collapsed and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse_state()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


    def _get_display_pixmap(self, target_size):
        """
        Retrieve the appropriate display image, preferring a thumbnail if available.

        Args:
            target_size (int): The target width and height for a fallback transparent pixmap.

        Returns:
            QPixmap: The loaded image or a transparent fallback.
        """
        img_path = self.data.get("image_path")
        if not img_path or not os.path.exists(img_path):
            pixmap = QPixmap(target_size, target_size)
            pixmap.fill(Qt.GlobalColor.transparent)
            return pixmap

        path_obj = os.path.splitext(img_path)
        thumb_path = f"{path_obj[0]}_thumb{path_obj[1]}"

        if os.path.exists(thumb_path):
            return QPixmap(thumb_path)

        return QPixmap(img_path)

    def _create_read_more_button(self):
        """
        Create and configure a 'Read More' button to request the full encyclopedia view.

        Returns:
            QPushButton: The configured button.
        """
        btn = QPushButton("")
        set_custom_tooltip(
            btn,
            title = translate("Read More"),
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("class", "btnTool")
        btn.setIcon(
            create_svg_icon(
                "assets/control/article_read.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        btn.setIconSize(QSize(24, 24))
        btn.setFixedHeight(36)

        apply_button_opacity_effect(btn)
        btn.clicked.connect(self.fullViewRequested.emit)
        return btn

    def _setup_expanded_ui(self, container):
        """
        Build the user interface elements for the expanded view mode.

        Args:
            container (QWidget): The parent widget for the expanded UI.
        """
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        img_path = self.data.get("image_path")
        has_image = bool(img_path and os.path.exists(img_path))

        if self.item_type != "album" and has_image:
            pixmap = self._get_display_pixmap(128)
            self.cover_expanded = ZoomableCoverLabel(pixmap, 4, container)
            self.cover_expanded.setFixedSize(128, 128)

            self.cover_expanded.zoomRequested.connect(
                lambda _, path=img_path: self.mw.ui_manager.components.show_cover_viewer(
                    QPixmap(path)
                )
            )
            layout.addWidget(self.cover_expanded, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = ""
        content = ""
        blocks = self.data.get("blocks", [])
        if blocks:
            content = blocks[0].get("content", "")

        if self.item_type == "album":
            title = translate("About Album")
        elif self.item_type == "artist":
            title = translate("About Artist")
        elif self.item_type == "genre":
            title = translate("About Genre")
        elif self.item_type == "composer":
            title = translate("About Composer")
        else:
            if blocks:
                title = blocks[0].get("title", "")

        header_label = QLabel(title)
        header_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        header_label.setWordWrap(True)
        header_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        text_label = QLabel(content)
        text_label.setProperty("class", "textSecondary textColorPrimary")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        text_layout.addWidget(header_label)
        text_layout.addWidget(text_label)

        links = self.data.get("links", [])
        if links:
            links_widget = LinksOverflowWidget(links)
            links_widget.setFixedHeight(36)
            text_layout.addWidget(links_widget)

        layout.addLayout(text_layout, 1)

        btns_container = QWidget()
        btns_layout = QHBoxLayout(btns_container)
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.setSpacing(4)

        self.read_btn_expanded = self._create_read_more_button()
        self.more_btn_expanded = self._create_more_button()

        btns_layout.addWidget(self.read_btn_expanded)
        btns_layout.addWidget(self.more_btn_expanded)

        layout.addWidget(btns_container, 0, Qt.AlignmentFlag.AlignTop)


    def _setup_collapsed_ui(self, container):
        """
        Build the user interface elements for the collapsed view mode.

        Args:
            container (QWidget): The parent widget for the collapsed UI.
        """
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 8, 16, 8)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        img_path = self.data.get("image_path")
        has_image = bool(img_path and os.path.exists(img_path))

        if self.item_type != "album" and has_image:
            pixmap = self._get_display_pixmap(48)
            self.cover_collapsed = RoundedCoverLabel(pixmap, 4, container)
            self.cover_collapsed.setFixedSize(48, 48)
            layout.addWidget(self.cover_collapsed)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = ""
        content = ""
        blocks = self.data.get("blocks", [])
        if blocks:
            content = blocks[0].get("content", "")

        if self.item_type == "album":
            title = translate("About Album")
        elif self.item_type == "artist":
            title = translate("About Artist")
        elif self.item_type == "genre":
            title = translate("About Genre")
        elif self.item_type == "composer":
            title = translate("About Composer")
        else:
            if blocks:
                title = blocks[0].get("title", "")

        doc = QTextDocument()
        doc.setHtml(content)
        plain_content = doc.toPlainText().replace("\n", " ").replace("\r", "").strip()

        doc.setHtml(title)
        plain_title = doc.toPlainText().replace("\n", " ").strip()

        header_label = ElidedLabel(plain_title)
        header_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        header_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        header_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        header_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.text_label = ElidedLabel(plain_content)
        self.text_label.setProperty("class", "textSecondary textColorPrimary")
        self.text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        text_layout.addWidget(header_label)
        text_layout.addWidget(self.text_label)
        layout.addLayout(text_layout, 1)

        btns_layout = QHBoxLayout()
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.setSpacing(4)

        self.read_btn_collapsed = self._create_read_more_button()
        self.more_btn_collapsed = self._create_more_button()

        btns_layout.addWidget(self.read_btn_collapsed)
        btns_layout.addWidget(self.more_btn_collapsed)

        layout.addLayout(btns_layout)

    def _create_more_button(self):
        """
        Create and configure a 'More' actions button.

        Returns:
            QPushButton: The configured button for displaying the context menu.
        """
        btn = QPushButton("")
        set_custom_tooltip(
            btn,
            title = translate("Actions"),
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("class", "btnTool")
        btn.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        btn.setIconSize(QSize(24, 24))
        btn.setFixedHeight(36)
        apply_button_opacity_effect(btn)
        btn.clicked.connect(lambda: self.show_more_menu(btn))
        return btn

    def _update_view_mode(self):
        """
        Update the widget stack and size policies to reflect the current collapsed/expanded state.
        """
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )

        if self.is_collapsed:
            self.stack.setCurrentWidget(self.collapsed_widget)
            self.collapsed_widget.setSizePolicy(size_policy)

            self.expanded_widget.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
            )
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(self, title = translate("Expand"))
        else:
            self.stack.setCurrentWidget(self.expanded_widget)
            self.expanded_widget.setSizePolicy(size_policy)

            self.collapsed_widget.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
            )

            self.unsetCursor()
            set_custom_tooltip(self)

        self.setSizePolicy(size_policy)
        self.adjustSize()

    def toggle_collapse_state(self):
        """
        Toggle between collapsed and expanded modes and persist the preference if possible.
        """
        self.is_collapsed = not self.is_collapsed
        self._update_view_mode()

        if self.mw:
            self.mw.encyclopedia_collapsed = self.is_collapsed
            self.mw.save_current_settings()

    def show_more_menu(self, sender_btn):
        """
        Display a context menu for toggling collapse state, opening the manager, or editing.

        Args:
            sender_btn (QPushButton): The button that triggered the menu, used for positioning.
        """
        self.menu = TranslucentMenu(sender_btn)
        self.menu.setProperty("class", "popMenu")

        if self.is_collapsed:
            icn_expand = QIcon(
                create_svg_icon(
                    "assets/control/arrow_chevron_down.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_toggle = QAction(icn_expand, translate("Expand"), self.menu)
        else:
            icn_collapse = QIcon(
                create_svg_icon(
                    "assets/control/arrow_chevron_up.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_toggle = QAction(icn_collapse, translate("Collapse"), self.menu)

        act_toggle.triggered.connect(self.toggle_collapse_state)
        self.menu.addAction(act_toggle)
        self.menu.addSeparator()

        icn_manage = QIcon(
            create_svg_icon(
                "assets/control/encyclopedia.svg",
                theme.COLORS["PRIMARY"],
                QSize(20, 20),
            )
        )
        act_manage = QAction(icn_manage, translate("Open Encyclopedia"), self.menu)

        if hasattr(self, "item_key"):
            act_manage.triggered.connect(
                lambda: self.mw.open_encyclopedia_manager(self.item_key, self.item_type)
            )
        else:
            act_manage.triggered.connect(self.mw.open_encyclopedia_manager)

        self.menu.addAction(act_manage)

        icn_edit = QIcon(
            create_svg_icon(
                "assets/control/article_edit.svg",
                theme.COLORS["PRIMARY"],
                QSize(20, 20),
            )
        )
        act_edit = QAction(icn_edit, translate("Edit"), self.menu)
        act_edit.triggered.connect(self.editRequested.emit)
        self.menu.addAction(act_edit)

        sender_btn.setProperty("active", True)
        sender_btn.style().unpolish(sender_btn)
        sender_btn.style().polish(sender_btn)

        self.menu.exec(sender_btn.mapToGlobal(QPoint(0, sender_btn.height())))

        sender_btn.setProperty("active", False)
        sender_btn.style().unpolish(sender_btn)
        sender_btn.style().polish(sender_btn)

class EncyclopediaFullViewer(QWidget):
    """
    Full-page encyclopedia viewer with a two-column layout.
    """

    backRequested = pyqtSignal()
    galleryNavigationRequested = pyqtSignal(list, int)
    galleryZoomRequested = pyqtSignal(QPixmap)

    relationNavigationRequested = pyqtSignal(object, str, dict)

    libraryNavigationRequested = pyqtSignal(object, str)

    manageRequested = pyqtSignal()
    editRequested = pyqtSignal()

    def __init__(
        self,
        data,
        title,
        item_type="item",
        parent=None,
        show_header=True,
        is_missing=False,
        item_key=None,
    ):
        """
        Initialize the full-page encyclopedia viewer.

        Args:
            data (dict): Data dict representing the encyclopedia article.
            title (str): Display title of the article.
            item_type (str, optional): Type of the item (e.g., 'artist', 'album'). Defaults to "item".
            parent (QWidget, optional): Parent widget. Defaults to None.
            show_header (bool, optional): Whether to display the top header bar. Defaults to True.
            is_missing (bool, optional): Flag indicating if the entry is missing/empty. Defaults to False.
            item_key (tuple/str, optional): Unique key for identifying the entry in the library. Defaults to None.
        """
        super().__init__(parent)

        self.item_key = item_key
        self.item_type = item_type
        self.title_text = title
        self.is_missing = is_missing

        self.mw = None

        if isinstance(parent, QMainWindow):
            self.mw = parent
        elif parent and hasattr(parent, "mw"):
            self.mw = parent.mw
        if not self.mw:
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMainWindow):
                    self.mw = widget
                    break

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.base_font_size = 12
        self.font_level = 0
        self.max_font_level = 3
        self.min_font_level = 0
        self.body_labels = []

        self.header_widget = QWidget()

        if show_header:
            self._setup_header(title, item_type)
            self.main_layout.addWidget(self.header_widget)
        else:
            self.header_widget.hide()

        self.scroll_area = StyledScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setProperty("class", "backgroundPrimary")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.main_layout.addWidget(self.scroll_area)

        if self.is_missing:
            self._setup_missing_entry_ui()
            if hasattr(self, "btn_dec"):
                self.btn_dec.hide()
            if hasattr(self, "btn_inc"):
                self.btn_inc.hide()
        else:
            self.reload_view(data)

    def _setup_header(self, title, item_type):
        """
        Create and configure the top header bar with navigation, font sizing, and management actions.

        Args:
            title (str): The main title to show in the header.
            item_type (str): The item type mapped to a readable subtitle.
        """
        self.header_widget.setFixedHeight(56)

        layout = QHBoxLayout(self.header_widget)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        back_btn = QPushButton()
        set_custom_tooltip(
            back_btn,
            title = translate("Back"),
        )
        back_btn.setIcon(
            create_svg_icon(
                "assets/control/arrow_back.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setIconSize(QSize(24, 24))
        back_btn.setFixedHeight(36)
        back_btn.setProperty("class", "btnTool")
        apply_button_opacity_effect(back_btn)

        back_btn.clicked.connect(self.backRequested.emit)
        layout.addWidget(back_btn)

        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setProperty("class", "textHeaderSecondary textColorPrimary")

        type_map = {
            "artist": translate("Artist"),
            "album": translate("Album"),
            "genre": translate("Genre"),
            "composer": translate("Composer"),
        }
        type_str = type_map.get(item_type, item_type.capitalize())

        self.type_lbl = QLabel(type_str)
        self.type_lbl.setProperty("class", "textSecondary textColorTertiary")

        title_layout.addWidget(self.title_lbl)
        title_layout.addWidget(self.type_lbl)

        layout.addWidget(title_container)
        layout.addStretch()

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
        self.btn_dec.clicked.connect(lambda: self.change_font_size(-1))
        apply_button_opacity_effect(self.btn_dec)
        layout.addWidget(self.btn_dec)

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
        self.btn_inc.clicked.connect(lambda: self.change_font_size(1))
        apply_button_opacity_effect(self.btn_inc)
        layout.addWidget(self.btn_inc)

        self.manage_btn = QPushButton()
        self.manage_btn.setIcon(
            create_svg_icon(
                "assets/control/encyclopedia.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manage_btn.setIconSize(QSize(24, 24))
        self.manage_btn.setFixedHeight(36)
        self.manage_btn.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.manage_btn,
            title = translate("Open Encyclopedia"),
        )
        apply_button_opacity_effect(self.manage_btn)

        self.manage_btn.clicked.connect(self.manageRequested.emit)
        layout.addWidget(self.manage_btn)

        self.edit_btn = QPushButton()
        self.edit_btn.setIcon(
            create_svg_icon(
                "assets/control/article_edit.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setIconSize(QSize(24, 24))
        self.edit_btn.setFixedHeight(36)
        self.edit_btn.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.edit_btn,
            title = translate("Edit Article"),
        )
        apply_button_opacity_effect(self.edit_btn)

        self.edit_btn.clicked.connect(self.editRequested.emit)
        layout.addWidget(self.edit_btn)

        self._update_font_buttons_state()

    def change_font_size(self, delta):
        """
        Modify the text size scale level for article content.

        Args:
            delta (int): The integer value to add to the current font level (usually -1 or 1).
        """
        new_level = self.font_level + delta
        if self.min_font_level <= new_level <= self.max_font_level:
            self.font_level = new_level
            self._update_font_ui()
            self._update_font_buttons_state()

    def _update_font_ui(self):
        """
        Apply the calculated font size level to all trackable body labels and text blocks.
        """
        new_size = self.base_font_size + (self.font_level * 2)
        label_style = f"font-size: {new_size}px;"

        for widget in self.body_labels:
            try:
                if isinstance(widget, EncyclopediaTextBrowser):
                    widget.update_font_scale(self.base_font_size, self.font_level)
                else:
                    widget.setStyleSheet(label_style)
            except RuntimeError:
                pass

    def _update_font_buttons_state(self):
        """
        Enable or disable font sizing buttons based on the maximum and minimum allowed levels.
        """
        has_content = len(self.body_labels) > 0

        if hasattr(self, "btn_dec"):
            self.btn_dec.setEnabled(
                has_content and self.font_level > self.min_font_level
            )
        if hasattr(self, "btn_inc"):
            self.btn_inc.setEnabled(
                has_content and self.font_level < self.max_font_level
            )

    def reload_view(self, data):
        """
        Parse the provided article data and dynamically construct the scrollable content layout.

        Args:
            data (dict): The full encyclopedia article data to render (blocks, gallery, discography, etc.).
        """
        if data is None:
            data = {}

        self.body_labels.clear()

        dm = self.mw.data_manager

        generated_discography = []

        if self.item_type == "composer" and self.mw:
            comp_name = self.title_text
            if comp_name in dm.composers_data:
                comp_data = dm.composers_data[comp_name]
                for album_key in comp_data.get("albums", []):
                    real_key = tuple(album_key)
                    if real_key in dm.albums_data:
                        alb = dm.albums_data[real_key]
                        generated_discography.append(
                            {
                                "title": real_key[1],
                                "year": (
                                    real_key[2]
                                    if len(real_key) > 2
                                    else alb.get("year", 0)
                                ),
                                "genre": ", ".join(alb.get("genre", [])[:1]),
                                "in_library": True,
                                "library_key": list(real_key),
                            }
                        )
            generated_discography.sort(key = lambda x: int(x.get("year", 0) or 0))

        elif self.item_type == "artist":
            raw_discography = data.get("discography", [])
            for item in raw_discography:
                lib_key = item.get("library_key")
                if lib_key and self.mw:
                    k_t = tuple(lib_key)

                    found_alb = None
                    if k_t in dm.albums_data:
                        found_alb = dm.albums_data[k_t]
                    elif len(k_t) == 3:
                        for real_k, real_v in dm.albums_data.items():
                            if real_k[:3] == k_t:
                                found_alb = real_v
                                break

                    if found_alb:
                        item["title"] = k_t[1]
                        item["year"] = (
                            k_t[2] if len(k_t) > 2 else found_alb.get("year", 0)
                        )
                        item["genre"] = ", ".join(found_alb.get("genre", [])[:1])
                        item["in_library"] = True
                    else:
                        if "title" not in item:
                            item["title"] = str(k_t[1]) if len(k_t) > 1 else translate("Unknown Album")
                        if "year" not in item:
                            try:
                                item["year"] = int(k_t[2]) if len(k_t) > 2 else 0
                            except (ValueError, TypeError):
                                item["year"] = 0
                        item["in_library"] = False

            generated_discography = raw_discography

        all_images = []
        main_img_path = data.get("image_path")

        if main_img_path and os.path.exists(main_img_path):
            all_images.append({"path": main_img_path, "caption": ""})

        gallery_items = data.get("gallery", [])
        valid_gallery_paths = []

        for item in gallery_items:
            if isinstance(item, dict):
                path = item.get("path")
                caption = item.get("caption", "")
            else:
                path = item
                caption = ""

            if path and os.path.exists(path):
                all_images.append({"path": path, "caption": caption})
                valid_gallery_paths.append(path)

        content = QWidget()
        content.setProperty("class", "backgroundPrimary")
        content.setContentsMargins(0, 0, 0, 0)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(32)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        top_row_layout = QHBoxLayout()
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(32)
        top_row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        has_left_column = False
        has_right_column = False

        left_meta_column = QVBoxLayout()
        left_meta_column.setContentsMargins(0, 0, 0, 0)
        left_meta_column.setSpacing(16)
        left_meta_column.setAlignment(Qt.AlignmentFlag.AlignTop)

        if main_img_path and os.path.exists(main_img_path):
            pixmap = QPixmap(main_img_path)
            if not pixmap.isNull():
                scaled_pix = pixmap.scaled(
                    256,
                    256,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_lbl = ZoomableCoverLabel(scaled_pix, 6, content)
                img_lbl.setFixedSize(256, 256)
                img_lbl.zoomRequested.connect(
                    lambda _: self.galleryNavigationRequested.emit(all_images, 0)
                )
                left_meta_column.addWidget(img_lbl)
                has_left_column = True

        if has_left_column:
            left_meta_column.addStretch()
            left_meta_widget = QWidget()
            left_meta_widget.setLayout(left_meta_column)
            left_meta_widget.setFixedWidth(260)
            top_row_layout.addWidget(left_meta_widget)

        blocks = data.get("blocks", [])

        first_block = blocks[0] if blocks else {}
        title_text = first_block.get("title", "")
        content_text = first_block.get("content", "")

        has_text_content = bool(title_text or content_text)

        is_linked = False
        if self.mw:
            dm = self.mw.data_manager
            if self.item_type == "artist":
                is_linked = self.title_text in dm.artists_data
            elif self.item_type == "composer":
                is_linked = self.title_text in dm.composers_data
            elif self.item_type == "genre":
                is_linked = self.title_text in dm.genres_data
            elif self.item_type == "album":
                art = data.get("artist") or data.get("album_artist")
                yr = data.get("year", 0)
                target = (art, self.title_text, yr)
                is_linked = any(
                    isinstance(k, (tuple, list)) and k[:3] == target
                    for k in dm.albums_data.keys()
                )

        show_buttons = bool(self.mw) and is_linked and has_text_content

        if has_text_content or show_buttons:
            first_block_container = QWidget()
            fb_layout = QVBoxLayout(first_block_container)
            fb_layout.setContentsMargins(0, 0, 0, 0)
            fb_layout.setSpacing(16)
            fb_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            if title_text:
                head = StyledLabel(title_text)
                head.setProperty("class", "textHeaderPrimary textColorPrimary")
                head.setWordWrap(True)
                head.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                head.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                fb_layout.addWidget(head)

            if show_buttons:
                btns_container = QWidget()
                btns_layout = QHBoxLayout(btns_container)
                btns_layout.setContentsMargins(0, 0, 0, 0)
                btns_layout.setSpacing(16)
                btns_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                nav_matches = []
                single_target_key = None

                if self.item_type == "album":
                    art = (
                            data.get("artist")
                            or data.get("album_artist")
                            or translate("Unknown Artist")
                    )
                    alb = self.title_text
                    yr = data.get("year", 0)
                    base_key = (art, alb, yr)

                    dm = self.mw.data_manager
                    for real_key in dm.albums_data.keys():
                        if isinstance(real_key, tuple) and len(real_key) >= 3:
                            if real_key[:3] == base_key:
                                nav_matches.append(real_key)

                    nav_matches.sort(key = lambda k: k[3] if len(k) > 3 else "")

                    if not nav_matches:
                        single_target_key = base_key
                    elif len(nav_matches) == 1:
                        single_target_key = nav_matches[0]
                else:
                    single_target_key = {"type": self.item_type, "data": self.title_text}

                if self.item_type == "album" and len(nav_matches) > 1:
                    play_btn = StyledToolButton()
                    play_btn.setProperty("class", "btnToolMenuBorder textAlignLeft")
                    play_btn.setText(" " + translate("Play"))
                    play_btn.setIcon(
                        create_svg_icon(
                            "assets/control/play_inverted.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(20, 20),
                        )
                    )
                    play_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

                    play_btn.setPopupMode(StyledToolButton.ToolButtonPopupMode.InstantPopup)

                    play_menu = TranslucentMenu(play_btn)

                    for i, m_key in enumerate(nav_matches, 1):
                        if len(m_key) > 3:
                            folder_name = os.path.basename(m_key[3])
                            text = f"{folder_name} ({translate("Disc")} {i})"
                        else:
                            text = f"{self.title_text} ({translate("Disc")} {i})"

                        icon = QIcon(
                            create_svg_icon(
                                "assets/control/play_outline.svg",
                                theme.COLORS["PRIMARY"],
                                QSize(16, 16),
                            )
                        )
                        action = QAction(icon, text, play_menu)
                        action.triggered.connect(
                            lambda checked, k = m_key: self.mw.player_controller.play_data(k)
                        )
                        play_menu.addAction(action)

                    play_btn.setMenu(play_menu)
                else:
                    play_btn = QPushButton(translate("Play"))
                    play_btn.setProperty("class", "btnText textAlignLeft")
                    play_btn.setIcon(
                        create_svg_icon(
                            "assets/control/play_inverted.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(20, 20),
                        )
                    )

                    if self.item_type == "album":
                        if self.item_key and self.item_key in nav_matches:
                            play_data = self.item_key
                        elif single_target_key:
                            play_data = single_target_key
                        else:
                            play_data = base_key
                    else:
                        play_data = single_target_key

                    play_btn.clicked.connect(
                        lambda checked, pd = play_data: self.mw.player_controller.play_data(pd)
                    )

                play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                play_btn.setFixedHeight(36)

                if isinstance(play_btn, QToolButton):
                    play_btn.setSizePolicy(
                        QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
                    )

                btns_layout.addWidget(play_btn)

                if self.item_type == "album" and len(nav_matches) > 1:
                    goto_btn = StyledToolButton()
                    goto_btn.setProperty("class", "btnToolMenuBorder")
                    goto_btn.setText(translate("Go to Library"))
                    goto_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                    goto_btn.setPopupMode(StyledToolButton.ToolButtonPopupMode.InstantPopup)

                    goto_menu = TranslucentMenu(goto_btn)

                    for i, m_key in enumerate(nav_matches, 1):
                        if len(m_key) > 3:
                            folder_name = os.path.basename(m_key[3])
                            text = f"{folder_name} ({translate("Disc")} {i})"
                        else:
                            text = f"{self.title_text} ({translate("Disc")} {i})"

                        icon = QIcon(
                            create_svg_icon(
                                "assets/control/album.svg",
                                theme.COLORS["PRIMARY"],
                                QSize(16, 16),
                            )
                        )
                        action = QAction(icon, text, goto_menu)
                        action.triggered.connect(
                            lambda checked, k = m_key: self.libraryNavigationRequested.emit(
                                k, "album"
                            )
                        )
                        goto_menu.addAction(action)

                    goto_btn.setMenu(goto_menu)

                else:
                    goto_btn = QPushButton(translate("Go to Library"))
                    goto_btn.setProperty("class", "btnText")

                    if self.item_type == "album":
                        target_key = single_target_key if single_target_key else base_key
                    else:
                        target_key = self.title_text

                    goto_btn.clicked.connect(
                        lambda checked, t = target_key: self.libraryNavigationRequested.emit(
                            t, self.item_type
                        )
                    )

                goto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                goto_btn.setFixedHeight(36)

                if isinstance(goto_btn, QToolButton):
                    goto_btn.setSizePolicy(
                        QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
                    )

                btns_layout.addWidget(goto_btn)
                fb_layout.addWidget(btns_container)

            if self.item_type == "album":
                meta_container = QWidget()
                meta_layout = FlowLayout(meta_container)
                meta_layout.setContentsMargins(0, 0, 0, 0)
                meta_layout.setSpacing(20)

                def add_meta_item(label, value):
                    if value:
                        item_box = QWidget()
                        item_vbox = QVBoxLayout(item_box)
                        item_vbox.setContentsMargins(0, 0, 0, 0)
                        item_vbox.setSpacing(2)

                        lbl = QLabel(label)
                        lbl.setProperty("class", "textTertiary")

                        val = QLabel(str(value))
                        val.setProperty("class", "textSecondary textColorPrimary")
                        val.setWordWrap(True)
                        val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                        self.body_labels.append(val)

                        item_vbox.addWidget(lbl)
                        item_vbox.addWidget(val)
                        meta_layout.addWidget(item_box)
                        return True
                    return False

                has_any_meta = False
                if add_meta_item(translate("Artist:"), data.get("artist")):
                    has_any_meta = True
                if add_meta_item(translate("Album Artist:"), data.get("album_artist")):
                    has_any_meta = True
                if add_meta_item(translate("Composer:"), data.get("composer")):
                    has_any_meta = True
                if add_meta_item(translate("Genre:"), data.get("genre")):
                    has_any_meta = True

                yr = data.get("year")
                if yr and str(yr) != "0":
                    if add_meta_item(translate("Year:"), yr):
                        has_any_meta = True

                if has_any_meta:
                    fb_layout.addWidget(meta_container)
                    fb_layout.addSpacing(8)

            if content_text:
                body = EncyclopediaTextBrowser(content_text, content)
                body.setProperty(
                    "class", "EncyclopediaTextBlock textSecondary textColorPrimary"
                )
                body.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                self.body_labels.append(body)
                fb_layout.addWidget(body)

                src_lbl = self._create_source_label(
                    first_block.get("source_name", ""),
                    first_block.get("source_url", "")
                )
                if src_lbl:
                    src_layout = QHBoxLayout()
                    src_layout.setContentsMargins(0, 0, 0, 0)
                    src_layout.addStretch()
                    src_layout.addWidget(src_lbl)
                    fb_layout.addLayout(src_layout)

            fb_layout.addStretch()
            top_row_layout.addWidget(first_block_container, 1)
            has_right_column = True

        if has_left_column or has_right_column:
            main_layout.addLayout(top_row_layout)

        links = data.get("links", [])
        if links:
            links_group = QWidget()
            links_vbox = QVBoxLayout(links_group)
            links_vbox.setContentsMargins(0, 0, 0, 0)
            links_vbox.setSpacing(16)
            links_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

            r_head = QLabel(translate("External Links"))
            r_head.setProperty("class", "textHeaderSecondary textColorPrimary")
            links_vbox.addWidget(r_head)

            links_widget = LinksOverflowWidget(links)
            links_widget.setFixedHeight(36)
            links_vbox.addWidget(links_widget)

            main_layout.addWidget(links_group)

        relations = data.get("relations", [])
        if relations:
            sorted_relations = sorted(
                relations, key = lambda x: (x.get("type", ""), x.get("name", ""))
            )

            rel_group = QWidget()
            rel_vbox = QVBoxLayout(rel_group)
            rel_vbox.setContentsMargins(0, 0, 0, 0)
            rel_vbox.setSpacing(16)
            rel_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

            r_head = QLabel(translate("Related Articles"))
            r_head.setProperty("class", "textHeaderSecondary textColorPrimary")
            rel_vbox.addWidget(r_head)

            rel_container = QWidget()
            rel_flow = FlowLayout(rel_container)
            rel_flow.setSpacing(8)

            icon_map = {
                "artist": "artist",
                "album": "album",
                "genre": "genre",
                "composer": "composer",
            }

            for item in sorted_relations:
                name = item.get("name", "Unknown")
                typ = item.get("type", "item")
                key = item.get("key")

                btn = IconSpaceButton(text = name, spacing = 8)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(36)
                btn.setProperty("class", "btnRelationLink")
                set_custom_tooltip(
                    btn,
                    title = translate(typ.capitalize()),
                    text = name,
                )
                svg_name = icon_map.get(typ, "file")
                icon_pix = create_svg_icon(
                    f"assets/control/{svg_name}.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(16, 16),
                ).pixmap(16, 16)

                btn.setCustomIcon(icon_pix)
                btn.clicked.connect(partial(self._navigate_to_relation, key, typ))

                rel_flow.addWidget(btn)

            rel_vbox.addWidget(rel_container)
            main_layout.addWidget(rel_group)

        if valid_gallery_paths:
            gallery_section = QWidget()
            gs_layout = QVBoxLayout(gallery_section)
            gs_layout.setContentsMargins(0, 0, 0, 0)
            gs_layout.setSpacing(16)
            gs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            g_head = QLabel(translate("Gallery"))
            g_head.setProperty("class", "textHeaderSecondary textColorPrimary")
            gs_layout.addWidget(g_head)

            gallery_container = QWidget()
            gallery_flow = FlowLayout(gallery_container)
            gallery_flow.setSpacing(16)

            start_index = 1 if (main_img_path and os.path.exists(main_img_path)) else 0
            thumb_size = 120

            for i, g_path in enumerate(valid_gallery_paths):
                folder, filename = os.path.split(g_path)
                name, ext = os.path.splitext(filename)
                thumb_path = os.path.join(folder, f"{name}_thumb{ext}")
                display_pix = (
                    QPixmap(thumb_path)
                    if os.path.exists(thumb_path)
                    else QPixmap(g_path)
                )

                if display_pix.isNull():
                    continue

                final_thumb = self._create_square_thumbnail(display_pix, thumb_size)
                z_lbl = ZoomableCoverLabel(final_thumb, 4, gallery_container)
                z_lbl.setFixedSize(thumb_size, thumb_size)

                full_index = start_index + i
                gallery_item = all_images[full_index]
                caption = gallery_item.get("caption", "")

                item_wrapper = QWidget()
                wrapper_layout = QVBoxLayout(item_wrapper)
                wrapper_layout.setContentsMargins(0, 0, 0, 0)
                wrapper_layout.setSpacing(6)
                wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

                z_lbl.zoomRequested.connect(
                    lambda _, index = full_index: self.galleryNavigationRequested.emit(
                        all_images, index
                    )
                )
                wrapper_layout.addWidget(z_lbl)

                if caption:
                    caption_label = ElidedLabel(caption)
                    caption_label.setProperty("class", "textTertiary textColorTertiary")
                    caption_label.setWordWrap(True)
                    caption_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                    caption_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

                    caption_label.setFixedWidth(thumb_size)

                    wrapper_layout.addWidget(caption_label)

                gallery_flow.addWidget(item_wrapper)

            gs_layout.addWidget(gallery_container)
            main_layout.addWidget(gallery_section)

        discography = generated_discography

        if discography:
            disco_section = QWidget()
            ds_layout = QVBoxLayout(disco_section)
            ds_layout.setContentsMargins(0, 0, 0, 0)
            ds_layout.setSpacing(16)
            ds_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            total = len(discography)
            collected = 0
            if self.mw:
                for album in discography:
                    lib_key = album.get("library_key")
                    if lib_key:
                        k_tuple = tuple(lib_key)
                        if k_tuple in self.mw.data_manager.albums_data:
                            collected += 1
                        elif len(k_tuple) == 3:
                            for real_k in self.mw.data_manager.albums_data.keys():
                                if real_k[:3] == k_tuple:
                                    collected += 1
                                    break

            if self.item_type == "composer":
                header_text = translate("Works in Library")
            else:
                header_text = translate("Discography")

            stats_text = translate("Collected {c} of {t}", c = collected, t = total)

            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(8)

            h_lbl = QLabel(header_text)
            h_lbl.setProperty("class", "textHeaderSecondary textColorPrimary")

            s_lbl = QLabel(stats_text)
            s_lbl.setProperty("class", "textSecondary textColorTertiary")

            h_layout.addWidget(h_lbl)
            h_layout.addWidget(s_lbl)
            h_layout.addStretch()
            ds_layout.addLayout(h_layout)

            cards_container = QWidget()
            cards_layout = FlowLayout(cards_container, stretch_items = True)
            cards_layout.setSpacing(16)
            cards_layout.setContentsMargins(0, 0, 0, 0)

            for album in discography:
                card = self._create_discography_card(album, self.mw)
                cards_layout.addWidget(card)

            ds_layout.addWidget(cards_container)
            main_layout.addWidget(disco_section)

        if len(blocks) > 1:
            for block in blocks[1:]:
                if not block.get("title") and not block.get("content"):
                    continue

                b_container = QWidget()
                b_layout = QVBoxLayout(b_container)
                b_layout.setContentsMargins(0, 0, 0, 0)
                b_layout.setSpacing(8)
                b_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

                if t := block.get("title"):
                    head = QLabel(t)
                    head.setProperty("class", "textHeaderSecondary textColorPrimary")
                    b_layout.addWidget(head)

                body = EncyclopediaTextBrowser(block.get("content", ""), b_container)
                body.setProperty(
                    "class", "EncyclopediaTextBlock textSecondary textColorPrimary"
                )

                self.body_labels.append(body)
                b_layout.addWidget(body)

                src_lbl = self._create_source_label(
                    block.get("source_name", ""),
                    block.get("source_url", "")
                )

                if src_lbl:
                    src_layout = QHBoxLayout()
                    src_layout.setContentsMargins(0, 0, 0, 0)
                    src_layout.addStretch()
                    src_layout.addWidget(src_lbl)
                    b_layout.addLayout(src_layout)

                main_layout.addWidget(b_container)

        main_layout.addStretch(1)

        self.scroll_area.setWidget(content)
        self._update_font_ui()
        self._update_font_buttons_state()

    def _navigate_to_relation(self, key, typ, extra_data=None):
        """
        Trigger navigation to a related item based on its type and key.

        Args:
            key (tuple/str/list): The unique identifier for the related item.
            typ (str): The item type being navigated to (e.g., 'album', 'artist').
            extra_data (dict, optional): Any supplementary metadata for the relation. Defaults to None.
        """
        real_key = tuple(key) if typ == "album" and isinstance(key, list) else key

        self.relationNavigationRequested.emit(real_key, typ, extra_data or {})

    def _create_square_thumbnail(self, pixmap, size):
        """
        Create a cropped, square thumbnail from an existing pixmap.

        Args:
            pixmap (QPixmap): The source image pixmap.
            size (int): The target width and height in pixels.

        Returns:
            QPixmap: The generated square thumbnail.
        """
        if pixmap.isNull():
            return pixmap
        target_size = QSize(size, size)
        scaled_pix = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        copy_pix = scaled_pix.copy(
            (scaled_pix.width() - size) // 2,
            (scaled_pix.height() - size) // 2,
            size,
            size,
        )
        return copy_pix

    def _create_discography_card(self, album_data, mw):
        """
        Create a clickable widget representing a discography entry.

        Args:
            album_data (dict): Data dict detailing the album information.
            mw (QMainWindow): Reference to the main application window.

        Returns:
            ClickableWidget: The populated card widget.
        """
        display_title = album_data.get("title", translate("Unknown Album"))
        display_year = album_data.get("year", 0)
        display_genre = album_data.get("genre", "")

        extra_meta = {
            "year": display_year,
            "genre": display_genre,
            "artist": album_data.get("artist") or self.title_text,
            "album_artist": album_data.get("album_artist") or self.title_text,
            "composer": album_data.get("composer")
            or (self.title_text if self.item_type == "composer" else None),
        }

        found_real_key = None
        pixmap = QPixmap()
        is_playable = False

        if mw:
            dm = mw.data_manager
            if lib_key := album_data.get("library_key"):
                k_tuple = tuple(lib_key)
                if k_tuple in dm.albums_data:
                    found_real_key = k_tuple
                elif len(k_tuple) == 3:
                    for real_k in dm.albums_data.keys():
                        if real_k[:3] == k_tuple:
                            found_real_key = real_k
                            break
            if found_real_key:
                is_playable = True
                art_dict = dm.albums_data[found_real_key].get("artwork")
                pixmap = mw.ui_manager.components.get_pixmap(art_dict, 64)

        if pixmap.isNull():
            pixmap = (
                mw.ui_manager.components.get_pixmap(None, 64) if mw else QPixmap(64, 64)
            )

        action_key = found_real_key or (
            extra_meta["artist"],
            display_title,
            extra_meta["year"],
        )
        widget = ClickableWidget(data=action_key, click_mode="single")

        if is_playable:
            set_custom_tooltip(
                widget,
                title = translate("Go to Album in Library"),
            )
            widget.activated.connect(
                lambda _: self._navigate_to_relation(found_real_key, "album")
            )
        else:
            set_custom_tooltip(
                widget,
                title = translate("This album is not in your library yet"),
                text = translate("This album is only present in the encyclopedia article. You can manage the album list on the \"Discography\" tab when editing the artist's article."),
            )
            widget.activated.connect(
                lambda _: self._navigate_to_relation(action_key, "album", extra_meta)
            )

        widget.contextMenuRequested.connect(
            lambda data, pos: self._show_discography_context_menu(
                data, pos, mw, extra_meta, is_playable
            )
        )

        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumWidth(224)
        widget.setMaximumWidth(280)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        root_layout = QVBoxLayout(widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        styled_frame = QFrame()
        styled_frame.setProperty("class", "contentWidget")
        root_layout.addWidget(styled_frame)
        layout = QHBoxLayout(styled_frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        if is_playable:
            cover_widget = InteractiveCoverWidget(
                data=found_real_key, pixmap=pixmap, size=64, parent=styled_frame
            )
            cover_widget.playClicked.connect(
                lambda: mw.player_controller.smart_play(found_real_key)
            )
            cover_widget.pauseClicked.connect(mw.player.pause)
            if found_real_key:
                mw.main_view_cover_widgets[found_real_key].append(cover_widget)
        else:
            cover_widget = RoundedCoverLabel(pixmap, 3, parent=styled_frame)
            cover_widget.setFixedSize(64, 64)
            op = QGraphicsOpacityEffect(cover_widget)
            op.setOpacity(0.5)
            cover_widget.setGraphicsEffect(op)
        layout.addWidget(cover_widget)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        title_lbl = ElidedLabel(display_title)
        title_lbl.setProperty("class", "textPrimary bold")
        sub_text = (
            str(display_year) if display_year and str(display_year) != "0" else ""
        )
        if display_genre:
            sub_text += f" • {display_genre}" if sub_text else display_genre
        sub_lbl = ElidedLabel(sub_text)
        sub_lbl.setProperty("class", "textTertiary textColorTertiary")
        status_text = (
            translate("In Library") if is_playable else translate("Encyclopedia Only")
        )
        status_lbl = QLabel(status_text)
        status_lbl.setProperty("class", "textTertiary textColorTertiary")
        if is_playable:
            status_lbl.setStyleSheet(f"color: {theme.COLORS['PRIMARY']};")
        info_layout.addWidget(title_lbl)
        info_layout.addWidget(sub_lbl)
        info_layout.addWidget(status_lbl)
        layout.addLayout(info_layout, 1)
        return widget

    def _show_discography_context_menu(self, key, pos, mw, extra_meta, is_playable):
        """
        Show a context menu for a specific discography card.

        Args:
            key (tuple/str): The identifier key for the target album.
            pos (QPoint): The screen position to display the context menu.
            mw (QMainWindow): The main window instance holding context actions.
            extra_meta (dict): Fallback metadata for the album.
            is_playable (bool): Flag indicating if the album exists in the local library to play.
        """
        menu = TranslucentMenu(mw)
        entry = mw.encyclopedia_manager.get_entry(key, "album")

        if is_playable:
            icn_play = QIcon(
                create_svg_icon(
                    "assets/control/play_outline.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_play = QAction(icn_play, translate("Play"), menu)
            act_play.triggered.connect(lambda: mw.player_controller.play_data(key))
            menu.addAction(act_play)

            icn_add = QIcon(
                create_svg_icon(
                    "assets/control/playback_queue_add.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_add = QAction(icn_add, translate("Add to Queue"), menu)
            act_add.triggered.connect(lambda: mw.action_handler.add_to_queue(key))
            menu.addAction(act_add)

            menu.addSeparator()

            icn_lib = QIcon(
                create_svg_icon(
                    "assets/control/album.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
                )
            )
            act_goto = QAction(icn_lib, translate("Go to Library"), menu)
            act_goto.triggered.connect(
                lambda: self.libraryNavigationRequested.emit(key, "album")
            )
            menu.addAction(act_goto)

            menu.addSeparator()

        icn_manage = QIcon(
            create_svg_icon(
                "assets/control/encyclopedia.svg",
                theme.COLORS["PRIMARY"],
                QSize(20, 20),
            )
        )
        act_manage = QAction(icn_manage, translate("Open Encyclopedia"), menu)
        act_manage.triggered.connect(lambda: mw.open_encyclopedia_manager(key, "album"))
        menu.addAction(act_manage)

        if entry:
            icn_read = QIcon(
                create_svg_icon(
                    "assets/control/article_read.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_read = QAction(icn_read, translate("Read Article"), menu)
            act_read.triggered.connect(
                lambda: mw.ui_manager.open_encyclopedia_full_view(key, "album")
            )
            menu.addAction(act_read)

            icn_edit = QIcon(
                create_svg_icon(
                    "assets/control/article_edit.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_edit = QAction(icn_edit, translate("Edit Article"), menu)
            act_edit.triggered.connect(
                lambda: mw.ui_manager.open_encyclopedia_editor(key, "album")
            )
            menu.addAction(act_edit)
        else:
            icn_add_enc = QIcon(
                create_svg_icon(
                    "assets/control/encyclopedia_add.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(20, 20),
                )
            )
            act_create = QAction(
                icn_add_enc, translate("Create Encyclopedia Article"), menu
            )
            act_create.triggered.connect(
                lambda: mw.ui_manager.open_encyclopedia_editor(
                    key, "album", initial_meta=extra_meta
                )
            )
            menu.addAction(act_create)

        menu.exec(pos)

    def _setup_missing_entry_ui(self):
        """
        Build a placeholder interface indicating that the requested encyclopedia entry is missing.
        Provides a prompt for the user to create the article.
        """
        content = QWidget()
        content.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(content)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        icon_lbl = QLabel()
        icon_pix = create_svg_icon(
            "assets/control/encyclopedia_search.svg",
            theme.COLORS["TERTIARY"],
            QSize(64, 64),
        ).pixmap(64, 64)
        icon_lbl.setPixmap(icon_pix)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        title_lbl = QLabel(translate("This article does not exist yet"))
        title_lbl.setProperty("class", "textHeaderPrimary textColorPrimary")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            translate(
                "Add an article to the encyclopedia to expand your library collection info."
            )
        )
        desc_lbl.setProperty("class", "textSecondary textColorPrimary")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc_lbl.setFixedWidth(400)
        layout.addWidget(desc_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        create_btn = QPushButton(translate("Add to Encyclopedia"))
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setProperty("class", "btnText")
        create_btn.setFixedHeight(36)

        create_btn.clicked.connect(self.editRequested.emit)

        layout.addWidget(create_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.scroll_area.setWidget(content)

    def _create_source_label(self, source_name, source_url):
        """
        Creates an interface element for the article source.
        Uses a clickable button if a link is provided, or a plain text label if there is no link.
        """
        if not source_name and not source_url:
            return None

        display_name = source_name if source_name else source_url
        prefix = f"{translate('Source')}: "

        if not source_url:
            lbl = QLabel(f"{prefix}{display_name} ")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setProperty("class", "textSecondary textColorTertiary italic")
            return lbl

        btn = QPushButton(f"{prefix}{display_name}")
        btn.setProperty("class", "btnLink textSecondary italic")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_custom_tooltip(
            btn,
            title = translate('Open in browser'),
            text = source_url,
            activity_type="external"
        )

        btn.setProperty("url", source_url)
        btn.clicked.connect(self._on_link_clicked)

        return btn

    def _on_link_clicked(self):
        """
        Opens the URL associated with the clicked source button in the default system browser.
        """
        btn = self.sender()
        if not btn:
            return

        url = btn.property("url")
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            QDesktopServices.openUrl(QUrl(url))