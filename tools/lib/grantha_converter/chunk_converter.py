# Standard library imports
import json
import tempfile
from pathlib import Path
import re

# Third-party imports
import yaml

# Local imports
from gemini_processor.base_client import BaseGeminiClient
from gemini_processor.prompt_manager import PromptManager


class ChunkConverter:
    """Converts a single text chunk using the Gemini API."""

    def __init__(
        self,
        client: BaseGeminiClient,
        prompt_manager: PromptManager,
        file_log_dir: Path,
        use_upload_cache: bool = True,
    ):
        self.client = client
        self.prompt_manager = prompt_manager
        self.file_log_dir = file_log_dir
        self.use_upload_cache = use_upload_cache

    def convert(
        self,
        chunk_text: str,
        chunk_metadata: dict,
        analysis_result: dict,
        model: str,
    ) -> str:
        """
        Orchestrates the conversion of a single chunk of text.

        This method handles the temporary file management, API interaction,
        and final assembly of the converted chunk with its frontmatter.
        """
        chunk_index = chunk_metadata.get("chunk_index")
        chunk_log_dir = self.file_log_dir / "chunks" / f"chunk_{chunk_index}"
        
        temp_chunk_dir = Path(tempfile.gettempdir()) / "grantha_temp_chunks"
        temp_chunk_dir.mkdir(exist_ok=True)
        temp_file_path = temp_chunk_dir / f"chunk_{chunk_index}.md"

        try:
            # Create a temporary file with the chunk content to be uploaded.
            temp_file_path.write_text(chunk_text, encoding="utf-8")

            # Upload the file and get the Gemini API response.
            uploaded_file = self._upload_chunk_for_conversion(temp_file_path, chunk_log_dir)
            converted_body = self._get_conversion_from_gemini(
                model, uploaded_file, analysis_result, chunk_text, chunk_log_dir
            )

            # Combine the converted body with the standard frontmatter.
            return self._add_frontmatter(converted_body, analysis_result)

        finally:
            # Ensure the temporary file is always cleaned up.
            if temp_file_path.exists():
                temp_file_path.unlink()

    def _upload_chunk_for_conversion(self, temp_file_path: Path, chunk_log_dir: Path):
        """Uploads the temporary chunk file to the Gemini API."""
        uploaded_chunk_file = self.client.upload_file(
            file_path=temp_file_path,
            use_upload_cache=self.use_upload_cache,
            verbose=True,
        )
        if not uploaded_chunk_file:
            raise ValueError(f"Failed to upload chunk {temp_file_path.name} to File API.")

        # Log the details of the uploaded file for debugging purposes.
        self._save_log_file(
            chunk_log_dir / "00_uploaded_chunk_info.txt",
            f"File name: {uploaded_chunk_file.name}\\n"
            f"Display name: {uploaded_chunk_file.display_name}\\n"
            f"Size: {uploaded_chunk_file.size_bytes} bytes\\n"
            f"State: {uploaded_chunk_file.state}\\n"
            f"URI: {uploaded_chunk_file.uri}\\n",
        )
        return uploaded_chunk_file

    def _get_conversion_from_gemini(
        self, model: str, uploaded_file, analysis_result: dict, chunk_text: str, chunk_log_dir: Path
    ) -> str:
        """
        Prepares the prompt, calls the Gemini API, and processes the response.
        """
        # Create the detailed prompt required for the conversion.
        prompt = self._create_chunk_conversion_prompt(analysis_result)
        self._save_log_file(chunk_log_dir / "01_chunk_input.md", chunk_text)
        self._save_log_file(chunk_log_dir / "02_conversion_prompt.txt", prompt)

        print(f"🤖 Calling Gemini API model:'{model}' for chunk conversion...")
        response_text = self.client.generate_content(
            model=model, prompt=prompt, uploaded_file=uploaded_file
        )
        self._save_log_file(chunk_log_dir / "03_conversion_response_raw.txt", response_text)

        # Clean up the response by removing markdown fences.
        converted_body = self._strip_code_fences(response_text)
        self._save_log_file(chunk_log_dir / "04_converted_body.md", converted_body)
        
        return converted_body


    def _create_chunk_conversion_prompt(self, analysis_result: dict) -> str:
        """Creates the prompt for chunk conversion."""
        continuation_template = self.prompt_manager.load_template(
            "chunk_continuation_prompt.txt"
        )
        print(f"  📄 Using prompt: chunk_continuation_prompt.txt")

        metadata = analysis_result.get("metadata", {})
        commentary_id = metadata.get("commentary_id", "prakasika")

        analysis_json = json.dumps(analysis_result, indent=2, ensure_ascii=False)

        return continuation_template.format(
            commentary_id=commentary_id, analysis_json=analysis_json
        )

    def _strip_code_fences(self, text: str) -> str:
        """Remove markdown code fences from text."""
        text = re.sub(
            r"^```(?:yaml|markdown|md|yml|text)?\s*\n", "", text, flags=re.MULTILINE
        )
        text = re.sub(r"\n```\s*$", "", text)
        return text.strip()

    def _add_frontmatter(self, converted_body: str, analysis_result: dict) -> str:
        """Adds YAML frontmatter to the converted chunk body."""
        main_metadata = analysis_result.get("metadata", {})
        commentaries_metadata = []
        if main_metadata.get("commentary_id"):
            commentaries_metadata.append(
                {
                    "commentary_id": main_metadata.get("commentary_id"),
                    "commentary_title": main_metadata.get("commentary_title"),
                    "commentator": main_metadata.get("commentator"),
                    "authored_colophon": main_metadata.get("authored_colophon"),
                }
            )

        chunk_frontmatter = {
            "grantha_id": main_metadata.get("grantha_id"),
            "part_num": main_metadata.get("part_num", 1),
            "canonical_title": main_metadata.get("canonical_title"),
            "structure_type": main_metadata.get("structure_type"),
            "commentaries_metadata": (
                commentaries_metadata if commentaries_metadata else None
            ),
            "structure_levels": analysis_result.get("structural_analysis", {}).get(
                "structure_levels", {}
            ),
        }
        chunk_frontmatter = {
            k: v for k, v in chunk_frontmatter.items() if v is not None
        }

        frontmatter_yaml = yaml.dump(
            chunk_frontmatter, allow_unicode=True, sort_keys=False
        )
        return f"---\n{frontmatter_yaml}---\n\n{converted_body}"

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
