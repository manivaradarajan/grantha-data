#!/usr/bin/env python3
"""Batch Devanagari Repair and Validation Tool.

This script automates the process of finding and repairing Devanagari text
across a source and destination directory structure, and validates content
hashes upon successful repair.

Workflow:
1.  Iterates through each subdirectory in a given source location.
2.  For each source directory, it finds the best-matching destination
    directory by name similarity in a target location.
3.  For each Markdown file in the source directory, it finds the best-matching
    file in the destination directory using a weighted similarity score that
    combines filename and Devanagari content similarity.
4.  If a suitable match is found with fewer than a set number of differences,
    it calls the `devanagari-repair` logic on the file pair.
5.  If the repair is successful and results in zero differences (i.e., the
    content was already a perfect match), it calculates a validation hash based
    on the normalized Devanagari content and updates the `grantha_hash` field
    in the destination file's YAML frontmatter.
6.  A detailed log of all operations is saved to a timestamped file.
"""

import argparse
import hashlib
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import diff_match_patch
import yaml
from rapidfuzz import fuzz, process

# Add local library path to resolve imports
script_dir = Path(__file__).parent.parent.parent
sys.path.append(str(script_dir / "lib"))

from grantha_converter.devanagari_extractor import extract_devanagari_words
from grantha_converter.devanagari_repair import repair_file
from grantha_converter.devanagari_validator import (
    extract_devanagari,
    normalize_devanagari,
)

# --- Constants ---
DEFAULT_SOURCE_DIR = Path("sources/upanishads/meghamala")
DEFAULT_DEST_DIR = Path("structured_md/upanishads")
DEFAULT_LOGS_DIR = Path("logs")
DIFF_THRESHOLD = 300
FILENAME_SIMILARITY_WEIGHT = 0.7
CONTENT_SIMILARITY_WEIGHT = 0.3


def setup_logging(log_dir: Path) -> logging.Logger:
    """Configures a logger to write to a timestamped file and the console.

    Args:
        log_dir: The directory where the log file will be saved.

    Returns:
        A configured logging.Logger instance.
    """
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"batch_repair_{timestamp}.log"

    logger = logging.getLogger("batch_repair")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_format = "%(asctime)s - %(levelname)s - %(message)s"
    file_handler.setFormatter(logging.Formatter(file_format))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def _clean_text_for_comparison(text: str) -> str:
    """Prepares text for comparison by removing non-content elements.

    Args:
        text: The raw text content of a file.

    Returns:
        Cleaned text with frontmatter, comments, and bold markers removed.
    """
    if text.strip().startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _clean_filename(filename: str) -> str:
    """Normalizes a filename for similarity comparison.

    Args:
        filename: The filename to clean.

    Returns:
        A cleaned, lowercase filename without the extension.
    """
    return Path(filename).stem.lower()


def get_devanagari_diff_count(text1: str, text2: str) -> int:
    """Calculates the number of Devanagari differences between two texts.

    Args:
        text1: The first string for comparison.
        text2: The second string for comparison.

    Returns:
        The total number of differing Devanagari characters.
    """
    devanagari1 = extract_devanagari(text1)
    devanagari2 = extract_devanagari(text2)
    dmp = diff_match_patch.diff_match_patch()
    diffs = dmp.diff_main(devanagari1, devanagari2)
    dmp.diff_cleanupSemantic(diffs)
    return sum(1 for op, _ in diffs if op != dmp.DIFF_EQUAL)


def update_hash_in_frontmatter(content: str, logger: logging.Logger) -> Optional[str]:
    """Updates the grantha_hash in YAML frontmatter using validator logic.

    Args:
        content: The full string content of the file.
        logger: The logger instance for reporting.

    Returns:
        The updated file content as a string, or None if no update was needed
        or an error occurred.
    """
    if not content.strip().startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        frontmatter = yaml.safe_load(parts[1])
        if not isinstance(frontmatter, dict):
            logger.warning("   - Could not update hash: Frontmatter is not a valid dictionary.")
            return None

        body_content = parts[2]
        full_content_for_hash = parts[1] + body_content

        devanagari_text = extract_devanagari(full_content_for_hash)
        normalized_text = normalize_devanagari(devanagari_text)
        new_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

        if frontmatter.get("grantha_hash") == new_hash:
            logger.info("   - Hash is already up-to-date.")
            return None

        frontmatter["grantha_hash"] = new_hash
        updated_frontmatter_str = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
        return f"---\n{updated_frontmatter_str}---{body_content}"

    except yaml.YAMLError as e:
        logger.error(f"   - Error processing YAML frontmatter: {e}")
        return None


