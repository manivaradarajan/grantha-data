# Standard library imports
import unittest
import tempfile
import shutil
from pathlib import Path

# Local imports
from grantha_converter.utils import (
    extract_part_number_from_filename,
    get_directory_parts,
)


class TestUtils(unittest.TestCase):
    def test_extract_part_number_from_filename(self):
        test_cases = {
            "01-02.md": 2,
            "part-3.md": 3,
            "part4.md": 4,
            "chAndogyopaniSat-prathama.md": 1,
            "kaThopaniSat-dvitIyA-valla.md": 2,
            "brihadaranyaka-03.md": 3,
            "05.md": 5,
            "no_number.md": 1,  # Default
            "isa.md": 1,  # Default
        }
        for filename, expected in test_cases.items():
            with self.subTest(filename=filename):
                self.assertEqual(extract_part_number_from_filename(filename), expected)

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_get_directory_parts(self):
        # Create dummy files
        dir_path = Path(self.test_dir)
        (dir_path / "part-02.md").touch()
        (dir_path / "part-01.md").touch()
        (dir_path / "PROVENANCE.yaml").touch()  # Should be ignored
        (dir_path / "another_file.txt").touch()  # Should be ignored

        parts = get_directory_parts(dir_path)

        self.assertEqual(len(parts), 2)
        # Check if sorted correctly
        self.assertEqual(parts[0][0].name, "part-01.md")
        self.assertEqual(parts[0][1], 1)
        self.assertEqual(parts[1][0].name, "part-02.md")
        self.assertEqual(parts[1][1], 2)


if __name__ == "__main__":
    unittest.main()
