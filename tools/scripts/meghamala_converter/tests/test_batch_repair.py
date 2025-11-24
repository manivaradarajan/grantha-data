import pytest
from pathlib import Path
import subprocess
import sys

# Add the script's directory to the path to allow importing
script_to_test = Path(__file__).parent.parent / "batch_repair.py"

@pytest.fixture
def setup_test_environment(tmp_path: Path) -> Path:
    """Create a temporary directory structure for testing batch_repair.py."""
    base_dir = tmp_path / "grantha-data"

    # --- Source Directory ---
    source_base = base_dir / "sources/upanishads/meghamala"
    source_upanishad_dir = source_base / "test_upanishad"
    source_upanishad_dir.mkdir(parents=True)

    (source_upanishad_dir / "perfect_match.md").write_text("""---
grantha_id: test-upanishad-perfect
---
# Title
देवनागरी पाठः
""", encoding="utf-8")

    (source_upanishad_dir / "unmatched_source.md").write_text("""---
grantha_id: test-upanishad-unmatched-src
---
# Unmatched
अद्वितीय स्रोत पाठः
""", encoding="utf-8")

    (source_upanishad_dir / "too_different_source.md").write_text("""---
grantha_id: test-upanishad-too-different
---
# Different
भिन्न स्रोत पाठः
""", encoding="utf-8")

    # --- Destination Directory ---
    dest_base = base_dir / "structured_md/upanishads"
    dest_upanishad_dir = dest_base / "test_upanishad"
    dest_upanishad_dir.mkdir(parents=True)

    (dest_upanishad_dir / "perfect_match_dest.md").write_text("""---
grantha_id: test-upanishad-perfect-dest
grantha_hash: dummy_hash
---
# Title
देवनागरी पाठः
""", encoding="utf-8")

    (dest_upanishad_dir / "unmatched_dest.md").write_text("""---
grantha_id: test-upanishad-unmatched-dest
---
# Unmatched Dest
अद्वितीय गंतव्य पाठः
""", encoding="utf-8")

    (dest_upanishad_dir / "too_different_dest.md").write_text("""---
grantha_id: test-upanishad-too-different-dest
---
# Very Different
अत्यంతं भिन्नः गंतव्यः पाठः
""", encoding="utf-8")

    return base_dir

def run_script(cwd: Path, log_dir: Path) -> None:
    """Helper to run the batch_repair.py script."""
    # Using sys.executable to ensure we use the same Python interpreter
    subprocess.run(
        [
            sys.executable,
            str(script_to_test),
            "--source_dir", str(cwd / "sources/upanishads/meghamala"),
            "--dest_dir", str(cwd / "structured_md/upanishads"),
            "--log_dir", str(log_dir),
            "--diff_threshold", "5", # Low threshold for testing
        ],
        check=True,
        capture_output=True,
        text=True,
    )

def test_logging_logic(setup_test_environment: Path):
    """
    Tests that all three logging mechanisms (unmatched source, unmatched dest,
    and unrepairable) work correctly in a single run.
    """
    base_dir = setup_test_environment
    log_dir = base_dir / "logs"
    log_dir.mkdir()

    run_script(base_dir, log_dir)

    # --- Find the log files ---
    unmatched_source_log = next(log_dir.glob("unmatched_source_files_*.log"), None)
    unmatched_dest_log = next(log_dir.glob("unmatched_dest_files_*.log"), None)
    unrepairable_log = next(log_dir.glob("unrepairable_files_*.log"), None)

    # --- Assertions ---
    assert unmatched_source_log is not None, "Unmatched source log was not created."
    assert unmatched_dest_log is not None, "Unmatched destination log was not created."
    assert unrepairable_log is not None, "Unrepairable files log was not created."

    # --- Verify content of unmatched source log ---
    source_log_content = unmatched_source_log.read_text(encoding="utf-8")
    assert "unmatched_source.md" in source_log_content
    assert "too_different_source.md" in source_log_content # Should be here because its match is too different
    assert "perfect_match.md" not in source_log_content

    # --- Verify content of unmatched destination log ---
    dest_log_content = unmatched_dest_log.read_text(encoding="utf-8")
    assert "unmatched_dest.md" in dest_log_content
    assert "too_different_dest.md" in dest_log_content # Should be here as well
    assert "perfect_match_dest.md" not in dest_log_content

    # --- Verify content of unrepairable files log ---
    unrepairable_content = unrepairable_log.read_text(encoding="utf-8")
    assert "Source: sources/upanishads/meghamala/test_upanishad/too_different_source.md" in unrepairable_content
    assert "Destination: structured_md/upanishads/test_upanishad/too_different_dest.md" in unrepairable_content
    assert "Repair pre-check failed" in unrepairable_content