def find_best_match_file(
    source_file: Path, dest_dir: Path, logger: logging.Logger
) -> Tuple[Optional[Path], int]:
    """Finds the best file match based on filename and content similarity.

    Args:
        source_file: The source markdown file.
        dest_dir: The destination directory to search for a match.
        logger: The logger instance for reporting.

    Returns:
        A tuple containing the Path to the best matching file (or None) and
        the absolute Devanagari diff count of that match.
    """
    try:
        source_text = source_file.read_text(encoding="utf-8")
    except (IOError, OSError) as e:
        logger.error(f"    - Could not read source file '{source_file}': {e}")
        return None, -1

    candidate_files = [f for f in dest_dir.glob("*.md") if not f.name.endswith(".repaired.md")]
    if not candidate_files:
        logger.warning(f"    - No non-repaired markdown files found in '{dest_dir.name}'.")
        return None, -1

    logger.info(f"    - Comparing against {len(candidate_files)} candidate(s) in '{dest_dir.name}'.")

    source_text_cleaned = _clean_text_for_comparison(source_text)
    source_words = extract_devanagari_words(source_text_cleaned)
    source_words_joined = " ".join(source_words)
    source_filename_cleaned = _clean_filename(source_file.name)

    best_match_file: Optional[Path] = None
    max_combined_score = -1.0

    for dest_file in candidate_files:
        try:
            dest_text = dest_file.read_text(encoding="utf-8")
        except (IOError, OSError) as e:
            logger.warning(f"      - Could not read candidate file '{dest_file}': {e}")
            continue

        dest_filename_cleaned = _clean_filename(dest_file.name)
        filename_similarity = fuzz.ratio(source_filename_cleaned, dest_filename_cleaned)

        dest_text_cleaned = _clean_text_for_comparison(dest_text)
        dest_words = extract_devanagari_words(dest_text_cleaned)
        content_similarity = fuzz.ratio(source_words_joined, " ".join(dest_words)) if dest_words else 0

        combined_score = (filename_similarity * FILENAME_SIMILARITY_WEIGHT) + (content_similarity * CONTENT_SIMILARITY_WEIGHT)

        log_msg = f"      - Candidate '{dest_file.name}': Filename Sim: {filename_similarity:.1f}%%, Content Sim: {content_similarity:.1f}%%, Combined: {combined_score:.1f}%%"
        logger.info(log_msg)

        if combined_score > max_combined_score:
            max_combined_score = combined_score
            best_match_file = dest_file

    if not best_match_file:
        return None, -1

    best_match_text = best_match_file.read_text(encoding="utf-8")
    diff_count = get_devanagari_diff_count(source_text, best_match_text)
    return best_match_file, diff_count


