# Copyright (C) 2026 Maxim Moshkin
# Licensed under the MIT License.

import os
import importlib.util
import json

# --- SETTINGS ---
TRANSLATIONS_DIR = "../translations"
DICT_NAME = "TRANSLATIONS"
COMMENT_PREFIX = "    # ⚠️ WARNING: Missing line break or tag in translation"
MARKERS_TO_CHECK = ['\n', '\\n', '<br>', '<br/>', '<br />']
# ----------------

def load_existing_translations(filepath):
    """Loads the translation dictionary from the file."""
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


def get_missing_markers(key, value):
    """Checks which line-break markers are in the key but missing in the value."""
    missing = []
    for marker in MARKERS_TO_CHECK:
        if marker in key:
            if isinstance(value, str):
                if marker not in value:
                    missing.append(marker)
            elif isinstance(value, list):
                if any(isinstance(v, str) and marker not in v for v in value):
                    missing.append(marker)
    return missing


def process_file(filepath):
    """Scans the file and adds comments for missing line breaks."""
    translations = load_existing_translations(filepath)
    if not translations:
        return

    problematic_keys = {}
    for key, value in translations.items():
        missing = get_missing_markers(key, value)
        if missing:
            problematic_keys[key] = missing

    filename = os.path.basename(filepath)
    if not problematic_keys:
        print(f"✅ {filename}: All line breaks are present.")
        return

    print(f"⚠️ {filename}: Found {len(problematic_keys)} keys with missing line breaks. Adding comments...")

    formatted_problems = {json.dumps(k, ensure_ascii=False): m for k, m in problematic_keys.items()}

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_line = line.lstrip()

        found_key = None
        for f_key in formatted_problems.keys():
            if stripped_line.startswith(f_key + ":"):
                found_key = f_key
                break

        if found_key:
            markers_str = ", ".join(formatted_problems[found_key]).replace('\n', '\\n')
            comment_line = f"{COMMENT_PREFIX} ({markers_str})\n"

            if i == 0 or COMMENT_PREFIX not in lines[i - 1]:
                new_lines.append(comment_line)

        new_lines.append(line)
        i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


def main():
    if not os.path.exists(TRANSLATIONS_DIR):
        print(f"❌ Directory {TRANSLATIONS_DIR} not found!")
        return

    translation_files = [f for f in os.listdir(TRANSLATIONS_DIR) if f.endswith(".py") and f != "__init__.py"]

    if not translation_files:
        print(f"⚠️ No translation files found in {TRANSLATIONS_DIR}")
        return

    for trans_file in translation_files:
        process_file(os.path.join(TRANSLATIONS_DIR, trans_file))


if __name__ == "__main__":
    main()