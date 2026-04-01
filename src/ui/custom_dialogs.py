"""
Vinyller — Custom dialogs and messages
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

import copy
import json

from PyQt6.QtCore import (
    pyqtSignal, QSize, Qt,
    QTimer, QEvent
)
from PyQt6.QtGui import (
    QAction, QIcon,
    QPainter, QPixmap
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox, QDialog, QDialogButtonBox,
    QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QGridLayout,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QStackedWidget, QVBoxLayout, QWidget, QAbstractItemView, QSizePolicy
)

from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledListWidget, StyledTextEdit, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect
)
from src.ui.custom_lists import (
    BlacklistItemWidget, NavCategoryItem, UnavailableItemWidget
)
from src.utils import theme
from src.utils.constants import SUPPORTED_LANGUAGES
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate


class ChangedFilesDialog(StyledDialog):
    """
    Dialog for displaying a list of changed (added/modified) and removed files.
    Allows the user to search and filter through the affected files.
    """
    def __init__(self, changed_files, removed_files, parent=None, title=""):
        """
        Initialize the dialog.

        :param changed_files: List of added or modified file paths or tuples (status, path).
        :param removed_files: List of removed file paths.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Changed Files"))
        self.setMinimumSize(640, 480)
        self.resize(640, 480)
        self.setProperty("class", "backgroundPrimary")

        self.changed_files = changed_files or []
        self.removed_files = removed_files or []
        self.all_items = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        title = QLabel(translate("Changed Files"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")
        content_layout.addWidget(title)

        added_count = sum(1 for item in self.changed_files if isinstance(item, tuple) and item[0] == "new")
        modified_count = len(self.changed_files) - added_count

        desc_text = translate(
            "Added: {add_count}  |  Modified: {mod_count}  |  Removed: {rem_count}",
            add_count = added_count,
            mod_count = modified_count,
            rem_count = len(self.removed_files)
        )

        desc = QLabel(desc_text)
        desc.setProperty("class", "textSecondary textColorPrimary")
        content_layout.addWidget(desc)

        self.search_input = StyledLineEdit()
        self.search_input.setPlaceholderText(translate("Search..."))
        self.search_input.textChanged.connect(self.filter_files)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.findChild(QAction).setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        content_layout.addWidget(self.search_input)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidget")
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.list_widget.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        content_layout.addWidget(self.list_widget)

        self.populate_data()
        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)
        close_btn = self.button_box.addButton(translate("Close"), QDialogButtonBox.ButtonRole.AcceptRole)

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.button_box.accepted.connect(self.accept)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def populate_data(self):
        """
        Populate the internal list of all items based on changed and removed files.
        """
        for item in self.changed_files:
            if isinstance(item, tuple) and len(item) == 2:
                status, path = item
                self.all_items.append((status, path))
            else:
                self.all_items.append(("modified", item))

        for f in self.removed_files:
            self.all_items.append(("removed", f))

        self.update_list_view("")

    def update_list_view(self, filter_text):
        """
        Update the displayed list of files based on a search filter.

        :param filter_text: The text to filter file paths by.
        """
        self.list_widget.clear()
        filter_text = filter_text.lower()

        self.list_widget.setIconSize(QSize(18, 18))

        for status, path in self.all_items:
            if filter_text in path.lower():
                item = QListWidgetItem(path)
                item.setSizeHint(QSize(0, 32))

                set_custom_tooltip(
                    item,
                    title = translate("File Path"),
                    text = path
                )

                icon_file = ""
                if status == "new":
                    icon_file = "assets/control/add.svg"
                elif status == "modified":
                    icon_file = "assets/control/replace.svg"
                elif status == "removed":
                    icon_file = "assets/control/remove.svg"

                if icon_file:
                    icon = create_svg_icon(icon_file, theme.COLORS["PRIMARY"], QSize(18, 18))
                    item.setIcon(icon)

                self.list_widget.addItem(item)

    def filter_files(self, text):
        """
        Slot to handle search input changes.

        :param text: Current search input text.
        """
        self.update_list_view(text)


class CustomInputDialog(StyledDialog):
    """
    A custom modal dialog for requesting text input from the user.
    """
    def __init__(
        self,
        parent=None,
        title="",
        label="",
        text="",
        ok_text=translate("OK"),
        cancel_text=translate("Cancel"),
    ):
        """
        Initialize the custom input dialog.

        :param parent: Parent widget.
        :param title: Dialog window title.
        :param label: Descriptive label above the input field.
        :param text: Default text for the input field.
        :param ok_text: Text for the confirm button.
        :param cancel_text: Text for the cancel button.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setProperty("class", "backgroundPrimary")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        if title:
            title_label = QLabel(title)
            title_label.setProperty("class", "textHeaderPrimary textColorPrimary")
            content_layout.addWidget(title_label)

        if label:
            desc_label = QLabel(label)
            desc_label.setProperty("class", "textSecondary textColorPrimary")
            desc_label.setWordWrap(True)
            desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            content_layout.addWidget(desc_label)

        self.lineEdit = StyledLineEdit(self)
        self.lineEdit.setText(text)
        content_layout.addWidget(self.lineEdit)
        self.lineEdit.setFocus()

        self.error_label = QLabel("", self)
        self.error_label.setProperty("class", "textPrimary textColorAccent")
        self.error_label.setWordWrap(True)
        self.error_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.error_label.hide()
        content_layout.addWidget(self.error_label)
        content_layout.addStretch()

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        if ok_text:
            ok_button = QPushButton(ok_text)
            self.button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)

        if cancel_text:
            cancel_button = QPushButton(cancel_text)
            self.button_box.addButton(
                cancel_button, QDialogButtonBox.ButtonRole.RejectRole
            )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.lineEdit.textChanged.connect(lambda: self.error_label.hide())

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def show_error(self, message):
        """
        Display an error message inside the dialog.

        :param message: The error text to display.
        """
        self.error_label.setText(message)
        self.error_label.show()

    def textValue(self):
        """
        Get the current value of the input field.

        :return: String from the line edit.
        """
        return self.lineEdit.text()

    @staticmethod
    def getText(
        parent=None,
        title="",
        label="",
        text="",
        ok_text=translate("OK"),
        cancel_text=translate("Cancel"),
    ):
        """
        Static helper to create and show the dialog, returning the input result.

        :return: A tuple containing the input text and a boolean indicating if accepted.
        """
        dialog = CustomInputDialog(parent, title, label, text, ok_text, cancel_text)
        result = dialog.exec()
        text_value = dialog.textValue()
        return text_value, result == QDialog.DialogCode.Accepted


class CustomConfirmDialog(StyledDialog):
    """
    A custom modal dialog for confirming actions.
    Supports OK, Cancel, and an optional Restart action.
    """
    RestartCode = 2

    def __init__(
        self,
        parent=None,
        title="",
        label="",
        ok_text=translate("OK"),
        cancel_text=translate("Cancel"),
        restart_text=None,
    ):
        """
        Initialize the custom confirmation dialog.

        :param parent: Parent widget.
        :param title: Dialog window title.
        :param label: Descriptive text or question.
        :param ok_text: Text for the accept button.
        :param cancel_text: Text for the cancel button.
        :param restart_text: Optional text for an alternative action button (e.g., Restart).
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setProperty("class", "backgroundPrimary")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        title_label = QLabel(title)
        title_label.setProperty("class", "textHeaderPrimary textColorPrimary")

        desc_label = QLabel(label)
        desc_label.setProperty("class", "textSecondary textColorPrimary")
        desc_label.setWordWrap(True)
        desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        content_layout.addWidget(title_label)
        content_layout.addWidget(desc_label)
        content_layout.addStretch()

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        if ok_text:
            ok_button = QPushButton(ok_text)
            self.button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)

        if restart_text:
            restart_button = QPushButton(restart_text)
            restart_button.clicked.connect(self.on_restart_clicked)
            self.button_box.addButton(
                restart_button, QDialogButtonBox.ButtonRole.ActionRole
            )

        if cancel_text:
            cancel_button = QPushButton(cancel_text)
            self.button_box.addButton(
                cancel_button, QDialogButtonBox.ButtonRole.RejectRole
            )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def on_restart_clicked(self):
        """
        Slot to handle the optional restart action button.
        Finishes the dialog with the RestartCode.
        """
        self.done(self.RestartCode)

    @staticmethod
    def confirm(
        parent=None,
        title="",
        label="",
        ok_text=translate("OK"),
        cancel_text=translate("Cancel"),
        restart_text=None,
    ):
        """
        Static helper to create and show a general confirmation dialog.

        :return: Result code of the dialog execution.
        """
        dialog = CustomConfirmDialog(
            parent, title, label, ok_text, cancel_text, restart_text
        )
        return dialog.exec()

    @staticmethod
    def confirm_removal(parent, item_name, track_count, item_type_str, mode):
        """
        Static helper to create and show a specialized confirmation dialog for removing items.

        :param parent: Parent widget.
        :param item_name: Name of the item being removed.
        :param track_count: Number of tracks associated with the item.
        :param item_type_str: String representation of the item type (e.g. 'Album').
        :param mode: Removal mode ('blacklist' or 'delete').
        :return: True if accepted, False otherwise.
        """
        if mode == "blacklist":
            title = translate("Confirm Blacklisting")
            label = translate("The following files will be removed from the library and added to the blacklist")
            label += ":<br><b>"
            label += item_type_str + " " + item_name + " ("
            label += translate("{count} track(s)", count = track_count)
            label += ")</b>"
        else:
            title = translate("Confirm Deletion")
            label = translate("<b>Attention!</b> The following files will be deleted from the library and from your drive")
            label += ":<br><b>"
            label += item_type_str + " " + item_name + " ("
            label += translate("{count} track(s)", count = track_count)
            label += ")</b>"

        dialog = CustomConfirmDialog(
            parent,
            title,
            label,
            ok_text=translate("Confirm"),
            cancel_text=translate("Cancel"),
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


class ClearStatsConfirmDialog(StyledDialog):
    """
    A dialog to confirm clearing statistics, including an option to delete archives.
    """
    def __init__(
        self,
        parent=None,
        title="",
        label="",
        checkbox_text="",
        ok_text=translate("OK"),
        cancel_text=translate("Cancel"),
    ):
        """
        Initialize the clear stats confirmation dialog.

        :param parent: Parent widget.
        :param title: Dialog title.
        :param label: Dialog main description text.
        :param checkbox_text: Text for the archive deletion checkbox.
        :param ok_text: Text for the accept button.
        :param cancel_text: Text for the cancel button.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setProperty("class", "backgroundPrimary")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "textHeaderPrimary textColorPrimary")

        desc_lbl = QLabel(label)
        desc_lbl.setProperty("class", "textSecondary textColorPrimary")
        desc_lbl.setWordWrap(True)
        desc_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        content_layout.addWidget(title_lbl)
        content_layout.addWidget(desc_lbl)

        self.delete_archive_checkbox = QCheckBox(checkbox_text)
        self.delete_archive_checkbox.setMinimumHeight(18)
        self.delete_archive_checkbox.setProperty("class", "textColorPrimary")
        self.delete_archive_checkbox.setChecked(False)
        content_layout.addWidget(self.delete_archive_checkbox)
        content_layout.addStretch()

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        if ok_text:
            ok_button = QPushButton(ok_text)
            self.button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)

        if cancel_text:
            cancel_button = QPushButton(cancel_text)
            self.button_box.addButton(
                cancel_button, QDialogButtonBox.ButtonRole.RejectRole
            )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def is_archive_delete_checked(self):
        """
        Check if the archive deletion checkbox is checked.

        :return: True if checked, False otherwise.
        """
        return self.delete_archive_checkbox.isChecked()

    @staticmethod
    def confirm_clear_stats(
        parent=None,
        title="",
        label="",
        checkbox_text="",
        ok_text=translate("OK"),
        cancel_text=translate("Cancel"),
    ):
        """
        Static helper to create and show the clear stats dialog.

        :return: Tuple containing (is_accepted: bool, is_checkbox_checked: bool)
        """
        dialog = ClearStatsConfirmDialog(
            parent, title, label, checkbox_text, ok_text, cancel_text
        )
        result = dialog.exec()
        checkbox_checked = dialog.is_archive_delete_checked()
        return (result == QDialog.DialogCode.Accepted, checkbox_checked)


class DeleteWithCheckboxDialog(StyledDialog):
    """
    A generic deletion confirmation dialog featuring an additional optional checkbox.
    """
    def __init__(
        self,
        parent=None,
        title="",
        label="",
        checkbox_text="",
        ok_text=translate("Delete"),
        cancel_text=translate("Cancel"),
        checkbox_checked_by_default=True,
    ):
        """
        Initialize the dialog.

        :param parent: Parent widget.
        :param title: Dialog title.
        :param label: Dialog main description text.
        :param checkbox_text: Text for the optional checkbox.
        :param ok_text: Text for the confirm button.
        :param cancel_text: Text for the cancel button.
        :param checkbox_checked_by_default: Initial state of the checkbox.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setProperty("class", "backgroundPrimary")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "textHeaderPrimary textColorPrimary")

        desc_lbl = QLabel(label)
        desc_lbl.setProperty("class", "textSecondary textColorPrimary")
        desc_lbl.setWordWrap(True)
        desc_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        content_layout.addWidget(title_lbl)
        content_layout.addWidget(desc_lbl)

        self.checkbox = None
        if checkbox_text:
            self.checkbox = QCheckBox(checkbox_text)
            self.checkbox.setMinimumHeight(18)
            self.checkbox.setProperty("class", "textColorPrimary")
            self.checkbox.setChecked(checkbox_checked_by_default)
            content_layout.addWidget(self.checkbox)
        content_layout.addStretch()

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        if ok_text:
            ok_button = QPushButton(ok_text)
            self.button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        if cancel_text:
            cancel_button = QPushButton(cancel_text)
            self.button_box.addButton(
                cancel_button, QDialogButtonBox.ButtonRole.RejectRole
            )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    @staticmethod
    def confirm(
        parent=None,
        title="",
        label="",
        checkbox_text="",
        ok_text=translate("Delete"),
        cancel_text=translate("Cancel"),
        checkbox_checked_by_default=True,
    ):
        """
        Static helper to create and show the dialog.

        :return: Tuple containing (is_accepted: bool, is_checkbox_checked: bool)
        """
        dialog = DeleteWithCheckboxDialog(
            parent,
            title,
            label,
            checkbox_text,
            ok_text,
            cancel_text,
            checkbox_checked_by_default,
        )
        result = dialog.exec()
        checkbox_checked = dialog.checkbox.isChecked() if dialog.checkbox else False
        return (result == QDialog.DialogCode.Accepted, checkbox_checked)


