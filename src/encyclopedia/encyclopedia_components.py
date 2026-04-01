"""
Vinyller — Encyclopedia widgets and components
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
    pyqtSignal, QEvent, QObject, QSize, Qt, QTimer, QUrl
)
from PyQt6.QtGui import (
    QAction, QBrush, QDesktopServices, QFont, QPalette,
    QTextCharFormat, QTextCursor
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget
)

from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledTextBrowser, StyledTextEdit, TranslucentMenu, StyledToolButton, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ElidedLabel, RoundedCoverLabel
)
from src.ui.custom_dialogs import (
    CustomInputDialog
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class BlockListItemWidget(QWidget):
    """
    Simple list item widget: Title (left) + Move/Delete buttons (right, on hover).
    """

    removeRequested = pyqtSignal()
    moveUpRequested = pyqtSignal()
    moveDownRequested = pyqtSignal()

    def __init__(self, title="", parent=None):
        """
        Initializes the BlockListItemWidget.

        Args:
            title (str): The initial title of the block.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setFixedHeight(36)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)

        self.title_label = ElidedLabel(title or translate("New Block"))
        self.title_label.setProperty("class", "textColorPrimary")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.title_label, 1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(2)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)

        self.up_btn = self._create_action_btn("arrow_up", translate("Move up"))
        self.up_btn.clicked.connect(self.moveUpRequested.emit)
        self.actions_layout.addWidget(self.up_btn)

        self.down_btn = self._create_action_btn("arrow_down", translate("Move down"))
        self.down_btn.clicked.connect(self.moveDownRequested.emit)
        self.actions_layout.addWidget(self.down_btn)

        self.delete_btn = self._create_action_btn("clear", translate("Remove section"))
        self.delete_btn.clicked.connect(self.removeRequested.emit)
        self.actions_layout.addWidget(self.delete_btn)

        layout.addLayout(self.actions_layout)
        main_layout.addWidget(self.container)

        self._set_buttons_visible(False)

    def _create_action_btn(self, icon_name, tooltip):
        """
        Creates a standardized action button for the list item.

        Args:
            icon_name (str): The name of the SVG icon file (without extension).
            tooltip (str): The tooltip text for the button.

        Returns:
            QPushButton: The configured action button.
        """
        btn = QPushButton()
        btn.setFixedSize(24, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(
            create_svg_icon(
                f"assets/control/{icon_name}.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        btn.setProperty("class", "btnListAction")
        set_custom_tooltip(
            btn,
            title = tooltip,
        )
        apply_button_opacity_effect(btn)
        return btn

    def _set_buttons_visible(self, visible):
        """
        Toggles the visibility of the action buttons.

        Args:
            visible (bool): True to show buttons, False to hide them.
        """
        self.up_btn.setVisible(visible)
        self.down_btn.setVisible(visible)
        self.delete_btn.setVisible(visible)

    def set_title(self, text):
        """
        Sets the title text of the block.

        Args:
            text (str): The new title text.
        """
        display_text = text.strip() if text.strip() else translate("New Block")
        self.title_label.setText(display_text)

    def enterEvent(self, event):
        """Shows action buttons when the mouse enters the widget."""
        self._set_buttons_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides action buttons when the mouse leaves the widget."""
        self._set_buttons_visible(False)
        super().leaveEvent(event)


class RelationsItemWidget(QWidget):
    """Widget for displaying an item in the relations list."""

    removeRequested = pyqtSignal()
    addRequested = pyqtSignal()

    def __init__(self, data, is_selected_list=False, parent=None):
        """
        Initializes the RelationsItemWidget.

        Args:
            data (dict): Dictionary containing relation data (type, name, subtitle, in_library).
            is_selected_list (bool): If True, shows a remove button; otherwise, shows an add button.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.data = data

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setMinimumHeight(44)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        icon_map = {
            "artist": "artist",
            "album": "album",
            "genre": "genre",
            "composer": "composer",
        }
        svg_name = icon_map.get(data["type"], "file")
        is_real = data.get("in_library", True)
        color = theme.COLORS["ACCENT"] if is_real else theme.COLORS["TERTIARY"]

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            create_svg_icon(
                f"assets/control/{svg_name}.svg", color, QSize(24, 24)
            ).pixmap(24, 24)
        )
        tooltip = (
            translate("Present in library")
            if is_real
            else translate("Missing from library")
        )
        set_custom_tooltip(
            icon_lbl,
            title = tooltip,
        )
        layout.addWidget(icon_lbl)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        name_lbl = ElidedLabel(data["name"])
        name_lbl.setProperty("class", "textColorPrimary")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(name_lbl)

        type_map = {
            "artist": translate("Artist"),
            "album": translate("Album"),
            "genre": translate("Genre"),
            "composer": translate("Composer"),
        }
        display_type = type_map.get(data["type"], data["type"].capitalize())
        sub_text = display_type
        if data.get("subtitle"):
            sub_text += f" • {data['subtitle']}"

        type_lbl = ElidedLabel(sub_text)
        type_lbl.setProperty("class", "textTertiary textColorTertiary")
        type_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(type_lbl)

        layout.addLayout(text_layout, 1)

        self.action_btn = QPushButton()
        self.action_btn.setFixedSize(24, 24)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.action_btn)

        if is_selected_list:
            self.action_btn.setIcon(
                create_svg_icon(
                    "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
                )
            )
            self.action_btn.setProperty("class", "btnListAction")
            set_custom_tooltip(
                self.action_btn,
                title = translate("Remove Relation"),
            )
            self.action_btn.clicked.connect(self.removeRequested.emit)
        else:
            self.action_btn.setIcon(
                create_svg_icon(
                    "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
                )
            )
            self.action_btn.setProperty("class", "btnListAction")
            set_custom_tooltip(
                self.action_btn,
                title = translate("Add Relation"),
            )
            self.action_btn.clicked.connect(self.addRequested.emit)

        self.action_btn.hide()
        layout.addWidget(self.action_btn)

        main_layout.addWidget(self.container)

    def enterEvent(self, event):
        """Shows the action button when the mouse enters the widget."""
        self.action_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the action button when the mouse leaves the widget."""
        self.action_btn.hide()
        super().leaveEvent(event)


class DiscographyItemWidget(QWidget):
    """Widget for displaying an album in the discography list."""

    removeRequested = pyqtSignal()

    def __init__(self, data, parent=None):
        """
        Initializes the DiscographyItemWidget.

        Args:
            data (dict): Dictionary containing album data (title, year, in_library).
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.data = data

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setMinimumHeight(42)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        is_real = data.get("in_library", False)
        color = theme.COLORS["ACCENT"] if is_real else theme.COLORS["TERTIARY"]
        tooltip = (
            translate("Present in library")
            if is_real
            else translate("Missing from library")
        )

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            create_svg_icon("assets/control/album.svg", color, QSize(20, 20)).pixmap(
                20, 20
            )
        )
        set_custom_tooltip(
            icon_lbl,
            title = tooltip,
        )
        layout.addWidget(icon_lbl)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        year = data.get("year")
        year_str = f"{year} — " if year and str(year) != "0" else ""

        name_lbl = ElidedLabel(f"{year_str}{data['title']}")
        name_lbl.setProperty("class", "textColorPrimary")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(name_lbl)

        status_text = translate("In Library") if is_real else translate("Manual Entry")
        status_lbl = QLabel(status_text)
        status_lbl.setProperty("class", "textTertiary textColorTertiary")
        status_lbl.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        text_layout.addWidget(status_lbl)

        layout.addLayout(text_layout, 1)

        self.remove_btn = QPushButton()
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        self.remove_btn.setProperty("class", "btnListAction")
        set_custom_tooltip(
            self.remove_btn,
            title = translate("Remove album from list"),
        )
        apply_button_opacity_effect(self.remove_btn)
        self.remove_btn.clicked.connect(self.removeRequested.emit)

        self.remove_btn.hide()
        layout.addWidget(self.remove_btn)

        main_layout.addWidget(self.container)

    def enterEvent(self, event):
        """Shows the remove button when the mouse enters the widget."""
        self.remove_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the remove button when the mouse leaves the widget."""
        self.remove_btn.hide()
        super().leaveEvent(event)


class GalleryImageItem(QWidget):
    """
    Gallery image widget with overlay, edit button, and delete button on hover.
    Supports caption editing via button or context menu.
    """

    removeRequested = pyqtSignal()
    captionChanged = pyqtSignal(str)

    def __init__(self, pixmap, path_or_data, radius=6, is_missing=False, tooltip="", parent=None):
        """
        Initializes the GalleryImageItem.

        Args:
            pixmap (QPixmap): The image to display.
            path_or_data (str or dict): Image file path, or dictionary containing 'path' and 'caption'.
            radius (int, optional): Border radius for the image. Defaults to 6.
            is_missing (bool, optional): Indicates if the original file is missing. Defaults to False.
            tooltip (str, optional): Base tooltip text. Defaults to empty string.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.setFixedSize(128, 128)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        self.base_tooltip = tooltip

        if isinstance(path_or_data, dict):
            self.image_path = path_or_data.get("path")
            self.caption = path_or_data.get("caption", "")
        else:
            self.image_path = path_or_data
            self.caption = ""

        self.thumb = RoundedCoverLabel(pixmap, radius, self)
        self.thumb.setGeometry(0, 0, 128, 128)

        self.overlay = QFrame(self)
        self.overlay.setGeometry(0, 0, 128, 128)
        self.overlay.setProperty("class", "galleryThumbOverlay")
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay.hide()

        self.btns_container = QWidget(self.overlay)
        self.btns_container.setGeometry(0, 0, 128, 128)
        btns_layout = QHBoxLayout(self.btns_container)
        btns_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btns_layout.setSpacing(8)

        self.edit_btn = QPushButton()
        self.edit_btn.setFixedSize(36, 36)
        self.edit_btn.setProperty("class", "btnTranslucentBG")
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setIcon(create_svg_icon("assets/control/article_edit.svg", "WHITE", QSize(24, 24)))
        self.edit_btn.setIconSize(QSize(24, 24))
        set_custom_tooltip(
            self.edit_btn,
            title = translate("Edit Caption"),
        )
        apply_button_opacity_effect(self.edit_btn)
        self.edit_btn.clicked.connect(self._edit_caption)

        self.del_btn = QPushButton()
        self.del_btn.setFixedSize(36, 36)
        self.del_btn.setProperty("class", "btnTranslucentBG")
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setIcon(create_svg_icon("assets/control/clear.svg", "WHITE", QSize(24, 24)))
        self.del_btn.setIconSize(QSize(24, 24))
        set_custom_tooltip(
            self.del_btn,
            title = translate("Delete"),
        )
        apply_button_opacity_effect(self.del_btn)
        self.del_btn.clicked.connect(self.removeRequested.emit)

        btns_layout.addWidget(self.edit_btn)
        btns_layout.addWidget(self.del_btn)

        self.caption_indicator = QLabel(self)
        self.caption_indicator.setPixmap(
            create_svg_icon("assets/control/info.svg", theme.COLORS["WHITE"], QSize(20, 20)).pixmap(20, 20)
        )
        self.caption_indicator.move(104, 104)
        self.caption_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._update_ui_states()

    def _update_ui_states(self):
        """Updates tooltips and caption indicator visibility based on the current caption."""
        has_caption = bool(self.caption)

        self.caption_indicator.setVisible(has_caption)

        if has_caption:
            title = translate("Caption")
            text = self.caption
            if self.base_tooltip:
                text += f"\n\n{self.base_tooltip}"
        else:
            title = None
            text = self.base_tooltip or translate("Edit to add caption to the image")

        set_custom_tooltip(self, title = title, text = text)

    def _edit_caption(self):
        """Opens a dialog to edit the image caption."""
        text, ok = CustomInputDialog.getText(
            self,
            title=translate("Image Caption"),
            label=translate("Enter a caption for this image."),
            text=self.caption,
            ok_text=translate("Save"),
            cancel_text=translate("Cancel"),
        )

        if ok:
            self.caption = text.strip()
            self._update_ui_states()
            self.captionChanged.emit(self.caption)

    def enterEvent(self, event):
        """Shows the overlay with action buttons when the mouse enters the widget."""
        self.overlay.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the overlay when the mouse leaves the widget."""
        self.overlay.hide()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        """
        Provides a context menu to edit or delete the image.

        Args:
            event (QContextMenuEvent): The context menu event.
        """
        menu = TranslucentMenu(self)
        edit_action = QAction(translate("Edit Caption"), menu)
        edit_action.triggered.connect(self._edit_caption)
        menu.addAction(edit_action)

        remove_action = QAction(translate("Delete"), menu)
        remove_action.triggered.connect(self.removeRequested.emit)
        menu.addAction(remove_action)
        menu.exec(event.globalPos())

    def get_data(self):
        """
        Retrieves the current data for the gallery item.

        Returns:
            dict: A dictionary containing 'path' and 'caption'.
        """
        return {
            "path": self.image_path,
            "caption": self.caption
        }


class LocalSearchInteractionFilter(QObject):
    """
    Event filter to manage the opacity of a target effect based on hover and focus events.
    """
    def __init__(self, target_effect, parent=None):
        """
        Initializes the LocalSearchInteractionFilter.

        Args:
            target_effect (QGraphicsEffect): The visual effect (like opacity) to be modified.
            parent (QObject, optional): The parent object.
        """
        super().__init__(parent)
        self.target_effect = target_effect
        self.is_hovered = False
        self.is_focused = False

    def _update_opacity(self):
        """Updates the opacity of the target effect based on focus and hover state."""
        if self.is_hovered or self.is_focused:
            self.target_effect.setOpacity(1.0)
        else:
            self.target_effect.setOpacity(0.3)

    def eventFilter(self, obj, event):
        """
        Intercepts events for the installed object to update interaction states.

        Args:
            obj (QObject): The object being filtered.
            event (QEvent): The event to process.

        Returns:
            bool: True if the event was handled, otherwise False.
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


