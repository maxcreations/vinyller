"""
Vinyller — Encyclopedia dialogs and messages
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
import re

import requests
from PyQt6.QtCore import (
    pyqtSignal, QSize, Qt,
    QTimer, QUrl
)
from PyQt6.QtGui import (
    QDesktopServices, QPixmap
)
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup,
    QDialogButtonBox,
    QFrame, QGridLayout,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QVBoxLayout, QWidget, QSizePolicy
)

from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledListWidget, StyledScrollArea,
    TranslucentCombo, set_custom_tooltip
)
from src.ui.custom_classes import (
    FlowLayout, RoundedCoverLabel
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class EncyclopediaCleanupDialog(StyledDialog):
    """
    Dialog prompting the user to confirm the deletion of unused image files from the encyclopedia.
    """
    def __init__(self, file_paths, base_dir, parent=None, title=""):
        """
        Initialize the cleanup dialog.

        :param file_paths: List of unused image filenames.
        :param base_dir: Base directory path containing these files.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.file_paths = file_paths
        self.base_dir = base_dir
        self.setWindowTitle(translate("Encyclopedia Cleanup"))
        self.resize(640, 480)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        title = QLabel(translate("Encyclopedia Cleanup"))
        title.setProperty("class", "textHeaderPrimary textColorPrimary")
        content_layout.addWidget(title)

        count = len(file_paths)
        desc_text = translate("Found {count} unused images:", count=count)
        desc = QLabel(desc_text)
        desc.setProperty("class", "textSecondary textColorPrimary")
        content_layout.addWidget(desc)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidget")
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        for file_name in file_paths:
            item = QListWidgetItem(file_name)
            item.setSizeHint(QSize(0, 32))
            self.list_widget.addItem(item)

        content_layout.addWidget(self.list_widget)

        warning_label = QLabel(
            translate("Confirm deletion? This action cannot be undone!")
        )
        warning_label.setProperty(
            "class", "textSecondary textColorAccent"
        )
        warning_label.setWordWrap(True)
        warning_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_layout.addWidget(warning_label)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        open_folder_btn = QPushButton(translate("Open Folder"))
        open_folder_btn.setProperty("class", "btnText")
        open_folder_btn.setFixedHeight(36)
        open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder_btn.clicked.connect(self._open_folder)

        self.button_box = QDialogButtonBox(self)
        apply_button = self.button_box.addButton(
            translate("Confirm"), QDialogButtonBox.ButtonRole.AcceptRole
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

        bottom_layout.addWidget(open_folder_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def _open_folder(self):
        """
        Open the target folder containing the unused files in the system file explorer.
        """
        if os.path.exists(self.base_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.base_dir))


class ExportSuccessDialog(StyledDialog):
    """
    Dialog to display a success message after exporting the encyclopedia, allowing the user to open the output folder.
    """
    def __init__(self, folder_path, parent=None, title=""):
        """
        Initialize the success dialog.

        :param folder_path: The path where the export was saved.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.folder_path = folder_path
        self.setWindowTitle(translate("Export Successful"))
        self.setMinimumWidth(400)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        icon_label = QLabel()
        icon_pixmap = create_svg_icon(
            "assets/control/encyclopedia.svg", theme.COLORS["PRIMARY"], QSize(32, 32)
        ).pixmap(32, 32)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        title = QLabel(translate("Encyclopedia exported successfully"))
        title.setProperty("class", "textHeaderSecondary textColorPrimary")

        desc = QLabel(translate("The archive has been saved to the selected folder."))
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setProperty("class", "textSecondary textColorPrimary")

        text_layout.addWidget(title)
        text_layout.addWidget(desc)

        content_layout.addWidget(icon_label)
        content_layout.addLayout(text_layout)
        layout.addLayout(content_layout)
        layout.addStretch()
        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        open_btn = QPushButton(translate("Open Folder"))
        ok_btn = QPushButton(translate("OK"))

        for btn in [open_btn, ok_btn]:
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        open_btn.clicked.connect(self._open_folder)
        ok_btn.clicked.connect(self.accept)

        bottom_layout.addWidget(open_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(ok_btn)
        main_layout.addWidget(bottom_panel)

    def _open_folder(self):
        """
        Open the exported file's directory in the system file explorer.
        """
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_path))
        self.accept()


class EncyclopediaRestoreDialog(StyledDialog):
    """Dialog for selecting an automatic backup or importing a file."""

    importFileRequested = pyqtSignal()

    def __init__(self, backups, parent=None, title=""):
        """
        Initialize the restore dialog.

        :param backups: List of dictionaries representing available backups.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Restore Encyclopedia"))
        self.setMinimumWidth(500)
        self.setProperty("class", "backgroundPrimary")
        self.selected_index = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        title = QLabel(translate("Restore from Backup"))
        title.setProperty("class", "textHeaderSecondary textColorPrimary")
        layout.addWidget(title)

        desc = QLabel(
            translate(
                "Choose an automatic backup to restore text data or import a ZIP archive:"
            )
        )
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setProperty("class", "textSecondary textColorPrimary")
        layout.addWidget(desc)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidgetNav")

        if not backups:
            item = QListWidgetItem(translate("No automatic backups found."))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
        else:
            for b in backups:
                if b["count"] == -1:
                    articles_text = f" — {translate('File damaged')}"
                    icon_color = theme.COLORS["ACCENT"]
                else:
                    count = b["count"]
                    articles_text = translate("{count} article(s)", count=count)
                    icon_color = theme.COLORS["PRIMARY"]

                text = (
                    f"{translate('Backup')} {b['index']} ({b['date']}) {articles_text}"
                )

                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, b["index"])
                item.setIcon(
                    create_svg_icon(
                        "assets/control/encyclopedia.svg", icon_color, QSize(18, 18)
                    )
                )

                if b["count"] == -1:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                    set_custom_tooltip(
                        item,
                        title = translate("File Corrupted"),
                        text = translate("This backup file is corrupted and cannot be restored."),
                    )

                self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        self.btn_file = QPushButton(translate("Choose ZIP file..."))
        self.btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_file.setProperty("class", "btnText")
        self.btn_file.setFixedHeight(36)
        self.btn_file.setIcon(
            create_svg_icon(
                "assets/control/folder.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        self.btn_file.clicked.connect(self._on_file_requested)
        layout.addWidget(self.btn_file)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        self.btn_restore = self.button_box.addButton(
            translate("Restore"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.btn_restore.setEnabled(False)

        self.btn_cancel = self.button_box.addButton(
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

        self.list_widget.itemSelectionChanged.connect(
            lambda: self.btn_restore.setEnabled(
                len(self.list_widget.selectedItems()) > 0
            )
        )

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def _on_file_requested(self):
        """
        Emit a signal that the user has chosen to import from an external ZIP file, and close the dialog.
        """
        self.importFileRequested.emit()
        self.reject()

    def get_selected_backup_index(self):
        """
        Get the internal index of the selected backup file.

        :return: Integer index of the backup, or None if nothing is selected.
        """
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


class ImportOptionsDialog(StyledDialog):
    """
    Dialog asking the user how to handle duplicate data when importing an encyclopedia archive.
    """
    def __init__(self, has_existing_data, parent = None, title=""):
        """
        Initialize the import options dialog.

        :param has_existing_data: Boolean indicating if there is already data in the local encyclopedia.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Import Encyclopedia"))
        self.setMinimumWidth(450)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        title = QLabel(translate("Import Strategy"))
        title.setProperty("class", "textHeaderSecondary textColorPrimary")
        layout.addWidget(title)

        self.strategy_group = QButtonGroup(self)
        self.duplicate_group = QButtonGroup(self)

        if has_existing_data:
            desc = QLabel(
                translate(
                    "Your encyclopedia is not empty. How would you like to proceed?"
                )
            )
            desc.setWordWrap(True)
            desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            desc.setProperty("class", "textSecondary textColorPrimary")
            layout.addWidget(desc)

            self.rb_replace = QRadioButton(
                translate("Replace entire encyclopedia (Delete current)")
            )
            self.rb_replace.setProperty("class", "textColorPrimary")

            self.rb_merge = QRadioButton(translate("Merge with current encyclopedia"))
            self.rb_merge.setProperty("class", "textColorPrimary")
            self.rb_merge.setChecked(True)

            self.strategy_group.addButton(self.rb_replace, 1)
            self.strategy_group.addButton(self.rb_merge, 2)

            layout.addWidget(self.rb_replace)
            layout.addWidget(self.rb_merge)

            self.duplicates_widget = QWidget()
            dup_layout = QVBoxLayout(self.duplicates_widget)
            dup_layout.setContentsMargins(24, 8, 0, 0)

            dup_lbl = QLabel(translate("If duplicates found:"))
            dup_lbl.setProperty("class", "textSecondary textColorPrimary")
            dup_layout.addWidget(dup_lbl)

            self.rb_dup_skip = QRadioButton(translate("Skip (Keep existing)"))
            self.rb_dup_skip.setProperty("class", "textColorPrimary")

            self.rb_dup_overwrite = QRadioButton(translate("Overwrite with imported"))
            self.rb_dup_overwrite.setProperty("class", "textColorPrimary")

            self.rb_dup_merge = QRadioButton(
                translate("Merge (Add new info to existing)")
            )
            self.rb_dup_merge.setProperty("class", "textColorPrimary")

            self.rb_dup_ask = QRadioButton(translate("Ask and Compare"))
            self.rb_dup_ask.setProperty("class", "textColorPrimary")
            self.rb_dup_ask.setChecked(True)

            self.duplicate_group.addButton(self.rb_dup_skip, 1)
            self.duplicate_group.addButton(self.rb_dup_overwrite, 2)
            self.duplicate_group.addButton(self.rb_dup_merge, 4)
            self.duplicate_group.addButton(self.rb_dup_ask, 3)

            dup_layout.addWidget(self.rb_dup_skip)
            dup_layout.addWidget(self.rb_dup_overwrite)
            dup_layout.addWidget(self.rb_dup_merge)
            dup_layout.addWidget(self.rb_dup_ask)

            layout.addWidget(self.duplicates_widget)

            self.rb_replace.toggled.connect(
                lambda c: self.duplicates_widget.setDisabled(c)
            )

        else:
            info = QLabel(
                translate("Your encyclopedia is empty. Data will be imported.")
            )
            info.setProperty("class", "textSecondary textColorPrimary")
            layout.addWidget(info)
            self.rb_merge = QRadioButton()
            self.rb_merge.setChecked(True)
            self.rb_dup_overwrite = QRadioButton()
            self.rb_dup_overwrite.setChecked(True)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        import_btn = self.button_box.addButton(
            translate("Import"), QDialogButtonBox.ButtonRole.AcceptRole
        )

        cancel_btn = self.button_box.addButton(
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

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

    def get_result(self):
        """
        Evaluate the UI selections to determine the chosen import strategy.

        :return: A tuple of booleans (replace_all, overwrite_duplicates, merge_duplicates, interactive_mode)
        """
        replace_all = False
        overwrite_duplicates = False
        merge_duplicates = False
        interactive_mode = False

        if hasattr(self, "rb_replace") and self.rb_replace.isChecked():
            replace_all = True

        if hasattr(self, "rb_dup_overwrite") and self.rb_dup_overwrite.isChecked():
            overwrite_duplicates = True

        if hasattr(self, "rb_dup_merge") and self.rb_dup_merge.isChecked():
            merge_duplicates = True

        if hasattr(self, "rb_dup_ask") and self.rb_dup_ask.isChecked():
            interactive_mode = True

        return replace_all, overwrite_duplicates, merge_duplicates, interactive_mode


class EncyclopediaConflictDialog(StyledDialog):
    """
    Dialog to handle individual item conflicts during encyclopedia imports.
    Displays side-by-side previews of the current vs. new article.
    """
    ResultCancel = 0
    ResultKeepCurrent = 1
    ResultOverwrite = 2
    ResultKeepAll = 3
    ResultOverwriteAll = 4
    ResultMerge = 5

    def __init__(
            self, item_key, item_type, current_data, new_data, base_image_path, parent = None, title = "",
            is_import = False
    ):
        """
        Initialize the conflict resolution dialog.

        :param item_key: Identifier/Name of the conflicting item.
        :param item_type: The type category (e.g., 'artist').
        :param current_data: Dictionary containing the existing encyclopedia entry.
        :param new_data: Dictionary containing the incoming encyclopedia entry.
        :param base_image_path: Directory path for loading preview images.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Conflict Resolution"))
        self.setMinimumSize(1024, 640)
        self.setProperty("class", "backgroundPrimary")
        self.base_image_path = base_image_path

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_widget.setProperty("class", "backgroundPrimary")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        header = QLabel(translate("Conflict found for: {item}", item=str(item_key)))
        header.setProperty("class", "textHeaderPrimary textColorPrimary")
        content_layout.addWidget(header)

        self.warn_lbl = QLabel(
            translate(
                "Note: When merging, Relations and Discography lists may require manual cleanup."
            )
        )
        self.warn_lbl.setProperty("class", "textSecondary textColorAccent")
        self.warn_lbl.setWordWrap(True)
        self.warn_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_layout.addWidget(self.warn_lbl)

        comparison_layout = QHBoxLayout()
        comparison_layout.setSpacing(24)

        left_col = self._create_entry_preview(
            translate("Current Version"), current_data
        )
        comparison_layout.addWidget(left_col)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setProperty("class", "headerDivider")
        comparison_layout.addWidget(line)

        right_col = self._create_entry_preview(translate("New Version"), new_data)
        comparison_layout.addWidget(right_col)

        content_layout.addLayout(comparison_layout, 1)
        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.btn_cancel = QPushButton(translate("Cancel"))
        self.btn_keep = QPushButton(translate("Keep Current"))
        self.btn_merge = QPushButton(translate("Merge"))
        self.btn_overwrite = QPushButton(translate("Overwrite"))
        self.btn_keep_all = QPushButton(translate("Keep All"))
        self.btn_overwrite_all = QPushButton(translate("Overwrite All"))

        conflict_btns = [
            self.btn_cancel,
            self.btn_keep,
            self.btn_merge,
            self.btn_overwrite,
            self.btn_keep_all,
            self.btn_overwrite_all,
        ]
        for btn in conflict_btns:
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_keep.clicked.connect(lambda: self.done(self.ResultKeepCurrent))
        self.btn_merge.clicked.connect(lambda: self.done(self.ResultMerge))
        self.btn_overwrite.clicked.connect(lambda: self.done(self.ResultOverwrite))
        self.btn_keep_all.clicked.connect(lambda: self.done(self.ResultKeepAll))
        self.btn_overwrite_all.clicked.connect(
            lambda: self.done(self.ResultOverwriteAll)
        )

        if not is_import:
            self.btn_keep_all.hide()
            self.btn_overwrite_all.hide()

        bottom_layout.addWidget(self.btn_keep_all)
        bottom_layout.addWidget(self.btn_keep)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_merge)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_overwrite)
        bottom_layout.addWidget(self.btn_overwrite_all)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_cancel)

        main_layout.addWidget(bottom_panel)

    def _create_entry_preview(self, title_text, data):
        """
        Creates an article preview widget styled after EncyclopediaFullViewer.

        :param title_text: Title identifying the source (e.g., 'Current Version').
        :param data: The encyclopedia entry dictionary.
        :return: A QWidget containing the preview UI.
        """
        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        lbl_title = QLabel(title_text)
        lbl_title.setProperty("class", "textHeaderSecondary textColorAccent")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        scroll = StyledScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setProperty("class", "backgroundPrimary")

        content = QWidget()
        content.setProperty("class", "backgroundPrimary")
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(16)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        img_path = data.get("image_path")
        if img_path:
            full_path = os.path.join(self.base_image_path, img_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    lbl_img = QLabel()
                    lbl_img.setPixmap(
                        pixmap.scaled(
                            128,
                            128,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    c_layout.addWidget(lbl_img)
            else:
                c_layout.addWidget(
                    QLabel(translate("[Image missing: {path}]", path=img_path))
                )
        else:
            lbl_no_img = QLabel(translate("[No Main Image]"))
            lbl_no_img.setProperty("class", "textTertiary")
            lbl_no_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(lbl_no_img)

        meta_fields = [
            (translate("Artist:"), data.get("artist")),
            (translate("Album Artist:"), data.get("album_artist")),
            (translate("Year:"), data.get("year")),
            (translate("Genre:"), data.get("genre")),
            (translate("Composer:"), data.get("composer")),
        ]

        if any(f[1] for f in meta_fields):
            meta_grid = QGridLayout()
            meta_grid.setSpacing(4)
            row = 0
            for label, value in meta_fields:
                if value and str(value) != "0":
                    l = QLabel(label)
                    l.setProperty("class", "textTertiary")
                    v = QLabel(str(value))
                    v.setProperty("class", "textSecondary textColorPrimary")
                    v.setWordWrap(True)
                    v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                    meta_grid.addWidget(l, row, 0, Qt.AlignmentFlag.AlignTop)
                    meta_grid.addWidget(v, row, 1, Qt.AlignmentFlag.AlignTop)
                    row += 1
            c_layout.addLayout(meta_grid)

        blocks = data.get("blocks", [])
        if blocks:
            html = ""
            for block in blocks:
                if t := block.get("title"):
                    html += f"<h4 style='color: {theme.COLORS['PRIMARY']}; margin-bottom: 2px;'>{t}</h4>"
                if c := block.get("content"):
                    html += f"<div style='margin-bottom: 8px;'>{c}</div>"

                s_name = block.get("source_name", "").strip()
                s_url = block.get("source_url", "").strip()

                if s_name or s_url:
                    display_name = s_name if s_name else s_url
                    tertiary_color = theme.COLORS.get("TERTIARY")

                    if s_url:
                        accent_color = theme.COLORS.get("ACCENT")
                        html += f"<div style='text-align: right; color: {tertiary_color}; margin-bottom: 12px;'>" \
                                f"{translate('Source')}: <a href='{s_url}' style='color: {accent_color}; text-decoration: none;'>{display_name}</a></div>"
                    else:
                        html += f"<div style='text-align: right; color: {tertiary_color}; margin-bottom: 12px;'>" \
                                f"{translate('Source')}: {display_name}</div>"

            lbl_text = QLabel(html)
            lbl_text.setTextFormat(Qt.TextFormat.RichText)
            lbl_text.setWordWrap(True)
            lbl_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            lbl_text.setProperty("class", "textSecondary textColorPrimary")
            c_layout.addWidget(lbl_text)

        gallery_paths = data.get("gallery", [])
        if gallery_paths:
            count = len(gallery_paths)
            lbl_gal = QLabel(
                translate("Gallery ({count})", count=count)
            )
            lbl_gal.setProperty("class", "textSecondary bold")
            c_layout.addWidget(lbl_gal)

            gal_container = QWidget()
            gal_flow = FlowLayout(gal_container)
            gal_flow.setSpacing(6)
            gal_flow.setContentsMargins(0, 0, 0, 0)

            for g_item in gallery_paths[:12]:
                g_path = g_item.get("path", "") if isinstance(g_item, dict) else str(g_item)

                if not g_path:
                    continue

                g_full = (
                    g_path
                    if os.path.isabs(g_path)
                    else os.path.join(self.base_image_path, g_path)
                )
                if os.path.exists(g_full):
                    g_pix = QPixmap(g_full)
                    if not g_pix.isNull():
                        thumb = RoundedCoverLabel(
                            g_pix.scaled(
                                56,
                                56,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation,
                            ),
                            3,
                        )
                        thumb.setFixedSize(56, 56)
                        gal_flow.addWidget(thumb)
            c_layout.addWidget(gal_container)

        links = data.get("links", [])
        if links:
            lbl_links = QLabel(translate("External Links"))
            lbl_links.setProperty("class", "textSecondary bold")
            c_layout.addWidget(lbl_links)

            for link in links:
                title = link.get("title", "Link")
                url = link.get("url", "")

                link_html = f"<b>{title}</b><br><span style='font-size: 10px; color: {theme.COLORS['TERTIARY']};'>{url}</span>"

                l_lbl = QLabel(link_html)
                l_lbl.setTextFormat(Qt.TextFormat.RichText)
                l_lbl.setWordWrap(True)
                l_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                l_lbl.setProperty("class", "textSecondary textColorPrimary")
                c_layout.addWidget(l_lbl)

        c_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        return container


class RelationsSyncDialog(StyledDialog):
    """
    Dialog for synchronizing relations: shows auto‑find results
    and allows selective removal of outdated links.
    """

    def __init__(self, new_count, orphan_data, parent = None, title=""):
        """
        Initialize the relation sync dialog.

        :param new_count: Number of new relations found.
        :param orphan_data: List of tuples (index, display_text) for orphaned/outdated links.
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Sync Relations"))
        self.resize(640, 480)
        self.setProperty("class", "backgroundPrimary")

        self.orphan_data = orphan_data

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header_lbl = QLabel(translate("Auto Find"))
        header_lbl.setProperty("class", "textHeaderSecondary textColorPrimary")
        layout.addWidget(header_lbl)

        new_msg = translate("New relations found: {count}.", count = new_count)
        if new_count == 0:
            new_msg = translate("No new relations found.")

        lbl_new = QLabel(new_msg)
        lbl_new.setProperty(
            "class",
            (
                "textSecondary textColorAccent"
                if new_count > 0
                else "textSecondary textColorTertiary"
            ),
        )
        layout.addWidget(lbl_new)

        if orphan_data:
            warn_text = translate(
                "However, some existing links are no longer supported by current metadata "
                "(they might have been added manually, or tags have changed).\n\n"
                "Select the items you want to remove:"
            )
            lbl_warn = QLabel(warn_text)
            lbl_warn.setProperty("class", "textSecondary textColorPrimary")
            lbl_warn.setWordWrap(True)
            lbl_warn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            layout.addWidget(lbl_warn)

            self.list_widget = StyledListWidget()
            self.list_widget.setProperty("class", "listWidget")
            self.list_widget.setSelectionMode(
                QListWidget.SelectionMode.NoSelection
            )

            for real_index, display_text in orphan_data:
                item = QListWidgetItem(display_text)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(
                    Qt.ItemDataRole.UserRole, real_index
                )
                self.list_widget.addItem(item)

            self.list_widget.itemChanged.connect(self._update_btn_text)

            layout.addWidget(self.list_widget, 1)
        else:
            layout.addStretch(1)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(self)

        self.btn_unlink = self.button_box.addButton(
            translate("Nothing to unlink"), QDialogButtonBox.ButtonRole.AcceptRole
        )

        self.btn_keep = self.button_box.addButton(
            translate("Keep All"), QDialogButtonBox.ButtonRole.RejectRole
        )

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_unlink.setStyleSheet(
            f"color: {theme.COLORS['ACCENT']}; font-weight: bold;"
        )

        if not orphan_data:
            self.btn_unlink.setText(translate("OK"))
            self.btn_keep.hide()

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

        self._update_btn_text()

    def _update_btn_text(self):
        """
        Update the text of the primary button to reflect the number of checked items.
        """
        if not self.orphan_data:
            return

        checked_count = 0
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked:
                checked_count += 1

        self.btn_unlink.setText(translate("Unlink {count} items", count=checked_count))

    def get_indices_to_remove(self):
        """
        Get a list of internal indices that the user chose to unlink.

        :return: List of index integers.
        """
        indices = []
        if not self.orphan_data:
            return indices

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                indices.append(item.data(Qt.ItemDataRole.UserRole))
        return indices


class EncyclopediaSearchDialog(StyledDialog):
    """
    Dialog facilitating manual searches on Wikipedia to populate encyclopedia articles.
    """
    def __init__(self, query, lang_code="ru", parent=None, title=""):
        """
        Initialize the encyclopedia search dialog.

        :param query: Initial search query text.
        :param lang_code: Default language code for the Wikipedia instance (e.g. 'en').
        :param parent: Parent widget.
        """
        super().__init__(parent, title=title)
        self.setWindowTitle(translate("Search Wikipedia"))
        self.resize(600, 500)
        self.setProperty("class", "backgroundPrimary")

        self.selected_title = None

        self.languages = [
            ("English", "en"),
            ("Русский", "ru"),
            ("Deutsch", "de"),
            ("Français", "fr"),
            ("Español", "es"),
            ("Italiano", "it"),
            ("Português", "pt"),
            ("日本語", "ja"),
            ("中文", "zh"),
        ]

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        search_label = QLabel()
        search_label.setText(
            translate(
                "Search query (e.g. Artist, Album title) and Wikipedia Source Language"
            )
        )
        search_label.setProperty("class", "textTertiary textColorTertiary")
        layout.addWidget(search_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(0)

        self.query_input = StyledLineEdit(query)
        self.query_input.setPlaceholderText(translate("Enter search term..."))
        self.query_input.setProperty(
            "class", "inputBorderMultiLeft inputBorderPaddingTextEdit"
        )
        self.query_input.returnPressed.connect(self.perform_search)

        self.lang_combo = TranslucentCombo()
        self.lang_combo.setFixedWidth(160)
        self.lang_combo.setProperty(
            "class", "inputBorderMultiMiddle inputBorderPaddingTextEdit"
        )

        default_index = 0
        for i, (name, code) in enumerate(self.languages):
            self.lang_combo.addItem(name, code)
            if code == lang_code:
                default_index = i

        self.lang_combo.setCurrentIndex(default_index)
        self.selected_lang = (
            self.lang_combo.currentData()
        )

        search_btn = QPushButton(translate("Search"))
        search_btn.setProperty(
            "class", "btnText inputBorderMultiRight inputBorderPaddingButton"
        )
        search_btn.setFixedHeight(36)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self.perform_search)

        search_row.addWidget(self.query_input, 1)
        search_row.addWidget(self.lang_combo)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)
        layout.addSpacing(8)

        self.results_list = StyledListWidget()
        self.results_list.setProperty("class", "listWidget")
        layout.addWidget(self.results_list)
        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
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

        if query:
            QTimer.singleShot(100, self.perform_search)

    def perform_search(self):
        """
        Fetch search results from the Wikipedia API and display them in the list.
        """
        query = self.query_input.text().strip()
        lang = self.lang_combo.currentData()
        if not query:
            return

        self.results_list.clear()
        self.results_list.addItem(translate("Searching Wikipedia..."))
        QApplication.processEvents()

        try:
            url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 15,
                "utf8": 1,
            }
            headers = {"User-Agent": "VinyllerPlayer/1.0"}
            response = requests.get(url, params=params, timeout=10, headers=headers)
            response.raise_for_status()
            data = response.json()

            self.results_list.clear()
            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                self.results_list.addItem(translate("Nothing found."))
                return

            for res in search_results:
                title = res.get("title")
                snippet = re.sub(r"<[^>]+>", "", res.get("snippet", ""))
                item = QListWidgetItem(f"{title}\n{snippet}...")
                item.setData(Qt.ItemDataRole.UserRole, title)
                self.results_list.addItem(item)

            self.selected_lang = lang

        except Exception as e:
            self.results_list.clear()
            self.results_list.addItem(translate("Error occurred during search."))

    def accept(self):
        """
        Record the selected article title and finish the dialog.
        """
        current_item = self.results_list.currentItem()
        if current_item:
            self.selected_title = current_item.data(Qt.ItemDataRole.UserRole)
            super().accept()

    def get_result(self):
        """
        Get the chosen Wikipedia article properties.

        :return: Tuple containing (article_title, language_code).
        """
        return self.selected_title, self.selected_lang