class RemoveFromLibraryDialog(StyledDialog):
    """
    Dialog allowing the user to select how an item should be removed from the library
    (blacklist vs. permanent delete) with an optional toggle for removing favorites.
    """
    def __init__(
            self, item_name, track_count, item_type_str, parent = None,
            has_favorites = False, has_virtual_tracks = False, title=""
    ):
        """
        Initialize the removal dialog.

        :param item_name: Name of the item to remove.
        :param track_count: Number of affected tracks.
        :param item_type_str: Item type as a string (e.g. 'Artist').
        :param parent: Parent widget.
        :param has_favorites: Whether the item contains favorites, enabling the favorites checkbox.
        :param has_virtual_tracks: Whether the item contains virtual tracks from CUE sheets.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Remove from Library"))
        self.setMinimumWidth(450)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        title = QLabel(translate("Remove from Library"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")

        desc = QLabel(translate("Select how you want to remove this item:"))
        desc.setProperty("class", "textSecondary textColorPrimary")
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        content_layout.addWidget(title)
        content_layout.addWidget(desc)

        self.blacklist_radio = QRadioButton(translate("Add to blacklist"))
        self.delete_radio = QRadioButton(translate("Delete from computer"))
        self.blacklist_radio.setChecked(True)

        self.radio_group = QButtonGroup(self)
        self.radio_group.addButton(self.blacklist_radio, 0)
        self.radio_group.addButton(self.delete_radio, 1)

        content_layout.addWidget(self.blacklist_radio)
        content_layout.addWidget(self.delete_radio)

        self.remove_fav_checkbox = None
        if has_favorites:
            self.remove_fav_checkbox = QCheckBox(
                translate("Also remove related items from favorites")
            )
            self.remove_fav_checkbox.setMinimumHeight(18)
            self.remove_fav_checkbox.setProperty("class", "textColorPrimary")
            self.remove_fav_checkbox.setChecked(True)

            content_layout.addWidget(self.remove_fav_checkbox)

        self.description_stack = QStackedWidget()
        self.description_stack.setContentsMargins(0, 8, 0, 0)

        blacklist_desc_text = translate(
            "The following files will be removed from the library and added to the blacklist")
        blacklist_desc_text += ":<br><b>"
        blacklist_desc_text += item_type_str + " " + item_name + " ("
        blacklist_desc_text += translate("{count} track(s)", count = track_count)
        blacklist_desc_text += ")</b><br><br>"
        blacklist_desc_text += translate(
            "During subsequent library updates, the contents of the blacklist will be ignored. "
            "The files will still remain on your drive. Use settings window to manage blacklisted items.")

        blacklist_label = QLabel(blacklist_desc_text)
        blacklist_label.setProperty("class", "textColorPrimary")
        blacklist_label.setTextFormat(Qt.TextFormat.RichText)
        blacklist_label.setWordWrap(True)
        blacklist_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.description_stack.addWidget(blacklist_label)

        delete_desc_text = translate(
            "<b>Attention!</b> The following files will be deleted from the library and from your drive")
        delete_desc_text += ":<br><b>"
        delete_desc_text += item_type_str + " " + item_name + " ("
        delete_desc_text += translate("{count} track(s)", count = track_count)
        delete_desc_text += ")</b><br><br>"
        delete_desc_text += translate(
            "This action will delete only music files. Folders and any other files contained within them "
            "must be deleted manually.")

        if has_virtual_tracks:
            delete_desc_text += "<br><br><b>"
            delete_desc_text += translate("This item contains virtual tracks from CUE sheets.")
            delete_desc_text += "</b><br>"
            delete_desc_text += translate("When deleting virtual tracks generated from a single-file FLAC and its associated CUE file, the album and all its tracks will be deleted entirely.")

        delete_label = QLabel(delete_desc_text)
        delete_label.setProperty("class", "textColorPrimary")
        delete_label.setTextFormat(Qt.TextFormat.RichText)
        delete_label.setWordWrap(True)
        delete_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        delete_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.description_stack.addWidget(delete_label)

        content_layout.addWidget(self.description_stack)
        self.radio_group.idClicked.connect(self.description_stack.setCurrentIndex)
        content_layout.addStretch(1)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)
        continue_button = QPushButton(translate("Continue"))
        cancel_button = QPushButton(translate("Cancel"))
        self.button_box.addButton(
            continue_button, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    @staticmethod
    def select_removal_mode(
            parent, item_name, track_count, item_type_str,
            has_favorites = False, has_virtual_tracks = False
    ):
        """
        Static helper to create and show the removal dialog.

        :return: Tuple containing (mode: str ['delete' or 'blacklist'], remove_favs: bool)
                 or (None, False) if canceled.
        """
        dialog = RemoveFromLibraryDialog(
            item_name, track_count, item_type_str, parent,
            has_favorites, has_virtual_tracks
        )
        if dialog.exec():
            mode = "delete" if dialog.delete_radio.isChecked() else "blacklist"
            remove_favs = (
                dialog.remove_fav_checkbox.isChecked()
                if dialog.remove_fav_checkbox
                else False
            )
            return mode, remove_favs
        return None, False


class NavOrderDialog(StyledDialog):
    """
    Dialog for reordering navigation tabs via drag and drop.
    """

    def __init__(self, current_order, parent = None, title = ""):
        """
        Initialize the navigation order dialog.

        :param current_order: A list of current navigation keys defining the order.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Navigation Tab Order"))
        self.setMinimumWidth(400)
        self.setProperty("class", "backgroundPrimary")

        self.definitions = {
            "artist": (translate("Artists"), "artist"),
            "album": (translate("Albums"), "album"),
            "genre": (translate("Genres"), "genre"),
            "composer": (translate("Composers"), "composer"),
            "track": (translate("All tracks"), "track"),
            "playlist": (translate("Playlists"), "playlist"),
            "folder": (translate("Folders"), "folder"),
            "charts": (translate("Charts"), "charts"),
        }

        self.default_keys = ["artist", "album", "genre", "composer", "track", "playlist", "folder", "charts"]

        self.current_order = []
        for key in current_order:
            if key in self.definitions:
                self.current_order.append(key)

        for key in self.default_keys:
            if key not in self.current_order:
                self.current_order.append(key)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(translate("Navigation Tab Order"))
        title.setProperty("class", "textHeaderSecondary textColorPrimary")
        layout.addWidget(title)

        desc = QLabel(translate("Drag and drop items to reorder the side navigation bar.") + "\n" + translate("Restart Required") + "." )
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setProperty("class", "textSecondary textColorPrimary")
        layout.addWidget(desc)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidget")
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)

        self._populate_list(self.current_order)
        layout.addWidget(self.list_widget)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        reset_btn = QPushButton(translate("Reset"))
        reset_btn.setProperty("class", "btnText")
        reset_btn.setFixedHeight(36)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_to_default)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        for btn in btn_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        bottom_layout.addWidget(reset_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_box)
        main_layout.addWidget(bottom_panel)

    def _populate_list(self, order_list):
        """
        Populate the list widget with the provided order.

        :param order_list: List of navigation keys.
        """
        self.list_widget.clear()
        for key in order_list:
            if key not in self.definitions:
                continue

            name, icon_name = self.definitions[key]
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)

            icon = create_svg_icon(f"assets/control/{icon_name}.svg", theme.COLORS["PRIMARY"], QSize(24, 24))
            item.setIcon(icon)

            item.setSizeHint(QSize(0, 32))

            self.list_widget.addItem(item)

    def _reset_to_default(self):
        """
        Reset the list to the default order.
        """
        self._populate_list(self.default_keys)

    def get_order(self):
        """
        Get the final order defined by the user.

        :return: A list of navigation keys representing the new order.
        """
        new_order = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_order.append(item.data(Qt.ItemDataRole.UserRole))
        return new_order


