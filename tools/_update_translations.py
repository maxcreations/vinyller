# Copyright (C) 2026 Maxim Moshkin
# Licensed under the MIT License.

import ast
import importlib.util
import json
import os
import re
from datetime import datetime

# --- SETTINGS ---
SOURCE_DIR = "../src"
TRANSLATIONS_DIR = "../translations"
DICT_NAME = "TRANSLATIONS"
ADD_TOOLTIP_COMMENTS = False
# ----------------


def extract_keys_from_file(filepath):
    """Searches for translate("String") calls and identifies tooltips."""
    keys_with_pos = []
    tooltip_keys = set()

    with open(filepath, "r", encoding = "utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)

        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "translate":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if isinstance(node.args[0].value, str):
                            key = node.args[0].value
                            keys_with_pos.append(
                                (node.lineno, node.col_offset, key)
                            )

                            current = node
                            is_tooltip = False

                            for _ in range(3):
                                if hasattr(current, 'parent'):
                                    parent = current.parent
                                    if isinstance(parent, ast.Call):
                                        if getattr(parent.func, 'attr', '') == 'setToolTip' or getattr(parent.func,
                                                                                                       'id',
                                                                                                       '') == 'setToolTip':
                                            is_tooltip = True
                                            break
                                    current = parent
                                else:
                                    break

                            if is_tooltip:
                                tooltip_keys.add(key)

        keys_with_pos.sort(key = lambda x: (x[0], x[1]))
        return [k[2] for k in keys_with_pos], tooltip_keys

    except Exception as e:
        print(f"⚠️ AST warning for {filepath}: {e}")
        pattern = r'(?<!f)translate\(\s*["\'](.*?)["\']'
        return re.findall(pattern, content), set()


def load_existing_translations(filepath):
    """Loads the current translation file as a Python module."""
    if not os.path.exists(filepath):
        return {}

    module_name = os.path.splitext(os.path.basename(filepath))[0]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        if hasattr(module, DICT_NAME):
            return getattr(module, DICT_NAME)
    except Exception as e:
        print(f"❌ Error loading {filepath}: {e}")
    return {}


def force_double_quotes(val):
    if isinstance(val, str):
        return json.dumps(val, ensure_ascii = False)
    return repr(val)


def format_value(value):
    if isinstance(value, list):
        formatted_list = "[\n"
        for item in value:
            formatted_list += f"        {force_double_quotes(item)},\n"
        formatted_list += "    ]"
        return formatted_list
    else:
        return force_double_quotes(value)


def process_translation_file(filepath, file_map, found_keys_set, tooltip_keys_set):
    """Updates a specific translation file."""
    existing_data = load_existing_translations(filepath)
    filename_lang = os.path.basename(filepath)

    new_content = [
        f"# {TRANSLATIONS_DIR}/{filename_lang}",
        f"# Updated by _update_translations.py at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"{DICT_NAME} = {{",
    ]

    written_keys = set()
    new_keys_count = 0

    for source_file, keys in file_map.items():
        keys_to_write = [k for k in keys if k not in written_keys]
        if not keys_to_write:
            continue

        new_content.append(f"\n    # --- {source_file} ---")
        for key in keys_to_write:
            formatted_key = force_double_quotes(key)

            if ADD_TOOLTIP_COMMENTS and key in tooltip_keys_set:
                new_content.append("    # tooltip:")

            if key not in existing_data:
                val = key
                new_keys_count += 1
                line = f"    # --- New string: ---\n    # {formatted_key}: {format_value(val)},"
            else:
                val = existing_data[key]
                line = f"    {formatted_key}: {format_value(val)},"

            new_content.append(line)
            written_keys.add(key)

    remaining_keys = [k for k in existing_data.keys() if k not in written_keys]
    if remaining_keys:
        new_content.append(
            "\n    # --- Other / Dynamic / Not found in source files ---"
        )
        for key in sorted(remaining_keys):
            val = existing_data[key]
            new_content.append(f"    {force_double_quotes(key)}: {format_value(val)},")

    new_content.append("}")

    with open(filepath, "w", encoding = "utf-8") as f:
        f.write("\n".join(new_content) + "\n")

    print(
        f"💾 Updated {filename_lang}: {len(written_keys)} used, {len(remaining_keys)} unused/custom, {new_keys_count} new."
    )


def main():
    print(f"🔍 Scanning source code in: {os.path.abspath(SOURCE_DIR)}")

    file_map = {}
    found_keys_set = set()
    tooltip_keys_set = set()

    ignore_dirs = ["venv", ".git", "__pycache__", TRANSLATIONS_DIR]

    for root, dirs, files in os.walk(SOURCE_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in sorted(files):
            if file.endswith(".py") and file != "update_translations.py":
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, SOURCE_DIR)

                found_keys, found_tooltips = extract_keys_from_file(filepath)

                if found_keys:
                    unique_found = list(dict.fromkeys(found_keys))
                    file_map[rel_path] = unique_found
                    found_keys_set.update(unique_found)
                    tooltip_keys_set.update(found_tooltips)

    print(f"✅ Found {len(found_keys_set)} unique keys in source code.")

    if not os.path.exists(TRANSLATIONS_DIR):
        print(f"❌ Directory {TRANSLATIONS_DIR} not found!")
        return

    translation_files = [
        f
        for f in os.listdir(TRANSLATIONS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    ]

    if not translation_files:
        print(f"⚠️ No translation files found in {TRANSLATIONS_DIR}")
        return

    for trans_file in translation_files:
        full_path = os.path.join(TRANSLATIONS_DIR, trans_file)
        process_translation_file(full_path, file_map, found_keys_set, tooltip_keys_set)


if __name__ == "__main__":
    main()