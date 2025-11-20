"""
A Gemini client that replays responses from a log directory.
"""

from pathlib import Path
from typing import List

class ReplayGeminiClient:
    """
    A mock Gemini client that replays responses from a log directory.
    """

    def __init__(self, log_dir: Path, input_file_stem: str):
        self.log_dir = log_dir
        self.input_file_stem = input_file_stem
        self.responses = self._load_responses()
        self.call_count = 0

    def _load_responses(self) -> List[str]:
        """Loads all expected responses from the log directory in order."""
        responses = []
        file_log_dir = self.log_dir / self.input_file_stem

        # Load analysis response
        analysis_log_path = file_log_dir / "analysis" / "02_analysis_response_raw.txt"
        if analysis_log_path.exists():
            responses.append(analysis_log_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(f"Analysis log not found: {analysis_log_path}")

        # Load conversion responses
        chunk_dir = file_log_dir / "chunks"
        if chunk_dir.exists():
            for i in range(1000):  # A reasonable upper limit for chunks
                log_file = chunk_dir / f"{i:03d}_response.txt"
                if not log_file.exists():
                    break
                responses.append(log_file.read_text(encoding="utf-8"))
        
        return responses

    def generate_content(self, model: str, prompt: str, uploaded_file=None) -> str:
        """
        Returns the next response from the pre-loaded log files.
        """
        if self.call_count >= len(self.responses):
            raise ValueError("No more responses to replay in the log directory.")
        
        response = self.responses[self.call_count]
        self.call_count += 1
        return response

    def upload_file(self, file_path: Path, use_upload_cache: bool, verbose: bool):
        """
        This is a no-op in replay mode.
        """
        return None