class BlacklistDialog(StyledDialog):
    """Dialog for managing the blacklist."""

    def __init__(self, blacklist_data, main_window_ref, parent = None, title = ""):
        """
        Initialize the blacklist management dialog.

        :param blacklist_data: Dictionary containing currently blacklisted items.
        :param main_window_ref: Reference to the main window application.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.main_window = main_window_ref
        self.modified_blacklist_data = copy.deepcopy(blacklist_data)
        self.setWindowTitle(translate("Blacklist"))
        self.resize(800, 600)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel(translate("Blacklist"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")
        desc = QLabel(translate("Blacklist sections description text..."))
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setProperty("class", "textSecondary textColorPrimary")
        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        content_layout.addLayout(header_layout)

        split_layout = QHBoxLayout()
        split_layout.setSpacing(24)

        self.nav_list = StyledListWidget()
        self.nav_list.setProperty("class", "listWidgetNav")
        self.nav_list.setFixedWidth(256)
        self.nav_list.setSpacing(2)

        self.stacked_widget = QStackedWidget()

        split_layout.addWidget(self.nav_list)
        split_layout.addWidget(self.stacked_widget, 1)

        content_layout.addLayout(split_layout, 1)

        self.nav_items_widgets = {}
        self.tabs = {}

        categories = [
            ("tracks", translate("Tracks")),
            ("albums", translate("Albums")),
            ("artists", translate("Artists")),
            ("composers", translate("Composers")),
            ("folders", translate("Folders")),
        ]

        for key, name in categories:
            self._create_category(key, name)

        self.nav_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        if self.nav_list.count() > 0:
            self.nav_list.setCurrentRow(0)

        self._populate_lists()
        main_layout.addWidget(content_container, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        restore_all_button = QPushButton(translate("Restore all"))
        restore_all_button.setProperty("class", "btnText")
        restore_all_button.setFixedHeight(36)
        restore_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_all_button.clicked.connect(self.restore_all)

        self.button_box = QDialogButtonBox(self)
        apply_button = self.button_box.addButton(
            translate("Apply"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel_button = self.button_box.addButton(
            translate("Cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addWidget(restore_all_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def _create_category(self, key, name):
        """
        Create a category tab within the blacklist dialog.

        :param key: Category key (e.g., 'tracks').
        :param name: Display name for the category.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        list_widget = StyledListWidget()
        list_widget.setProperty("class", "listWidget")
        layout.addWidget(list_widget)

        self.stacked_widget.addWidget(page)
        self.tabs[key] = list_widget

        nav_item = QListWidgetItem()
        nav_item.setSizeHint(QSize(nav_item.sizeHint().width(), 40))

        widget = NavCategoryItem(
            name, 0
        )

        self.nav_list.addItem(nav_item)
        self.nav_list.setItemWidget(nav_item, widget)

        self.nav_items_widgets[key] = widget

    def _update_nav_counter(self, key):
        """
        Update the item counter displayed on the category navigation list.

        :param key: Category key.
        """
        if key in self.modified_blacklist_data and key in self.nav_items_widgets:
            count = len(self.modified_blacklist_data[key])
            self.nav_items_widgets[key].set_count(count)

    def _populate_lists(self):
        """
        Populate all lists with the current modified blacklist data.
        """
        for tab_key, list_widget in self.tabs.items():
            list_widget.clear()
            items = self.modified_blacklist_data.get(tab_key, [])

            self._update_nav_counter(tab_key)

            has_path = tab_key in ["tracks", "folders"]
            for item_data in items:
                display_text = ""
                if tab_key == "albums":
                    display_text = f"{item_data[0]} - {item_data[1]}"
                else:
                    display_text = str(item_data)
                self._add_item_to_list(list_widget, item_data, display_text, has_path)

    def _add_item_to_list(self, list_widget, item_data, display_text, has_path):
        """
        Helper method to insert a custom BlacklistItemWidget into a QListWidget.
        """
        list_item = QListWidgetItem(list_widget)
        item_widget = BlacklistItemWidget(
            item_data, display_text, list_item, has_path, self
        )

        item_widget.restore_requested.connect(self._on_restore_item)
        item_widget.show_in_explorer_requested.connect(self._on_show_in_explorer)
        size_hint = item_widget.sizeHint()
        list_item.setSizeHint(QSize(0, size_hint.height()))
        list_widget.addItem(list_item)
        list_widget.setItemWidget(list_item, item_widget)

    def _on_restore_item(self, list_item):
        """
        Remove an item from the blacklist and visual list.

        :param list_item: The QListWidgetItem to restore.
        """
        list_widget = list_item.listWidget()
        item_widget = list_widget.itemWidget(list_item)
        item_data = item_widget.item_data

        target_key = None
        for tab_key, lw in self.tabs.items():
            if lw is list_widget:
                target_key = tab_key
                if item_data in self.modified_blacklist_data[tab_key]:
                    self.modified_blacklist_data[tab_key].remove(item_data)
                    break

        list_widget.takeItem(list_widget.row(list_item))

        if target_key:
            self._update_nav_counter(target_key)

    def _on_show_in_explorer(self, item_data):
        """
        Trigger an action to open the selected item's path in the system file explorer.

        :param item_data: Data defining the item's path.
        """
        data_for_explorer = item_data
        if isinstance(item_data, list):
            data_for_explorer = tuple(item_data)
        self.main_window.action_handler.show_in_explorer(data_for_explorer)

    def restore_all(self):
        """
        Confirm and perform clearing of all blacklist categories.
        """
        confirmed = CustomConfirmDialog.confirm(
            self,
            title=translate("Restore All"),
            label=translate(
                "Are you sure you want to remove all items from the blacklist?"
            ),
            ok_text=translate("Restore All"),
            cancel_text=translate("Cancel"),
        )
        if confirmed:
            for tab_key in self.modified_blacklist_data:
                self.modified_blacklist_data[tab_key].clear()
            self._populate_lists()

    def get_blacklist_data(self):
        """
        Retrieve the modified dictionary of blacklisted items.

        :return: A dictionary representing the new blacklist data.
        """
        return self.modified_blacklist_data


