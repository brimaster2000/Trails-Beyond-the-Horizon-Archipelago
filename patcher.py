"""
Installs the game patch: a bsdiff4 delta from the game's own script_eng.p3a to the patched one (tools/build_game_patch.py
output), so the release never ships game files. Made by tools/make_release_patch.py; bsdiff4 comes with Archipelago.
"""
from __future__ import annotations

import hashlib
import json
import os
import pkgutil
import sys
from pathlib import Path

GAME_FOLDER_NAME = "The Legend of Heroes Trails beyond the Horizon"
ARCHIVE = "script_eng.p3a"
BACKUP = "script_eng.p3a.archipelago_backup"


def patch_data() -> tuple[bytes, dict]:
    delta = pkgutil.get_data(__package__, "data/script_eng.p3a.bsdiff4")
    info = json.loads(pkgutil.get_data(__package__, "data/patch.json"))
    return delta, info


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def steam_library_folders() -> list[Path]:
    if sys.platform != "win32":
        return []
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except OSError:
        return []
    folders = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for line in vdf.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.strip().split('"')
            if len(parts) >= 4 and parts[1] == "path":
                folders.append(Path(parts[3].replace("\\\\", "\\")))
    return folders


def find_game_folder() -> Path | None:
    for library in steam_library_folders():
        folder = library / "steamapps" / "common" / GAME_FOLDER_NAME
        if (folder / "kai.exe").exists():
            return folder
    return None


def status(folder: Path, info: dict) -> str:
    """'patched', 'vanilla', 'unknown' or 'missing'."""
    archive = folder / ARCHIVE
    if not archive.exists():
        return "missing"
    digest = md5(archive)
    if digest == info["patched_md5"]:
        return "patched"
    if digest == info["vanilla_md5"]:
        return "vanilla"
    return "unknown"


def install(folder: Path, delta: bytes, info: dict) -> str:
    """Patches script_eng.p3a in place, keeping the original as a backup. Returns a message for the player."""
    import bsdiff4

    archive = folder / ARCHIVE
    state = status(folder, info)
    if state == "patched":
        return "The game patch is already installed."
    if state == "missing":
        return f"No {ARCHIVE} in {folder}."
    if state == "unknown":
        return (f"{ARCHIVE} is not the version this patch was made for (game update or other mods?). "
                "Verify the game files in Steam, then try again.")
    original = archive.read_bytes()
    patched = bsdiff4.patch(original, delta)
    if hashlib.md5(patched).hexdigest() != info["patched_md5"]:
        return "The patch did not apply cleanly; nothing was changed."
    backup = folder / BACKUP
    if not backup.exists():
        backup.write_bytes(original)
    temporary = folder / (ARCHIVE + ".archipelago_tmp")
    temporary.write_bytes(patched)
    os.replace(temporary, archive)
    return f"Game patch installed (original saved as {BACKUP})."


def uninstall(folder: Path, info: dict) -> str:
    archive, backup = folder / ARCHIVE, folder / BACKUP
    if status(folder, info) == "vanilla":
        return "The game patch is not installed."
    if not backup.exists() or md5(backup) != info["vanilla_md5"]:
        return "No usable backup found: verify the game files in Steam to restore the original."
    os.replace(backup, archive)
    return "Game patch removed; the original script_eng.p3a is back."
