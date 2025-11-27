"""Tests for meghamala_chunker module."""

import unittest
from grantha_converter.meghamala_chunker import split_by_execution_plan


class TestSplitByExecutionPlan(unittest.TestCase):
    """Test cases for split_by_execution_plan function."""

    def test_no_gap_between_chunks(self):
        """Test that there are no gaps between consecutive chunks.

        This test addresses the bug where content between the end marker
        of one chunk and the start marker of the next chunk was being lost.

        Example: In the Chandogya Upanishad conversion, lines 625-642
        (commentary after Khanda 10 and before Khanda 11) were missing.
        """
        # Simulate the structure from the actual file
        test_text = """**प्रथमः खण्डः**

Some content in Khanda 1.

॥ इति दशमः खण्डः ॥

**प्र.** - This is important commentary that was getting lost!
More commentary here.
Even more important text.

**एकादशः खण्डः**

Content in Khanda 11.

॥ इति एकादशः खण्डः ॥
"""

        execution_plan = [
            {
                "chunk_id": 1,
                "start_marker": "**प्रथमः खण्डः**",
                "end_marker": "॥ इति दशमः खण्डः ॥",
            },
            {
                "chunk_id": 2,
                "start_marker": "**एकादशः खण्डः**",
                "end_marker": "॥ इति एकादशः खण्डः ॥",
            },
        ]

        # Run the chunking
        chunks = split_by_execution_plan(test_text, execution_plan)

        # Verify we got 2 chunks
        self.assertEqual(len(chunks), 2)

        # Verify the commentary is included in chunk 2
        chunk_2_content = chunks[1][0]
        self.assertIn("**प्र.** - This is important commentary", chunk_2_content)
        self.assertIn("More commentary here.", chunk_2_content)
        self.assertIn("Even more important text.", chunk_2_content)

        # Verify chunks are contiguous (no gap)
        chunk1_content, _ = chunks[0]
        chunk2_content, _ = chunks[1]

        # The chunks should cover the entire text with no gaps
        # We allow for the final newline to be missing, so we check >= len - 1
        total_extracted = len(chunk1_content) + len(chunk2_content)
        self.assertGreaterEqual(total_extracted, len(test_text) - 1)

    def test_single_chunk_uses_last_end_marker(self):
        """Test that single chunk mode uses the last occurrence of end_marker."""
        test_text = """Start

॥ इति प्रथमः खण्डः ॥

Middle content

॥ इति द्वितीयः खण्डः ॥

End content
"""

        execution_plan = [
            {
                "chunk_id": 1,
                "start_marker": "Start",
                "end_marker": "॥ इति द्वितीयः खण्डः ॥",
            }
        ]

        chunks = split_by_execution_plan(test_text, execution_plan)

        self.assertEqual(len(chunks), 1)
        chunk_content = chunks[0][0]

        # Should include middle content and end at the LAST occurrence
        self.assertIn("Middle content", chunk_content)
        self.assertIn("॥ इति द्वितीयः खण्डः ॥", chunk_content)

    def test_three_chunks_no_gaps(self):
        """Test that three consecutive chunks have no gaps."""
        test_text = """**Chunk 1 Start**
Content 1
**Chunk 1 End**
Gap content A
**Chunk 2 Start**
Content 2
**Chunk 2 End**
Gap content B
**Chunk 3 Start**
Content 3
**Chunk 3 End**
"""

        execution_plan = [
            {
                "chunk_id": 1,
                "start_marker": "**Chunk 1 Start**",
                "end_marker": "**Chunk 1 End**",
            },
            {
                "chunk_id": 2,
                "start_marker": "**Chunk 2 Start**",
                "end_marker": "**Chunk 2 End**",
            },
            {
                "chunk_id": 3,
                "start_marker": "**Chunk 3 Start**",
                "end_marker": "**Chunk 3 End**",
            },
        ]

        chunks = split_by_execution_plan(test_text, execution_plan)

        self.assertEqual(len(chunks), 3)

        # Verify gap content is included
        self.assertIn("Gap content A", chunks[1][0])
        self.assertIn("Gap content B", chunks[2][0])

        # Verify total coverage
        total_extracted = sum(len(content) for content, _ in chunks)
        self.assertGreaterEqual(total_extracted, len(test_text) - 1)


if __name__ == "__main__":
    unittest.main()
