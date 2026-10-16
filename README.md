# Trails beyond the Horizon for Archipelago (0.1 alpha)

An [Archipelago](https://archipelago.gg) multiworld randomizer for *The Legend of Heroes: Trails beyond the Horizon*
(Steam, Windows).

**Alpha:** a full playthrough has been beaten with it, but expect rough edges. Please report what you find.

## Features
- **Chests and hack boxes** are checks; what they hold comes from the multiworld.
- **4SPGs:** side quests, bounties and the chapter-end main requests can be checks.
- **Grim Garten:** chests and domain clears, including repeat clears (adjustable).
- **Acts as items:** Act I-A/B/C, every Act II and Act III route, and the Finale. The story follows the game's own
  Time Chart, but an act only starts once you hold its item. A locked act tells you what you need, and lets you pick
  another route or save.
- **Items arrive live**, straight into your inventory, while you play.
- **The Act Menu** fixes missable checks: hold R3 (or F1) while opening the pause menu to replay any act you have
  cleared, keeping your items and checks, then return to your current act.
- **Goal:** the final boss, behind a door that stays sealed until your goal requirements are met.

## Requirements
- *The Legend of Heroes: Trails beyond the Horizon* on Steam (Windows), English script, unmodded
  (Steam build 3316940).
- Archipelago 0.6.7 or newer.

## Install
1. Download `beyondthehorizon.apworld` from the release and double-click it (or put it in Archipelago's
   `custom_worlds` folder). Restart the Archipelago Launcher.
2. Close the game. Open **Trails Beyond the Horizon Client** from the Launcher and type `/install_patch`.
   It patches the game's `script_eng.p3a` and keeps the original as `script_eng.p3a.archipelago_backup`.
3. Generate a seed with a Trails beyond the Horizon YAML (Launcher, "Generate Template Options"), host it, and
   connect with the client.

Full guide: [docs/setup_en.md](docs/setup_en.md).

## Uninstall
`/uninstall_patch` in the client, or verify the game files in Steam. Then remove the .apworld from `custom_worlds`.

## Troubleshooting
- The client log is in Archipelago's `logs` folder (`TBTHClient_*.txt`).
- A fullscreen game can freeze the client's window, and the server then drops the connection: run the client with
  `--nogui`, or play in borderless windowed mode.
- `/patch_status` shows whether the game patch is installed. After a game update the patch refuses to install until
  it is updated.
- `/tbth` shows whether the client is attached to the game.

## How it works
The patch changes the game's own scripts and tables: chests hand out an "Archipelago Item", hooks record checks in
spare story flags, and the act gate and Act Menu are new script code. The Act Menu builds on the jump code Falcom left
in the game's debug script. The client reads and writes those flags, and the inventory, in the running game.
The release ships only a binary patch (bsdiff4) made from your own copy of the game, never game files.
For developers, `tools/build_game_patch.py` rebuilds the patch from scratch and `tools/MODLOG.md` is the full
research log.

## Credits
- Made by Brimaster2000.
- Built with [Claude Code](https://claude.com/claude-code) (Anthropic's Claude Opus 5.5), which did most of the
  reverse engineering and code under Brimaster2000's direction and in-game testing.
- Tools used to build the patch (players don't need them):
  - [Ingert](https://github.com/Aureole-Suite/Ingert) by Aureole Suite: decompiles and recompiles the game's scripts.
  - [KuroTools](https://github.com/nnguyen259/KuroTools) by nnguyen259: reads and writes the game's tables.
  - `p3a_extract` / `p3a_archive` from [kuro_dlc_tool](https://github.com/eArmada8/kuro_dlc_tool) by eArmada8:
    unpack and repack the game's .p3a archives.
- Act and area lists, and the 4SPG and Grim Garten logic: the Neoseeker walkthrough for Trails beyond the Horizon,
  plus NoobFeed for the Act I parts.
- Launcher icon: cropped from official *Trails beyond the Horizon* artwork (Nihon Falcom / NIS America).
- *The Legend of Heroes: Trails beyond the Horizon* is © Nihon Falcom Corporation, published in English by
  NIS America. This project is unofficial and not affiliated with them.

## License
MIT (see [LICENSE](LICENSE)) for this project's code and docs; the game and its artwork are not covered.
