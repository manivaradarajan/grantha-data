"""Tests for the GranthaBuilder."""

import unittest

from grantha_data.builder import GranthaBuilder
from grantha_data.models import Structure


class TestGranthaBuilder(unittest.TestCase):
    """Test suite for the GranthaBuilder."""

    def setUp(self):
        """Set up the test case."""
        self.builder = GranthaBuilder(
            grantha_id="test-grantha",
            canonical_title={"devanagari": "टेस्ट ग्रन्थ"},
            text_type="upanishad",
            language="sanskrit",
            structure=Structure(
                levels=[
                    {"name": "adhyaya"},
                    {"name": "khanda"},
                    {"name": "mantra"},
                ]
            ),
        )

    def test_add_passage(self):
        """Test adding a passage."""
        self.builder.add_passage("1.1.1", {"devanagari": "मन्त्र १"})
        self.assertIn("1.1.1", self.builder._passages)

    def test_remove_passage(self):
        """Test removing a passage."""
        self.builder.add_passage("1.1.1", {"devanagari": "मन्त्र १"})
        self.builder.remove_passage("1.1.1")
        self.assertNotIn("1.1.1", self.builder._passages)

    def test_update_passage_content(self):
        """Test updating a passage's content."""
        self.builder.add_passage("1.1.1", {"devanagari": "मन्त्र १"})
        self.builder.update_passage_content("1.1.1", {"devanagari": "मन्त्र १.१"})
        self.assertEqual(
            self.builder._passages["1.1.1"].content["devanagari"],
            "मन्त्र १.१",
        )

    def test_add_commentary(self):
        """Test adding a commentary."""
        self.builder.add_commentary(
            "1.1.1",
            "shankara",
            {"devanagari": "शङ्कर भाष्य"},
        )
        self.assertIn("shankara", self.builder._commentaries)
        self.assertEqual(len(self.builder._commentaries["shankara"]), 1)

    def test_build_json_grantha(self):
        """Test building a JsonGrantha object."""
        self.builder.add_passage("1.1.1", {"devanagari": "मन्त्र १"})
        grantha = self.builder.build("json")
        self.assertEqual(grantha.grantha_id, "test-grantha")
        passage = grantha.get_passage("1.1.1")
        self.assertEqual(passage.content["devanagari"], "मन्त्र १")


if __name__ == "__main__":
    unittest.main()
