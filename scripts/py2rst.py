#!/usr/bin/env python3
"""Convert Python source code to reStructuredText.

Top-level docstrings become regular RST text, everything else becomes
code blocks.
"""

import argparse
import re
import sys


def convert_py_to_rst(source: str) -> str:
    """Convert Python source to RST.

    Args:
        source: Python source code

    Returns:
        reStructuredText content
    """
    lines = source.split('\n')
    result: list[str] = []
    code_buffer: list[str] = []
    i = 0

    def flush_code():
        """Flush accumulated code as a code block."""
        nonlocal code_buffer
        # Strip leading/trailing empty lines from code buffer
        while code_buffer and not code_buffer[0].strip():
            code_buffer.pop(0)
        while code_buffer and not code_buffer[-1].strip():
            code_buffer.pop()

        if code_buffer:
            result.append('::')
            result.append('')
            for line in code_buffer:
                result.append('    ' + line if line.strip() else '')
            result.append('')
        code_buffer = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check for start of a top-level docstring (triple quotes at column 0)
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]

            # Flush any pending code
            flush_code()

            # Check if it's a single-line docstring
            if stripped.count(quote) >= 2 and stripped.endswith(quote) and len(stripped) > 6:
                # Single line docstring: """text"""
                docstring_content = stripped[3:-3]
                result.append(docstring_content)
                result.append('')
                i += 1
                continue

            # Multi-line docstring
            docstring_lines: list[str] = []

            # Handle first line - might have content after opening quotes
            first_line_content = stripped[3:]
            if first_line_content:
                docstring_lines.append(first_line_content)

            i += 1

            # Collect lines until closing quotes
            while i < len(lines):
                docline = lines[i]
                if quote in docline:
                    # Found closing quotes
                    end_idx = docline.find(quote)
                    final_content = docline[:end_idx]
                    if final_content.strip():
                        docstring_lines.append(final_content.rstrip())
                    i += 1
                    break
                else:
                    docstring_lines.append(docline.rstrip())
                    i += 1

            # Output docstring content as RST text
            for dline in docstring_lines:
                result.append(dline)
            result.append('')

        else:
            # Regular code line
            code_buffer.append(line)
            i += 1

    # Flush any remaining code
    flush_code()

    # Clean up multiple consecutive blank lines
    output: list[str] = []
    prev_blank = False
    for line in result:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        output.append(line)
        prev_blank = is_blank

    # Remove trailing blank lines
    while output and not output[-1].strip():
        output.pop()

    return '\n'.join(output) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description='Convert Python source to reStructuredText'
    )
    parser.add_argument(
        'input',
        nargs='?',
        type=argparse.FileType('r'),
        default=sys.stdin,
        help='Input Python file (default: stdin)'
    )
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help='Output RST file (default: stdout)'
    )
    parser.add_argument(
        '--start',
        type=str,
        default=None,
        help='Start marker comment (content after this line)'
    )
    parser.add_argument(
        '--end',
        type=str,
        default=None,
        help='End marker comment (content before this line)'
    )

    args = parser.parse_args()

    source = args.input.read()

    # Extract section between markers if specified
    if args.start or args.end:
        lines = source.split('\n')
        start_idx = 0
        end_idx = len(lines)

        if args.start:
            for idx, line in enumerate(lines):
                if args.start in line:
                    start_idx = idx + 1
                    break

        if args.end:
            for idx, line in enumerate(lines):
                if args.end in line:
                    end_idx = idx
                    break

        source = '\n'.join(lines[start_idx:end_idx])

    rst = convert_py_to_rst(source)
    args.output.write(rst)


if __name__ == '__main__':
    main()
