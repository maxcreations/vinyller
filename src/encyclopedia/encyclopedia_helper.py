"""
Vinyller — Encyclopedia UI helper
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
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QFileDialog

from src.encyclopedia.encyclopedia_dialogs import (
    EncyclopediaConflictDialog, EncyclopediaRestoreDialog, ExportSuccessDialog, ImportOptionsDialog
)
from src.encyclopedia.encyclopedia_editor_dialog import EncyclopediaEditorDialog
from src.encyclopedia.encyclopedia_injects import EncyclopediaFullViewer, EncyclopediaWidget
from src.ui.custom_dialogs import CustomConfirmDialog
from src.utils.utils_translator import translate


class EncyclopediaHelper:
    """
    Helper class for managing the Encyclopedia UI (viewing, editing, importing/exporting).
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the EncyclopediaHelper.

        :param main_window: Reference to the main application window.
        :param ui_manager: Reference to the UI manager instance.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager

    def inject_encyclopedia_section(
        self, layout, item_key, item_type, refresh_callback=None
    ):
        """
        A universal method to inject an encyclopedia block into any given layout.

        :param layout: The layout where the widget should be added.
        :param item_key: The unique key or identifier of the item.
        :param item_type: The type of the item (e.g., 'album', 'artist', 'genre').
        :param refresh_callback: Optional callback function to execute when the section needs to be refreshed.
        """
        mw = self.main_window

        enc_data = mw.encyclopedia_manager.get_entry(item_key, item_type)

        if not enc_data:
            return

        blocks = enc_data.get("blocks", [])
        has_content = False

        if blocks:
            raw_html = blocks[0].get("content", "")
            clean_text = re.sub(r"<[^>]+>", "", raw_html).strip()
            if clean_text:
                has_content = True

        if not has_content:
            return

        item_name = ""
        if item_type == "album":
            if isinstance(item_key, (list, tuple)) and len(item_key) >= 2:
                item_name = item_key[1]
            else:
                item_name = str(item_key)
        else:
            item_name = str(item_key)

        enc_widget = self._create_encyclopedia_widget(
            enc_data, item_name, item_type, item_key, refresh_callback
        )

        layout.addWidget(enc_widget)

    def _create_encyclopedia_widget(
        self, enc_data, item_name, item_type, item_key, refresh_callback
    ):
        """
        Creates a compact encyclopedia widget and connects it to shared logic methods.
        """
        mw = self.main_window

        encyclopedia_widget = EncyclopediaWidget(
            enc_data, item_type=item_type, main_window=mw
        )
        encyclopedia_widget.item_key = item_key

        encyclopedia_widget.fullViewRequested.connect(
            lambda: self.open_encyclopedia_full_view(item_key, item_type)
        )

        def handle_edit():
            self.open_encyclopedia_editor(
                item_key,
                item_type,
                on_success=lambda *args, **kwargs: (
                    refresh_callback() if refresh_callback else None
                ),
            )

        encyclopedia_widget.editRequested.connect(handle_edit)

        return encyclopedia_widget

    def open_encyclopedia_editor(
            self, item_key, item_type, on_success=None, initial_meta=None, parent=None
    ):
        """
        Universal caller for the encyclopedia article editor dialog.
        """
        mw = self.main_window
        em = mw.encyclopedia_manager

        item_name = str(
            item_key[1]
            if item_type == "album" and isinstance(item_key, (list, tuple))
            else item_key
        )
        sec_query = (
            item_key[0]
            if item_type == "album" and isinstance(item_key, (tuple, list))
            else None
        )

        album_key_arg = item_key if item_type == "album" else None
        def_img_path = self.ui_manager._extract_default_image_path(
            item_name, item_type, album_key=album_key_arg
        )

        current_data = em.get_entry(item_key, item_type)

        scroll_attr, scroll_val = self.ui_manager._capture_current_scroll()

        target_parent = parent if parent else mw

        dialog = EncyclopediaEditorDialog(
            item_name=item_name,
            default_image_path=def_img_path,
            item_type=item_type,
            existing_data=current_data,
            parent=target_parent,
            secondary_query=sec_query,
            main_window=mw,
            full_item_key=item_key,
            initial_meta=initial_meta,
        )

        if dialog.exec():
            new_data = dialog.get_data()
            actual_key = dialog.full_item_key
            actual_type = dialog.item_type

            t_new = tuple(em.normalize_album_key(actual_key)) if actual_type == "album" else actual_key
            t_old = tuple(em.normalize_album_key(item_key)) if item_type == "album" else item_key

            if new_data:
                interlink = new_data.pop("interlink_all", False)
                unlink = getattr(dialog, "unlink_on_delete", False)

                if new_data.get("image_path"):
                    cached = em.cache_image(new_data["image_path"], max_size=1024)
                    if cached:
                        new_data["image_path"] = cached

                if new_data.get("gallery"):
                    cached_gallery = []
                    for item in new_data["gallery"]:
                        orig_path = item.get("path", "") if isinstance(item, dict) else str(item)
                        orig_caption = item.get("caption", "") if isinstance(item, dict) else ""

                        if orig_path:
                            c = em.cache_image(orig_path, max_size=2048)
                            final_path = c if c else orig_path
                            cached_gallery.append({
                                "path": final_path,
                                "caption": orig_caption
                            })
                    new_data["gallery"] = cached_gallery

                em.save_entry(
                    actual_key,
                    actual_type,
                    new_data,
                    interlink_others=interlink,
                    unlink_others=unlink,
                    data_manager=mw.data_manager,
                )

                moved = (t_new != t_old) or (actual_type != item_type)
                if moved:
                    em.save_entry(item_key, item_type, None, data_manager=mw.data_manager)

                if on_success:
                    on_success(actual_key, actual_type, moved=moved)
            else:
                unlink = getattr(dialog, "unlink_on_delete", False)
                em.save_entry(item_key, item_type, None, unlink_others=unlink, data_manager=mw.data_manager)
                if on_success:
                    on_success(None, None, moved=True)

            def delayed_refresh():
                if hasattr(mw, "refresh_current_view"):
                    mw.refresh_current_view()
                self.ui_manager._schedule_scroll_restore(scroll_attr, scroll_val)

            QTimer.singleShot(300, delayed_refresh)

    def open_encyclopedia_full_view(self, item_key, item_type):
        """
        Opens the full-screen view for an encyclopedia article.
        """
        mw = self.main_window
        current_data = mw.encyclopedia_manager.get_entry(item_key, item_type)
        is_missing = current_data is None

        item_name = str(item_key)
        if (
            item_type == "album"
            and isinstance(item_key, (list, tuple))
            and len(item_key) >= 2
        ):
            item_name = item_key[1]

        prev_head = mw.header_stack.currentIndex()
        prev_main = mw.main_stack.currentIndex()
        previous_view_state = (
            mw.current_view_state.copy() if mw.current_view_state else {}
        )

        full_widget = EncyclopediaFullViewer(
            current_data,
            item_name,
            item_type=item_type,
            parent=mw,
            is_missing=is_missing,
            item_key=item_key,
        )

        if not is_missing:
            full_widget.galleryNavigationRequested.connect(
                lambda img_list, idx: self.ui_manager.components.show_cover_viewer(
                    QPixmap(), parent=mw, image_list=img_list, current_index=idx
                )
            )
            full_widget.galleryZoomRequested.connect(self.ui_manager.components.show_cover_viewer)
            full_widget.relationNavigationRequested.connect(self.handle_relation_click)

        full_widget.manageRequested.connect(
            lambda: mw.open_encyclopedia_manager(item_key, item_type)
        )

        def go_back():
            mw.header_stack.setCurrentIndex(prev_head)
            mw.main_stack.setCurrentIndex(prev_main)
            mw.header_stack.removeWidget(full_widget.header_widget)
            mw.main_stack.removeWidget(full_widget.scroll_area)
            full_widget.deleteLater()

            if previous_view_state:
                mw.current_view_state = previous_view_state
                mw.save_current_view_state()
                tab_name = previous_view_state.get("main_tab_name")
                if tab_name and tab_name in mw.nav_button_icon_names:
                    try:
                        idx = mw.nav_button_icon_names.index(tab_name)
                        mw.nav_buttons[idx].setChecked(True)
                        self.ui_manager.update_nav_button_icons()
                    except (ValueError, IndexError):
                        pass

        full_widget.backRequested.connect(go_back)

        def handle_library_goto(key, t_type):
            go_back()
            if t_type == "artist":
                self.ui_manager.navigate_to_artist(key)
            elif t_type == "genre":
                self.ui_manager.navigate_to_genre(key)
            elif t_type == "composer":
                self.ui_manager.navigate_to_composer(key)
            elif t_type == "album":
                self.ui_manager.navigate_to_album(key)

        full_widget.libraryNavigationRequested.connect(handle_library_goto)

        def on_edit_clicked():
            def update_after_edit(new_key, new_type, moved=False):
                if not new_key:
                    go_back()
                elif moved:
                    mw.update_current_view_state(
                        "encyclopedia_full",
                        {
                            "item_key": (
                                list(new_key) if isinstance(new_key, tuple) else new_key
                            ),
                            "item_type": new_type,
                            "prev_main": prev_main,
                            "prev_head": prev_head,
                            "previous_state": previous_view_state,
                        },
                    )
                    go_back()
                    self.open_encyclopedia_full_view(new_key, new_type)
                else:
                    full_widget.is_missing = False
                    full_widget.reload_view(
                        mw.encyclopedia_manager.get_entry(new_key, new_type)
                    )
                    if hasattr(full_widget, "btn_dec"):
                        full_widget.btn_dec.show()
                    if hasattr(full_widget, "btn_inc"):
                        full_widget.btn_inc.show()

            self.open_encyclopedia_editor(
                item_key, item_type, on_success=update_after_edit
            )

        full_widget.editRequested.connect(on_edit_clicked)

        mw.header_stack.addWidget(full_widget.header_widget)
        mw.main_stack.addWidget(full_widget.scroll_area)
        mw.header_stack.setCurrentWidget(full_widget.header_widget)
        mw.main_stack.setCurrentWidget(full_widget.scroll_area)

        if not mw.is_restoring_state:
            mw.update_current_view_state(
                "encyclopedia_full",
                {
                    "item_key": (
                        list(item_key) if isinstance(item_key, tuple) else item_key
                    ),
                    "item_type": item_type,
                    "prev_main": prev_main,
                    "prev_head": prev_head,
                    "previous_state": previous_view_state,
                },
            )

        self.ui_manager.update_all_track_widgets()

    def handle_relation_click(self, item_key, item_type, extra_data=None):
        """
        Smart navigation handling for related items:
        1. If the article exists -> Open it.
        2. If not -> Offer to create it (pre-filling data from extra_data).
        """
        mw = self.main_window
        entry = mw.encyclopedia_manager.get_entry(item_key, item_type)

        if entry:
            self.open_encyclopedia_full_view(item_key, item_type)
        else:
            item_name = str(item_key)
            if (
                item_type == "album"
                and isinstance(item_key, (list, tuple))
                and len(item_key) >= 2
            ):
                item_name = item_key[1]

            msg = translate(
                "The encyclopedia entry for '{name}' does not exist yet. Would you like to create it?",
                name=item_name,
            )

            if CustomConfirmDialog.confirm(
                mw,
                translate("Missing Article"),
                msg,
                ok_text=translate("Create"),
                cancel_text=translate("Cancel"),
            ):

                def_img_path = self.ui_manager._extract_default_image_path(
                    item_name,
                    item_type,
                    album_key=item_key if item_type == "album" else None,
                )
                sec_query = (
                    item_key[0]
                    if item_type == "album" and isinstance(item_key, (tuple, list))
                    else None
                )

                dialog = EncyclopediaEditorDialog(
                    item_name,
                    def_img_path,
                    item_type,
                    None,
                    mw,
                    secondary_query=sec_query,
                    full_item_key=item_key,
                    initial_meta=extra_data,
                )

                if dialog.exec():
                    new_data = dialog.get_data()

                    if new_data:
                        interlink = new_data.pop("interlink_all", False)

                        if new_data.get("image_path"):
                            cached = mw.encyclopedia_manager.cache_image(
                                new_data["image_path"]
                            )
                            if cached:
                                new_data["image_path"] = cached

                        mw.encyclopedia_manager.save_entry(
                            item_key,
                            item_type,
                            new_data,
                            interlink_others = interlink,
                            data_manager = mw.data_manager,
                        )

                        self.open_encyclopedia_full_view(item_key, item_type)

    def handle_encyclopedia_import(self, parent_widget):
        """
        Handles the encyclopedia import process, showing a restore dialog for backups
        or triggering a ZIP archive import.

        :param parent_widget: The parent widget to anchor dialogs to.
        """
        mw = self.main_window
        em = mw.encyclopedia_manager

        backups = em.get_available_backups(max_count=5)

        restore_dlg = EncyclopediaRestoreDialog(backups, parent_widget)

        restore_dlg.importFileRequested.connect(
            lambda: self._handle_zip_import(parent_widget)
        )

        if restore_dlg.exec() == QDialog.DialogCode.Accepted:
            backup_idx = restore_dlg.get_selected_backup_index()
            if backup_idx:
                self._confirm_and_restore_backup(backup_idx, parent_widget)

    def _confirm_and_restore_backup(self, index, parent_widget):
        """
        Prompts for confirmation and restores the encyclopedia texts from a selected backup index.

        :param index: The identifier/index of the backup to restore.
        :param parent_widget: The parent widget for the confirmation dialog.
        """
        mw = self.main_window
        em = mw.encyclopedia_manager

        msg = translate(
            "This will replace your current encyclopedia texts with version from backup. Images won't be affected. Continue?"
        )

        if CustomConfirmDialog.confirm(
            parent_widget,
            translate("Confirm Restore"),
            msg,
            ok_text=translate("Restore"),
            cancel_text=translate("Cancel"),
        ):
            success, error = em.restore_from_backup(index)
            if success:
                mw.refresh_current_view()
                CustomConfirmDialog.confirm(
                    parent_widget,
                    translate("Done!"),
                    translate("Encyclopedia restored from automatic backup."),
                    ok_text=translate("OK"),
                    cancel_text=None,
                )
            else:
                CustomConfirmDialog.confirm(
                    parent_widget,
                    translate("Error"),
                    translate("Failed to restore: {error}", error=error),
                    ok_text=translate("OK"),
                    cancel_text=None,
                )

    def _handle_zip_import(self, parent_widget):
        """
        Handles importing an encyclopedia from a ZIP archive, including conflict resolution options.

        :param parent_widget: The parent widget for file selection and dialogs.
        """
        mw = self.main_window

        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            translate("Import Encyclopedia"),
            str(Path.home()),
            translate("Zip Archive (*.zip)"),
        )
        if not file_path:
            return

        current_data = mw.encyclopedia_manager.load_data()
        dlg = ImportOptionsDialog(bool(current_data), parent_widget)

        if dlg.exec():
            replace_all, overwrite_duplicates, merge_duplicates, interactive_mode = (
                dlg.get_result()
            )

            def conflict_resolver(item_key, item_type, current, new, base_img_path):
                c_dlg = EncyclopediaConflictDialog(
                    item_key, item_type, current, new, base_img_path, parent_widget, is_import=True
                )
                return c_dlg.exec()

            cb = conflict_resolver if interactive_mode else None

            success, error, count = mw.encyclopedia_manager.import_package(
                file_path, replace_all, overwrite_duplicates, merge_duplicates, cb
            )

            if success:
                mw.refresh_current_view()
                msg = (
                    translate(
                        "Encyclopedia imported successfully. Updated {count} articles.",
                        count=count,
                    )
                    if count > 0
                    else translate(
                        "All articles in the file are identical to your current encyclopedia. Nothing to update."
                    )
                )
                CustomConfirmDialog.confirm(
                    parent_widget,
                    translate("Import Finished"),
                    msg,
                    ok_text=translate("OK"),
                    cancel_text=None,
                )
            else:
                if error != translate("Import cancelled by user."):
                    CustomConfirmDialog.confirm(
                        parent_widget,
                        translate("Import Failed"),
                        translate("Error: {error}", error=error),
                        ok_text=translate("OK"),
                        cancel_text=None,
                    )

    def handle_encyclopedia_export(self, parent_widget):
        """
        Handles exporting the current encyclopedia to a ZIP archive.

        :param parent_widget: The parent widget for the file save dialog.
        """
        mw = self.main_window

        date_str = datetime.now().strftime("%d-%m-%Y")
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            translate("Export Encyclopedia"),
            str(Path.home() / f"VinyllerEncyclopedia_{date_str}.zip"),
            translate("Zip Archive (*.zip)"),
        )
        if not file_path:
            return

        success, error = mw.encyclopedia_manager.export_package(file_path)
        if success:
            ExportSuccessDialog(os.path.dirname(file_path), parent_widget).exec()
        else:
            CustomConfirmDialog.confirm(
                parent_widget,
                translate("Export Failed"),
                translate("Error: {error}", error=error),
                ok_text=translate("OK"),
                cancel_text=None,
            )