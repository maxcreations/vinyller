# Copyright (C) 2026 Maxim Moshkin
# Licensed under the MIT License.

import os
import importlib.util
import json

# --- SETTINGS ---
TRANSLATIONS_DIR = "../translations"
DICT_NAME = "TRANSLATIONS"
REFERENCE_FILE = "ru.py"
COMMENT_PREFIX = "    # ⚠️ WARNING (relative to reference):"
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


def get_markers_in_value(value):
    """Finds all formatting markers present in a translation value."""
    found_markers = set()
    for marker in MARKERS_TO_CHECK:
        if isinstance(value, str):
            if marker in value:
                found_markers.add(marker)
        elif isinstance(value, list):
            if any(isinstance(v, str) and marker in v for v in value):
                found_markers.add(marker)
    return found_markers


def get_marker_discrepancies(ref_value, target_value):
    """Compares target value against reference value for missing and extra markers."""
    ref_markers = get_markers_in_value(ref_value)
    target_markers = get_markers_in_value(target_value)

    missing = ref_markers - target_markers
    extra = target_markers - ref_markers

    return missing, extra


def process_file(filepath, ref_translations):
    """Scans the target file and adds comments for formatting discrepancies relative to reference."""
    filename = os.path.basename(filepath)
    if filename == REFERENCE_FILE:
        return

    target_translations = load_existing_translations(filepath)
    if not target_translations:
        return

    problematic_keys = {}
    for key, target_value in target_translations.items():
        if key in ref_translations:
            ref_value = ref_translations[key]
            missing, extra = get_marker_discrepancies(ref_value, target_value)
            if missing or extra:
                problematic_keys[key] = {"missing": missing, "extra": extra}

    if not problematic_keys:
        print(f"✅ {filename}: All line breaks and tags match the reference ({REFERENCE_FILE}).")
        return

    print(f"⚠️ {filename}: Found {len(problematic_keys)} keys with discrepancies. Updating comments...")

    formatted_problems = {json.dumps(k, ensure_ascii=False): v for k, v in problematic_keys.items()}

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_line = line.lstrip()

        if stripped_line.startswith(COMMENT_PREFIX.strip()):
            i += 1
            continue

        found_key = None
        for f_key in formatted_problems.keys():
            if stripped_line.startswith(f_key + ":"):
                found_key = f_key
                break

        if found_key:
            probs = formatted_problems[found_key]
            messages = []
            if probs["missing"]:
                missing_str = ", ".join(probs["missing"]).replace('\n', '\\n')
                messages.append(f"Missing: [{missing_str}]")
            if probs["extra"]:
                extra_str = ", ".join(probs["extra"]).replace('\n', '\\n')
                messages.append(f"Extra: [{extra_str}]")

            comment_line = f"{COMMENT_PREFIX} {', '.join(messages)}\n"
            new_lines.append(comment_line)

        new_lines.append(line)
        i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


def main():
    if not os.path.exists(TRANSLATIONS_DIR):
        print(f"❌ Directory {TRANSLATIONS_DIR} not found!")
        return

    ref_filepath = os.path.join(TRANSLATIONS_DIR, REFERENCE_FILE)
    if not os.path.exists(ref_filepath):
        print(f"❌ Reference file {ref_filepath} not found!")
        return

    print(f"📖 Loading reference: {REFERENCE_FILE}...")
    ref_translations = load_existing_translations(ref_filepath)
    if not ref_translations:
        print(f"❌ Failed to read TRANSLATIONS dictionary from reference.")
        return

    translation_files = [f for f in os.listdir(TRANSLATIONS_DIR) if f.endswith(".py") and f != "__init__.py"]

    for trans_file in translation_files:
        process_file(os.path.join(TRANSLATIONS_DIR, trans_file), ref_translations)


if __name__ == "__main__":
    main()