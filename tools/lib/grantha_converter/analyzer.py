# Standard library imports
import json
import re
from pathlib import Path
import sys
from typing import Optional

# Local imports
from gemini_processor.cache_manager import AnalysisCache
from gemini_processor.client import GeminiClient
from gemini_processor.replay_client import ReplayGeminiClient # New import
from gemini_processor.prompt_manager import PromptManager
from gemini_processor.sampler import create_smart_sample


class Analyzer:
    """Analyzes the structure of a file using the Gemini API."""

    def __init__(
        self,
        client: GeminiClient,
        prompt_manager: PromptManager,
        file_log_dir: Path,
        use_cache: bool = True,
        use_upload_cache: bool = True,
        force_reanalysis: bool = False,
        verbose: bool = False,
        analysis_cache_dir: Optional[Path] = None,
        replay_from: Optional[Path] = None, # New argument
        input_file_stem: Optional[str] = None, # New argument
    ):
        self._original_client = client # Store the original client
        self.prompt_manager = prompt_manager
        self.file_log_dir = file_log_dir
        self.use_cache = use_cache
        self.use_upload_cache = use_upload_cache
        self.force_reanalysis = force_reanalysis
        self.verbose = verbose
        self.analysis_cache_dir = analysis_cache_dir
        self.replay_from = replay_from
        self.input_file_stem = input_file_stem

        # Conditionally set the active client
        if self.replay_from and self.input_file_stem:
            self.client = ReplayGeminiClient(self.replay_from, self.input_file_stem)
        else:
            self.client = client

    def analyze(self, input_file: Path, model: str) -> dict | None:
        """
        Orchestrates the file analysis process.

        Handles caching, file reading, API interaction, and response parsing.
        Returns the analysis dictionary on success, or None on failure.
        """
        print("🔍 Analyzing file structure...")
        
        # Attempt to load the analysis from cache first.
        cached_result, cache = self._handle_analysis_cache(input_file)
        if cached_result:
            print("🚀 Skipping Gemini API call (using cached analysis)")
            self._save_log_file(
                "analysis/03_analysis_result_from_cache.json",
                json.dumps(cached_result, indent=2, ensure_ascii=False),
            )
            return cached_result

        # If no cached result, proceed with full analysis.
        try:
            full_text = input_file.read_text(encoding="utf-8")
            analysis_result = self._get_analysis_from_gemini(input_file, full_text, model)
            
            if self.use_cache and analysis_result:
                cache.save(analysis_result, verbose=self.verbose)
            
            return analysis_result

        except FileNotFoundError:
            print(f"❌ Error: Input file not found: {input_file}", file=sys.stderr)
            return None
        except ValueError as e:
            print(f"❌ Error during analysis: {e}", file=sys.stderr)
            return None

    def _get_analysis_from_gemini(self, input_file: Path, full_text: str, model: str) -> dict | None:
        """
        Handles the interaction with the Gemini API for file analysis.

        This includes uploading the file, preparing the prompt, generating
        content, and parsing the response.
        """
        # Upload the file for analysis, or fall back to text embedding.
        uploaded_file = self._upload_file_for_analysis(input_file)

        # Prepare the prompt using the appropriate template.
        analysis_prompt = self._prepare_analysis_prompt(
            "full_file_analysis_prompt.txt", full_text, uploaded_file
        )

        # Call the Gemini API to get the analysis.
        response_text = self.client.generate_content(
            model=model, prompt=analysis_prompt, uploaded_file=uploaded_file
        )
        self._save_log_file("analysis/02_analysis_response_raw.txt", response_text)

        # Parse and validate the JSON response from the API.
        analysis_result = self._parse_and_validate_analysis(response_text)
        
        return analysis_result


    def _handle_analysis_cache(self, input_file: Path):
        """Handles loading and clearing of the analysis cache."""
        cache = AnalysisCache(input_file, cache_dir=self.analysis_cache_dir)
        if self.force_reanalysis:
            cache.clear(verbose=self.verbose)
            print("📡 Forcing re-analysis - will call Gemini API and update cache")
            return None, cache

        if self.use_cache:
            cached_analysis = cache.load(verbose=self.verbose)
            if cached_analysis is not None:
                return cached_analysis, cache
            else:
                print("📡 Cache miss - will call Gemini API")
        elif not self.use_cache:
            print("📡 Cache disabled - calling Gemini API (will not save)")

        return None, cache

    def _upload_file_for_analysis(self, input_file: Path):
        """
        Uploads a file to the Gemini API for analysis, using a cache.
        In replay mode, this is a no-op.
        """
        if isinstance(self.client, ReplayGeminiClient):
            return None # No file upload in replay mode

        uploaded_file = self.client.upload_file(
            file_path=input_file,
            use_upload_cache=self.use_upload_cache,
            verbose=self.verbose,
        )

        if uploaded_file:
            self._save_log_file(
                "analysis/00_uploaded_file_info.txt",
                f"File name: {uploaded_file.name}\n"
                f"Display name: {uploaded_file.display_name}\n"
                f"Size: {uploaded_file.size_bytes} bytes\n"
                f"State: {uploaded_file.state}\n"
                f"URI: {uploaded_file.uri}\n",
            )
        else:
            print("   Falling back to text embedding...", file=sys.stderr)

        return uploaded_file

    def _prepare_analysis_prompt(
        self,
        template_name: str,
        full_text: str,
        uploaded_file
    ):
        """Prepares the analysis prompt, using file API or text embedding."""
        template = self.prompt_manager.load_template(template_name)
        print(f"  📄 Using prompt: {template_name}")

        if uploaded_file:
            analysis_prompt = template.replace(
                "\n--- INPUT TEXT ---\n{input_text}\n--- END INPUT TEXT ---",
                "\n\n[File content provided via Gemini File API - see uploaded file]",
            )
            print("📄 Using File API for analysis (efficient mode)")
        else:
            analysis_text, was_sampled = create_smart_sample(full_text, max_size=500000)
            if was_sampled:
                sample_size = len(analysis_text)
                print(f"✂️ File too large - using smart sampling")
                print(f"  📊 Sample size: {sample_size:,} bytes")
            else:
                print("📄 Using text embedding for analysis")
            analysis_prompt = template.format(input_text=analysis_text)

        self._save_log_file("analysis/01_analysis_prompt.txt", analysis_prompt)
        return analysis_prompt

    def _parse_and_validate_analysis(self, response_text: str) -> dict:
        """Parses the raw JSON response and validates its structure."""
        analysis_result = self._parse_analysis_response(response_text)
        self._validate_analysis_result(analysis_result)
        return analysis_result

    def _parse_analysis_response(self, response_text: str) -> dict:
        """
        Parses a JSON string from the API response, cleaning it first.
        """
        print(f"📝 Gemini response received ({len(response_text)} chars)")
        print("🔍 Parsing JSON response...")

        # Regex to find a JSON object within the text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if not json_match:
            raise ValueError("No JSON object found in the Gemini response.")

        json_str = json_match.group(0)
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"\n❌ Error: Could not parse extracted JSON: {e}", file=sys.stderr)
            # For debugging, save the problematic string
            self._save_log_file("analysis/04_failed_json_parse.txt", json_str)
            raise ValueError(f"Invalid JSON response from Gemini: {e}")

    def _validate_analysis_result(self, analysis_result: dict):
        """Validates the structure and content of the parsed analysis result."""
        if "metadata" not in analysis_result:
            raise ValueError("Missing 'metadata' section in analysis response")
        if (
            "chunking_strategy" not in analysis_result
            or "parsing_instructions" not in analysis_result
        ):
            raise ValueError(
                "Missing 'chunking_strategy' or 'parsing_instructions' in analysis response"
            )

        metadata = analysis_result.get("metadata", {})
        chunking_strategy = analysis_result.get("chunking_strategy", {})
        parsing_instructions = analysis_result.get("parsing_instructions", {})

        required_metadata = ["canonical_title", "grantha_id", "structure_type"]
        for field in required_metadata:
            if field not in metadata:
                print(
                    f"Warning: Missing required metadata field: {field}", file=sys.stderr
                )

        if "execution_plan" not in chunking_strategy:
            print(
                f"Warning: Missing execution_plan in chunking_strategy",
                file=sys.stderr,
            )
        if "recommended_unit" not in parsing_instructions:
            print(
                f"Warning: Missing recommended_unit in parsing_instructions",
                file=sys.stderr,
            )

        print("✓ Analysis complete")
        execution_plan = chunking_strategy.get("execution_plan", [])
        print(f"  • Chunking: {len(execution_plan)} chunks planned")
        print(
            f"  • Parsing unit: {parsing_instructions.get('recommended_unit', 'unknown')}"
        )

    def _save_log_file(self, log_path: str, content: str):
        """Saves content to a specified path in the log directory."""
        try:
            full_log_path = self.file_log_dir / log_path
            full_log_path.parent.mkdir(parents=True, exist_ok=True)
            full_log_path.write_text(content, encoding="utf-8")
            try:
                relative_path = full_log_path.relative_to(Path.cwd())
            except ValueError:
                relative_path = full_log_path
            print(f"  💾 Saved: {relative_path}")
        except Exception as e:
            print(
                f"  ⚠️  Warning: Could not save log file {full_log_path}: {e}",
                file=sys.stderr,
            )

    def _repair_json_escapes(self, text: str) -> str:
        """Attempt to repair common JSON escape sequence issues."""
        regex_pattern = r"""regex":\s*"([^"]*)"""

        def fix_regex(match):
            regex_value = match.group(1)
            fixed = regex_value.replace("\\", "\\\\")
            fixed = fixed.replace("\\\\", "\\")
            return f'"regex": "{fixed}"'

        repaired = re.sub(regex_pattern, fix_regex, text)
        return repaired