class CleanRichTextEdit(StyledTextEdit):
    """
    A text edit widget configured to strip formatting upon pasting, inserting plain text.
    """
    def __init__(self, parent=None):
        """
        Initializes the CleanRichTextEdit.

        Args:
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.setAcceptRichText(True)
        self.setProperty("class", "lyricsEditor")

    def insertFromMimeData(self, source):
        """
        Overrides the default paste behavior to ensure pasted text drops rich formatting.

        Args:
            source (QMimeData): The data being pasted.
        """
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


class BlockWidget(QWidget):
    """
    Widget representing a single block of content with a title and rich text editor.
    """
    titleChanged = pyqtSignal(str)

    def __init__(self, parent=None, title="", content="", source_name="", source_url=""):
        """
        Initializes the BlockWidget.

        Args:
            parent (QWidget, optional): The parent widget.
            title (str, optional): The initial title of the block.
            content (str, optional): The initial HTML content of the block.
            source_name (str, optional): The initial source name text.
            source_url (str, optional): The initial source URL text.
        """
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel(translate("Title"))
        title_label.setProperty("class", "textTertiary textColorTertiary")
        layout.addWidget(title_label)

        title_text = str(title) if title is not None else ""
        self.title_edit = StyledLineEdit(title_text)
        self.title_edit.setFixedHeight(36)
        self.title_edit.setPlaceholderText(translate("Optional"))
        self.title_edit.setProperty("class", "inputBorderSinglePadding")
        self.title_edit.textChanged.connect(self.titleChanged.emit)

        self.toolbar_layout = QHBoxLayout()
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(4)

        self.format_btns = {}
        self._setup_toolbar()

        content_text = str(content) if content is not None else ""
        self.content_edit = CleanRichTextEdit()
        self.content_edit.setProperty("class", "inputBorderSingle")
        self.content_edit.setHtml(content_text)
        self.content_edit.setPlaceholderText(translate("Content text..."))

        self.content_edit.cursorPositionChanged.connect(self._update_format_buttons)

        main_source_layout = QHBoxLayout()
        main_source_layout.setContentsMargins(0, 0, 0, 0)
        main_source_layout.setSpacing(16)

        source_title_layout = QVBoxLayout()
        source_title_layout.setContentsMargins(0, 0, 0, 0)
        source_title_layout.setSpacing(8)

        source_title_label = QLabel(translate("Source Title"))
        source_title_label.setProperty("class", "textTertiary textColorTertiary")
        source_title_layout.addWidget(source_title_label)

        self.source_name_edit = StyledLineEdit(str(source_name) if source_name else "")
        self.source_name_edit.setFixedHeight(36)
        self.source_name_edit.setPlaceholderText(translate("Optional"))
        self.source_name_edit.setProperty("class", "inputBorderSinglePadding")
        source_title_layout.addWidget(self.source_name_edit)

        source_link_layout = QVBoxLayout()
        source_link_layout.setContentsMargins(0, 0, 0, 0)
        source_link_layout.setSpacing(8)

        source_link_label = QLabel(translate("Source URL"))
        source_link_label.setProperty("class", "textTertiary textColorTertiary")
        source_link_layout.addWidget(source_link_label)

        self.source_url_edit = StyledLineEdit(str(source_url) if source_url else "")
        self.source_url_edit.setFixedHeight(36)
        self.source_url_edit.setPlaceholderText(translate("Optional"))
        self.source_url_edit.setProperty("class", "inputBorderSinglePadding")
        source_link_layout.addWidget(self.source_url_edit, 2)

        main_source_layout.addLayout(source_title_layout, 1)
        main_source_layout.addLayout(source_link_layout, 2)

        layout.addWidget(self.title_edit)
        layout.addSpacing(8)
        layout.addLayout(self.toolbar_layout)
        layout.addWidget(self.content_edit, 1)
        layout.addSpacing(8)
        layout.addLayout(main_source_layout)

    def _setup_toolbar(self):
        """Initializes formatting buttons for the text editor toolbar."""
        formats = [
            ("format_bold", translate("Bold"), "b"),
            ("format_italic", translate("Italic"), "i"),
            ("format_underlined", translate("Underline"), "u"),
        ]

        for icon_name, tooltip, tag in formats:
            btn = self._create_toolbar_btn(icon_name, tooltip, is_checkable=True)
            btn.clicked.connect(partial(self._toggle_format, tag))
            self.format_btns[tag] = (btn, icon_name)
            self.toolbar_layout.addWidget(btn)

        self.list_btn = self._create_toolbar_btn(
            "format_list_bulleted", translate("Bullet List")
        )
        self.list_btn.clicked.connect(self._insert_list)
        self.toolbar_layout.addWidget(self.list_btn)

        self.clear_btn = self._create_toolbar_btn(
            "format_clear", translate("Clear Formatting")
        )
        self.clear_btn.clicked.connect(self._clear_formatting)
        self.toolbar_layout.addWidget(self.clear_btn)

        self.toolbar_layout.addStretch()

    def _create_toolbar_btn(self, icon_name, tooltip, is_checkable=False):
        """
        Creates a formatting button for the toolbar.

        Args:
            icon_name (str): The name of the SVG icon file (without extension).
            tooltip (str): The tooltip text for the button.
            is_checkable (bool, optional): Whether the button acts as a toggle. Defaults to False.

        Returns:
            QPushButton: The customized toolbar button.
        """
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        btn.setCheckable(is_checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(
            create_svg_icon(
                f"assets/control/{icon_name}.svg",
                theme.COLORS["PRIMARY"],
                QSize(20, 20),
            )
        )
        btn.setIconSize(QSize(20, 20))
        set_custom_tooltip(
            btn,
            title = tooltip,
        )
        btn.setProperty("class", "btnTool")
        apply_button_opacity_effect(btn)
        return btn

    def _update_format_buttons(self):
        """Checks the format and presence of a list under the cursor, updating button colors."""
        cursor = self.content_edit.textCursor()
        fmt = cursor.charFormat()

        active_states = {
            "b": fmt.fontWeight() >= QFont.Weight.Bold,
            "i": fmt.fontItalic(),
            "u": fmt.fontUnderline(),
        }

        for tag, (btn, icon_name) in self.format_btns.items():
            is_active = active_states.get(tag, False)
            btn.blockSignals(True)
            btn.setChecked(is_active)
            color = theme.COLORS["ACCENT"] if is_active else theme.COLORS["PRIMARY"]
            btn.setIcon(
                create_svg_icon(f"assets/control/{icon_name}.svg", color, QSize(20, 20))
            )
            btn.setIconSize(QSize(20, 20))
            btn.blockSignals(False)

        current_line_text = cursor.block().text().strip()
        is_list_active = current_line_text.startswith("•")

        list_color = (
            theme.COLORS["ACCENT"] if is_list_active else theme.COLORS["PRIMARY"]
        )
        self.list_btn.setIcon(
            create_svg_icon(
                "assets/control/format_list_bulleted.svg", list_color, QSize(20, 20)
            )
        )
        self.list_btn.setIconSize(QSize(20, 20))

    def _toggle_format(self, tag):
        """
        Smart style toggling and merging for text formatting.

        Args:
            tag (str): The tag character representing the style ('b', 'i', 'u').
        """
        cursor = self.content_edit.textCursor()
        btn, _ = self.format_btns[tag]
        is_now_active = btn.isChecked()

        fmt = QTextCharFormat()
        if tag == "b":
            fmt.setFontWeight(
                QFont.Weight.Bold if is_now_active else QFont.Weight.Normal
            )
        elif tag == "i":
            fmt.setFontItalic(is_now_active)
        elif tag == "u":
            fmt.setFontUnderline(is_now_active)

        cursor.mergeCharFormat(fmt)
        self.content_edit.mergeCurrentCharFormat(fmt)
        self.content_edit.setFocus()
        self._update_format_buttons()

    def _insert_list(self):
        """Intelligent list management: adding or removing bullet points."""
        cursor = self.content_edit.textCursor()

        if not cursor.hasSelection():
            line_text = cursor.block().text()
            if line_text.strip().startswith("•"):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(
                    QTextCursor.MoveOperation.EndOfBlock,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                text = cursor.selectedText().strip()
                new_text = text[1:].lstrip() if text.startswith("•") else text
                cursor.insertText(new_text)
            else:
                cursor.insertText("• ")
            self.content_edit.setFocus()
            self._update_format_buttons()
            return

        text = cursor.selectedText().replace("\u2029", "\n")
        lines = text.split("\n")
        is_removal = any(line.strip().startswith("•") for line in lines if line.strip())

        new_lines = []
        for line in lines:
            stripped = line.lstrip()
            if is_removal:
                if stripped.startswith("•"):
                    content = stripped[1:].lstrip()
                    new_lines.append(content)
                else:
                    new_lines.append(line)
            else:
                if line.strip():
                    new_lines.append(f"• {line.strip()}")
                else:
                    new_lines.append(line)

        cursor.insertText("\n".join(new_lines))
        self.content_edit.setFocus()
        self._update_format_buttons()

    def _clear_formatting(self):
        """Corrected clearing: reset all character formats in the selection."""
        cursor = self.content_edit.textCursor()

        if not cursor.hasSelection():
            self.content_edit.setCurrentCharFormat(QTextCharFormat())
        else:
            cursor.setCharFormat(QTextCharFormat())
            self.content_edit.setTextCursor(cursor)

        self.content_edit.setFocus()
        self._update_format_buttons()

    def get_data(self):
        """
        Retrieves the content and metadata of the current block.

        Returns:
            dict or None: A dictionary containing 'title', 'content',
            'source_name', and 'source_url' if valid data exists, otherwise None.
        """
        t = self.title_edit.text().strip()
        raw_html = self.content_edit.toHtml()
        match = re.search(r"<body[^>]*>(.*?)</body>", raw_html, re.DOTALL | re.IGNORECASE)
        clean_html = match.group(1).strip() if match else raw_html
        clean_html = re.sub(r"margin-top:\d+px;", "margin-top:0px;", clean_html)
        clean_html = re.sub(r"margin-bottom:\d+px;", "margin-bottom:0px;", clean_html)

        s_name = self.source_name_edit.text().strip()
        s_url = self.source_url_edit.text().strip()

        if not t and not self.content_edit.toPlainText().strip():
            return None

        return {
            "title": t,
            "content": clean_html,
            "source_name": s_name,
            "source_url": s_url
        }


class LinkWidget(QWidget):
    """
    Widget containing inputs for a link's title and URL, with an option to remove it.
    """
    def __init__(self, parent=None, title="", url=""):
        """
        Initializes the LinkWidget.

        Args:
            parent (QWidget, optional): The parent widget.
            title (str, optional): The initial title of the link.
            url (str, optional): The initial URL of the link.
        """
        super().__init__(parent)
        self._is_removed = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setProperty("class", "contentWidget")
        self.container.setObjectName("linkContainer")
        main_layout.addWidget(self.container)

        row_layout = QHBoxLayout(self.container)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(8)

        title_text = str(title) if title is not None else ""
        url_text = str(url) if url is not None else ""

        self.title_edit = StyledLineEdit(title_text)
        self.title_edit.setFixedHeight(36)
        self.title_edit.setPlaceholderText(translate("Link Title"))
        self.title_edit.setProperty("class", "inputBorderSinglePadding")

        self.url_edit = StyledLineEdit(url_text)
        self.url_edit.setFixedHeight(36)
        self.url_edit.setPlaceholderText("https://...")
        self.url_edit.setProperty("class", "inputBorderSinglePadding")

        self.remove_btn = QPushButton()
        self.remove_btn.setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        self.remove_btn.setFixedSize(24, 24)
        set_custom_tooltip(
            self.remove_btn,
            title = translate("Remove Link"),
        )
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.clicked.connect(self._mark_removed)
        apply_button_opacity_effect(self.remove_btn)

        sp = self.remove_btn.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.remove_btn.setSizePolicy(sp)
        self.remove_btn.hide()

        row_layout.addWidget(self.title_edit, 1)
        row_layout.addWidget(self.url_edit, 2)
        row_layout.addWidget(self.remove_btn)

    def enterEvent(self, event):
        """Shows the remove button when the mouse enters the widget."""
        self.remove_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the remove button when the mouse leaves the widget."""
        self.remove_btn.hide()
        super().leaveEvent(event)

    def _mark_removed(self):
        """Marks the link widget for deletion and hides it."""
        self._is_removed = True
        self.setVisible(False)
        self.deleteLater()

    def get_data(self):
        """
        Retrieves the link's title and URL data.

        Returns:
            dict or None: A dictionary with 'title' and 'url' if valid, otherwise None.
        """
        if self._is_removed:
            return None
        t = self.title_edit.text().strip()
        u = self.url_edit.text().strip()
        if not t and not u:
            return None
        return {"title": t, "url": u}