class UnavailableFavoritesDialog(StyledDialog):
    """Dialog for managing unavailable favorite items."""

    def __init__(self, unavailable_data, parent = None, title=""):
        """
        Initialize the unavailable favorites dialog.

        :param unavailable_data: Dictionary tracking missing favorite items.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.modified_unavailable_data = copy.deepcopy(unavailable_data)
        self.setWindowTitle(translate("Unavailable Favorites"))
        self.resize(800, 600)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel(translate("Unavailable Favorites"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")
        desc = QLabel(translate("Unavailable sections description text..."))
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setProperty("class", "textSecondary textColorPrimary")
        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        content_layout.addLayout(header_layout)

        split_layout = QHBoxLayout()
        split_layout.setSpacing(24)

        self.nav_list = StyledListWidget()
        self.nav_list.setProperty("class", "listWidgetNav")
        self.nav_list.setFixedWidth(256)
        self.nav_list.setSpacing(2)

        self.stacked_widget = QStackedWidget()

        split_layout.addWidget(self.nav_list)
        split_layout.addWidget(self.stacked_widget, 1)

        content_layout.addLayout(split_layout, 1)

        self.nav_items_widgets = {}
        self.tabs = {}

        categories = [
            ("tracks", translate("Tracks")),
            ("albums", translate("Albums")),
            ("artists", translate("Artists")),
            ("genres", translate("Genres")),
            ("composers", translate("Composers")),
            ("playlists", translate("Playlists")),
            ("folders", translate("Folders")),
        ]

        for key, name in categories:
            self._create_category(key, name)

        self.nav_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        if self.nav_list.count() > 0:
            self.nav_list.setCurrentRow(0)

        self._populate_lists()
        main_layout.addWidget(content_container, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        remove_all_button = QPushButton(translate("Remove All"))
        remove_all_button.setProperty("class", "btnText")
        remove_all_button.setFixedHeight(36)
        remove_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_all_button.clicked.connect(self.remove_all)

        self.button_box = QDialogButtonBox(self)
        apply_button = self.button_box.addButton(
            translate("Apply"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel_button = self.button_box.addButton(
            translate("Cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addWidget(remove_all_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def _create_category(self, key, name):
        """
        Create a category tab within the unavailable items dialog.

        :param key: Category key.
        :param name: Display name.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        list_widget = StyledListWidget()
        list_widget.setProperty("class", "listWidget")
        layout.addWidget(list_widget)

        self.stacked_widget.addWidget(page)
        self.tabs[key] = list_widget

        nav_item = QListWidgetItem()
        nav_item.setSizeHint(QSize(nav_item.sizeHint().width(), 40))
        widget = NavCategoryItem(name, 0)
        self.nav_list.addItem(nav_item)
        self.nav_list.setItemWidget(nav_item, widget)
        self.nav_items_widgets[key] = widget

    def _update_nav_counter(self, key):
        """
        Update the item counter displayed on the category navigation list.

        :param key: Category key.
        """
        if key in self.modified_unavailable_data and key in self.nav_items_widgets:
            count = len(self.modified_unavailable_data[key])
            self.nav_items_widgets[key].set_count(count)

    def _populate_lists(self):
        """
        Populate all lists with the currently modified unavailable data.
        """
        for tab_key, list_widget in self.tabs.items():
            list_widget.clear()
            items_dict = self.modified_unavailable_data.get(tab_key, {})

            self._update_nav_counter(tab_key)

            for item_key_str in items_dict.keys():
                display_text = ""
                if tab_key == "albums":
                    try:
                        item_data_list = json.loads(item_key_str)
                        display_text = f"{item_data_list[0]} - {item_data_list[1]}"
                    except json.JSONDecodeError:
                        display_text = item_key_str
                else:
                    display_text = item_key_str

                self._add_item_to_list(list_widget, item_key_str, display_text)

    def _add_item_to_list(self, list_widget, item_key_str, display_text):
        """
        Helper method to insert a custom UnavailableItemWidget into a QListWidget.
        """
        list_item = QListWidgetItem(list_widget)
        item_widget = UnavailableItemWidget(item_key_str, display_text, list_item, self)
        item_widget.remove_requested.connect(self._on_remove_item)
        size_hint = item_widget.sizeHint()
        list_item.setSizeHint(QSize(0, size_hint.height()))

        list_widget.addItem(list_item)
        list_widget.setItemWidget(list_item, item_widget)

    def _on_remove_item(self, list_item):
        """
        Remove an item from the unavailable favorites tracking list.

        :param list_item: The QListWidgetItem to remove.
        """
        list_widget = list_item.listWidget()
        item_widget = list_widget.itemWidget(list_item)
        item_key_str = item_widget.item_key_str

        target_key = None
        for tab_key, lw in self.tabs.items():
            if lw is list_widget:
                target_key = tab_key
                if item_key_str in self.modified_unavailable_data[tab_key]:
                    del self.modified_unavailable_data[tab_key][item_key_str]
                    break

        list_widget.takeItem(list_widget.row(list_item))

        if target_key:
            self._update_nav_counter(target_key)

    def remove_all(self):
        """
        Confirm and perform clearing of all unavailable favorites categories.
        """
        confirmed = CustomConfirmDialog.confirm(
            self,
            title=translate("Remove All"),
            label=translate(
                "Are you sure you want to remove all items from this list?"
            ),
            ok_text=translate("Remove All"),
            cancel_text=translate("Cancel"),
        )
        if confirmed:
            for tab_key in self.modified_unavailable_data:
                self.modified_unavailable_data[tab_key].clear()
            self._populate_lists()

    def get_unavailable_data(self):
        """
        Retrieve the modified dictionary of unavailable favorites.

        :return: A dictionary representing the updated unavailable items state.
        """
        return self.modified_unavailable_data


