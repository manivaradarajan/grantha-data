
import pytest

from grantha_converter.grantha_markdown_validator import validate_markdown_file


@pytest.fixture
def valid_header():
    return """---
grantha_id: test-grantha
part_num: 1
canonical_title: "Test Grantha"
text_type: upanishad
language: sanskrit
structure_levels: []
commentaries_metadata:
  test-commentator:
    commentary_title: "Test Commentary"
    commentator:
      devanagari: "Test"
---
"""

def test_valid_file_simple_commentary(tmpdir, valid_header):
    content = valid_header + """
# Mantra 1.1
<!-- sanskrit:devanagari -->
Mantra text.
<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "test-commentator"} -->
# Commentary: 1.1
<!-- sanskrit:devanagari -->
Commentary on mantra 1.1.
<!-- /sanskrit:devanagari -->
"""
    filepath = tmpdir.join("valid.md")
    filepath.write(content)
    errors = validate_markdown_file(str(filepath))
    assert not errors, f"Validation failed unexpectedly: {errors}"

def test_valid_file_verbose_commentary_backwards_compatible(tmpdir, valid_header):
    content = valid_header + """
# Mantra 1.1
<!-- sanskrit:devanagari -->
Mantra text.
<!-- /sanskrit:devanagari -->

<!-- commentary: {"passage_ref": "1.1", "commentary_id": "test-commentator"} -->
# Commentary: 1.1
<!-- sanskrit:devanagari -->
Commentary on mantra 1.1.
<!-- /sanskrit:devanagari -->
"""
    filepath = tmpdir.join("valid_verbose.md")
    filepath.write(content)
    errors = validate_markdown_file(str(filepath))
    assert not errors, f"Validation failed unexpectedly on backwards-compatible format: {errors}"

def test_missing_commentary_id(tmpdir, valid_header):
    content = valid_header + """
# Mantra 1.1
<!-- sanskrit:devanagari -->
Mantra text.
<!-- /sanskrit:devanagari -->

<!-- commentary: {"passage_ref": "1.1"} -->
# Commentary: 1.1
<!-- sanskrit:devanagari -->
Commentary on mantra 1.1.
<!-- /sanskrit:devanagari -->
"""
    filepath = tmpdir.join("invalid.md")
    filepath.write(content)
    errors = validate_markdown_file(str(filepath))
    assert len(errors) == 1
    assert "missing 'commentary_id'" in errors[0]
