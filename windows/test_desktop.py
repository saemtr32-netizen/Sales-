"""Controller data migration tests; no interactive Tk window is opened."""

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import desktop


class DesktopDataTest(unittest.TestCase):
    def test_existing_source_database_is_copied_without_loss_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "source.db"
            copied = Path(directory) / "desktop" / "sales.db"
            db = sqlite3.connect(original)
            try:
                db.execute("CREATE TABLE business(name TEXT)")
                db.execute("INSERT INTO business VALUES ('Nexvant Engineering')")
                db.commit()
            finally:
                db.close()
            desktop.copy_database(original, copied)
            db = sqlite3.connect(copied)
            try:
                self.assertEqual(db.execute("SELECT name FROM business").fetchone()[0], "Nexvant Engineering")
            finally:
                db.close()
            with self.assertRaises(FileExistsError):
                desktop.copy_database(original, copied)
            self.assertTrue(original.exists())
            self.assertEqual(list(copied.parent.glob("import-*.db")), [])

    def test_database_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SALES_DB": str(Path(directory) / "chosen.db")}):
            self.assertEqual(desktop.data_path(), Path(directory) / "chosen.db")

    def test_default_database_is_outside_installation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"LOCALAPPDATA": directory}):
            with patch.dict(os.environ):
                os.environ.pop("SALES_DB", None)
                self.assertEqual(desktop.data_path(), Path(directory) / "NexvantEngineering" / "data" / "sales.db")


if __name__ == "__main__":
    unittest.main()
