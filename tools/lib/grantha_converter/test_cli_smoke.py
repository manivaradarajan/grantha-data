"""
Smoke tests for all CLI commands registered in pyproject.toml.

These tests verify that:
1. All CLI commands can be imported and invoked
2. --help works for each command
3. Basic error handling works (invalid arguments)

These are NOT comprehensive functional tests - just smoke tests to ensure
the commands are properly wired up and don't crash on startup.
"""

import subprocess
import sys
import pytest
from pathlib import Path


class TestCLISmokeTests:
    """Smoke tests for all CLI commands."""

    def run_command(self, cmd: list, expect_success: bool = True):
        """Helper to run a command and check exit code.

        Args:
            cmd: Command and arguments as list
            expect_success: If True, expect exit code 0, otherwise expect non-zero

        Returns:
            CompletedProcess result
        """
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if expect_success:
            assert result.returncode == 0, (
                f"Command {' '.join(cmd)} failed with exit code {result.returncode}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )
        else:
            assert result.returncode != 0, (
                f"Command {' '.join(cmd)} should have failed but succeeded\n"
                f"STDOUT: {result.stdout}"
            )

        return result

    def test_grantha_converter_help(self):
        """Test grantha-converter --help works."""
        result = self.run_command(["grantha-converter", "--help"])
        assert "grantha-converter" in result.stdout.lower()
        assert "json2md" in result.stdout
        assert "md2json" in result.stdout

    def test_grantha_converter_no_args(self):
        """Test grantha-converter with no arguments shows usage."""
        result = self.run_command(["grantha-converter"], expect_success=False)
        # Should fail with usage message
        assert "usage:" in result.stderr.lower() or "usage:" in result.stdout.lower()

    def test_grantha_converter_json2md_help(self):
        """Test grantha-converter json2md --help works."""
        result = self.run_command(["grantha-converter", "json2md", "--help"])
        assert "json2md" in result.stdout.lower()
        assert "--input" in result.stdout or "-i" in result.stdout

    def test_grantha_converter_md2json_help(self):
        """Test grantha-converter md2json --help works."""
        result = self.run_command(["grantha-converter", "md2json", "--help"])
        assert "md2json" in result.stdout.lower()
        assert "--input" in result.stdout or "-i" in result.stdout

    def test_grantha_converter_verify_help(self):
        """Test grantha-converter verify --help works."""
        result = self.run_command(["grantha-converter", "verify", "--help"])
        assert "verify" in result.stdout.lower()

    def test_devanagari_diff_help(self):
        """Test devanagari-diff --help works."""
        result = self.run_command(["devanagari-diff", "--help"])
        assert "devanagari" in result.stdout.lower()
        # Should show positional arguments for file1 and file2
        assert "file" in result.stdout.lower()

    def test_devanagari_diff_missing_args(self):
        """Test devanagari-diff fails gracefully with missing arguments."""
        result = self.run_command(["devanagari-diff"], expect_success=False)
        # Should fail with usage or error about required arguments

    def test_devanagari_diff_nonexistent_files(self):
        """Test devanagari-diff fails gracefully with non-existent files."""
        result = self.run_command(
            ["devanagari-diff", "/nonexistent/file1.md", "/nonexistent/file2.md"],
            expect_success=False
        )
        # Should fail because files don't exist

    def test_devanagari_repair_help(self):
        """Test devanagari-repair --help works."""
        result = self.run_command(["devanagari-repair", "--help"])
        assert "repair" in result.stdout.lower()
        assert "fileA" in result.stdout or "source" in result.stdout.lower()
        assert "fileB" in result.stdout or "target" in result.stdout.lower()

    def test_devanagari_repair_missing_args(self):
        """Test devanagari-repair fails gracefully with missing arguments."""
        result = self.run_command(["devanagari-repair"], expect_success=False)
        # Should fail with usage or error about required arguments

    def test_devanagari_repair_nonexistent_files(self):
        """Test devanagari-repair fails gracefully with non-existent files."""
        result = self.run_command(
            ["devanagari-repair", "/nonexistent/file1.md", "/nonexistent/file2.md"],
            expect_success=False
        )
        # Should fail because files don't exist

    def test_convert_meghamala_help(self):
        """Test convert-meghamala --help works."""
        result = self.run_command(["convert-meghamala", "--help"])
        assert "meghamala" in result.stdout.lower()

    def test_pdf_ocr_help(self):
        """Test pdf-ocr --help works."""
        result = self.run_command(["pdf-ocr", "--help"])
        assert "pdf" in result.stdout.lower() or "ocr" in result.stdout.lower()

    @pytest.mark.skipif(
        not Path("sources/upanishads/meghamala/aitareya/aitareyopaniSat.md").exists(),
        reason="Test files not available"
    )
    def test_devanagari_diff_actual_files(self):
        """Test devanagari-diff works with actual repository files."""
        file1 = "sources/upanishads/meghamala/aitareya/aitareyopaniSat.md"
        file2 = "structured_md/upanishads/aitareya/aitareya-upanishad-rangaramanuja-01-01.md"

        if not Path(file2).exists():
            pytest.skip("Second test file not available")

        # Should succeed (files exist and are valid)
        result = self.run_command(["devanagari-diff", file1, file2])
        # Should output something about Devanagari characters or differences

    @pytest.mark.skipif(
        not Path("sources/upanishads/meghamala/aitareya/aitareyopaniSat.md").exists(),
        reason="Test files not available"
    )
    def test_devanagari_repair_actual_files(self):
        """Test devanagari-repair works with actual repository files."""
        import tempfile

        file1 = "sources/upanishads/meghamala/aitareya/aitareyopaniSat.md"
        file2 = "structured_md/upanishads/aitareya/aitareya-upanishad-rangaramanuja-01-01.md"

        if not Path(file2).exists():
            pytest.skip("Second test file not available")

        # Use temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp:
            output_file = tmp.name

        try:
            # Should succeed (files exist and are valid)
            result = self.run_command([
                "devanagari-repair",
                file1,
                file2,
                "-o", output_file
            ])

            # Verify output file was created
            assert Path(output_file).exists(), "Repair should create output file"

            # Verify output has content
            content = Path(output_file).read_text()
            assert len(content) > 0, "Repaired file should have content"
            assert "---" in content, "Repaired file should have YAML frontmatter"

        finally:
            # Clean up
            if Path(output_file).exists():
                Path(output_file).unlink()


class TestCLIImports:
    """Test that all CLI entry points can be imported."""

    def test_grantha_converter_import(self):
        """Test grantha_converter.cli:main can be imported."""
        from grantha_converter.cli import main
        assert callable(main)

    def test_devanagari_diff_import(self):
        """Test scripts.devanagari_tools.devanagari_diff:main can be imported."""
        from scripts.devanagari_tools.devanagari_diff import main
        assert callable(main)

    def test_devanagari_repair_import(self):
        """Test scripts.devanagari_tools.devanagari_repair:main can be imported."""
        from scripts.devanagari_tools.devanagari_repair import main
        assert callable(main)

    def test_convert_meghamala_import(self):
        """Test scripts.meghamala_converter.convert_meghamala:main can be imported."""
        from scripts.meghamala_converter.convert_meghamala import main
        assert callable(main)

    def test_pdf_ocr_import(self):
        """Test scripts.pdf_ocr:main can be imported."""
        from scripts.pdf_ocr import main
        assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
