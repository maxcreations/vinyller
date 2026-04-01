# Copyright (C) 2026 Maxim Moshkin
# Licensed under the MIT License.

import io
import os
import tokenize

# --- SETTINGS ---
KEEP_DOCSTRINGS = True
KEEP_EMPTY_LINES = False
ADD_SUFFIX = True
SUFFIX = "_cleaned"
OUTPUT_DIR = "cleaned_files"
# ----------------

def clean_python_file(filepath, output_directory=""):
    """
    Removes comments and (optionally) docstrings.
    If KEEP_EMPTY_LINES is False, it only removes lines that are empty
    specifically because a comment or docstring was removed from them.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    source = "".join(lines)
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)

    to_delete = []
    prev_toktype = None
    modified_lines = set()

    for toktype, tokval, start, end, line in tokens:
        if toktype == tokenize.COMMENT:
            to_delete.append((start, end))
            modified_lines.add(start[0])

        elif not KEEP_DOCSTRINGS and toktype == tokenize.STRING:
            if prev_toktype in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL) or prev_toktype is None:
                to_delete.append((start, end))
                for r in range(start[0], end[0] + 1):
                    modified_lines.add(r)

        if toktype not in (tokenize.NL, tokenize.NEWLINE):
            prev_toktype = toktype

    lines_list = list(lines)

    for (s_row, s_col), (e_row, e_col) in reversed(to_delete):
        row_idx = s_row - 1
        end_row_idx = e_row - 1

        if row_idx == end_row_idx:
            line = lines_list[row_idx]
            lines_list[row_idx] = line[:s_col] + line[e_col:]
        else:
            lines_list[row_idx] = lines_list[row_idx][:s_col] + "\n"
            for i in range(row_idx + 1, end_row_idx):
                lines_list[i] = "\n"
            lines_list[end_row_idx] = lines_list[end_row_idx][e_col:]

    processed_lines = []
    for i, line in enumerate(lines_list):
        line_number = i + 1
        stripped_line = line.strip()

        if not KEEP_EMPTY_LINES and not stripped_line and line_number in modified_lines:
            continue

        processed_lines.append(line.rstrip())

    cleaned_code = "\n".join(processed_lines)

    original_filename = os.path.basename(filepath)
    name, ext = os.path.splitext(original_filename)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)
        new_filepath = os.path.join(output_directory, f"{name}{SUFFIX}{ext}" if ADD_SUFFIX else f"{name}{ext}")
    else:
        base_dir = os.path.dirname(filepath)
        new_filepath = os.path.join(base_dir, f"{name}{SUFFIX}{ext}" if ADD_SUFFIX else f"{name}{ext}")

    with open(new_filepath, 'w', encoding='utf-8') as f:
        f.write(cleaned_code)
    return new_filepath


def main():
    current_script = os.path.basename(__file__)
    for filename in os.listdir('.'):
        if filename.endswith('.py') and filename != current_script and SUFFIX not in filename:
            try:
                res = clean_python_file(filename, OUTPUT_DIR)
                print(f"✅ Success: {filename} -> {res}")
            except Exception as e:
                print(f"❌ Error in {filename}: {e}")

if __name__ == "__main__":
    main()