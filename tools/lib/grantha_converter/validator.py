# Standard library imports
from pathlib import Path
import sys

# Local imports
from grantha_converter.devanagari_extractor import (
    extract_devanagari,
    clean_text_for_devanagari_comparison,
)
from grantha_converter.diff_utils import (
    show_devanagari_diff,
    show_transliteration_diff,
)


class Validator:
    """Validates the Devanagari preservation in converted chunks."""

    def __init__(
        self,
        file_log_dir: Path,
        no_diff: bool = False,
        show_transliteration: bool = False,
    ):
        self.file_log_dir = file_log_dir
        self.no_diff = no_diff
        self.show_transliteration = show_transliteration

    def validate_chunk(
        self, chunk_text: str, converted_body: str, chunk_metadata: dict
    ) -> dict:
        """
        Validates Devanagari preservation for a single chunk.

        Args:
            chunk_text: The original text content of the chunk.
            converted_body: The converted body of the chunk (without frontmatter).
            chunk_metadata: Metadata associated with the chunk.

        Returns:
            A dictionary containing the validation status and stats.
        """
        chunk_index = chunk_metadata.get("chunk_index")
        chunk_log_dir = self.file_log_dir / "chunks" / f"chunk_{chunk_index}"

        description = chunk_metadata.get("description")
        # Use clean_text_for_devanagari_comparison to match devanagari-diff behavior
        cleaned_input = clean_text_for_devanagari_comparison(chunk_text)
        input_devanagari = extract_devanagari(cleaned_input)
        cleaned_output = clean_text_for_devanagari_comparison(converted_body)
        output_devanagari = extract_devanagari(cleaned_output)

        validation_status = "PASSED"
        diff_chars = 0
        if input_devanagari != output_devanagari:
            validation_status = "MISMATCH"
            diff_chars = abs(len(input_devanagari) - len(output_devanagari))
            print(
                f"  ⚠️  Devanagari mismatch in chunk {chunk_index} ({len(input_devanagari)} -> {len(output_devanagari)} chars, diff: {diff_chars})",
                file=sys.stderr,
            )
            if not self.no_diff:
                show_devanagari_diff(input_devanagari, output_devanagari)
                if self.show_transliteration:
                    show_transliteration_diff(
                        input_devanagari,
                        output_devanagari,
                        chunk_index,
                        lambda f, c, s=None: self._save_log_file(
                            chunk_log_dir / f, c
                        ),
                    )
        else:
            print(f"  ✓ Devanagari preserved ({len(input_devanagari)} chars)")

        return {
            "chunk_index": chunk_index,
            "description": description,
            "status": validation_status,
            "input_chars": len(input_devanagari),
            "output_chars": len(output_devanagari),
            "char_diff": diff_chars,
        }

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