def attempt_repair_and_update(
    source_file: Path,
    dest_file: Path,
    diffs: int,
    logger: logging.Logger,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """Attempts to repair a file and update its hash if successful.

    Args:
        source_file: The source file with the correct Devanagari.
        dest_file: The destination file to be repaired.
        diffs: The pre-calculated number of Devanagari differences.
        logger: The logger instance for reporting.
        dry_run: If True, performs a dry run without writing changes.
    
    Returns:
        A tuple of (success_boolean, message_string).
    """
    logger.info(f"    - Diffs ({diffs}) are below threshold ({DIFF_THRESHOLD}). Attempting repair...")
    if dry_run:
        logger.info("    - DRY RUN: Skipping actual repair and hash update.")
        return True, "Dry run successful."

    success, message = repair_file(
        input_file=str(source_file),
        output_file=str(dest_file),
        create_backup=True,
    )

    if success:
        logger.info(f"    - ✅ Repair successful: {message}")
        if diffs == 0:
            logger.info("   - Zero diffs found, checking and updating hash...")
            try:
                dest_content = dest_file.read_text(encoding="utf-8")
                updated_content = update_hash_in_frontmatter(dest_content, logger)
                if updated_content:
                    dest_file.write_text(updated_content, encoding="utf-8")
                    logger.info(f"   - ✅ Successfully updated hash in '{dest_file.name}'.")
            except (IOError, OSError) as e:
                logger.error(f"   - ❌ Failed to update hash for '{dest_file.name}': {e}")
    else:
        logger.error(f"    - ❌ Repair failed: {message}")
    
    return success, message


def run_batch_repair(args: argparse.Namespace):
    """Main orchestration function for the batch repair process.

    Args:
        args: Command-line arguments parsed by argparse.
    """
    logger = setup_logging(args.log_dir)
    logger.info("--- Starting Batch Devanagari Repair ---")
    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED: No files will be modified. ***")

    try:
        source_dirs = [d for d in args.source_dir.iterdir() if d.is_dir()]
        dest_dirs = [d for d in args.dest_dir.iterdir() if d.is_dir()]
    except FileNotFoundError as e:
        logger.error(f"Error: Directory not found: {e}. Please check paths.")
        sys.exit(1)

    # --- Track unmatched and unrepairable files ---
    unmatched_dest_files = set()
    for directory in dest_dirs:
        unmatched_dest_files.update(
            f for f in directory.glob("*.md") if not f.name.endswith(".repaired.md")
        )
    unrepairable_files: List[Tuple[Path, Path, str]] = []
    # ---

    dest_dir_names = [d.name for d in dest_dirs]

    for source_dir in source_dirs:
        logger.info(f"\nProcessing source directory: '{source_dir.name}'")
        match_result = process.extractOne(source_dir.name, dest_dir_names, scorer=fuzz.ratio)

        if not match_result or match_result[1] < 70:
            score_str = f"{match_result[1]:.1f}%" if match_result else "N/A"
            logger.warning(f"  - No suitable destination directory found (best match score: {score_str}).")
            continue

        match_dir_name = match_result[0]
        match_dir = args.dest_dir / match_dir_name
        logger.info(f"  - Matched with '{match_dir.name}' (score: {match_result[1]:.1f}%).")

        source_files = list(source_dir.glob("*.md"))
        if not source_files:
            logger.info("  - No markdown files found in this source directory.")
            continue

        for source_file in source_files:
            logger.info(f"  - Processing source file: '{source_file.name}'")
            best_match, diffs = find_best_match_file(source_file, match_dir, logger)

            if best_match is None:
                logger.warning(f"    - No matching destination file found.")
                continue
            
            if best_match in unmatched_dest_files:
                unmatched_dest_files.remove(best_match)

            logger.info(f"    - Best match found: '{best_match.name}' with {diffs} diffs.")

            if diffs < args.diff_threshold:
                success, message = attempt_repair_and_update(source_file, best_match, diffs, logger, args.dry_run)
                if not success:
                    unrepairable_files.append((source_file, best_match, message))
            else:
                logger.warning(f"    - Diffs ({diffs}) exceed threshold ({args.diff_threshold}). Skipping repair.")

    # --- Log any remaining unmatched files ---
    if unmatched_dest_files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unmatched_log_path = args.log_dir / f"unmatched_dest_files_{timestamp}.log"
        logger.info(f"\nFound {len(unmatched_dest_files)} unmatched destination files. Logging to {unmatched_log_path}")
        try:
            with open(unmatched_log_path, "w", encoding="utf-8") as f:
                for file_path in sorted(list(unmatched_dest_files)):
                    f.write(f"{file_path}\n")
        except IOError as e:
            logger.error(f"Error writing unmatched files log: {e}")
    else:
        logger.info("\nNo unmatched destination files found.")
    
    # --- Log any unrepairable files ---
    if unrepairable_files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unrepairable_log_path = args.log_dir / f"unrepairable_files_{timestamp}.log"
        logger.info(f"\nFound {len(unrepairable_files)} unrepairable files. Logging to {unrepairable_log_path}")
        try:
            with open(unrepairable_log_path, "w", encoding="utf-8") as f:
                f.write("The following files were matched but could not be repaired:\n\n")
                for source, dest, msg in unrepairable_files:
                    f.write(f"Source: {source}\n")
                    f.write(f"Destination: {dest}\n")
                    f.write(f"Reason: {msg}\n\n")
        except IOError as e:
            logger.error(f"Error writing unrepairable files log: {e}")
    else:
        logger.info("\nNo unrepairable files were found.")

    logger.info("\n--- Batch Repair Complete ---")


def main():
    """Parses command-line arguments and starts the repair process."""
    parser = argparse.ArgumentParser(
        description="Batch find and repair Devanagari text in markdown files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source_dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Source directory containing Upanishad subdirectories.",
    )
    parser.add_argument(
        "--dest_dir",
        type=Path,
        default=DEFAULT_DEST_DIR,
        help="Destination directory to find matching files for repair.",
    )
    parser.add_argument(
        "--log_dir",
        type=Path,
        default=DEFAULT_LOGS_DIR,
        help="Directory to save log files.",
    )
    parser.add_argument(
        "--diff_threshold",
        type=int,
        default=DIFF_THRESHOLD,
        help="Maximum number of Devanagari diffs to attempt a repair.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without modifying any files.",
    )
    args = parser.parse_args()

    run_batch_repair(args)


if __name__ == "__main__":
    main()