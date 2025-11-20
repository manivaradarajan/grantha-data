"""
A Gemini client that replays responses from a log directory.
"""

from pathlib import Path
from typing import List
from .base_client import BaseGeminiClient


class MockUploadedFile:
    """A mock uploaded file object for replay mode."""
    def __init__(self):
        self.name = "replay_mock_file"
        self.display_name = "Replay Mock File"
        self.size_bytes = 0
        self.state = "ACTIVE"
        self.uri = "mock://replay/file"


class ReplayGeminiClient(BaseGeminiClient):
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

        # Load conversion responses from chunk subdirectories
        chunk_dir = file_log_dir / "chunks"
        if chunk_dir.exists():
            # Scan for all chunk_* subdirectories and sort them
            chunk_subdirs = sorted(
                [d for d in chunk_dir.iterdir() if d.is_dir() and d.name.startswith("chunk_")],
                key=lambda d: d.name
            )

            for chunk_subdir in chunk_subdirs:
                response_file = chunk_subdir / "03_conversion_response_raw.txt"
                if response_file.exists():
                    responses.append(response_file.read_text(encoding="utf-8"))
                else:
                    raise FileNotFoundError(f"Chunk response not found: {response_file}")

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

    def upload_file(self, file_path: Path, use_upload_cache: bool = True, verbose: bool = False):
        """
        Returns a mock uploaded file object in replay mode.
        """
        return MockUploadedFile()