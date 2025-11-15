import difflib
import sys
import os
from pathlib import Path
import traceback

from aksharamukha import transliterate
from colorama import Fore, Back, Style, init as colorama_init

colorama_init(autoreset=True)

from grantha_converter.devanagari_repair import extract_devanagari


def normalize_devanagari_for_comparison(text: str) -> str:
    """Normalize Devanagari text to ignore non-consequential variations.

    Args:
        text: Devanagari text to normalize

    Returns:
        Normalized text with equivalent characters unified
    """
    # Normalize double danda variations
    # ॥ (U+0965 double danda) ↔ ।। (U+0964 U+0964 two single dandas)
    text = text.replace('॥', '।।')

    # Could add more normalizations here as needed:
    # - Zero-width joiners/non-joiners
    # - Various space characters
    # - Nukta variations

    return text


def show_inline_char_diff(text1: str, text2: str, title: str, context_chars: int = 40, max_diffs: int = 10):
    """
    Generates and prints a compact character diff showing only differences with context.

    Args:
        text1: Original text
        text2: Modified text
        title: Title for the diff
        context_chars: Number of characters to show before/after each difference
        max_diffs: Maximum number of differences to show
    """
    print(f"\n{Fore.YELLOW}{'='*80}")
    print(f"{Fore.YELLOW}{title}")
    print(f"{Fore.YELLOW}{'='*80}{Style.RESET_ALL}")

    # Normalize for comparison to ignore non-consequential variations
    text1_normalized = normalize_devanagari_for_comparison(text1)
    text2_normalized = normalize_devanagari_for_comparison(text2)

    # Transliterate for easier reading
    try:
        text1_hk = transliterate.process("Devanagari", "HK", text1)
        text2_hk = transliterate.process("Devanagari", "HK", text2)
        show_transliteration = True
    except Exception as e:
        print(f"⚠️  Transliteration failed: {e}", file=sys.stderr)
        show_transliteration = False

    # Compare normalized versions
    matcher = difflib.SequenceMatcher(None, text1_normalized, text2_normalized, autojunk=False)

    # Collect all non-equal sections
    diffs = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            diffs.append((tag, i1, i2, j1, j2))

    if not diffs:
        print(f"{Fore.GREEN}✓ No differences found{Style.RESET_ALL}\n")
        return

    print(f"{Fore.CYAN}Found {len(diffs)} difference(s), showing first {min(len(diffs), max_diffs)}:{Style.RESET_ALL}\n")

    # Show each diff with context
    for idx, (tag, i1, i2, j1, j2) in enumerate(diffs[:max_diffs]):
        # Get context before (from normalized text)
        ctx_start1 = max(0, i1 - context_chars)
        ctx_start2 = max(0, j1 - context_chars)
        prefix1 = text1_normalized[ctx_start1:i1]
        prefix2 = text2_normalized[ctx_start2:j1]

        # Get context after (from normalized text)
        ctx_end1 = min(len(text1_normalized), i2 + context_chars)
        ctx_end2 = min(len(text2_normalized), j2 + context_chars)
        suffix1 = text1_normalized[i2:ctx_end1]
        suffix2 = text2_normalized[j2:ctx_end2]

        # Build the diff strings (using normalized text)
        if tag == 'replace':
            orig = f"{Style.DIM}{prefix1}{Style.RESET_ALL}{Back.YELLOW}{Fore.BLACK}{text1_normalized[i1:i2]}{Style.RESET_ALL}{Style.DIM}{suffix1}{Style.RESET_ALL}"
            modi = f"{Style.DIM}{prefix2}{Style.RESET_ALL}{Back.YELLOW}{Fore.BLACK}{text2_normalized[j1:j2]}{Style.RESET_ALL}{Style.DIM}{suffix2}{Style.RESET_ALL}"
        elif tag == 'delete':
            orig = f"{Style.DIM}{prefix1}{Style.RESET_ALL}{Back.RED}{Fore.BLACK}{text1_normalized[i1:i2]}{Style.RESET_ALL}{Style.DIM}{suffix1}{Style.RESET_ALL}"
            modi = f"{Style.DIM}{prefix2}{suffix2}{Style.RESET_ALL}"
        elif tag == 'insert':
            orig = f"{Style.DIM}{prefix1}{suffix1}{Style.RESET_ALL}"
            modi = f"{Style.DIM}{prefix2}{Style.RESET_ALL}{Back.GREEN}{Fore.BLACK}{text2_normalized[j1:j2]}{Style.RESET_ALL}{Style.DIM}{suffix2}{Style.RESET_ALL}"

        print(f"{Fore.CYAN}Diff {idx+1}/{len(diffs)} (pos {i1}-{i2}):{Style.RESET_ALL}")
        print(f"  {Style.DIM}Devanagari:{Style.RESET_ALL}")
        print(f"    {Style.DIM}Original:{Style.RESET_ALL} {orig}")
        print(f"    {Style.DIM}Modified:{Style.RESET_ALL} {modi}")

        # Show transliteration for easier reading
        if show_transliteration:
            # Get transliterated versions of the same regions (from normalized text)
            prefix1_hk = transliterate.process("Devanagari", "HK", prefix1)
            prefix2_hk = transliterate.process("Devanagari", "HK", prefix2)
            suffix1_hk = transliterate.process("Devanagari", "HK", suffix1)
            suffix2_hk = transliterate.process("Devanagari", "HK", suffix2)
            diff1_hk = transliterate.process("Devanagari", "HK", text1_normalized[i1:i2])
            diff2_hk = transliterate.process("Devanagari", "HK", text2_normalized[j1:j2])

            # Build transliterated diff strings
            if tag == 'replace':
                orig_hk = f"{Style.DIM}{prefix1_hk}{Style.RESET_ALL}{Back.YELLOW}{Fore.BLACK}{diff1_hk}{Style.RESET_ALL}{Style.DIM}{suffix1_hk}{Style.RESET_ALL}"
                modi_hk = f"{Style.DIM}{prefix2_hk}{Style.RESET_ALL}{Back.YELLOW}{Fore.BLACK}{diff2_hk}{Style.RESET_ALL}{Style.DIM}{suffix2_hk}{Style.RESET_ALL}"
            elif tag == 'delete':
                orig_hk = f"{Style.DIM}{prefix1_hk}{Style.RESET_ALL}{Back.RED}{Fore.BLACK}{diff1_hk}{Style.RESET_ALL}{Style.DIM}{suffix1_hk}{Style.RESET_ALL}"
                modi_hk = f"{Style.DIM}{prefix2_hk}{suffix2_hk}{Style.RESET_ALL}"
            elif tag == 'insert':
                orig_hk = f"{Style.DIM}{prefix1_hk}{suffix1_hk}{Style.RESET_ALL}"
                modi_hk = f"{Style.DIM}{prefix2_hk}{Style.RESET_ALL}{Back.GREEN}{Fore.BLACK}{diff2_hk}{Style.RESET_ALL}{Style.DIM}{suffix2_hk}{Style.RESET_ALL}"

            print(f"  {Style.DIM}Harvard-Kyoto:{Style.RESET_ALL}")
            print(f"    {Style.DIM}Original:{Style.RESET_ALL} {orig_hk}")
            print(f"    {Style.DIM}Modified:{Style.RESET_ALL} {modi_hk}")

        print()

    if len(diffs) > max_diffs:
        print(f"{Style.DIM}... and {len(diffs) - max_diffs} more difference(s) (use logs for full details){Style.RESET_ALL}")

    print(f"{Fore.YELLOW}{'='*80}{Style.RESET_ALL}\n")