class LinksOverflowWidget(QWidget):
    """
    Widget for displaying links in a single line.
    If there is not enough space, extra links are hidden in the 'More' button.
    """

    def __init__(self, links_data, parent=None):
        """
        Initializes the LinksOverflowWidget.

        Args:
            links_data (list of dict): List containing link dictionaries ('title', 'url').
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.links_data = links_data
        self.buttons = []

        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(16)

        self.overflow_btn = StyledToolButton()
        self.overflow_btn.setText(translate("More links"))
        self.overflow_btn.setProperty("class", "btnToolMenu")
        self.overflow_btn.setFixedHeight(36)
        self.overflow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overflow_btn.setPopupMode(StyledToolButton.ToolButtonPopupMode.InstantPopup)
        self.overflow_btn.setAutoRaise(True)

        self.overflow_menu = TranslucentMenu(self.overflow_btn)
        self.overflow_menu.setProperty("class", "popMenu")
        self.overflow_btn.setMenu(self.overflow_menu)

        for link in links_data:
            btn = QPushButton(link.get("title", "Link"))
            btn.setProperty("class", "btnLink")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                btn,
                title = translate('Open in browser'),
                text = link.get('url'),
                activity_type="external"
            )
            btn.setProperty("url", link.get("url"))
            btn.clicked.connect(self._on_link_clicked)

            self.layout.addWidget(btn)
            self.buttons.append(btn)

        self.layout.addWidget(self.overflow_btn)
        self.overflow_btn.hide()
        self.layout.addStretch()

    def showEvent(self, event):
        """
        Handles the show event to trigger an initial layout recalculation.

        Args:
            event (QShowEvent): The show event.
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._recalc_layout)

    def minimumSizeHint(self):
        """
        Provides a minimum size hint considering the overflow button.

        Returns:
            QSize: The recommended minimum size.
        """
        return QSize(self.overflow_btn.sizeHint().width(), 40)

    def _on_link_clicked(self):
        """Opens the associated URL in the system's default browser when a link button is clicked."""
        btn = self.sender()
        url = btn.property("url")
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            QDesktopServices.openUrl(QUrl(url))

    def resizeEvent(self, event):
        """
        Handles the resize event to adjust which links are visible and which are in the overflow menu.

        Args:
            event (QResizeEvent): The resize event.
        """
        self._recalc_layout()
        super().resizeEvent(event)

    def _recalc_layout(self):
        """Calculates available space and moves overflowing links into the drop-down menu."""
        if not self.buttons:
            return

        if self.width() <= 0:
            return

        total_width = self.width()
        spacing = self.layout.spacing()

        overflow_width = self.overflow_btn.sizeHint().width() + spacing

        current_x = 0
        hidden_items = []

        all_fit = True
        temp_x = 0
        for btn in self.buttons:
            w = btn.sizeHint().width()
            if temp_x + w > total_width:
                all_fit = False
                break
            temp_x += w + spacing

        if all_fit:
            for btn in self.buttons:
                btn.show()
            self.overflow_btn.hide()
            return

        available_width = total_width - overflow_width

        for btn in self.buttons:
            btn_width = btn.sizeHint().width()

            if current_x + btn_width <= available_width:
                btn.show()
                current_x += btn_width + spacing
            else:
                btn.hide()
                hidden_items.append(btn)

        if hidden_items:
            self.overflow_btn.show()
            self.overflow_menu.clear()
            for btn in hidden_items:
                text = btn.text()
                url = btn.property("url")

                if url and not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                action = QAction(text, self.overflow_menu)
                action.triggered.connect(partial(QDesktopServices.openUrl, QUrl(url)))
                self.overflow_menu.addAction(action)
        else:
            self.overflow_btn.hide()


