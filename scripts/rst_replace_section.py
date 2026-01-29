#!/usr/bin/env python3
"""Replace the contents of an RST section with contents from another file.

The section is identified by a label that appears right before it.
"""

import argparse
import re
import sys


# RST section characters in order of precedence (most to least significant)
SECTION_CHARS = ['=', '-', '`', ':', "'", '"', '~', '^', '_', '*', '+', '#']


def get_section_level(underline: str) -> int | None:
    """Get the section level from an underline character.

    Returns None if not a valid underline.
    """
    if not underline.strip():
        return None
    char = underline.strip()[0]
    if char in SECTION_CHARS and underline.strip() == char * len(underline.strip()):
        return SECTION_CHARS.index(char)
    return None


def is_section_underline(line: str, prev_line: str) -> bool:
    """Check if a line is a section underline for the previous line."""
    if not line.strip() or not prev_line.strip():
        return False
    char = line.strip()[0]
    if char not in SECTION_CHARS:
        return False
    if line.strip() != char * len(line.strip()):
        return False
    # Underline must be at least as long as the title
    return len(line.rstrip()) >= len(prev_line.rstrip())


def replace_section(rst_content: str, label: str, new_content: str) -> str:
    """Replace a section's content identified by a label.

    Args:
        rst_content: The RST file content
        label: The label before the section (e.g., 'qb-impl' for '.. _qb-impl:')
        new_content: The new content to insert

    Returns:
        The modified RST content
    """
    lines = rst_content.split('\n')

    # Find the label
    label_pattern = re.compile(rf'^\.\.\s+_({re.escape(label)}|#{re.escape(label)}):\s*$')
    label_idx = None
    for i, line in enumerate(lines):
        if label_pattern.match(line):
            label_idx = i
            break

    if label_idx is None:
        raise ValueError(f"Label '{label}' not found in RST content")

    # Find the section heading after the label
    section_title_idx = None
    section_underline_idx = None
    section_level = None

    for i in range(label_idx + 1, len(lines) - 1):
        if is_section_underline(lines[i + 1], lines[i]):
            section_title_idx = i
            section_underline_idx = i + 1
            section_level = get_section_level(lines[i + 1])
            break

    if section_title_idx is None or section_underline_idx is None or section_level is None:
        raise ValueError(f"No section heading found after label '{label}'")

    # Find where the section ends (next section at same or higher level)
    section_end_idx = len(lines)

    # Pattern to match RST labels like ".. _label-name:" or ".. _#label-name:"
    label_pattern = re.compile(r'^\.\.\s+_#?[\w-]+:\s*$')

    for i in range(section_underline_idx + 1, len(lines) - 1):
        if is_section_underline(lines[i + 1], lines[i]):
            next_level = get_section_level(lines[i + 1])
            if next_level is not None and next_level <= section_level:
                # Walk backward past blank lines and labels to find all labels
                # that belong to this next section
                section_end_idx = i

                idx = i
                while idx > section_underline_idx + 1:
                    prev_line = lines[idx - 1]
                    if label_pattern.match(prev_line):
                        idx -= 1
                        section_end_idx = idx
                    elif not prev_line.strip():
                        idx -= 1
                    else:
                        break
                break

    # Build the result
    result_lines = []

    # Everything up to and including the section underline
    result_lines.extend(lines[:section_underline_idx + 1])

    # Add blank line after heading if new content doesn't start with one
    new_content_lines = new_content.rstrip('\n').split('\n')
    if new_content_lines and new_content_lines[0].strip():
        result_lines.append('')

    # Add the new content
    result_lines.extend(new_content_lines)

    # Add blank line before next section if needed (when content doesn't end with one)
    if section_end_idx < len(lines):
        if result_lines and result_lines[-1].strip():
            result_lines.append('')
        result_lines.append('')

    # Everything from the next section onwards
    result_lines.extend(lines[section_end_idx:])

    return '\n'.join(result_lines)


def main():
    parser = argparse.ArgumentParser(
        description='Replace an RST section with content from another file'
    )
    parser.add_argument(
        'rst_file',
        help='The RST file to modify'
    )
    parser.add_argument(
        'label',
        help='The label identifying the section (e.g., "qb-impl" for ".. _qb-impl:")'
    )
    parser.add_argument(
        'content_file',
        nargs='?',
        type=argparse.FileType('r'),
        default=sys.stdin,
        help='File containing new section content (default: stdin)'
    )
    parser.add_argument(
        '-i', '--in-place',
        action='store_true',
        help='Modify the RST file in place'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output file (default: stdout, or same as input with -i)'
    )

    args = parser.parse_args()

    with open(args.rst_file, 'r') as f:
        rst_content = f.read()

    new_content = args.content_file.read()

    result = replace_section(rst_content, args.label, new_content)

    if args.in_place:
        with open(args.rst_file, 'w') as f:
            f.write(result)
    elif args.output:
        with open(args.output, 'w') as f:
            f.write(result)
    else:
        sys.stdout.write(result)


if __name__ == '__main__':
    main()
