"""Exercise filesystem boundaries before connecting real client destinations."""

import tempfile
import unittest
from pathlib import Path

from scripts.installer.files import Conflict, atomic_json, replace_link, safe_path, same_link


class FileTests(unittest.TestCase):
    """Keep unrelated paths and symlink ancestors outside deployment ownership."""

    def test_parent_link_rejected(self) -> None:
        """A directory link must not redirect a nominally scoped write."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside").mkdir()
            (root / "client").symlink_to(root / "outside")
            with self.assertRaises(Conflict):
                safe_path(root / "client" / "settings.json")

    def test_link_and_private_receipt(self) -> None:
        """Link text is stable and recovery metadata is private."""
        with tempfile.TemporaryDirectory(prefix="harness space ") as directory:
            root = Path(directory)
            source = root / "tracked"
            source.write_text("versioned")
            destination = root / "client" / "settings"
            replace_link(destination, source)
            self.assertTrue(same_link(destination, source))
            self.assertEqual(destination.read_text(), "versioned")
            receipt = root / "receipt.json"
            atomic_json(receipt, {"revision": "test"})
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
