"""
Turns a built script_eng.p3a (tools/build_game_patch.py) into the release patch: a bsdiff4 delta from the game's own
script_eng.p3a plus the checksums the client's /install_patch checks. Writes data/script_eng.p3a.bsdiff4 and
data/patch.json in this world. Dev-only: Archipelago never imports this.

Usage: make_release_patch.py <unpatched script_eng.p3a> <built script_eng.p3a> [<game build note>]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import bsdiff4

DATA = Path(__file__).resolve().parent.parent / "data"


def main(vanilla_path: Path, patched_path: Path, note: str) -> None:
    vanilla, patched = vanilla_path.read_bytes(), patched_path.read_bytes()
    delta = bsdiff4.diff(vanilla, patched)
    assert bsdiff4.patch(vanilla, delta) == patched, "round trip failed"
    DATA.mkdir(exist_ok=True)
    (DATA / "script_eng.p3a.bsdiff4").write_bytes(delta)
    info = {
        "vanilla_md5": hashlib.md5(vanilla).hexdigest(), "vanilla_size": len(vanilla),
        "patched_md5": hashlib.md5(patched).hexdigest(), "patched_size": len(patched),
        "game_build": note,
    }
    (DATA / "patch.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(f"patch: {len(delta)} bytes; {info}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