class ZoomableGraphicsView(QGraphicsView):
    """
    A custom QGraphicsView that provides mouse wheel zooming and click-and-drag panning.
    """
    clicked = pyqtSignal()

    def __init__(self, scene, parent=None):
        """
        Initialize the zoomable graphics view.

        :param scene: The QGraphicsScene to display.
        :param parent: Parent widget.
        """
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        self._zoom_factor = 1.15
        self._current_scale = 1.0
        self._is_1_to_1 = False
        self._has_manual_zoom = False
        self._is_panning = False
        self._mouse_press_pos = None

        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    def wheelEvent(self, event):
        """
        Handle mouse wheel events to zoom in or out.
        """
        zoom_in = event.angleDelta().y() > 0
        zoom_factor = self._zoom_factor if zoom_in else 1.0 / self._zoom_factor
        self.scale(zoom_factor, zoom_factor)
        self._current_scale = self.transform().m11()
        self._is_1_to_1 = False
        self._has_manual_zoom = True
        event.accept()
        self.viewport().update()

    def mousePressEvent(self, event):
        """
        Handle mouse press events to initiate panning.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_press_pos = event.pos()
            self._is_panning = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Handle mouse release events to stop panning and detect click operations.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            if self._mouse_press_pos:
                dist = (event.pos() - self._mouse_press_pos).manhattanLength()
                if dist < 3:
                    self.clicked.emit()
            self._is_panning = False
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        """
        Handle resize events to re-fit or re-center the scene.
        """
        super().resizeEvent(event)
        if not self.scene() or not self.scene().itemsBoundingRect().isValid():
            return
        if self._is_1_to_1:
            self.centerOn(self.scene().itemsBoundingRect().center())
        elif not self._has_manual_zoom:
            self.fitInView(
                self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio
            )
            self._current_scale = self.transform().m11()


class CoverViewerWidget(QWidget):
    """
    A standard widget for viewing cover images.
    Supports zooming, panning, and navigating through an image list.
    Designed to be embedded into standard layouts or used as an overlay.
    """

    closed = pyqtSignal()

    def __init__(self, pixmap, parent = None, image_list = None, current_index = 0):
        """
        Initialize the cover viewer widget.

        :param pixmap: A default QPixmap to show if no image list is provided.
        :param parent: Parent widget.
        :param image_list: Optional list of images (dicts with 'path' and 'caption', or strings).
        :param current_index: The index of the initial image to display.
        """
        super().__init__(parent)

        if parent:
            self.setGeometry(parent.contentsRect())
            parent.installEventFilter(self)

        self.caption_user_visible = True
        self.image_list = image_list if image_list else []
        self.current_index = current_index

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.background = QFrame(self)
        self.background.setProperty("class", "ImageViewer")

        self.main_layout.addWidget(self.background)

        self.stack_layout = QGridLayout(self.background)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        self.stack_layout.setSpacing(0)

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene, self.background)
        self.view.clicked.connect(self._handle_close)

        self.pixmap_item = QGraphicsPixmapItem()
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene.addItem(self.pixmap_item)

        self.stack_layout.addWidget(self.view, 0, 0)

        self.controls_container = QWidget(self.background)
        self.controls_container.setContentsMargins(0, 0, 0, 16)

        container_layout = QVBoxLayout(self.controls_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)

        self.caption_container = QWidget()
        caption_layout = QHBoxLayout(self.caption_container)
        caption_layout.setContentsMargins(0, 0, 0, 0)
        caption_layout.addStretch()

        self.lbl_caption = QLabel("")
        self.lbl_caption.setProperty("class", "ImageViewerCaption")
        self.lbl_caption.setContentsMargins(16, 8, 16, 8)
        self.lbl_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_caption.setWordWrap(True)
        self.lbl_caption.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        caption_layout.addWidget(self.lbl_caption)
        caption_layout.addStretch()

        container_layout.addWidget(self.caption_container)
        self.caption_container.hide()

        controls_widget = QWidget()
        controls_widget.setContentsMargins(0, 0, 0, 0)
        controls_widget.setProperty("class", "ImageViewerControl")
        controls_widget.setFixedHeight(52)

        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        controls_layout.setSpacing(8)

        if len(self.image_list) > 1:
            self.btn_prev = QPushButton()
            self.btn_prev.setIcon(
                create_svg_icon("assets/control/arrow_left.svg", theme.COLORS["WHITE"], QSize(24, 24)))
            self.btn_prev.setIconSize(QSize(24, 24))
            self.btn_prev.setFixedSize(36, 36)
            self.btn_prev.setProperty("class", "btnImageViewer")
            self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_button_opacity_effect(self.btn_prev)
            self.btn_prev.clicked.connect(self._show_previous)
            controls_layout.addWidget(self.btn_prev)

            self.lbl_counter = QLabel(f"{self.current_index + 1}/{len(self.image_list)}")
            self.lbl_counter.setProperty("class", "textImageViewer")
            controls_layout.addWidget(self.lbl_counter)

            self.btn_next = QPushButton()
            self.btn_next.setIcon(
                create_svg_icon("assets/control/arrow_right.svg", theme.COLORS["WHITE"], QSize(24, 24)))
            self.btn_next.setIconSize(QSize(24, 24))
            self.btn_next.setFixedSize(36, 36)
            self.btn_next.setProperty("class", "btnImageViewer")
            self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_button_opacity_effect(self.btn_next)
            self.btn_next.clicked.connect(self._show_next)
            controls_layout.addWidget(self.btn_next)

            sep1 = QFrame()
            sep1.setFrameShape(QFrame.Shape.VLine)
            sep1.setStyleSheet("background-color: rgba(255, 255, 255, 50);")
            sep1.setFixedWidth(1)
            controls_layout.addWidget(sep1)

        btn_1to1 = QPushButton()
        btn_1to1.setIcon(create_svg_icon("assets/control/scale_original.svg", theme.COLORS["WHITE"], QSize(24, 24)))
        btn_1to1.setIconSize(QSize(24, 24))
        btn_1to1.setFixedSize(36, 36)
        btn_1to1.setProperty("class", "btnImageViewer")
        set_custom_tooltip(
            btn_1to1,
            title = translate("1:1")
        )
        btn_1to1.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(btn_1to1)
        btn_1to1.clicked.connect(self._reset_zoom_1_to_1)
        controls_layout.addWidget(btn_1to1)

        btn_fit = QPushButton()
        btn_fit.setIcon(create_svg_icon("assets/control/scale_window.svg", theme.COLORS["WHITE"], QSize(24, 24)))
        btn_fit.setIconSize(QSize(24, 24))
        btn_fit.setFixedSize(36, 36)
        btn_fit.setProperty("class", "btnImageViewer")
        set_custom_tooltip(
            btn_fit,
            title = translate("Fit")
        )
        btn_fit.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(btn_fit)
        btn_fit.clicked.connect(self._reset_zoom_fit)
        controls_layout.addWidget(btn_fit)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("background-color: rgba(255, 255, 255, 50);")
        sep2.setFixedWidth(1)
        controls_layout.addWidget(sep2)

        self.btn_toggle_caption = QPushButton()
        self.btn_toggle_caption.setIcon(
            create_svg_icon("assets/control/info.svg", theme.COLORS["WHITE"], QSize(24, 24)))
        self.btn_toggle_caption.setIconSize(QSize(24, 24))
        self.btn_toggle_caption.setFixedSize(36, 36)
        self.btn_toggle_caption.setProperty("class", "btnImageViewer")
        self.btn_toggle_caption.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self.btn_toggle_caption,
            title = translate("Show Caption")
        )
        apply_button_opacity_effect(self.btn_toggle_caption)
        self.btn_toggle_caption.clicked.connect(self._toggle_caption_visibility)
        controls_layout.addWidget(self.btn_toggle_caption)

        self.sep3 = QFrame()
        self.sep3.setFrameShape(QFrame.Shape.VLine)
        self.sep3.setStyleSheet("background-color: rgba(255, 255, 255, 50);")
        self.sep3.setFixedWidth(1)
        controls_layout.addWidget(self.sep3)

        btn_close = QPushButton()
        btn_close.setIcon(create_svg_icon("assets/control/clear.svg", theme.COLORS["WHITE"], QSize(24, 24)))
        btn_close.setIconSize(QSize(24, 24))
        btn_close.setFixedSize(36, 36)
        btn_close.setProperty("class", "btnImageViewer")
        set_custom_tooltip(
            btn_close,
            title = translate("Close")
        )
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(btn_close)
        btn_close.clicked.connect(self._handle_close)
        controls_layout.addWidget(btn_close)

        container_layout.addWidget(controls_widget, 0, Qt.AlignmentFlag.AlignHCenter)

        self.stack_layout.addWidget(self.controls_container, 0, 0,
                                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)

        if self.image_list:
            self._load_image(self.current_index)
        elif not pixmap.isNull():
            self._set_scene_pixmap(pixmap)

        self._update_caption_ui()

    def eventFilter(self, obj, event):
        """
        Intercepts parent window resize events and adjusts the overlay size.
        """
        if obj == self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.contentsRect())
        return super().eventFilter(obj, event)

    def _handle_close(self):
        """
        Hides the widget and emits the closed signal so the parent container can act.
        """
        if self.parent():
            self.parent().removeEventFilter(self)

        self.hide()
        self.closed.emit()

    def _toggle_caption_visibility(self):
        """Toggles the visibility state of the image caption."""
        self.caption_user_visible = not self.caption_user_visible
        self._update_caption_ui()

    def _update_caption_ui(self):
        """Updates the UI elements related to the image caption based on visibility state and text content."""
        caption_text = self.lbl_caption.text().strip()

        if caption_text and self.caption_user_visible:
            self.caption_container.show()
        else:
            self.caption_container.hide()

        if not caption_text:
            self.btn_toggle_caption.hide()
            if hasattr(self, 'sep3'):
                self.sep3.hide()
        else:
            self.btn_toggle_caption.show()
            if hasattr(self, 'sep3'):
                self.sep3.show()

            if self.caption_user_visible:
                set_custom_tooltip(
                    self.btn_toggle_caption,
                    title = translate("Hide Caption"),
                )
                self.btn_toggle_caption.setIcon(
                    create_svg_icon("assets/control/info_disabled.svg", theme.COLORS["WHITE"], QSize(24, 24)))
            else:
                set_custom_tooltip(
                    self.btn_toggle_caption,
                    title = translate("Show Caption"),
                )
                self.btn_toggle_caption.setIcon(
                    create_svg_icon("assets/control/info.svg", theme.COLORS["WHITE"], QSize(24, 24)))

    def _load_image(self, index):
        """Loads and displays the image at the specified index from the image list."""
        if not self.image_list:
            return

        self.current_index = index % len(self.image_list)
        item_data = self.image_list[self.current_index]

        path = ""
        caption = ""

        if isinstance(item_data, dict):
            path = item_data.get("path", "")
            caption = item_data.get("caption", "")
        else:
            path = str(item_data)
            caption = ""

        import os
        if os.path.exists(path):
            pix = QPixmap(path)
            self._set_scene_pixmap(pix)
            self.lbl_caption.setText(caption)
            self._update_caption_ui()

            if hasattr(self, "lbl_counter"):
                self.lbl_counter.setText(f"{self.current_index + 1}/{len(self.image_list)}")

    def _set_scene_pixmap(self, pixmap):
        """Sets the given pixmap to the graphics scene and resets the zoom."""
        if not pixmap.isNull():
            self.pixmap_item.setPixmap(pixmap)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())
            self._reset_zoom_fit()

    def _show_next(self):
        """Advances the viewer to the next image in the list."""
        self._load_image(self.current_index + 1)

    def _show_previous(self):
        """Returns the viewer to the previous image in the list."""
        self._load_image(self.current_index - 1)

    def showEvent(self, event):
        """Handles the show event to ensure the image fits the view upon display."""
        super().showEvent(event)
        QTimer.singleShot(0, self._reset_zoom_fit)

    def _reset_zoom_fit(self):
        """Resets the view transform to fit the entire image within the viewport."""
        if not self.scene.itemsBoundingRect().isValid():
            return
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.view._current_scale = self.view.transform().m11()
        self.view._is_1_to_1 = False
        self.view._has_manual_zoom = False

    def _reset_zoom_1_to_1(self):
        """Resets the zoom level to a 1:1 original scale ratio and centers the image."""
        self.view.resetTransform()
        self.view._current_scale = 1.0
        self.view._is_1_to_1 = True
        self.view._has_manual_zoom = False
        if self.scene.itemsBoundingRect().isValid():
            self.view.centerOn(self.scene.itemsBoundingRect().center())

    def keyPressEvent(self, event):
        """Handles keyboard navigation for closing the viewer or switching images."""
        if event.key() == Qt.Key.Key_Escape:
            self._handle_close()
        elif event.key() == Qt.Key.Key_Left and self.image_list:
            self._show_previous()
        elif event.key() == Qt.Key.Key_Right and self.image_list:
            self._show_next()
        else:
            super().keyPressEvent(event)


class LanguageSelectionDialog(StyledDialog):
    """
    Dialog to select the application's interface language from a predefined list.
    """
    def __init__(self, parent=None, title=""):
        """
        Initialize the language selection dialog.

        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle("Sprache, Language, Idioma, Langue, Lingua, 言語, 언어, Язык, 语言")
        self.setWindowIcon(QIcon(resource_path("assets/logo/app_icon.png")))
        self.setModal(True)
        self.resize(360, 480)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 24, 0, 0)
        content_layout.setSpacing(24)

        desc = QLabel("Hallo! Hi! ¡Hola! Salut! Привет! Olá! 你好! こんにちは! 안녕하세요!")
        desc.setProperty("class", "textSecondary textColorPrimary")
        desc.setContentsMargins(24, 0, 24, 0)
        content_layout.addWidget(desc)

        self.list_widget = StyledListWidget()
        self.list_widget.setIconSize(QSize(32, 24))
        self.list_widget.setProperty("class", "listWidgetNav")

        for name, (code, icon_path) in SUPPORTED_LANGUAGES.items():
            item = QListWidgetItem(QIcon(resource_path(icon_path)), name)
            item.setData(Qt.ItemDataRole.UserRole, code)
            self.list_widget.addItem(item)

        default_lang_code = "en"
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == default_lang_code:
                self.list_widget.setCurrentItem(item)
                break
        else:
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)

        content_layout.addWidget(self.list_widget)
        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        ok_button = QPushButton("OK")
        ok_button.setProperty("class", "btnText")
        ok_button.setFixedHeight(36)
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_button.clicked.connect(self.accept)

        bottom_layout.addStretch()
        bottom_layout.addWidget(ok_button)
        main_layout.addWidget(bottom_panel)

        self.list_widget.itemDoubleClicked.connect(self.accept)

    def selected_language_code(self):
        """
        Get the language code associated with the selected list item.

        :return: String representing the selected language code, or None.
        """
        current_item = self.list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None


