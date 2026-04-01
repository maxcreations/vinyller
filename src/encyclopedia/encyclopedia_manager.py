"""
Vinyller — Encyclopedia data manger
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

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import traceback
import urllib
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image
from PyQt6.QtCore import (
    pyqtSignal, QThread
)

from src.utils.utils_translator import translate


class EncyclopediaManager:
    """
    Manages encyclopedia data, images, relations, and import/export operations.
    Extracted from LibraryManager.
    """

    def __init__(self, app_data_dir: Path):
        """
        Initializes the EncyclopediaManager, setting up the necessary file paths
        for the database, image storage, and backups.
        """
        self.app_data_dir = app_data_dir
        self.json_path = self.app_data_dir / "encyclopedia.json"
        self.images_dir = self.app_data_dir / "encyclopedia_images"
        self.backup_dir = self.app_data_dir / "encyclopedia_backups"

        self.images_dir.mkdir(parents=True, exist_ok=True)

    def rotate_json_backups(self, max_count=5):
        """
        Creates a rotational JSON backup of the encyclopedia database.
        The loop shifts existing backup files, freeing space for the freshest backup as number 1.
        Keeps up to `max_count` copies.
        """
        if not self.json_path.exists():
            return

        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            for i in range(max_count - 1, 0, -1):
                old_file = self.backup_dir / f"encyclopedia.json.bak{i}"
                new_file = self.backup_dir / f"encyclopedia.json.bak{i + 1}"

                if old_file.exists():
                    if new_file.exists():
                        new_file.unlink()
                    old_file.rename(new_file)

            target_bak1 = self.backup_dir / "encyclopedia.json.bak1"
            shutil.copy2(str(self.json_path), str(target_bak1))

            print(
                f"Encyclopedia: Rotation backup successful (kept up to {max_count} copies)."
            )
        except Exception as e:
            print(f"Encyclopedia Backup Error: {e}")

    def get_available_backups(self, max_count=5):
        """
        Retrieves a list of available database backups.

        Returns:
            list: A list of dictionaries containing backup index, path, formatted date, and article count.
        """
        backups = []
        if not self.backup_dir.exists():
            return backups

        for i in range(1, max_count + 1):
            path = self.backup_dir / f"encyclopedia.json.bak{i}"
            if path.exists():
                mtime = os.path.getmtime(path)
                entry_count = 0

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        temp_data = json.load(f)
                        entry_count = sum(
                            len(v) for v in temp_data.values() if isinstance(v, dict)
                        )
                except Exception:
                    entry_count = -1

                backups.append(
                    {
                        "index": i,
                        "path": path,
                        "date": datetime.fromtimestamp(mtime).strftime(
                            "%d.%m.%Y %H:%M"
                        ),
                        "count": entry_count,
                    }
                )
        return backups

    def restore_from_backup(self, index):
        """
        Restores the database from a selected backup file index.
        Before restoring, creates a `.old` safeguard copy of the current database.

        Returns:
            tuple: (success: bool, error_message: str|None)
        """
        source = self.backup_dir / f"encyclopedia.json.bak{index}"
        if not source.exists():
            return False, "Backup file not found"

        try:
            if self.json_path.exists():
                old_safe = self.json_path.with_suffix(".old")
                shutil.copy2(str(self.json_path), str(old_safe))

            shutil.copy2(str(source), str(self.json_path))
            return True, None
        except Exception as e:
            return False, str(e)

    def normalize_album_key(self, key):
        """
        Normalizes an album key to the standard 3-element tuple form (Artist, Album, Year).
        Appends 0 for missing elements.
        """
        if not isinstance(key, (list, tuple)):
            return key

        lst = list(key)
        while len(lst) < 3:
            lst.append(0)
        return tuple(lst[:3])

    def load_data(self) -> dict:
        """
        Loads and parses the entire encyclopedia JSON database.

        Returns:
            dict: The loaded data, or an empty dictionary if the file doesn't exist or is invalid.
        """
        if not self.json_path.exists():
            return {}
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading encyclopedia data: {e}")
            return {}

    def save_data(self, data: dict):
        """
        Serializes and writes the provided dictionary data to the encyclopedia JSON file.
        """
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error saving encyclopedia: {e}")

    def get_entry(self, item_key, item_type):
        """
        Retrieves a specific encyclopedia entry based on its key and type.
        Normalizes Album keys to 3 elements. Resolves absolute paths for images and gallery items.

        Returns:
            dict|None: The requested entry, or None if not found.
        """
        actual_key = item_key

        if item_type == "album" and isinstance(item_key, (list, tuple)):
            temp_key = list(item_key)
            while len(temp_key) < 3:
                temp_key.append(0)
            actual_key = tuple(temp_key[:3])

        data = self.load_data()
        str_key = (
            json.dumps(actual_key, ensure_ascii = False)
            if isinstance(actual_key, (list, tuple))
            else str(actual_key)
        )

        section = data.get(item_type, {})

        raw_entry = section.get(str_key)

        if not raw_entry and item_type == "genre":
            target_lower = str_key.lower()
            for k, v in section.items():
                if k.lower() == target_lower:
                    raw_entry = v
                    break

        entry = raw_entry.copy() if raw_entry else None

        if entry:
            if entry.get("image_path"):
                img_path = entry["image_path"]
                if isinstance(img_path, dict):
                    img_path = img_path.get("path", "")

                if img_path and not os.path.isabs(img_path):
                    full_path = self.images_dir / img_path
                    if full_path.exists():
                        entry["image_path"] = str(full_path.resolve())

            if entry.get("gallery"):
                restored_gallery = []
                for item in entry["gallery"]:
                    if isinstance(item, dict):
                        path = item.get("path", "")
                        caption = item.get("caption", "")
                        if path and not os.path.isabs(path):
                            full_path = self.images_dir / path
                            if full_path.exists():
                                restored_gallery.append(
                                    {
                                        "path": str(full_path.resolve()),
                                        "caption": caption,
                                    }
                                )
                        elif path:
                            if os.path.exists(path):
                                restored_gallery.append(
                                    {"path": path, "caption": caption}
                                )
                    else:
                        path = item
                        if path and not os.path.isabs(path):
                            full_path = self.images_dir / path
                            if full_path.exists():
                                restored_gallery.append(
                                    {"path": str(full_path.resolve()), "caption": ""}
                                )
                        elif path:
                            if os.path.exists(path):
                                restored_gallery.append({"path": path, "caption": ""})

                entry["gallery"] = restored_gallery

        return entry

    def save_entry(
            self,
            item_key,
            item_type,
            entry_data,
            interlink_others = False,
            unlink_others = False,
            data_manager = None,
    ):
        """
        Saves or updates an encyclopedia entry, handling complex relation linking/unlinking
        and image caching/cleanup. Enforces a 3-element key for albums.
        Properly standardizes gallery captions and normalizes relative image paths.
        """
        actual_key = item_key

        if item_type == "album" and isinstance(item_key, (list, tuple)):
            temp_key = list(item_key)
            while len(temp_key) < 3:
                temp_key.append(0)
            actual_key = tuple(temp_key[:3])

        data = self.load_data()

        if item_type not in data:
            data[item_type] = {}

        str_key = (
            json.dumps(actual_key, ensure_ascii = False)
            if isinstance(actual_key, (list, tuple))
            else str(actual_key)
        )

        if item_type == "genre":
            target_lower = str_key.lower()
            existing_key_in_db = None
            for k in data[item_type].keys():
                if k.lower() == target_lower:
                    existing_key_in_db = k
                    break
            if existing_key_in_db:
                str_key = existing_key_in_db

        current_name = str(actual_key)
        current_subtitle = ""
        if (
                item_type == "album"
                and isinstance(actual_key, (list, tuple))
                and len(actual_key) >= 2
        ):
            current_name = actual_key[1]
            current_subtitle = actual_key[0]

        if entry_data and "relations" in entry_data:
            clean_relations = []
            for rel in entry_data["relations"]:
                clean_rel = rel.copy()
                if clean_rel["type"] == "album" and isinstance(
                        clean_rel["key"], (list, tuple)
                ):
                    r_key = list(clean_rel["key"])
                    while len(r_key) < 3:
                        r_key.append(0)
                    clean_rel["key"] = r_key[:3]
                clean_relations.append(clean_rel)
            entry_data["relations"] = clean_relations

        self_relation_obj = {
            "key": actual_key,
            "type": item_type,
            "name": current_name,
            "subtitle": current_subtitle,
        }

        old_entry = data[item_type].get(str_key, {})
        old_relations = old_entry.get("relations", [])
        new_relations = entry_data.get("relations", []) if entry_data else []

        def get_rel_id(rel):
            r_key = rel["key"]
            if rel["type"] == "album" and isinstance(r_key, (list, tuple)):
                r_key = list(r_key)
                while len(r_key) < 3:
                    r_key.append(0)
                r_key = tuple(r_key[:3])
            if isinstance(r_key, list):
                r_key = tuple(r_key)
            return (rel["type"], r_key)

        old_rel_ids = {get_rel_id(r) for r in old_relations}
        new_rel_ids = {get_rel_id(r) for r in new_relations}

        removed_ids = old_rel_ids - new_rel_ids
        added_ids = new_rel_ids - old_rel_ids

        def normalize_target_key(t_key, t_type):
            if t_type == "album" and isinstance(t_key, (list, tuple)):
                lst = list(t_key)
                while len(lst) < 3:
                    lst.append(0)
                return tuple(lst[:3])
            return t_key

        def remove_relation_from_target(target_key, target_type, relation_to_remove):
            final_target_key = normalize_target_key(target_key, target_type)
            t_key_str = (
                json.dumps(final_target_key, ensure_ascii=False)
                if isinstance(final_target_key, (list, tuple))
                else str(final_target_key)
            )

            if target_type in data and t_key_str not in data[target_type]:
                alt_key = (
                    json.dumps(final_target_key, ensure_ascii = False)
                    if isinstance(final_target_key, (list, tuple))
                    else str(final_target_key)
                )
                if alt_key in data[target_type]:
                    t_key_str = alt_key

            if target_type in data and t_key_str in data[target_type]:
                target_entry = data[target_type][t_key_str]
                target_rels = target_entry.get("relations", [])
                original_len = len(target_rels)
                new_rels = []
                for r in target_rels:
                    if get_rel_id(r) != get_rel_id(relation_to_remove):
                        new_rels.append(r)
                if len(new_rels) < original_len:
                    target_entry["relations"] = new_rels
                    target_entry["last_modified"] = time.time()

        def add_relation_to_target(
                target_key, target_type, relation_to_add, data_manager = None
        ):
            final_target_key = normalize_target_key(target_key, target_type)
            if target_type not in data:
                data[target_type] = {}
            t_key_str = (
                json.dumps(final_target_key, ensure_ascii=False)
                if isinstance(final_target_key, (list, tuple))
                else str(final_target_key)
            )

            if t_key_str not in data[target_type]:
                alt_key = (
                    json.dumps(final_target_key, ensure_ascii = False)
                    if isinstance(final_target_key, (list, tuple))
                    else str(final_target_key)
                )
                if alt_key in data[target_type]:
                    t_key_str = alt_key

            if t_key_str not in data[target_type]:
                new_entry = {
                    "last_modified": time.time(),
                    "relations": [],
                    "blocks": [],
                }

                if data_manager:
                    meta = data_manager.get_best_metadata_for_key(
                        final_target_key, target_type
                    )
                    if meta:
                        new_entry["blocks"] = [{"title": meta["name"], "content": ""}]
                        if meta.get("image_path"):
                            image_source = meta["image_path"]
                            if isinstance(image_source, dict):
                                image_source = image_source.get("path", "")

                            cached_path = self.cache_image(image_source, max_size = 1024)
                            if cached_path:
                                new_entry["image_path"] = os.path.relpath(
                                    cached_path, self.images_dir
                                )

                data[target_type][t_key_str] = new_entry

            target_entry = data[target_type][t_key_str]
            target_rels = target_entry.get("relations", [])
            if not any(
                    get_rel_id(r) == get_rel_id(relation_to_add) for r in target_rels
            ):
                target_rels.append(relation_to_add)
                target_entry["relations"] = target_rels
                target_entry["last_modified"] = time.time()

        for rel in old_relations:
            if get_rel_id(rel) in removed_ids:
                remove_relation_from_target(rel["key"], rel["type"], self_relation_obj)

        for rel in new_relations:
            if get_rel_id(rel) in added_ids:
                add_relation_to_target(
                    rel["key"],
                    rel["type"],
                    self_relation_obj,
                    data_manager = data_manager,
                )

        if interlink_others and len(new_relations) > 1:
            for i, rel_source in enumerate(new_relations):
                for j, rel_target in enumerate(new_relations):
                    if i == j:
                        continue
                    relation_obj_to_add = {
                        "key": rel_source["key"],
                        "type": rel_source["type"],
                        "name": rel_source["name"],
                        "subtitle": rel_source.get("subtitle", ""),
                    }
                    add_relation_to_target(
                        rel_target["key"],
                        rel_target["type"],
                        relation_obj_to_add,
                        data_manager = data_manager,
                    )

        old_images = set()
        existing_key_for_images = str_key
        if str_key not in data[item_type]:
            alt_key = (
                json.dumps(actual_key, ensure_ascii = False)
                if isinstance(actual_key, (list, tuple))
                else str(actual_key)
            )
            if alt_key in data[item_type]:
                existing_key_for_images = alt_key

        if existing_key_for_images in data[item_type]:
            existing_entry = data[item_type][existing_key_for_images]
            if existing_entry.get("image_path"):
                img_path = existing_entry["image_path"]
                if isinstance(img_path, dict):
                    old_images.add(img_path.get("path", ""))
                else:
                    old_images.add(img_path)
            if existing_entry.get("gallery"):
                for img in existing_entry["gallery"]:
                    if isinstance(img, dict):
                        old_images.add(img.get("path", ""))
                    else:
                        old_images.add(img)

        def to_relative_if_possible(path_str):
            if not path_str:
                return path_str
            try:
                abs_path = os.path.abspath(path_str)
                abs_storage = os.path.abspath(self.images_dir)
                if abs_path.startswith(abs_storage):
                    return os.path.relpath(abs_path, abs_storage)
            except Exception:
                pass
            return path_str

        if entry_data is None:
            deleted = False
            if str_key in data[item_type]:
                del data[item_type][str_key]
                deleted = True

            if not deleted:
                alt_key = (
                    json.dumps(actual_key, ensure_ascii = False)
                    if isinstance(actual_key, (list, tuple))
                    else str(actual_key)
                )
                if alt_key != str_key and alt_key in data[item_type]:
                    del data[item_type][alt_key]
                    deleted = True

            if unlink_others:
                self_id = get_rel_id(self_relation_obj)
                for cat_type, entries in data.items():
                    for entry_val in entries.values():
                        relations = entry_val.get("relations", [])
                        if not relations:
                            continue
                        original_len = len(relations)
                        new_rels = [r for r in relations if get_rel_id(r) != self_id]
                        if len(new_rels) < original_len:
                            entry_val["relations"] = new_rels
                            entry_val["last_modified"] = time.time()
        else:
            if "interlink_all" in entry_data:
                del entry_data["interlink_all"]

            entry_data["last_modified"] = time.time()

            if entry_data.get("image_path"):
                entry_data["image_path"] = to_relative_if_possible(
                    entry_data["image_path"]
                )

            if entry_data and entry_data.get("gallery"):
                processed_gallery = []
                raw_gallery = entry_data["gallery"]

                for item in raw_gallery:
                    path = item.get("path", "") if isinstance(item, dict) else str(item)
                    caption = item.get("caption", "") if isinstance(item, dict) else ""

                    if not path:
                        continue

                    if os.path.isabs(path) and os.path.exists(path):
                        cached_path = self.cache_image(path, max_size = 2048)
                        if cached_path:
                            path = cached_path

                    filename = os.path.basename(to_relative_if_possible(path))

                    processed_gallery.append(
                        {"path": filename, "caption": caption.strip()}
                    )

                entry_data["gallery"] = processed_gallery

            data[item_type][str_key] = entry_data

        new_images = set()
        if entry_data:
            if entry_data.get("image_path"):
                new_images.add(entry_data["image_path"])
            if entry_data.get("gallery"):
                for img in entry_data["gallery"]:
                    if isinstance(img, dict):
                        new_images.add(img.get("path", ""))
                    else:
                        new_images.add(img)

        candidates_to_delete = [
            img for img in (old_images - new_images) if not os.path.isabs(img)
        ]

        if candidates_to_delete:
            all_used_images = set()
            for section in data.values():
                for entry in section.values():
                    if entry.get("image_path"):
                        all_used_images.add(entry["image_path"])
                    if entry.get("gallery"):
                        for g_img in entry["gallery"]:
                            if isinstance(g_img, dict):
                                all_used_images.add(g_img.get("path", ""))
                            else:
                                all_used_images.add(g_img)

            for img_to_remove in candidates_to_delete:
                if img_to_remove not in all_used_images:
                    try:
                        file_path = self.images_dir / img_to_remove
                        if file_path.exists():
                            os.remove(file_path)

                        thumb_name = self.get_thumb_filename(img_to_remove)
                        thumb_path = self.images_dir / thumb_name
                        if thumb_path.exists():
                            os.remove(thumb_path)
                    except OSError:
                        pass

        self.save_data(data)

    def cache_image(self, source_path, max_size=1024):
        """
        Caches an image into the encyclopedia's image directory.
        Resizes the image if it is larger than max_size and creates a 128px thumbnail.

        Returns:
            str|None: The absolute path to the cached image, or None if caching failed.
        """
        if isinstance(source_path, dict):
            path = source_path.get("path", "")
        else:
            path = source_path

        if not path or not os.path.exists(path):
            return None

        try:
            with open(path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            ext = os.path.splitext(path)[1].lower() or ".jpg"
            new_filename = f"{file_hash}_{max_size}{ext}"
            new_path = self.images_dir / new_filename
            thumb_path = self.images_dir / f"{file_hash}_thumb{ext}"

            if new_path.exists() and thumb_path.exists():
                return str(new_path)

            with Image.open(path) as img:
                if not new_path.exists():
                    width, height = img.size
                    main_img = img.copy()

                    if width > max_size or height > max_size:
                        main_img.thumbnail(
                            (max_size, max_size), Image.Resampling.LANCZOS
                        )

                        if ext in [".jpg", ".jpeg"] and main_img.mode in ("RGBA", "LA"):
                            background = Image.new(
                                "RGB", main_img.size, (255, 255, 255)
                            )
                            background.paste(main_img, mask=main_img.split()[-1])
                            main_img = background

                        main_img.save(new_path, quality=90, optimize=True)
                    else:
                        shutil.copy2(path, new_path)

                if not thumb_path.exists():
                    thumb_img = img.copy()
                    thumb_img.thumbnail((128, 128), Image.Resampling.LANCZOS)
                    thumb_img.save(thumb_path, quality=85, optimize=True)

            return str(new_path)
        except Exception as e:
            print(f"Error caching image ({max_size}px): {e}")
            return None

    def get_thumb_filename(self, image_filename: str) -> str:
        """
        Correctly calculates the thumbnail filename by stripping the size suffix (1024/2048) if present.
        """
        name, ext = os.path.splitext(image_filename)
        if "_" in name:
            base_hash = name.rsplit("_", 1)[0]
            return f"{base_hash}_thumb{ext}"
        return f"{name}_thumb{ext}"

    def get_used_images(self) -> set:
        """
        Compiles a whitelist of all used images and their corresponding thumbnails from the database.

        Returns:
            set: A set containing the filenames of all valid images and thumbnails.
        """
        data = self.load_data()
        valid_filenames = set()

        def add_to_whitelist(path_obj):
            if not path_obj:
                return

            if isinstance(path_obj, dict):
                path_str = path_obj.get("path", "")
            else:
                path_str = str(path_obj)

            if not path_str:
                return

            filename = os.path.basename(path_str)
            valid_filenames.add(filename)
            valid_filenames.add(self.get_thumb_filename(filename))

        for section in data.values():
            for entry in section.values():
                add_to_whitelist(entry.get("image_path"))
                for g_path in entry.get("gallery", []):
                    add_to_whitelist(g_path)

        return valid_filenames

    def get_orphaned_images(self) -> list:
        """
        Scans the encyclopedia images directory and returns a list of orphaned images.

        Returns:
            list: A list of filenames that are not referenced in the database.
        """
        if not self.images_dir.exists():
            return []

        valid_filenames = self.get_used_images()
        orphans = []

        try:
            for filename in os.listdir(self.images_dir):
                if filename.startswith("."):
                    continue
                if filename not in valid_filenames:
                    orphans.append(filename)
        except Exception as e:
            print(f"Error scanning encyclopedia: {e}")

        return orphans

    def remove_images(self, filenames: list) -> int:
        """
        Deletes the specified images from the encyclopedia images directory.

        Args:
            filenames (list): A list of filenames to delete.

        Returns:
            int: The number of successfully deleted files.
        """
        deleted_count = 0
        for filename in filenames:
            file_path = self.images_dir / filename
            try:
                if file_path.exists():
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                print(f"Error deleting {filename}: {e}")
        return deleted_count

    def run_global_cleanup(self):
        """
        Performs a global garbage collection on the encyclopedia image directory.
        Uses the helper methods to find and remove unreferenced or orphaned image files.
        """
        print("Starting global encyclopedia cleanup...")

        if not self.images_dir.exists():
            return

        orphans = self.get_orphaned_images()

        if not orphans:
            print("Global Cleanup Finished. No orphans found.")
            return

        total_size_freed = 0
        for filename in orphans:
            try:
                file_path = self.images_dir / filename
                if file_path.exists():
                    total_size_freed += os.path.getsize(file_path)
            except OSError:
                pass

        deleted_count = self.remove_images(orphans)

        if deleted_count > 0:
            mb_freed = total_size_freed / (1024 * 1024)
            print(f"Global Cleanup Finished. Removed {deleted_count} files ({mb_freed:.2f} MB freed).")

    def export_package(self, target_zip_path):
        """
        Creates a zip archive packaging the encyclopedia.json and all associated images.

        Returns:
            tuple: (success: bool, error_message: str|None)
        """
        try:
            with zipfile.ZipFile(target_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                if self.json_path.exists():
                    zipf.write(self.json_path, arcname="encyclopedia.json")

                if self.images_dir.exists():
                    for root, dirs, files in os.walk(self.images_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = str(os.path.relpath(file_path, self.app_data_dir)).replace("\\", "/")
                            zipf.write(file_path, arcname = arcname)
            return True, None
        except Exception as e:
            return False, str(e)

    def import_package(
        self,
        source_zip_path,
        replace_all=False,
        overwrite_duplicates=False,
        merge_duplicates=False,
        interactive_callback=None,
    ):
        """
        Imports encyclopedia data from a zip archive. Parses the incoming JSON,
        merges data, and extracts bundled images AFTER confirming changes.
        Automatically cleans up any unreferenced images extracted from the archive.

        Returns:
            tuple: (success: bool, error_message: str|None, change_count: int)
        """
        try:
            with zipfile.ZipFile(source_zip_path, "r") as zipf:
                try:
                    with zipf.open("encyclopedia.json") as f:
                        imported_data = json.loads(f.read().decode('utf-8'))
                except KeyError:
                    return False, "Invalid archive: encyclopedia.json not found", 0

                current_data = self.load_data() if not replace_all else {}
                auto_action = None
                changed_count = 0

                for category, items in imported_data.items():
                    if category not in current_data:
                        current_data[category] = {}

                    for key, entry in items.items():
                        if key in current_data[category] and not replace_all:

                            curr_entry = current_data[category][key]
                            if json.dumps(curr_entry, sort_keys = True, ensure_ascii = False) == json.dumps(
                                    entry, sort_keys = True, ensure_ascii = False
                            ):
                                continue

                            if merge_duplicates and auto_action is None:
                                current_data[category][key] = self.merge_entry_data(
                                    curr_entry, entry
                                )
                                changed_count += 1
                                continue

                            if interactive_callback and auto_action is None:
                                display_key = key
                                try:
                                    if category == "album":
                                        display_key = tuple(json.loads(key))
                                except:
                                    pass

                                action = interactive_callback(
                                    display_key,
                                    category,
                                    curr_entry,
                                    entry,
                                    str(self.images_dir),
                                )

                                if action == 0:
                                    return (
                                        False,
                                        translate("Import cancelled by user."),
                                        changed_count,
                                    )
                                elif action == 1:
                                    continue
                                elif action == 2:
                                    current_data[category][key] = entry
                                    changed_count += 1
                                elif action == 5:
                                    current_data[category][key] = self.merge_entry_data(
                                        curr_entry, entry
                                    )
                                    changed_count += 1
                                elif action == 3:
                                    auto_action = 3
                                    continue
                                elif action == 4:
                                    auto_action = 4
                                    current_data[category][key] = entry
                                    changed_count += 1
                                continue

                            if auto_action == 3:
                                continue
                            if auto_action == 4:
                                current_data[category][key] = entry
                                changed_count += 1
                                continue

                            if overwrite_duplicates:
                                current_data[category][key] = entry
                                changed_count += 1

                        else:
                            current_data[category][key] = entry
                            changed_count += 1

                if changed_count > 0:
                    self.save_data(current_data)

                    for file_info in zipf.infolist():
                        normalized_filename = file_info.filename.replace("\\", "/")

                        if (
                                normalized_filename.startswith("encyclopedia_images/")
                                and not file_info.is_dir()
                        ):
                            target_path = self.app_data_dir / normalized_filename
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            with zipf.open(file_info) as source, open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)

                    orphans = self.get_orphaned_images()
                    if orphans:
                        self.remove_images(orphans)

                return True, None, changed_count

        except Exception as e:
            traceback.print_exc()
            return False, str(e), 0

    def merge_entry_data(self, result, extra_data):
        """
        Merges extra_data into an existing entry dictionary.
        Updates fields like images, metadata, blocks, links, gallery, relations,
        and discography. Identifies unique gallery items and relations to prevent duplication.

        Returns:
            dict: The newly merged data structure.
        """
        for key in ["image_path", "artist", "year", "interlink_all"]:
            if key in extra_data and not result.get(key):
                result[key] = extra_data[key]

        for key in ["album_artist", "composer", "genre"]:
            raw_a = result.get(key)
            raw_b = extra_data.get(key)

            val_a = "" if raw_a is None else str(raw_a).strip()
            val_b = "" if raw_b is None else str(raw_b).strip()

            if val_b:
                if val_a:
                    tags_a = [t.strip() for t in re.split(r"[,;]", val_a) if t.strip()]
                    tags_b = [t.strip() for t in re.split(r"[,;]", val_b) if t.strip()]

                    final_tags = list(tags_a)
                    for tb in tags_b:
                        if tb not in final_tags:
                            final_tags.append(tb)

                    result[key] = ", ".join(final_tags)
                else:
                    result[key] = val_b

        if "blocks" in extra_data:
            if "blocks" not in result:
                result["blocks"] = []
            result["blocks"].extend(extra_data["blocks"])

        if "links" in extra_data:
            if "links" not in result:
                result["links"] = []
            existing_urls = {l.get("url", "") for l in result["links"]}
            for link in extra_data["links"]:
                url = link.get("url", "")
                if url not in existing_urls:
                    result["links"].append(link)
                    existing_urls.add(url)

        gallery_dict = {}

        def get_key(p):
            return os.path.basename(str(p))

        for img in result.get("gallery", []):
            if isinstance(img, dict):
                path = img.get("path", "")
                if path:
                    gallery_dict[get_key(path)] = img.copy()
            else:
                path = str(img)
                if path:
                    gallery_dict[get_key(path)] = {"path": path, "caption": ""}

        extra_main = extra_data.get("image_path")
        res_main = result.get("image_path")
        if extra_main and extra_main != res_main:
            p = extra_main.get("path", "") if isinstance(extra_main, dict) else str(extra_main)
            if p and get_key(p) not in gallery_dict:
                gallery_dict[get_key(p)] = {"path": p, "caption": translate("Main cover of merged article")}

        for img in extra_data.get("gallery", []):
            if isinstance(img, dict):
                path = img.get("path", "")
                caption = img.get("caption", "").strip()
                if path:
                    key = get_key(path)
                    if key in gallery_dict:
                        if caption and not gallery_dict[key].get("caption"):
                            gallery_dict[key]["caption"] = caption
                    else:
                        gallery_dict[key] = {"path": path, "caption": caption}
            else:
                path = str(img)
                if path:
                    key = get_key(path)
                    if key not in gallery_dict:
                        gallery_dict[key] = {"path": path, "caption": ""}

        result["gallery"] = list(gallery_dict.values())

        if "relations" in extra_data:
            existing_rels = result.get("relations", [])
            new_rels = extra_data["relations"]

            seen = set()
            final_rels = []

            def get_rel_sig(r):
                k = r.get("key")
                if isinstance(k, list):
                    k = tuple(k)
                return (r.get("type"), k)

            for r in existing_rels:
                sig = get_rel_sig(r)
                seen.add(sig)
                final_rels.append(r)

            for r in new_rels:
                sig = get_rel_sig(r)
                if sig not in seen:
                    final_rels.append(r)
                    seen.add(sig)

            result["relations"] = final_rels

        if "discography" in extra_data:
            if "discography" not in result:
                result["discography"] = []

            existing_disco = result["discography"]
            new_disco = extra_data["discography"]

            seen_disco = set()
            final_disco = []

            def get_disco_sig(d):
                if d.get("library_key"):
                    return tuple(d["library_key"])
                return (d.get("title", ""), d.get("year", 0))

            for d in existing_disco:
                sig = get_disco_sig(d)
                seen_disco.add(sig)
                final_disco.append(d)

            for d in new_disco:
                sig = get_disco_sig(d)
                if sig not in seen_disco:
                    final_disco.append(d)
                    seen_disco.add(sig)

            result["discography"] = final_disco

        result["last_modified"] = time.time()
        return result

    def fetch_wikipedia_data(self, query: str, lang: str = "ru") -> dict:
        """
        Fetches summary data from the Wikipedia REST API for a given query and language.

        Returns:
            dict|None: A dictionary containing title, HTML content, and an image URL, or None if the query fails or returns a 404.
        """
        if not query:
            return None

        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"

        headers = {"User-Agent": "VinyllerPlayer/1.0"}

        try:
            response = requests.get(url, timeout=10, headers=headers)

            if response.status_code == 404:
                return None

            response.raise_for_status()

            if response.text.strip():
                data = response.json()

                page_url = ""
                if "content_urls" in data and "desktop" in data["content_urls"]:
                    page_url = data["content_urls"]["desktop"].get("page", "")
                else:
                    page_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(data.get('title', query))}"

                return {
                    "title": data.get("title", ""),
                    "content": data.get("extract_html", data.get("extract", "")),
                    "image_url": data.get("thumbnail", {}).get("source"),
                    "source_url": page_url
                }
            return None
        except Exception as e:
            print(f"Wikipedia Fetch Detail Error: {e}")
            return None

    def cache_image_from_url(self, url):
        """
        Downloads an image from a URL and passes it to the internal caching mechanism.
        Returns the absolute path to the local cached file.
        """
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
                    tf.write(response.content)
                    temp_path = tf.name

                return self.cache_image(temp_path)
        except Exception as e:
            print(f"Error downloading image from URL: {e}")
        return None

    def download_and_cache_image(self, url, max_size=1024):
        """
        Downloads an image from a link, saving it temporarily before caching it to
        the encyclopedia data folder. Detects the content type (JPG/PNG).
        Returns the final cached file path.
        """
        if not url:
            return None

        if isinstance(url, dict):
            url = url.get("path", url.get("url", ""))

        headers = {"User-Agent": "VinyllerPlayer/1.0"}
        try:
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()

            suffix = ".jpg"
            if "image/png" in response.headers.get("Content-Type", ""):
                suffix = ".png"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                tf.write(response.content)
                temp_path = tf.name

            final_path = self.cache_image(temp_path, max_size=max_size)

            if os.path.exists(temp_path):
                os.remove(temp_path)

            return final_path
        except Exception as e:
            print(f"Error downloading Wikipedia image: {e}")
            return None

    def bulk_update_relations(self, selected_items, action="link"):
        """
        Performs a batch update of relations between multiple items.
        Action can be 'link' (creates bi-directional connections between all selected items)
        or 'break' (removes connections linking them together).
        """
        if not selected_items:
            return

        data = self.load_data()
        modified = False

        def get_item_id(item):
            key = item["key"]
            if item["type"] == "album" and isinstance(key, (list, tuple)):
                lst = list(key)
                while len(lst) < 3:
                    lst.append(0)
                key = tuple(lst[:3])
            return item["type"], (
                json.dumps(list(key), ensure_ascii=False) if isinstance(key, tuple) else str(key)
            )

        group_ids = {get_item_id(i) for i in selected_items}

        for src_item in selected_items:
            src_type = src_item["type"]
            src_key_raw = src_item["key"]
            if src_type == "album" and isinstance(src_key_raw, (list, tuple)):
                lst = list(src_key_raw)
                while len(lst) < 3:
                    lst.append(0)
                src_key_raw = tuple(lst[:3])

            src_key_str = (
                json.dumps(list(src_key_raw), ensure_ascii=False)
                if isinstance(src_key_raw, tuple)
                else str(src_key_raw)
            )

            if src_type not in data:
                data[src_type] = {}
            if src_key_str not in data[src_type]:
                data[src_type][src_key_str] = {
                    "last_modified": time.time(),
                    "relations": [],
                    "blocks": [],
                }

            entry = data[src_type][src_key_str]
            current_rels = entry.get("relations", [])

            existing_rel_ids = {
                (
                    r["type"],
                    (
                        json.dumps(list(r["key"]), ensure_ascii=False)
                        if isinstance(r["key"], list)
                        else str(r["key"])
                    ),
                )
                for r in current_rels
            }

            new_rels = list(current_rels)
            src_id = get_item_id(src_item)

            if action == "link":
                for target_item in selected_items:
                    target_id = get_item_id(target_item)
                    if target_id != src_id and target_id not in existing_rel_ids:
                        new_rels.append(
                            {
                                "key": target_item["key"],
                                "type": target_item["type"],
                                "name": target_item["name"],
                                "subtitle": target_item.get("subtitle", ""),
                            }
                        )
                        existing_rel_ids.add(target_id)
                        modified = True
            elif action == "break":
                filtered_rels = [
                    r
                    for r in current_rels
                    if (
                        r["type"],
                        (
                            json.dumps(list(r["key"]), ensure_ascii=False)
                            if isinstance(r["key"], list)
                            else str(r["key"])
                        ),
                    )
                    not in group_ids
                ]
                if len(filtered_rels) < len(current_rels):
                    new_rels = filtered_rels
                    modified = True

            if modified:
                entry["relations"] = new_rels
                entry["last_modified"] = time.time()

        if modified:
            self.save_data(data)


class FetchWorker(QThread):
    """
    A PyQt6 QThread worker class designed to fetch encyclopedia summary data
    and associated images from Wikipedia asynchronously.
    """
    finished = pyqtSignal(dict)

    def __init__(self, manager, query, lang):
        """
        Initializes the FetchWorker with the encyclopedia manager instance,
        the search query, and the designated language code.
        """
        super().__init__()
        self.manager = manager
        self.query = query
        self.lang = lang

    def run(self):
        """
        Executes the fetch operation in a background thread. Calls the Wikipedia API,
        downloads and caches the resulting image if available, and emits the finished signal.
        """
        result = self.manager.fetch_wikipedia_data(self.query, self.lang)

        if result and result.get("image_url"):
            local_path = self.manager.download_and_cache_image(
                result["image_url"], max_size=1024
            )
            if local_path:
                result["local_image_path"] = local_path

        self.finished.emit(result if result else {})