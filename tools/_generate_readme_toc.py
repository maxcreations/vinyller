# Copyright (C) 2026 Maxim Moshkin
# Licensed under the MIT License.

import sys
import re
import os

# --- SETTINGS ---
FILE_NAME = "../docs/MANUAL.ru.md"
MAX_DEPTH = 3
# ----------------

def generate_anchor(text, existing_slugs):
    """Generates a GitHub-style anchor link."""
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = slug.strip().replace(' ', '-')

    if slug in existing_slugs:
        existing_slugs[slug] += 1
        slug = f"{slug}-{existing_slugs[slug]}"
    else:
        existing_slugs[slug] = 0

    return slug


def generate_toc(filename, max_depth):
    toc_lines = []
    existing_slugs = {}
    in_code_block = False

    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line in file:
                stripped_line = line.strip()

                if stripped_line.startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    continue

                match = re.match(r'^(#{1,6})\s+(.*)', stripped_line)

                if match:
                    hashes, title = match.groups()
                    level = len(hashes)
                    title = title.strip()

                    if level > max_depth:
                        continue

                    anchor = generate_anchor(title, existing_slugs)
                    indent = '  ' * (level - 1)
                    toc_entry = f"{indent}* [{title}](#{anchor})"
                    toc_lines.append(toc_entry)

        return toc_lines

    except FileNotFoundError:
        return [f"❌ Error: File '{filename}' not found."]
    except Exception as e:
        return [f"❌ An error occurred: {e}"]


if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else FILE_NAME

    print(f"--- Generating TOC for '{target_file}' (Depth: {MAX_DEPTH}) ---\n")

    toc = generate_toc(target_file, MAX_DEPTH)

    if not toc:
        print("No headings found or file is empty.")
    else:
        for line in toc:
            print(line)

    print("\n--- End ---")