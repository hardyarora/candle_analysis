#!/usr/bin/env python3
"""
CLI tool for candle analysis AI agent.

This tool reads JSON candle analysis files and formats them for AI agent consumption.
Supports batch processing (default) and single file mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from candle_data_formatter import (
    format_for_ai_agent,
    format_json_output,
    format_text_output,
    load_json_file,
)


def find_json_files(directory: Path) -> list[Path]:
    """
    Find all JSON files in a directory.

    Args:
        directory: Directory path to search

    Returns:
        List of Path objects for JSON files found
    """
    if not directory.is_dir():
        return []

    json_files = sorted(directory.glob("*.json"))
    return json_files


def process_single_file(
    file_path: Path, output_format: str = "both"
) -> tuple[dict[str, Any], str]:
    """
    Process a single JSON file and return formatted output.

    Args:
        file_path: Path to JSON file
        output_format: Output format ('text', 'json', or 'both')

    Returns:
        Tuple of (analysis_data, formatted_output_string)
    """
    try:
        json_data = load_json_file(file_path)
        analysis = format_for_ai_agent(json_data)

        output_parts: list[str] = []

        if output_format in ("text", "both"):
            text_output = format_text_output(analysis)
            output_parts.append(text_output)

        if output_format in ("json", "both"):
            json_output = format_json_output(analysis)
            json_str = json.dumps(json_output, indent=2, ensure_ascii=False)
            if output_format == "both":
                output_parts.append("\n" + "=" * 80)
                output_parts.append("JSON Output:")
                output_parts.append("=" * 80)
            output_parts.append(json_str)

        return analysis, "\n".join(output_parts)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def process_batch(
    directory: Path, output_format: str = "both"
) -> tuple[list[dict[str, Any]], str]:
    """
    Process all JSON files in a directory.

    Args:
        directory: Directory path containing JSON files
        output_format: Output format ('text', 'json', or 'both')

    Returns:
        Tuple of (list of analysis_data, combined_formatted_output_string)
    """
    json_files = find_json_files(directory)

    if not json_files:
        print(f"Warning: No JSON files found in {directory}", file=sys.stderr)
        return [], ""

    all_analyses: list[dict[str, Any]] = []
    output_parts: list[str] = []

    print(f"Processing {len(json_files)} JSON file(s)...", file=sys.stderr)

    for i, json_file in enumerate(json_files, 1):
        print(f"[{i}/{len(json_files)}] Processing {json_file.name}...", file=sys.stderr)
        analysis, output = process_single_file(json_file, output_format)
        all_analyses.append(analysis)

        if output_format == "both":
            output_parts.append(f"\n{'=' * 80}")
            output_parts.append(f"File: {json_file.name}")
            output_parts.append(f"{'=' * 80}\n")
        elif output_format == "text":
            output_parts.append(f"\n{'=' * 80}")
            output_parts.append(f"File: {json_file.name}")
            output_parts.append(f"{'=' * 80}\n")

        output_parts.append(output)

        if i < len(json_files) and output_format != "json":
            output_parts.append("\n")

    return all_analyses, "\n".join(output_parts)


def main() -> None:
    """Main entry point for the CLI tool."""
    parser = argparse.ArgumentParser(
        description="Candle Analysis AI Agent - Process JSON candle analysis files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all JSON files in a directory (batch mode, default)
  python candle_analysis_agent.py /path/to/directory

  # Process a single JSON file
  python candle_analysis_agent.py --single /path/to/file.json

  # Output only text format
  python candle_analysis_agent.py /path/to/directory --format text

  # Output only JSON format
  python candle_analysis_agent.py /path/to/directory --format json

  # Output both formats (default)
  python candle_analysis_agent.py /path/to/directory --format both
        """,
    )

    parser.add_argument(
        "path",
        type=str,
        help="Path to JSON file (with --single) or directory (batch mode)",
    )

    parser.add_argument(
        "--single",
        action="store_true",
        help="Process a single file instead of batch processing",
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "both"],
        default="both",
        help="Output format: 'text' for human-readable, 'json' for structured JSON, 'both' for both (default: both)",
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Optional output file path. If not specified, output goes to stdout",
    )

    args = parser.parse_args()

    path = Path(args.path)

    # Validate path
    if args.single:
        if not path.is_file():
            print(f"Error: File not found: {path}", file=sys.stderr)
            sys.exit(1)
        if not path.suffix.lower() == ".json":
            print(f"Error: File must be a JSON file: {path}", file=sys.stderr)
            sys.exit(1)
    else:
        if not path.is_dir():
            print(f"Error: Directory not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Process files
    if args.single:
        _, output = process_single_file(path, args.format)
    else:
        _, output = process_batch(path, args.format)

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Output written to: {output_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()







