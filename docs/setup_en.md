# Trails Beyond the Horizon Setup Guide

Work in progress: chests send checks and received items arrive in game. Act locking is not implemented yet.

## Requirements
- The Legend of Heroes: Trails beyond the Horizon (Steam, Windows)
- Archipelago, running from source with this world installed, plus the `zstandard` Python package
- Community tools in the game folder: `ingert.exe`, `p3a_extract.exe`, `p3a_archive.exe`
- A KuroTools checkout (tbl2json.py / json2tbl.py with its schemas folder)

## Installing the game patch
1. Close the game and back up `script_eng.p3a`.
2. Run `tools/build_game_patch.py "<game folder>" "<KuroTools folder>" "<work folder>" ["<unpatched script_eng.p3a>"]`
   and copy the built `script_eng.p3a` into the game folder.
3. The patch adds an "Archipelago Item" that every standard chest now gives instead of its normal contents,
   and a script hook that hands over items received from the multiworld.

## Playing
1. Start the game and load a save.
2. Open "Trails Beyond the Horizon Client" from the Archipelago Launcher and connect.
3. Opened chests are sent as checks immediately. Received items are handed over one per map change.
