import json
import re
# Standard library imports
import tempfile
from pathlib import Path
import sys
import traceback
from typing import Optional
import diff_match_patch
import os

# Third-party imports
from colorama import Fore, Style
import yaml

# Local imports
from gemini_processor.base_client import BaseGeminiClient
from gemini_processor.prompt_manager import PromptManager
from grantha_converter.analyzer import Analyzer
from grantha_converter.chunk_converter import ChunkConverter
from grantha_converter.validator import Validator
from grantha_converter.meghamala_chunker import split_by_execution_plan
from grantha_converter.meghamala_stitcher import (
    merge_chunks,
    cleanup_temp_chunks,
    extract_frontmatter_and_body,
    validate_merged_output,
)
from grantha_converter.devanagari_repair import repair_file
from grantha_converter.devanagari_extractor import extract_devanagari
from grantha_converter.visual_diff import print_visual_diff


class MeghamalaConverter:
    """Orchestrates the conversion of a single Meghamala file."""

    def __init__(self, client: BaseGeminiClient, prompt_manager: PromptManager, args, models: dict):
        self.client = client
        self.prompt_manager = prompt_manager
        self.args = args
        self.models = models

    def convert_file(
        self,
        input_path: Path,
        output_dir: Path,
        file_log_dir: Path,
        filename_override: str | None = None,
    ) -> bool:
        """
        Orchestrates the end-to-end conversion of a single file.

        This method acts as the main entry point for the conversion process,
        sequentially calling private methods to handle each phase:
        1. Analysis: Understand the structure of the input file.
        2. Chunking: Split the file into manageable pieces.
        3. Conversion: Convert each chunk to the target format.
        4. Stitching: Merge the converted chunks back together.
        5. Final Validation & Repair: Ensure integrity and attempt repairs.
        6. Write Output: Save the final converted file.

        Returns:
            True if the conversion was successful, False otherwise.
        """
        try:
            # Phase 1: Analysis
            analysis = self._run_analysis_phase(input_path, file_log_dir)
            if not analysis:
                return False

            output_path = self._determine_output_path(
                analysis, input_path, output_dir, filename_override
            )
            self._apply_metadata_overrides(analysis, input_path)
            self._display_analysis_summary(analysis, input_path)

            input_text = input_path.read_text(encoding="utf-8")
            input_text = self._preprocess_text(input_text)

            # Phase 2: Chunking
            chunks = self._run_chunking_phase(input_text, analysis)
            if not chunks:
                return False

            # Phase 3: Conversion and Validation
            temp_files, validations = self._run_conversion_phase(
                chunks, analysis, file_log_dir
            )
            if temp_files is None:
                return False
            self._display_validation_summary(validations)

            # Phase 4: Stitching
            merged_content = self._run_stitching_phase(temp_files, file_log_dir)
            if merged_content is None:
                cleanup_temp_chunks(temp_files, verbose=True)
                return False

            # Phase 5: Final Validation and Repair
            final_content = self._run_final_validation_and_repair_phase(
                input_text, merged_content, str(input_path), str(output_path), file_log_dir
            )
            if final_content is None:
                cleanup_temp_chunks(temp_files, verbose=True)
                return False

            # Phase 6: Write Output
            self._write_output(output_path, final_content)
            cleanup_temp_chunks(temp_files, verbose=False)
            return True

        except FileNotFoundError as e:
            print(f"❌ Error reading input file: {e}", file=sys.stderr)
            return False
        except Exception:
            print(f"❌ An unexpected error occurred during conversion:", file=sys.stderr)
            traceback.print_exc()
            return False

    def _run_analysis_phase(self, input_path: Path, file_log_dir: Path) -> dict | None:
        """Analyzes the input file to understand its structure."""
        print(f"\n{'='*60}")
        print(f"📋 PHASE 1: ANALYZING FILE STRUCTURE")
        print(f"{ '='*60}\n")
        analyzer = Analyzer(
            client=self.client,
            prompt_manager=self.prompt_manager,
            file_log_dir=file_log_dir,
            use_cache=not self.args.no_cache,
            use_upload_cache=not self.args.no_upload_cache,
            force_reanalysis=self.args.force_analysis,
            analysis_cache_dir=self.args.analysis_cache_dir,
        )
        print(f"📁 Analysis Cache Dir: {self.args.analysis_cache_dir}")
        try:
            analysis = analyzer.analyze(input_path, self.models["analysis"])
            self._save_log_file(file_log_dir / "00_analysis_result.json", json.dumps(analysis, indent=2, ensure_ascii=False))
            return analysis
        except Exception as e:
            print(f"❌ File analysis failed for {input_path.name}: {e}", file=sys.stderr)
            return None

    def _determine_output_path(
        self,
        analysis: dict,
        input_path: Path,
        output_dir: Path,
        filename_override: str | None,
    ) -> Path:
        """Determines the final output path for the converted file."""
        if filename_override:
            final_filename = filename_override
        else:
            suggestion = analysis.get("structural_analysis", {}).get("suggested_filename")
            final_filename = f"{suggestion}.md" if suggestion else f"{input_path.stem}_converted.md"
        
        if not final_filename or final_filename == ".":
            final_filename = f"{input_path.stem}_converted.md"

        output_path = output_dir / final_filename
        print(f"🎯 Target Output: {output_path}")
        return output_path

    def _run_chunking_phase(self, input_text: str, analysis: dict) -> list[tuple[str, dict]] | None:
        """Splits the input text into chunks based on the analysis execution plan."""
        print(f"\n{'='*60}")
        print(f"📋 PHASE 2: CHUNKING FILE")
        print(f"{ '='*60}\n")
        execution_plan = analysis.get("chunking_strategy", {}).get("execution_plan", [])
        if not execution_plan:
            print("❌ No execution plan found in analysis result.", file=sys.stderr)
            return None

        print(f"✂️ Splitting file using execution plan ({len(execution_plan)} chunks)...")
        return split_by_execution_plan(input_text, execution_plan, verbose=False)

    def _run_conversion_phase(
        self,
        chunks: list[tuple[str, dict]],
        analysis: dict,
        file_log_dir: Path,
    ) -> tuple[list[str], list[dict]] | tuple[None, None]:
        """Converts each chunk and validates its content."""
        print(f"\n{'='*60}")
        print(f"📋 PHASE 3: CONVERTING {len(chunks)} CHUNKS")
        print(f"{ '='*60}\n")
        return self._convert_and_validate_chunks(chunks, analysis, file_log_dir)

    def _run_stitching_phase(self, temp_files: list[str], file_log_dir: Path) -> str | None:
        """Merges the converted temporary chunk files into a single string."""
        print(f"\n{'='*60}")
        print("📋 PHASE 4: MERGING AND WRITING OUTPUT")
        print(f"{ '='*60}\n")
        success, merged_content, message = merge_chunks(temp_files, verbose=False)
        if not success or merged_content is None:
            print(f"❌ Merging failed: {message}", file=sys.stderr)
            return None
        self._save_log_file(file_log_dir / "05_merged_content.md", merged_content)
        print(f"✓ Merging complete: {len(merged_content)} characters")
        return merged_content

    def _run_final_validation_and_repair_phase(
        self,
        input_text: str,
        merged_content: str,
        input_file: str,
        output_file: str,
        file_log_dir: Path,
    ) -> str | None:
        """Validates, diffs, and optionally repairs the final merged content."""
        if self.args.skip_validation:
            return merged_content

        print(f"\n{'='*60}")
        print("📋 PHASE 5: FINAL VALIDATION, DIFF, AND REPAIR")
        print(f"{ '='*60}\n")

        # 1. Extract Devanagari for comparison
        source_devanagari = extract_devanagari(input_text)
        converted_devanagari = extract_devanagari(merged_content)

        # 2. Calculate initial diffs
        dmp = diff_match_patch.diff_match_patch()
        diffs_before = dmp.diff_main(source_devanagari, converted_devanagari)
        dmp.diff_cleanupSemantic(diffs_before)
        diff_count_before = sum(1 for op, _ in diffs_before if op != dmp.DIFF_EQUAL)

        # 3. Show visual diff
        print("🔎 Displaying Devanagari diff between source and converted text:")
        print_visual_diff(source_devanagari, converted_devanagari)

        if diff_count_before == 0:
            print("✓ No Devanagari discrepancies found. Skipping repair.")
            return merged_content

        print(f"\n⚠️  Found {diff_count_before} Devanagari discrepancies. Attempting repair...")

        # 4. Attempt repair
        # repair_file works on files, so we write the merged content to a temporary file
        temp_output_path = Path(output_file).with_suffix(".tmp_for_repair")
        temp_output_path.write_text(merged_content, encoding="utf-8")

        repair_successful, repair_message = repair_file(
            input_file=input_file,
            output_file=str(temp_output_path),
            verbose=False,
            dry_run=False,
            create_backup=False, # We handle our own temp files
        )

        if not repair_successful:
            print(f"❌ Repair failed: {repair_message}", file=sys.stderr)
            os.remove(temp_output_path)
            return merged_content # Return original merged content on failure

        # 5. Compare diffs and decide
        repaired_content = temp_output_path.read_text(encoding="utf-8")
        repaired_devanagari = extract_devanagari(repaired_content)
        diffs_after = dmp.diff_main(source_devanagari, repaired_devanagari)
        dmp.diff_cleanupSemantic(diffs_after)
        diff_count_after = sum(1 for op, _ in diffs_after if op != dmp.DIFF_EQUAL)

        print(f"📊 Repair analysis: Diffs before: {diff_count_before}, Diffs after: {diff_count_after}")

        if diff_count_after < diff_count_before:
            print(f"✅ Repair improved the output. Using repaired version.")
            final_content = repaired_content
        else:
            print(f"⚠️  Repair did not improve the output. Using original conversion.")
            final_content = merged_content

        # 6. Cleanup
        os.remove(temp_output_path)
        repaired_backup = Path(str(temp_output_path) + ".repaired")
        if repaired_backup.exists():
            os.remove(repaired_backup)

        return final_content

    def _write_output(self, output_path: Path, content: str):
        """Writes the final content to the output file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"✓ Output written to {output_path}")
        print(f"\n✅ CONVERSION COMPLETE: {output_path}")


    def _convert_and_validate_chunks(
        self,
        chunks: list[tuple[str, dict]],
        analysis_result: dict,
        file_log_dir: Path,
    ) -> tuple[list[str], list[dict]] | tuple[None, None]:
        """
        Initializes converters and validators, then processes each chunk in a loop.

        Returns:
            A tuple containing a list of temporary file paths and a list of
            validation dictionaries. Returns (None, None) if any chunk fails.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="grantha_chunks_"))
        temp_file_paths = []
        chunk_validations = []

        converter = ChunkConverter(
            client=self.client,
            prompt_manager=self.prompt_manager,
            file_log_dir=file_log_dir,
            use_upload_cache=not self.args.no_upload_cache,
        )
        validator = Validator(
            file_log_dir=file_log_dir,
            no_diff=self.args.no_diff,
            show_transliteration=self.args.show_transliteration,
        )

        for i, (chunk_text, chunk_metadata) in enumerate(chunks):
            try:
                temp_file, validation_result = self._process_single_chunk(
                    chunk_text, chunk_metadata, i, len(chunks), analysis_result,
                    converter, validator, temp_dir
                )
                temp_file_paths.append(str(temp_file))
                chunk_validations.append(validation_result)
            except Exception:
                print(f"❌ Error processing chunk {i+1}:", file=sys.stderr)
                traceback.print_exc()
                cleanup_temp_chunks(temp_file_paths, verbose=True)
                return None, None

        return temp_file_paths, chunk_validations

    def _process_single_chunk(
        self,
        chunk_text: str,
        chunk_metadata: dict,
        index: int,
        total_chunks: int,
        analysis_result: dict,
        converter: ChunkConverter,
        validator: Validator,
        temp_dir: Path,
    ) -> tuple[Path, dict]:
        """
        Converts, saves, and validates a single chunk of text.

        Returns:
            A tuple containing the path to the temporary file and the validation result.
        """
        display_chunk_index = index + 1
        chunk_metadata["chunk_index"] = display_chunk_index
        description = chunk_metadata.get("description", f"Chunk {display_chunk_index}")
        print(f"🔄 Converting chunk {display_chunk_index}/{total_chunks}: {description[:70]}...")

        # Convert the chunk text using the provided converter instance
        full_chunk_content = converter.convert(
            chunk_text=chunk_text,
            chunk_metadata=chunk_metadata,
            analysis_result=analysis_result,
            model=self.models["conversion"],
        )

        # Save the converted content to a temporary file
        temp_file = temp_dir / f"chunk_{index:03d}.md"
        temp_file.write_text(full_chunk_content, encoding="utf-8")

        # Validate the converted chunk against the original
        _, converted_body, _ = extract_frontmatter_and_body(full_chunk_content)
        validation_result = validator.validate_chunk(
            chunk_text, converted_body, chunk_metadata
        )

        return temp_file, validation_result


    def _validate_and_repair_final(
        self,
        input_text,
        merged_content,
        input_file,
        output_file,
        file_log_dir,
    ):
        is_valid, validation_message = validate_merged_output(input_text, merged_content)
        if is_valid:
            print(f"✓ {validation_message}\n")
            return merged_content

        print(f"⚠️  {validation_message}", file=sys.stderr)
        
        repair_log_dir = file_log_dir / "repair"
        (repair_log_dir).mkdir(parents=True, exist_ok=True)
        with open(repair_log_dir / "01_pre_repair_output.md", "w", encoding="utf-8") as f:
            f.write(merged_content)

        print("   Attempting repair...")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(merged_content)

        repair_successful, repair_message = repair_file(
            input_file=input_file,
            output_file=output_file,
            max_diff_size=2000,
            skip_frontmatter=False,
            verbose=False,
            dry_run=False,
            min_similarity=0.80,
            conservative=True,
            create_backup=True,
        )

        if repair_successful:
            repaired_content = Path(output_file).read_text(encoding="utf-8")
            with open(repair_log_dir / "02_post_repair_output.md", "w", encoding="utf-8") as f:
                f.write(repaired_content)
            
            print("✓ Repair successful.")
            return repaired_content
        else:
            print(f"❌ {repair_message}", file=sys.stderr)
            return None

    def _apply_metadata_overrides(self, analysis: dict, input_path: Path):
        """Applies command-line metadata overrides to the analysis result."""
        if not self.args.directory:
            return

        if "metadata" not in analysis:
            analysis["metadata"] = {}

        analysis_metadata = analysis.get("metadata", {})
        if self.args.grantha_id:
            analysis_metadata["grantha_id"] = self.args.grantha_id
        if self.args.canonical_title:
            analysis_metadata["canonical_title"] = self.args.canonical_title
        if self.args.commentary_id:
            analysis_metadata["commentary_id"] = self.args.commentary_id
        if self.args.commentator:
            analysis_metadata["commentator"] = self.args.commentator

        from grantha_converter.utils import extract_part_number_from_filename
        analysis_metadata["part_num"] = extract_part_number_from_filename(input_path.name)
        analysis["metadata"] = analysis_metadata

    def _display_analysis_summary(self, analysis: dict, input_path: Path):
        """Prints a summary of the analysis result."""
        metadata = analysis.get("metadata", {})
        print(f"\n✓ Analysis complete for {input_path.name}:")
        print(f"  📖 Text: {metadata.get('canonical_title', 'Unknown')}")
        print(f"  🆔 ID: {metadata.get('grantha_id', 'unknown')}")
        if metadata.get("commentary_id"):
            print(f"  📝 Commentary: {metadata.get('commentary_id')}")

    def _display_validation_summary(self, chunk_validations: list[dict] | None):
        """Prints a summary table of the chunk validation results."""
        if chunk_validations is None or not chunk_validations:
            return

        print(f"\n{'='*60}")
        print("📋 CHUNK VALIDATION SUMMARY")
        print(f"{ '='*60}")

        summary_table, total_diff = self._build_summary_table(chunk_validations)
        print(summary_table)
        print(f"Total Devanagari Character Difference: {total_diff}")

    def _build_summary_table(self, chunk_validations: list[dict]) -> tuple[str, int]:
        """
        Builds a formatted string table summarizing the validation results.

        Returns:
            A tuple containing the formatted table string and the total character difference.
        """
        # Filter out any None values from the list to prevent errors
        valid_validations = [v for v in chunk_validations if v is not None]
        if not valid_validations:
            return "", 0

        # Determine column width for description
        descriptions = [v.get("description") or "" for v in valid_validations]
        max_desc_len = max(len(d) for d in descriptions) if descriptions else 20
        max_desc_len = min(max(max_desc_len, 20), 50)

        # Header
        header = f"| {'Chunk':<5} | {'Status':<8} | {'Input':>7} | {'Output':>7} | {'Diff':>5} | {'Description':<{max_desc_len}} |"
        separator = f"|{'-'*7}|{'-'*10}|{'-'*9}|{'-'*9}|{'-'*7}|{'-'*(max_desc_len+2)}|"

        rows = [header, separator]
        total_diff = 0

        for v in valid_validations:
            status = v.get("status", "N/A")
            status_color = (
                Fore.YELLOW if status == "MISMATCH"
                else Fore.GREEN if status == "PASSED" else ""
            )
            diff = v.get("char_diff", 0)
            total_diff += diff
            desc = v.get("description") or ""
            if len(desc) > max_desc_len:
                desc = desc[: max_desc_len - 3] + "..."

            row = (
                f"| {v.get('chunk_index', ''):<5} "
                f"| {status_color}{status:<8}{Style.RESET_ALL} "
                f"| {v.get('input_chars', ''):>7} "
                f"| {v.get('output_chars', ''):>7} "
                f"| {diff:>5} "
                f"| {desc:<{max_desc_len}} |"
            )
            rows.append(row)

        rows.append(separator)
        return "\n".join(rows), total_diff

    def _save_log_file(self, log_path: Path, content: str):
        """Saves content to a specified path in the log directory."""
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(content, encoding="utf-8")
            try:
                relative_path = log_path.relative_to(Path.cwd())
            except ValueError:
                relative_path = log_path
            print(f"  💾 Saved: {relative_path}")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not save log file {log_path}: {e}")

    def _preprocess_text(self, raw_text: str) -> str:
        """Applies deterministic regex replacements to normalize noisy input text."""
        import re

        # Sanitize Headers: Convert noisy headers like **[उपक्रमशान्तिपाठः]** or **तृतीयोऽध्यायः**
        # into a standard format without brackets or excessive noise.
        # Find: **[?(.*?)]?** (Find bold text, optionally inside brackets)
        # Replace: **$1** (Keep just the bold text).
        # Refinement: If the text inside is metadata like (****...****), remove the inner asterisks.
        processed_text = re.sub(r"\*\*\[?(.*?)\]?\*\*", r"**\1**", raw_text)
        processed_text = re.sub(r"\*\*\*\*(.*?)\*\*\*\*", r"**\1**", processed_text)

        # Normalize Asterisks: Fix inconsistent bolding like **word ** or ** word**.
        processed_text = re.sub(r"\*\*\s+", r"**", processed_text)
        processed_text = re.sub(r"\s+\*\*", r"**", processed_text)

        # Fix Broken Separators: Ensure separators are standard.
        processed_text = re.sub(r"^\*{3,}$", r"******", processed_text, flags=re.MULTILINE)

        # Standardize Verse Numbers: Ensure verse numbers are detectable at the end of lines.
        processed_text = re.sub(r"(।।\s*[\u0966-\u096F]+\s*।।)\s*$", r"\1", processed_text, flags=re.MULTILINE)

        return processed_text