class AddFoldersConfirmDialog(StyledDialog):
    """
    Dialog for confirming the addition of new music folders to the library.
    Provides options to add common parent folders or specific raw folders.
    """
    def __init__(self, raw_folders, optimized_folders, parent=None, title=""):
        """
        Initialize the dialog.

        :param raw_folders: List of specific sub-folders discovered.
        :param optimized_folders: List of optimized parent folders that cover the raw paths.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.raw_folders = sorted(list(set(raw_folders)))
        self.optimized_folders = sorted(list(set(optimized_folders)))
        self.has_options = self.raw_folders != self.optimized_folders

        self.setWindowTitle(translate("Add to Library"))
        self.resize(640, 480)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        title = QLabel(translate("Add to Library"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")
        desc = QLabel(translate("New music folders found."))
        desc.setProperty("class", "textSecondary textColorPrimary")

        content_layout.addWidget(title)
        content_layout.addWidget(desc)

        if self.has_options:
            self.radio_group = QButtonGroup(self)
            self.radio_smart = QRadioButton(
                translate(
                    "Add common parent folders (Recommended)\n{count} folder(s) will be added",
                    count=len(self.optimized_folders),
                )
            )
            self.radio_smart.setProperty("class", "textColorPrimary")
            self.radio_smart.setChecked(True)
            content_layout.addWidget(self.radio_smart)
            self.radio_group.addButton(self.radio_smart)

            self.radio_exact = QRadioButton(
                translate(
                    "Add specific folders only\n{count} folder(s) will be added",
                    count=len(self.raw_folders),
                )
            )
            self.radio_exact.setProperty("class", "textColorPrimary")
            content_layout.addWidget(self.radio_exact)
            self.radio_group.addButton(self.radio_exact)
            self.radio_group.buttonToggled.connect(self._update_list)
        else:
            desc_lbl = QLabel(
                translate("The following folders will be added to your library:")
            )
            desc_lbl.setProperty("class", "textColorPrimary")
            content_layout.addWidget(desc_lbl)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidget")
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        content_layout.addWidget(self.list_widget)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)
        add_button = QPushButton(translate("Add and Scan"))
        cancel_button = QPushButton(translate("Cancel"))
        self.button_box.addButton(add_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

        self._update_list()

    def _update_list(self):
        """
        Update the displayed list of folders depending on the selected radio button mode.
        """
        self.list_widget.clear()
        if self.has_options and self.radio_exact.isChecked():
            items = self.raw_folders
        else:
            items = self.optimized_folders

        for folder in items:
            item = QListWidgetItem(folder)
            icon = QIcon(
                create_svg_icon(
                    "assets/control/folder_add.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(16, 16),
                )
            )
            item.setIcon(icon)
            self.list_widget.addItem(item)

    def get_selected_folders(self):
        """
        Get the final list of folders chosen to be added.

        :return: A list of folder path strings.
        """
        if self.has_options and self.radio_exact.isChecked():
            return self.raw_folders
        return self.optimized_folders


class ResetStatsOptionsDialog(StyledDialog):
    """Dialog for selecting the rating period to reset."""

    MODE_MONTHLY = 0
    MODE_ALL_TIME = 1

    def __init__(self, item_name, item_type_str, parent=None, title=""):
        """
        Initialize the reset stats options dialog.

        :param item_name: Name of the item being reset.
        :param item_type_str: The type string (e.g. 'Album').
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Reset Rating"))
        self.setMinimumWidth(450)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        title = QLabel(translate("Reset Rating"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")

        desc = QLabel(
            translate(
                "Choose which rating period to reset for {item_type} {item_name}:",
                item_type=item_type_str.lower(),
                item_name=item_name,
            )
        )
        desc.setProperty("class", "textSecondary textColorPrimary")
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setWordWrap(True)

        content_layout.addWidget(title)
        content_layout.addWidget(desc)

        self.rb_month = QRadioButton(translate("Current Month only"))
        self.rb_month.setProperty("class", "textColorPrimary")
        set_custom_tooltip(
            self.rb_month,
            title = translate("Reset month stats"),
            text = translate("Monthly value will be subtracted from All Time total"),
        )
        self.rb_all_time = QRadioButton(translate("All Time"))
        self.rb_all_time.setProperty("class", "textColorPrimary")
        self.rb_all_time.setChecked(True)

        self.group = QButtonGroup(self)
        self.group.addButton(self.rb_month, self.MODE_MONTHLY)
        self.group.addButton(self.rb_all_time, self.MODE_ALL_TIME)

        content_layout.addWidget(self.rb_month)
        content_layout.addWidget(self.rb_all_time)
        content_layout.addStretch()

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)
        self.button_box.addButton(
            QPushButton(translate("Confirm")), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.button_box.addButton(
            QPushButton(translate("Cancel")), QDialogButtonBox.ButtonRole.RejectRole
        )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def get_selected_mode(self):
        """
        Get the selected reset mode option.

        :return: Integer representing the mode (MODE_MONTHLY or MODE_ALL_TIME).
        """
        return self.group.checkedId()


class LicenseDialog(StyledDialog):
    """
    Dialog displaying the software license agreement loaded from a local file.
    """
    def __init__(self, parent = None, title=""):
        """
        Initialize the license viewer dialog.

        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("License Agreement"))
        self.setFixedSize(600, 500)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        self.text_edit = StyledTextEdit()
        self.text_edit.setReadOnly(True)

        license_path = resource_path("LICENSE")
        try:
            with open(license_path, "r", encoding = "utf-8") as f:
                self.text_edit.setPlainText(f.read())
        except Exception as e:
            self.text_edit.setPlainText(f"Error loading license: {e}")

        content_layout.addWidget(self.text_edit)
        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)
        self.button_box.addButton(
            QPushButton(translate("Close")), QDialogButtonBox.ButtonRole.AcceptRole
        )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)