class EncyclopediaTextBrowser(StyledTextBrowser):
    """
    A read-only text browser tailored for displaying encyclopedia article content
    with auto-resizing capabilities based on the document's height.
    """
    def __init__(self, html_content, parent=None):
        """
        Initializes the EncyclopediaTextBrowser.

        Args:
            html_content (str): The initial HTML content to display.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)

        self._original_html = html_content

        self.document().setDocumentMargin(0)

        self.setContentsMargins(0, 0, 0, 0)

        self.setFrameStyle(QFrame.Shape.NoFrame)

        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.setProperty("class", "EncyclopediaTextBlock")

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        palette = self.palette()
        palette.setBrush(QPalette.ColorRole.Base, QBrush(Qt.BrushStyle.NoBrush))
        self.setPalette(palette)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.setHtml(self._original_html)
        self.document().contentsChanged.connect(self.adjust_height)

    def adjust_height(self):
        """Automatically adjusts widget height to fit content."""
        self.document().setTextWidth(self.viewport().width())
        new_height = int(self.document().size().height()) + 15
        self.setFixedHeight(new_height)

    def resizeEvent(self, event):
        """
        Handles resize events by recalculating the required height via a timer.

        Args:
            event (QResizeEvent): The resize event.
        """
        super().resizeEvent(event)
        QTimer.singleShot(10, self.adjust_height)

    def update_font_scale(self, base_size, level):
        """
        Forces text to be wrapped in a div with the required font size.
        This is the most reliable way to override internal HTML styles.

        Args:
            base_size (int): The base font size in pixels.
            level (int): The scaling level applied to the base font size.
        """
        new_size = base_size + (level * 2)
        color = theme.COLORS.get("PRIMARY")

        styled_html = f"<div style='font-size:{new_size}px; color:{color};'>{self._original_html}</div>"

        self.setHtml(styled_html)
        self.adjust_height()