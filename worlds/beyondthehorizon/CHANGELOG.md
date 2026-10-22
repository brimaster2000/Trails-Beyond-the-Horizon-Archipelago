# Changelog

## 0.1.1-alpha (2026-10)
- Choose the game from any store: a Steam install is still found automatically; otherwise the client asks for the
  game's `kai.exe` in a file browser and remembers it (`host.yaml`: `trails_beyond_the_horizon_options` >
  `game_exe`). New client command `/game` to change it.
- **GOG and other stores are untested and need testers.** The game patch and the client's memory addresses come from
  the Steam version; a copy whose `script_eng.p3a` differs is refused with a message instead of being patched.
- The game patch itself is unchanged from 0.1.0.

## 0.1.0-alpha (2026-10)
First public test release.
- Checks: chests and hack boxes, 4SPGs (side quests, bounties, chapter-end main requests), Grim Garten chests and
  domain clears (with repeat clears).
- Acts and routes as items, following the game's Time Chart; a locked act shows what it needs and can save.
- Items delivered live into the inventory.
- Act Menu (hold R3 or F1 while pausing): replay cleared acts for missed checks, then return to your current act.
- Goal: the final boss, behind a door that opens once the goal requirements are met.
- Game patch installed from the client (`/install_patch`); the release contains a binary patch only.
- Logic fixes from the first full playthrough: Sandsea Chests 8/9 (Kevin Route 2), Blacklight District chests
  (Van Route 2; its hack box stays in Act I-B), Grim Garten bounties and domains placed where the game offers them.
- Known issues: no in-game item messages (watch the client log); a few story 4SPGs are re-marked as done when an act
  is replayed.
