"""
Vinyller — autobuild version update tools
Copyright (C) 2026 Maxim Moshkin
Licensed under GPL-3.0
"""

import os
import re
import sys

if len(sys.argv) < 2:
    print("ERROR: No version tag provided.")
    sys.exit(1)

tag = sys.argv[1]
version = tag.lstrip('v')

# Format the tuple for Windows (1.0.9 -> 1, 0, 9, 0)
parts = version.split('.')
while len(parts) < 4:
    parts.append('0')
v_tuple = f"{parts[0]}, {parts[1]}, {parts[2]}, {parts[3]}"


def patch_file(filepath, replacements):
    if not os.path.exists(filepath):
        print(f"WARNING: {filepath} not found, skipping.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    for pattern, replacement in replacements:
        # subn returns a tuple: (new_text, replacement_count)
        new_content, count = re.subn(pattern, replacement, new_content, flags=re.IGNORECASE)
        print(f"INFO: {filepath} -> {count} replacements for pattern '{pattern}'")

    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)


# 1. Windows properties (version_info.txt)
patch_file('version_info.txt', [
    (r'(filevers\s*=\s*)\([^)]+\)', r'\g<1>(' + v_tuple + ')'),
    (r'(prodvers\s*=\s*)\([^)]+\)', r'\g<1>(' + v_tuple + ')'),
    (r"(StringStruct\s*\(\s*['\"]FileVersion['\"]\s*,\s*['\"]).*?(['\"])", r'\g<1>' + version + r'\g<2>'),
    (r"(StringStruct\s*\(\s*['\"]ProductVersion['\"]\s*,\s*['\"]).*?(['\"])", r'\g<1>' + version + r'\g<2>')
])

# 2. Internal constants (constants.py)
patch_file('src/utils/constants.py', [
    (r'(APP_VERSION\s*=\s*["\']).*?(["\'])', r'\g<1>' + version + r'\g<2>')
])

# 3. Inno Setup installer (installer.iss)
patch_file('installer.iss', [
    (r'(AppVersion=).*', r'\g<1>' + version)
])

# 4. Project metadata (pyproject.toml)
patch_file('pyproject.toml', [
    (r'(version\s*=\s*["\']).*?(["\'])', r'\g<1>' + version + r'\g<2>')
])