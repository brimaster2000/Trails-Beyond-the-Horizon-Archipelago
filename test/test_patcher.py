import hashlib
import tempfile
import unittest
from pathlib import Path

import bsdiff4

from .. import patcher

VANILLA = b"PH3ARCV" + bytes(range(256)) * 40
PATCHED = VANILLA[:3000] + b"Archipelago was here" + VANILLA[3000:]
INFO = {"vanilla_md5": hashlib.md5(VANILLA).hexdigest(), "patched_md5": hashlib.md5(PATCHED).hexdigest()}
DELTA = bsdiff4.diff(VANILLA, PATCHED)


class TestPatcher(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        (self.folder / "kai.exe").write_bytes(b"")
        self.archive = self.folder / patcher.ARCHIVE

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_install_then_uninstall(self) -> None:
        self.archive.write_bytes(VANILLA)
        self.assertEqual(patcher.status(self.folder, INFO), "vanilla")
        self.assertIn("installed", patcher.install(self.folder, DELTA, INFO))
        self.assertEqual(self.archive.read_bytes(), PATCHED)
        self.assertEqual((self.folder / patcher.BACKUP).read_bytes(), VANILLA)
        self.assertIn("already installed", patcher.install(self.folder, DELTA, INFO))
        self.assertIn("removed", patcher.uninstall(self.folder, INFO))
        self.assertEqual(self.archive.read_bytes(), VANILLA)
        self.assertFalse((self.folder / patcher.BACKUP).exists())

    def test_unknown_version_is_left_alone(self) -> None:
        self.archive.write_bytes(VANILLA + b"updated")
        self.assertEqual(patcher.status(self.folder, INFO), "unknown")
        self.assertIn("not the version", patcher.install(self.folder, DELTA, INFO))
        self.assertEqual(self.archive.read_bytes(), VANILLA + b"updated")
        self.assertFalse((self.folder / patcher.BACKUP).exists())

    def test_missing_archive(self) -> None:
        self.assertEqual(patcher.status(self.folder, INFO), "missing")

    def test_uninstall_without_backup_points_to_steam(self) -> None:
        self.archive.write_bytes(PATCHED)
        self.assertIn("verify the game files", patcher.uninstall(self.folder, INFO))
        self.assertEqual(self.archive.read_bytes(), PATCHED)

    def test_release_patch_ships_with_the_world(self) -> None:
        delta, info = patcher.patch_data()
        self.assertGreater(len(delta), 1000)
        self.assertEqual(set(info) >= {"vanilla_md5", "patched_md5"}, True)