def show_devanagari_diff(
    input_text: str,
    output_text: str,
    context_lines: int = 3,
    max_diff_lines: int = 50,
    chunk_num: int | None = None,
    save_to_log_func = None,
):
    """Display a colored diff showing Devanagari character differences.

    Args:
        input_text: Input Devanagari text
        output_text: Output Devanagari text
        context_lines: Number of context lines (unused, for compatibility)
        max_diff_lines: Maximum lines to show (unused, for compatibility)
        chunk_num: Optional chunk number for logging
        save_to_log_func: Optional function to save diff to log file
    """
    # Save to log if function provided
    if save_to_log_func and chunk_num is not None:
        # Save input and output Devanagari to log files
        save_to_log_func(f"chunk_{chunk_num:03d}_input_devanagari.txt", input_text, subdir="chunks")
        save_to_log_func(f"chunk_{chunk_num:03d}_output_devanagari.txt", output_text, subdir="chunks")

        # Create a text-based diff for the log file
        diff_lines = []
        diff_lines.append("=" * 80)
        diff_lines.append("DEVANAGARI CHARACTER DIFF")
        diff_lines.append("=" * 80)
        diff_lines.append("")

        matcher = difflib.SequenceMatcher(None, input_text, output_text, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            elif tag == 'replace':
                diff_lines.append(f"REPLACE (pos {i1}-{i2}): '{input_text[i1:i2]}' → '{output_text[j1:j2]}'")
            elif tag == 'delete':
                diff_lines.append(f"DELETE (pos {i1}-{i2}): '{input_text[i1:i2]}'")
            elif tag == 'insert':
                diff_lines.append(f"INSERT (pos {j1}-{j2}): '{output_text[j1:j2]}'")

        diff_lines.append("")
        diff_lines.append(f"Original:  {input_text}")
        diff_lines.append(f"Modified:  {output_text}")
        diff_lines.append("=" * 80)

        save_to_log_func(f"chunk_{chunk_num:03d}_devanagari_diff.txt", "\n".join(diff_lines), subdir="chunks")

    # Show colored diff on console
    show_inline_char_diff(input_text, output_text, title="Devanagari Character Diff")


def show_transliteration_diff(
    input_devanagari: str, output_devanagari: str, chunk_num: int, save_to_log_func
):
    """
    Converts Devanagari to Harvard-Kyoto, logs them, and shows a colored diff.
    """

    # Transliterate
    try:
        input_hk = transliterate.process("Devanagari", "HK", input_devanagari)
        output_hk = transliterate.process("Devanagari", "HK", output_devanagari)
    except Exception as e:
        print(f"⚠️  Aksharamukha transliteration failed: {e}", file=sys.stderr)
        return

    # Log the transliterated files
    save_to_log_func(f"chunk_{chunk_num:03d}_input_hk.txt", input_hk, subdir="chunks")
    save_to_log_func(f"chunk_{chunk_num:03d}_output_hk.txt", output_hk, subdir="chunks")

    # Show the inline diff
    show_inline_char_diff(
        input_hk,
        output_hk,
        title=f"Harvard-Kyoto Transliteration Diff (chunk {chunk_num})",
    )
