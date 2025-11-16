"""Tests for sampler module."""

import unittest

from gemini_processor.sampler import create_custom_sample, create_smart_sample


class TestCreateSmartSample(unittest.TestCase):
    """Test suite for create_smart_sample function."""

    def test_small_file_returns_full_text(self):
        """Small files under max_size should return full text unchanged."""
        text = "A" * 1000  # 1KB
        result, was_sampled = create_smart_sample(text, max_size=500000)

        self.assertEqual(result, text)
        self.assertFalse(was_sampled)

    def test_exact_max_size_returns_full_text(self):
        """Files exactly at max_size should return full text."""
        text = "A" * 500000  # Exactly 500KB
        result, was_sampled = create_smart_sample(text, max_size=500000)

        self.assertEqual(result, text)
        self.assertFalse(was_sampled)

    def test_large_file_triggers_sampling(self):
        """Files over max_size should be sampled."""
        text = "A" * 600000  # 600KB
        result, was_sampled = create_smart_sample(text, max_size=500000)

        self.assertNotEqual(result, text)
        self.assertTrue(was_sampled)

    def test_sampled_output_contains_markers(self):
        """Sampled output should contain section markers."""
        text = "A" * 600000
        result, was_sampled = create_smart_sample(text, max_size=500000)

        self.assertIn("--- SAMPLE CONTINUES (MIDDLE SECTION) ---", result)
        self.assertIn("--- SAMPLE CONTINUES (END SECTION) ---", result)

    def test_sampled_output_has_three_sections(self):
        """Sampled output should have first, middle, and last sections."""
        # Create distinctive text for each region
        text = "A" * 200000 + "B" * 200000 + "C" * 200000  # 600KB total
        result, was_sampled = create_smart_sample(text, max_size=500000)

        # Should contain parts from beginning (A's), middle (B's), and end (C's)
        self.assertIn("A", result)
        self.assertIn("B", result)
        self.assertIn("C", result)

    def test_custom_max_size(self):
        """Should respect custom max_size parameter."""
        text = "A" * 100000  # 100KB
        result, was_sampled = create_smart_sample(text, max_size=50000)

        self.assertTrue(was_sampled)

    def test_very_large_file(self):
        """Should handle very large files (>1MB)."""
        text = "A" * 2000000  # 2MB
        result, was_sampled = create_smart_sample(text, max_size=500000)

        self.assertTrue(was_sampled)
        # Sample should be smaller than original
        self.assertLess(len(result), len(text))

    def test_empty_text(self):
        """Empty text should return empty text."""
        text = ""
        result, was_sampled = create_smart_sample(text, max_size=500000)

        self.assertEqual(result, "")
        self.assertFalse(was_sampled)


class TestCreateCustomSample(unittest.TestCase):
    """Test suite for create_custom_sample function."""

    def test_small_file_returns_full_text(self):
        """Small files under max_size should return full text."""
        text = "A" * 1000
        result, was_sampled = create_custom_sample(
            text, max_size=500000, first_bytes=1000, middle_bytes=500, last_bytes=500
        )

        self.assertEqual(result, text)
        self.assertFalse(was_sampled)

    def test_large_file_with_custom_chunks(self):
        """Should use custom chunk sizes for sampling."""
        text = "A" * 100000 + "B" * 100000 + "C" * 100000  # 300KB
        result, was_sampled = create_custom_sample(
            text,
            max_size=50000,
            first_bytes=10000,
            middle_bytes=5000,
            last_bytes=5000,
        )

        self.assertTrue(was_sampled)
        self.assertIn("A", result)
        self.assertIn("B", result)
        self.assertIn("C", result)

    def test_negative_chunk_size_raises_error(self):
        """Negative chunk sizes should raise ValueError."""
        text = "A" * 1000

        with self.assertRaises(ValueError) as context:
            create_custom_sample(
                text, max_size=500000, first_bytes=-100, middle_bytes=500, last_bytes=500
            )
        self.assertIn("non-negative", str(context.exception))

    def test_total_exceeds_max_size_raises_error(self):
        """Total sample size exceeding max_size should raise ValueError."""
        text = "A" * 1000

        with self.assertRaises(ValueError) as context:
            create_custom_sample(
                text,
                max_size=1000,
                first_bytes=500,
                middle_bytes=500,
                last_bytes=500,
            )
        self.assertIn("exceeds max_size", str(context.exception))

    def test_custom_sampling_has_markers(self):
        """Custom sampled output should contain section markers."""
        text = "A" * 600000
        result, was_sampled = create_custom_sample(
            text,
            max_size=50000,
            first_bytes=10000,
            middle_bytes=5000,
            last_bytes=5000,
        )

        self.assertIn("--- SAMPLE CONTINUES (MIDDLE SECTION) ---", result)
        self.assertIn("--- SAMPLE CONTINUES (END SECTION) ---", result)

    def test_zero_chunk_sizes(self):
        """Zero chunk sizes should be allowed."""
        text = "A" * 100000
        result, was_sampled = create_custom_sample(
            text, max_size=50000, first_bytes=10000, middle_bytes=0, last_bytes=0
        )

        self.assertTrue(was_sampled)

    def test_empty_text_custom_sample(self):
        """Empty text should return empty text."""
        text = ""
        result, was_sampled = create_custom_sample(
            text, max_size=500000, first_bytes=1000, middle_bytes=500, last_bytes=500
        )

        self.assertEqual(result, "")
        self.assertFalse(was_sampled)


if __name__ == "__main__":
    unittest.main()
