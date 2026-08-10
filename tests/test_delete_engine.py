import tempfile
import unittest
from pathlib import Path

from delete_engine import UnsafeDeleteError, delete_path, validate_target


class DeleteEngineTests(unittest.TestCase):
    def test_permanent_file_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "delete-me.txt"
            target.write_text("temporary test", encoding="utf-8")
            result = delete_path(target, mode="permanent")
            self.assertFalse(target.exists())
            self.assertIn("已永久删除", result)

    def test_permanent_folder_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "delete-folder"
            target.mkdir()
            (target / "nested.txt").write_text("temporary test", encoding="utf-8")
            delete_path(target, mode="permanent")
            self.assertFalse(target.exists())

    def test_filesystem_root_is_blocked(self):
        root = Path(Path.cwd().anchor)
        if not root.anchor:
            self.skipTest("No filesystem anchor available")
        with self.assertRaises(UnsafeDeleteError):
            validate_target(root)


if __name__ == "__main__":
    unittest.main()
