import unittest

from grantha_converter.md_to_json import convert_to_json


class TestCommentaryMetadata(unittest.TestCase):

    def test_merge_frontmatter_metadata(self):
        markdown_content = """---
grantha_id: test-grantha
structure_levels:
  - key: Mantra
commentaries_metadata:
  test-commentary:
    commentary_title: "Test Title"
    commentator:
      devanagari: "Test Commentator"
---
# Mantra 1.1
<!-- sanskrit:devanagari -->
Mantra text.
<!-- /sanskrit:devanagari -->
<!-- commentary: {"commentary_id": "test-commentary", "passage_ref": "1.1"} -->
# Commentary: 1.1
<!-- sanskrit:devanagari -->
Some commentary text.
<!-- /sanskrit:devanagari -->
"""

        json_data = convert_to_json(markdown_content)

        # commentaries is a dict keyed by commentary_id, not a list
        self.assertEqual(len(json_data['commentaries']), 1)
        self.assertIn('test-commentary', json_data['commentaries'])
        commentary = json_data['commentaries']['test-commentary']

        self.assertEqual(commentary['commentary_title'], "Test Title")
        self.assertEqual(commentary['commentator']['devanagari'], "Test Commentator")
        self.assertEqual(commentary['passages'][0]['ref'], "1.1")

if __name__ == '__main__':
    unittest.main()
