"""
Reads Trails beyond the Horizon save files (Steam, NISA release).

Layout, found by diffing real saves:
- Saved Games/FALCOM/Kai/saveNNN/user.dat is one zstd frame; it decompresses to a fixed 2,722,840-byte block.
- Scenario flags (the script VM's flag()/set_flag()) form a bit array at offset 0xC, least significant bit first:
  flag n is bit (n % 8) of byte 0xC + n // 8.
- The game autosaves straight after every chest (system.TBoxProcess calls savedata_auto_save), so the newest save
  always reflects the last chest opened.
"""
from __future__ import annotations

import os
from pathlib import Path

FLAG_ARRAY_OFFSET = 0xC
DEFAULT_SAVE_DIR = Path(os.path.expandvars(r"%USERPROFILE%\Saved Games\FALCOM\Kai"))


def decompress_save(path: Path) -> bytes:
    import zstandard  # imported lazily so generation never needs it

    return zstandard.ZstdDecompressor().decompress(path.read_bytes(), max_output_size=64 << 20)


def flag_is_set(save: bytes, flag: int, offset: int = FLAG_ARRAY_OFFSET) -> bool:
    """offset=0 for a bare flag array read from game memory."""
    return bool(save[offset + flag // 8] >> (flag % 8) & 1)


def newest_save(save_dir: Path = DEFAULT_SAVE_DIR) -> Path | None:
    saves = list(save_dir.glob("save*/user.dat"))
    return max(saves, key=lambda p: p.stat().st_mtime_ns) if saves else None


def checked_locations(save: bytes, location_flags: dict[int, int], offset: int = FLAG_ARRAY_OFFSET) -> set[int]:
    """location_flags maps AP location id -> scenario flag; returns the ids whose flag is set."""
    return {location_id for location_id, flag in location_flags.items() if flag_is_set(save, flag, offset)}
