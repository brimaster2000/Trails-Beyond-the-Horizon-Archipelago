# Trails beyond the Horizon Setup Guide

**Alpha.** A full playthrough has been beaten with this world, but expect rough edges. Please report anything odd.

## What is randomized
- **Chests:** the standard chests and hack boxes give an "Archipelago Item" instead of their normal contents; what they
  really hold comes from the multiworld.
- **4SPGs:** side quests, bounties and the main requests on each chapter-end report (options).
- **Grim Garten:** chests and domain clears, including repeat clears (options).
- **Acts:** every act and route (Act I-A/B/C, each Act II and Act III route, the Finale) is an item. The game follows
  its own Time Chart order, but an act only starts once you have its item.
- **Goal:** beat the final boss. The door after Mirabelle stays sealed until you have every act (and, with the Grim
  Garten goal, can reach every domain).

## Requirements
- The Legend of Heroes: Trails beyond the Horizon (Steam, Windows), English script.
- Archipelago 0.6.7 or newer, with this world installed.
- The game patch (see below).

## Installing the game patch
1. Close the game and back up `script_eng.p3a` from the game folder.
2. Build the patch from your own copy of the game:
   `tools/build_game_patch.py "<game folder>" "<KuroTools folder>" "<work folder>" ["<unpatched script_eng.p3a>"]`
   It needs the community tools `ingert.exe`, `p3a_extract.exe` and `p3a_archive.exe` in the game folder, and a
   KuroTools checkout. Copy the built `script_eng.p3a` into the game folder.
3. To uninstall, put your backup of `script_eng.p3a` back (or verify the game files in Steam).

## Playing
1. Start the game and load a save (or start a new game).
2. Open "Trails Beyond the Horizon Client" from the Archipelago Launcher and connect.
   - Run the client without its window (`--nogui`) or play the game in borderless windowed mode: a fullscreen game
     can freeze the client's window, and the server then drops the connection.
3. The first save you load is linked to your seed. Saves from another seed are ignored.
4. Checks are sent the moment they happen. Received items go straight into your inventory and are listed in the client
   log (there are no in-game item popups for now).
5. When an act ends and the next one is locked, the game shows which item you need, with options to choose another
   route, check again, save, or return to the title.

## The Act Menu (missable checks)
Almost every check in this game is missable: once an act ends, its areas close. The Act Menu lets you go back.
- **Open it:** hold **R3** (press the right stick in) while opening the pause menu. On a keyboard, hold **F1**
  instead. Change the key with the client command `/act_menu_key <key>` (for example `/act_menu_key F2`); it is
  remembered. The client must be running and connected.
- **Replay an act:** acts you have cleared can be picked; the rest show "(locked)". Acts with several routes let you
  choose one. The act restarts from its opening scene. Opened chests stay opened, and your items, levels and finished
  checks are kept.
- **Return to current act:** after replaying, this option takes you back to the start of the act you were on.
- Not available inside Grim Garten.
- Controllers: Xbox-style pads and PlayStation-layout pads (including controllers passed through as a PS4 pad) work.

## Known issues
- Replaying an act re-marks a few story 4SPGs as done. They should still be completable again for their check; please
  report it if one is not.
- Items arrive without an in-game message; watch the client log.
- Grim Garten chests opened during a fight are only counted after the fight ends.
