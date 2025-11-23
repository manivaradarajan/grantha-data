"""Converts individual text chunks to Grantha Markdown format using Gemini API.

This module provides the ChunkConverter class which handles the conversion of
a single text chunk by uploading it to the Gemini API, processing the response,
and assembling it with properly formatted YAML frontmatter.
"""

# Standard library imports
import json
import re
import tempfile
from pathlib import Path

# Third-party imports
import yaml

# Local imports
from gemini_processor.base_client import BaseGeminiClient
from gemini_processor.prompt_manager import PromptManager
from grantha_converter.devanagari_extractor import HASH_VERSION
from grantha_converter.hasher import hash_text


class ChunkConverter:
    """Converts a single text chunk using the Gemini API.

    This class orchestrates the conversion of meghamala-format text chunks to
    structured Grantha Markdown. It handles file upload, API interaction, and
    frontmatter generation with validation hashing.

    Attributes:
        client: The Gemini API client for file uploads and content generation.
        prompt_manager: Manager for loading prompt templates.
        file_log_dir: Directory for saving conversion logs.
        use_upload_cache: Whether to cache uploaded files to avoid re-uploading.
        custom_conversion_prompt: Optional path to custom prompt template.
    """

    def __init__(
        self,
        client: BaseGeminiClient,
        prompt_manager: PromptManager,
        file_log_dir: Path,
        use_upload_cache: bool = True,
        custom_conversion_prompt: Path | None = None,
    ):
        """Initializes the ChunkConverter.

        Args:
            client: Gemini API client for uploads and content generation.
            prompt_manager: Manager for loading prompt templates.
            file_log_dir: Directory where conversion logs will be saved.
            use_upload_cache: If True, cache uploaded files to avoid re-uploads.
                Defaults to True.
            custom_conversion_prompt: Optional path to custom prompt template.
                If None, uses default template. Defaults to None.
        """
        self.client = client
        self.prompt_manager = prompt_manager
        self.file_log_dir = file_log_dir
        self.use_upload_cache = use_upload_cache
        self.custom_conversion_prompt = custom_conversion_prompt

    def convert(
        self,
        chunk_text: str,
        chunk_metadata: dict,
        analysis_result: dict,
        model: str,
    ) -> str:
        """Converts a single chunk of text to Grantha Markdown format.

        This is the main entry point for chunk conversion. It orchestrates the
        entire process: creating a temporary file, uploading to Gemini API,
        receiving and processing the conversion response, and assembling the
        final output with frontmatter.

        Args:
            chunk_text: The raw text content to convert.
            chunk_metadata: Metadata about this chunk (index, description, etc.).
            analysis_result: The structural analysis containing metadata and
                structure levels for the entire document.
            model: Name of the Gemini model to use (e.g., "gemini-2.0-flash").

        Returns:
            Complete markdown content with YAML frontmatter and converted body.

        Raises:
            ValueError: If file upload to Gemini API fails.
        """
        chunk_index = chunk_metadata.get("chunk_index")
        chunk_log_dir = self.file_log_dir / "chunks" / f"chunk_{chunk_index}"

        # Create temp file with original text (WITH bold markers)
        # Conversion prompts rely on bold for structure identification
        temp_file_path = self._create_temp_file(chunk_text, chunk_index)

        try:
            uploaded_file = self._upload_chunk_for_conversion(
                temp_file_path, chunk_log_dir
            )
            converted_body = self._get_conversion_from_gemini(
                model, uploaded_file, analysis_result, chunk_text, chunk_log_dir
            )
            return self._add_frontmatter(converted_body, analysis_result)
        finally:
            self._cleanup_temp_file(temp_file_path)

    def _create_temp_file(self, chunk_text: str, chunk_index: int) -> Path:
        """Creates a temporary file containing the chunk text.

        Args:
            chunk_text: Text content to write to temporary file.
            chunk_index: Index of this chunk (used in filename).

        Returns:
            Path to the created temporary file.
        """
        temp_chunk_dir = Path(tempfile.gettempdir()) / "grantha_temp_chunks"
        temp_chunk_dir.mkdir(exist_ok=True)
        temp_file_path = temp_chunk_dir / f"chunk_{chunk_index}.md"
        temp_file_path.write_text(chunk_text, encoding="utf-8")
        return temp_file_path

    def _cleanup_temp_file(self, temp_file_path: Path) -> None:
        """Deletes a temporary file if it exists.

        Args:
            temp_file_path: Path to temporary file to delete.
        """
        if temp_file_path.exists():
            temp_file_path.unlink()

    def _upload_chunk_for_conversion(
        self, temp_file_path: Path, chunk_log_dir: Path
    ):
        """Uploads the chunk file to Gemini API for processing.

        Args:
            temp_file_path: Path to temporary file containing chunk content.
            chunk_log_dir: Directory where upload logs will be saved.

        Returns:
            Uploaded file object from Gemini API.

        Raises:
            ValueError: If upload fails.
        """
        uploaded_file = self.client.upload_file(
            file_path=temp_file_path,
            use_upload_cache=self.use_upload_cache,
            verbose=True,
        )

        if not uploaded_file:
            raise ValueError(
                f"Failed to upload chunk {temp_file_path.name} to File API."
            )

        self._log_upload_info(uploaded_file, chunk_log_dir)
        return uploaded_file

    def _log_upload_info(self, uploaded_file, chunk_log_dir: Path) -> None:
        """Logs information about an uploaded file for debugging.

        Args:
            uploaded_file: The uploaded file object from Gemini API.
            chunk_log_dir: Directory where log will be saved.
        """
        log_content = (
            f"File name: {uploaded_file.name}\n"
            f"Display name: {uploaded_file.display_name}\n"
            f"Size: {uploaded_file.size_bytes} bytes\n"
            f"State: {uploaded_file.state}\n"
            f"URI: {uploaded_file.uri}\n"
        )
        self._save_log_file(
            chunk_log_dir / "00_uploaded_chunk_info.txt", log_content
        )

    def _get_conversion_from_gemini(
        self,
        model: str,
        uploaded_file,
        analysis_result: dict,
        chunk_text: str,
        chunk_log_dir: Path,
    ) -> str:
        """Calls Gemini API to convert the chunk and processes the response.

        This method creates the conversion prompt, calls the Gemini API,
        receives the response, and cleans it up by removing code fences.
        All inputs and outputs are logged for debugging.

        Args:
            model: Name of the Gemini model to use.
            uploaded_file: The uploaded file object from previous upload step.
            analysis_result: Structural analysis containing metadata.
            chunk_text: Original chunk text (for logging).
            chunk_log_dir: Directory where conversion logs will be saved.

        Returns:
            Cleaned conversion response (markdown body without code fences).
        """
        prompt = self._create_chunk_conversion_prompt(analysis_result)

        # Log inputs
        self._save_log_file(chunk_log_dir / "01_chunk_input.md", chunk_text)
        self._save_log_file(chunk_log_dir / "02_conversion_prompt.txt", prompt)

        # Call Gemini API
        print(f"🤖 Calling Gemini API model:'{model}' for chunk conversion...")
        response_text = self.client.generate_content(
            model=model, prompt=prompt, uploaded_file=uploaded_file
        )

        # Log and clean response
        self._save_log_file(
            chunk_log_dir / "03_conversion_response_raw.txt", response_text
        )
        converted_body = self._strip_code_fences(response_text)
        self._save_log_file(chunk_log_dir / "04_converted_body.md", converted_body)

        return converted_body

    def _create_chunk_conversion_prompt(self, analysis_result: dict) -> str:
        """Creates the prompt for chunk conversion.

        Loads either a custom prompt template or the default template,
        then formats it with the analysis results and commentary ID.

        Args:
            analysis_result: Structural analysis containing metadata and
                structure information.

        Returns:
            Formatted prompt string ready to send to Gemini API.
        """
        if self.custom_conversion_prompt:
            template = self.custom_conversion_prompt.read_text(encoding="utf-8")
            print(f"  📄 Using custom prompt: {self.custom_conversion_prompt}")
        else:
            template = self.prompt_manager.load_template(
                "chunk_continuation_prompt.txt"
            )
            print("  📄 Using prompt: chunk_continuation_prompt.txt")

        metadata = analysis_result.get("metadata", {})
        commentary_id = metadata.get("commentary_id", "prakasika")
        analysis_json = json.dumps(analysis_result, indent=2, ensure_ascii=False)

        return template.format(
            commentary_id=commentary_id, analysis_json=analysis_json
        )

    def _strip_code_fences(self, text: str) -> str:
        """Removes markdown code fences from text.

        Gemini API often wraps responses in code fences like ```markdown or
        ```yaml. This method removes those fences to get clean content.

        Args:
            text: Text possibly containing code fences.

        Returns:
            Text with code fences removed and whitespace trimmed.
        """
        # Remove opening fence (with optional language specifier)
        text = re.sub(
            r"^```(?:yaml|markdown|md|yml|text)?\s*\n",
            "",
            text,
            flags=re.MULTILINE,
        )
        # Remove closing fence
        text = re.sub(r"\n```\s*$", "", text)
        return text.strip()

    def _add_frontmatter(self, converted_body: str, analysis_result: dict) -> str:
        """Adds YAML frontmatter with validation hash to converted content.

        This method constructs the complete frontmatter including:
        - Core metadata (grantha_id, part_num, canonical_title, etc.)
        - Commentary metadata with properly structured commentator field
        - Structure levels from analysis
        - Validation hash calculated from Devanagari content

        Args:
            converted_body: The converted markdown body content.
            analysis_result: Structural analysis containing all metadata.

        Returns:
            Complete document with YAML frontmatter and body.
        """
        metadata = analysis_result.get("metadata", {})
        commentaries = self._build_commentaries_metadata(metadata)
        validation_hash = hash_text(converted_body)

        frontmatter = self._build_frontmatter_dict(
            metadata, analysis_result, commentaries, validation_hash
        )
        frontmatter_yaml = yaml.dump(
            frontmatter,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

        return f"---\n{frontmatter_yaml}---\n\n{converted_body}"

    def _build_commentaries_metadata(self, metadata: dict) -> list:
        """Builds the commentaries_metadata list from analysis metadata.

        Ensures the commentator field is properly structured as an object
        with 'devanagari' and 'roman' subfields, not a simple string.

        Args:
            metadata: The metadata dict from analysis_result.

        Returns:
            List containing commentary entry dict, or empty list if no
            commentary is present.
        """
        if not metadata.get("commentary_id"):
            return []

        commentary_entry = {
            "commentary_id": metadata.get("commentary_id"),
            "commentary_title": metadata.get("commentary_title"),
        }

        # Ensure commentator is structured as an object
        commentator = metadata.get("commentator")
        if commentator:
            if isinstance(commentator, dict):
                commentary_entry["commentator"] = commentator
            else:
                # Convert string to proper structure
                commentary_entry["commentator"] = {
                    "devanagari": commentator,
                    "roman": "",  # To be filled manually if needed
                }

        if metadata.get("authored_colophon"):
            commentary_entry["authored_colophon"] = metadata.get("authored_colophon")

        return [commentary_entry]

    def _build_frontmatter_dict(
        self,
        metadata: dict,
        analysis_result: dict,
        commentaries: list,
        validation_hash: str,
    ) -> dict:
        """Builds the complete frontmatter dictionary.

        Args:
            metadata: Core metadata from analysis.
            analysis_result: Full analysis containing structure levels.
            commentaries: List of commentary metadata entries.
            validation_hash: SHA256 hash of Devanagari content.

        Returns:
            Complete frontmatter dict with all required fields, excluding
            any None values.
        """
        # Get structure_levels and ensure it's always a list
        structure_levels = analysis_result.get("structural_analysis", {}).get(
            "structure_levels", []
        )
        structure_levels = self._ensure_structure_levels_is_list(structure_levels)

        frontmatter = {
            "grantha_id": metadata.get("grantha_id"),
            "part_num": metadata.get("part_num", 1),
            "canonical_title": metadata.get("canonical_title"),
            "text_type": metadata.get("text_type", "upanishad"),
            "language": metadata.get("language", "sanskrit"),
            "structure_type": metadata.get("structure_type"),
            "commentaries_metadata": commentaries if commentaries else None,
            "structure_levels": structure_levels,
            "hash_version": HASH_VERSION,
            "validation_hash": validation_hash,
        }

        # Remove None values for cleaner output
        return {k: v for k, v in frontmatter.items() if v is not None}

    def _ensure_structure_levels_is_list(self, structure_levels) -> list:
        """Ensures structure_levels is always a list.

        The analysis may return structure_levels as a dict (single level)
        or list (multiple levels). This method normalizes it to always be
        a list for consistent YAML formatting.

        Args:
            structure_levels: Either a dict, list, or None from analysis.

        Returns:
            A list containing the structure level(s), or empty list if None.
        """
        if structure_levels is None:
            return []
        if isinstance(structure_levels, list):
            return structure_levels
        if isinstance(structure_levels, dict):
            # Single structure level as dict - wrap it in a list
            return [structure_levels]
        # Unexpected type - return empty list
        return []

    def _save_log_file(self, log_path: Path, content: str) -> None:
        """Saves content to a log file for debugging.

        Creates parent directories if needed and prints a confirmation message
        with the relative path. Warnings are printed if saving fails.

        Args:
            log_path: Path where log file will be saved.
            content: Text content to write to the log file.
        """
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(content, encoding="utf-8")

            # Try to display relative path for cleaner output
            try:
                relative_path = log_path.relative_to(Path.cwd())
            except ValueError:
                relative_path = log_path

            print(f"  💾 Saved: {relative_path}")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not save log file {log_path}: {e}")
