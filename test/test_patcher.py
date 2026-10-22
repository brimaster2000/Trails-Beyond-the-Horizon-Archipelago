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


class TestFolderChecks(unittest.TestCase):
    def test_exe_or_folder_both_give_the_folder(self) -> None:
        self.assertEqual(patcher.folder_from_path(r'"C:\Games\TBTH\kai.exe"'), Path(r"C:\Games\TBTH"))
        self.assertEqual(patcher.folder_from_path(r"C:\Games\TBTH"), Path(r"C:\Games\TBTH"))

    def test_problems_are_explained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.assertIn("kai.exe", patcher.folder_problem(folder))
            (folder / "kai.exe").write_bytes(b"")
            self.assertIn("script_eng.p3a", patcher.folder_problem(folder))
            (folder / "script_eng.p3a").write_bytes(b"")
            self.assertIsNone(patcher.folder_problem(folder))


class TestFindGame(unittest.TestCase):
    """The client's game lookup: given path, host.yaml, Steam, then a file browser (GOG and other stores)."""

    def setUp(self) -> None:
        from unittest import mock

        self.temp = tempfile.TemporaryDirectory()
        self.game = Path(self.temp.name) / "GOG Games" / "Trails beyond the Horizon"
        self.game.mkdir(parents=True)
        (self.game / "kai.exe").write_bytes(b"")
        (self.game / "script_eng.p3a").write_bytes(b"")
        from ..world import trailsbthSettings

        self.group = mock.Mock(game_exe=trailsbthSettings.GameExe(""))
        self.patches = [mock.patch("settings.get_settings"),
                        mock.patch.object(patcher, "find_steam_game_folder", return_value=None)]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def find(self, chosen: str = "", browse_result=None) -> Path | None:
        import asyncio
        from unittest import mock
        from .. import Client

        async def run():
            ctx = Client.TBTHContext(None, None)
            with mock.patch.object(Client.TBTHContext, "game_setting", return_value=self.group), \
                    mock.patch.object(type(self.group.game_exe), "browse", return_value=browse_result):
                return await ctx.find_game(chosen)

        return asyncio.run(run())

    def test_given_exe_is_used_and_remembered(self) -> None:
        self.assertEqual(self.find(str(self.game / "kai.exe")), self.game)
        self.assertEqual(str(self.group.game_exe), str(self.game / "kai.exe"))

    def test_given_wrong_folder_is_refused(self) -> None:
        self.assertIsNone(self.find(self.temp.name))
        self.assertEqual(str(self.group.game_exe), "")

    def test_saved_path_comes_first(self) -> None:
        from ..world import trailsbthSettings

        self.group.game_exe = trailsbthSettings.GameExe(str(self.game / "kai.exe"))
        self.assertEqual(self.find(), self.game)

    def test_steam_install_is_found_and_remembered(self) -> None:
        patcher.find_steam_game_folder.return_value = self.game
        self.assertEqual(self.find(), self.game)
        self.assertEqual(str(self.group.game_exe), str(self.game / "kai.exe"))

    def test_otherwise_the_player_picks_kai_exe(self) -> None:
        from ..world import trailsbthSettings

        self.assertEqual(self.find(browse_result=trailsbthSettings.GameExe(str(self.game / "kai.exe"))), self.game)
        self.assertEqual(str(self.group.game_exe), str(self.game / "kai.exe"))

    def test_cancelled_browser(self) -> None:
        self.assertIsNone(self.find(browse_result=None))

    def test_browser_refuses_a_wrong_exe(self) -> None:
        from ..world import trailsbthSettings

        with self.assertRaises(ValueError):
            trailsbthSettings.GameExe.validate(self.temp.name + r"\notepad.exe")

    def test_empty_setting_as_archipelago_resolves_it_counts_as_unset(self) -> None:
        # An empty game_exe reads back as "<Archipelago folder>\.exe"; it must not count as a saved (broken) path.
        from ..world import trailsbthSettings

        self.group.game_exe = trailsbthSettings.GameExe(self.temp.name + r"\.exe")
        patcher.find_steam_game_folder.return_value = self.game
        with self.assertNoLogs("Client", level="INFO"):  # no "saved game path no longer works"
            self.assertEqual(self.find(), self.game)
