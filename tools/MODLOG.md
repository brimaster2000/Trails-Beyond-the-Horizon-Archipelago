# MODLOG: Trails beyond the Horizon (Kai no Kiseki), Archipelago randomizer

## Game
- Steam app 3316940, install `D:\Steam\steamapps\common\The Legend of Heroes Trails beyond the Horizon`
- Falcom in-house engine (Kuro/Kai lineage, "ED9" script VM), `kai.exe` x64, no anti-cheat. Single-player only.
- Data lives in `.p3a` archives. Loose folders next to the archives (`script_eng/`, `se/`, `voice_eng/`, `asset_image/`) act as overrides.
- Existing user mods: `zKai1DifficultyMod/` (script_eng + table_eng overrides), `newscript/script.p3a`.

## Tooling already on disk
- `p3a_tool.exe` / `p3a_extract.exe` / `p3a_archive.exe`: unpack and repack archives.
- `ingert.exe`: script decompiler/compiler, `.dat` <-> `.ing` (samples in `Extracted/Script-p3a/script edit/scena/Test/`).
- KuroTools (`Extracted/Scripteng-p3a/table_eng EDIT/KuroTools-master/`): `tbl2json.py` / `json2tbl.py`, plus the ED9 disassembler.

## Archipelago world (state on 2026-10-07)
- `Archipelago/Archipelago/worlds/beyondthehorizon/` (untracked in a core AP checkout at 9b421450)
- Built from the APQuest template. 2 regions (VAR-halla sector -> Seiden Waterworks, gated by item "Act 1"), 16 locations, 19 items.
- Item IDs are 1..19 and location IDs are 1..16. These are placeholders and must become a unique base offset plus the real game IDs.
- Client.py is a stub: CommonClient that only connects. No game I/O; the mailbox code is commented out.
- Leftover template text: world docstring says APQuest; launch_client docstring says "Trails in the Sky the 3rd"; the `/ahit` command calls a get_ahit_status() that doesn't exist; tests are APQuest's (hammer/easy/hard).

## Chest data (location source)
- `t_tbox.tbl`, decoded at `.../KuroTools-master/t_tbox.json`: **669 chests across 70 scenas**.
- Fields: `scena`, `name` (Treasure00..), `flag` (FR/F/""/R/D), `hack_box_id`, `item_list` [item_id, qty, ...], and hack_box extras.
- Item names and IDs come from `t_item.tbl`.

## Open problem: game <-> client bridge
The game has no network or file I/O hooks we can use from scripts. Options:
1. **Memory bridge (recommended):** the client uses pymem against kai.exe.
   - Checks: patch every chest's `item_list` to a dummy item (or a script) that sets a unique scenario flag, then poll the flag array.
   - Receiving items: the client writes into a reserved global_work / flag range. A script hook (map-load or menu-open event) reads it and calls the item-add command, then acks.
   - Needs RE: flag array base, and a pointer path to global_work (Cheat Engine: toggle a known flag and diff).
2. Native proxy-DLL (winmm/version) with MinHook, hooking item-add and flag-set. More powerful, much more work.
3. Static randomizer only: shuffle t_tbox item_list at generation time, no live multiworld. Fast, but not a real AP client.

## 2026-10-07: Step 1 done (world v0.1.0)
- Backup of the pre-change world: `Archipelago/beyondthehorizon_backup_2026-10-07/`
- GOTCHA: `t_tboxUE.json` is NOT vanilla. Its 8 VAR-halla chests were all set to item 3802.
  - The real vanilla data is decoded from `Extracted/Scripteng-p3a/table_eng OG/t_tbox.tbl`.
  - The decoded copy is saved as `worlds/beyondthehorizon/tools/vanilla/t_tbox_og.json`.
  - KuroTools `tbl2json.py` reads `schemas/` and writes its output relative to the CWD, and decrypts the input file in place. Run it on a copy.
- `tools/build_data.py` generates `data.py`: 669 chests and 134 AP items (11 multi-item bundles).
  - Chest location ID = 10,000,000 + scena letter × 1,000,000 + scena number × 100 + chest slot (hack box = 99).
  - Item ID = 1,000,000 + game item ID × 1000 + quantity. Bundles start at 9,000,000. Story items are IDs 1–14.
  - Grim Garten location ID = 20,000,000 + domain × 100 + chest number (domain clear = 99).
- Chapter names come from t_chapter: Act I (3 parts), 6 Act II routes, 6 Act III routes, Finale.
- `scena_regions.py` maps each map to the chapter it opens in, filled in by hand. Only confirmed maps are assigned; the rest are None and left out of seeds.
- Options: act_order (ordered/actsanity), grim_garten_chest_checks (0–20), grim_garten_domain_clears, goal.
- Verified: 17 unittest tests pass (`py -3.13 -m unittest worlds.beyondthehorizon.test.test_act_order`), and a 2-player seed (ordered + actsanity) generates and is beatable.

## 2026-10-08: Act mapping + step 2 (chest detection), no memory hacking needed
- Act/area list from the user (from the Neoseeker walkthrough) is entered in scena_regions.py.
  - Grim Garten domains map to lists of routes; any one of them opens the domain.
  - Still unassigned: m4000 Rare Metal Mine (Rean 1 or 2?), m1100 Hillside, m7200 Reserve Railway Track, d0309 Coral Archipelago: Alternate.
- **Save format:** `Saved Games/FALCOM/Kai/saveNNN/user.dat` is a single zstd frame. It decompresses to a fixed 2,722,840-byte block with no encryption.
- **Scenario flags** are a bit array at offset 0xC, LSB first (flag n = byte 0xC + n//8, bit n%8).
  - Proven with the t_chapter `long1` chapter flags (32000…32385): all set in the finale save, only 32000 set at the start of the Prologue.
- **Chest opened flag = 1500 + t_tbox index**, for the first 187 entries (the hand-placed chests; the 187 matches the achievement count).
  - Also set: parallel copies at 1833+i and 2166+i.
  - Grim Garten, Floating Isles, Coral Alt and Hillside chests use something else (TODO).
- `system.ing` TBoxProcess handles every chest: map_obj_tbox_get(), then savedata_auto_save(). So the newest save always reflects the last chest opened.
- Client (`Client.py` + `save_reader.py`): polls the newest save every second and sends LocationChecks.
  - Verified end to end: local MultiServer + client on a copy of save226 sent 7 VAR-halla checks.
  - Needs the `zstandard` package (in the world's requirements.txt).
- The script VM has `item_add(id, qty)` = system[16,0]: the likely route for receiving items (step 3).

## 2026-10-08: live flag array in memory (step 3 groundwork)
- Saves backed up: `Archipelago/save_backup_2026-10-08/`.
- Read-only scan of kai.exe private memory found 4 copies of the flag array:
  - **live state**: changes on chest open, and differs from the save elsewhere;
  - **autosave buffer**: byte-identical to the newest autosave;
  - **loaded-save buffer**;
  - an older stale snapshot.
- **Pointer path: live flags = [kai.exe + 0xD60258] + 0x110.** kai.exe base is 0x140000000.
  - The object's vtable is 0x140B58070, usable as a fallback signature.
  - Tested in one session only; must confirm after a game restart.
- Verified live: opening VAR-halla Chest 6 set flag 1505 in the live copy (and in the autosave), not in the load buffer.
- `worlds/beyondthehorizon/game_memory.py`: find_game_pid, GameMemory.read_flags/flag/set_flag (write needs PROCESS_VM_WRITE). Not wired into the client yet.
- Scripts in memscan2.py / peekflags.py (scratchpad) were one-off tools.

## 2026-10-08: step 3, receiving items, WORKING end to end
- Pointer path confirmed after a game restart: the heap address changed, and the path plus vtable still matched.
- All 376 English scena scripts decompiled with ingert (in %TEMP%/tbth_ing):
  - No script references a flag above 37194, and no save sets one. Flags 37195-65535 are free.
  - The array is 0x2000 bytes (65536 flags).
  - The 40000+/59900/62000 flags seen earlier only appear in the user's Test folder.
- **The game loads scripts from the .p3a archives**, not the extracted loose folders.
  - Original `script_eng.p3a` backed up to `Archipelago/p3a_backup_2026-10-08/`.
  - The shipped archive is 1722 files, v1100, lz4.
  - ingert round-trips system.dat byte-identically.
  - GOTCHA: `p3a_archive.exe -a <path>` writes into its own folder, with ':' '\' '/' replaced by '_'.
- **Hook:** `system.APGrantItems()` is called at the end of `system.OnMapReinit` (after Patch101). It does:
  - if flag 40032: id = flags 40000-40015, qty = flags 40016-40031;
  - item_add(id, qty);
  - reset_flag(40032).
  - Silent (no popup) for now.
  - Built by `tools/build_script_patch.py`, which reproduces the installed archive byte-identically from the original.
- Verified flags above 37194 ARE saved: test flag 50000 was in the next autosave (then cleared).
- **Received counter:** a u32 in flags 50000-50031. The client writes the mailbox and counter+1 in one step, so saves stay consistent.
- Verified live:
  - a manual Teara Balm (id 2) via the mailbox arrived on the map change;
  - full chain: local MultiServer `!getitem Teara Balm`, then TBTHContext, then game memory, then map change. Arrived; counter = 1, pending cleared.
  - Checks are read live from memory (falling back to saves when not attached).

## 2026-10-08: chests give "Archipelago Item" instead of vanilla contents
- Item tables: category 2 = key items (stack 1, bad for 187 pickups); category 30 = stackable counters.
- New item **4922 "Archipelago Item"**, cloned from 107 Workshop Points (category 30, stack 50000).
- t_tbox: entries 0–186 (the hand-placed chests, hack boxes included) item_list → [4922, 1]. Entries 187+ untouched.
- KuroTools json2tbl round-trips t_item and t_tbox byte-identically. Appending a row to ItemTableData works (2116 → 2117).
- Builder renamed `tools/build_game_patch.py "<GAME>" "<KUROTOOLS>" "<work>" ["<source p3a>"]`. It does:
  - the system.dat hook;
  - the t_item row;
  - the t_tbox rewrite.
  - It refuses an already-patched source.
- Built from the backed-up archive; vs the installed archive, only t_item.tbl and t_tbox.tbl differ.
- User's request for the final product: an in-game popup when an AP item arrives, like opening a chest.

## 2026-10-08: act gating research (offline, decompiled scripts in %TEMP%/tbth_ing)
- `global_work(12)` = current chapter id (same ids as t_chapter):
  - 0 = Prologue; 1–3 = Act I parts; 4 = R1; 5 = K1; 6 = V1; 7–9 = Intermission;
  - 10 = R2; 11 = V2; 12 = V3; 13 = K2; 14 = V4; 15 = V5; 16 = R3; 17 = K3; 18 = V6; 19 = Finale.
- Chapter end: system.ChapterEnd → OnChapterChange → EVENT_NEXT. The next chapter is chosen in
  **sys_event.dat `EV_NEXT_CHAPTER_END`**, the only real `set_global_work(12, …)` (debug/test scripts aside).
- Its flow (the game's own structure), with each step's start event in brackets:
  - 0 → 1 [200]
  - 1 → 2 [232]
  - 2 → 3 [257]
  - 3 → Time Chart group 1: pick 4/5/6 (R1 [300] / K1 [400] / V1 [500]). Re-shown until done flags 32134, 32180, 32198 are all set.
  - Then group 4 → Intermission [600].
  - 9 → group 2: 10/11 (R2 [320] / V2 [520]). Repeats until 32160 + 32215; then group 3 → V3 (12) [540].
  - 12 → group 5: 13/14 (K2 [800] / V4 [900]). Repeats until 32310 + 32354; then group 6 → V5 (15) [930].
  - 15 → group 7: 16/17/18 (R3 [700] / K3 [840] / V6 [950]). Repeats until 32270 + 32331 + 32404.
  - Then Finale (19) [1000]; 19 → [1063].
- `ui_open_chapter_select(group)` = system[23,30]: the Time Chart route picker, which returns the chosen chapter id.
- **Gate point:** right after the route is chosen (or for fixed transitions), check our AP flag for that chapter
  before `set_global_work(12, var0)`. Missing → message + re-open the picker / waiting menu (the client sets flags live).
- **Logic implication:** the game only lets routes be picked within a "wave"; later waves need the earlier ones *finished*.
  - True "any route any time" (actsanity) would need skipping chapters (story state, party) → risky. Decision needed.

## 2026-10-08: act gating implemented (built, not yet installed)
- User decisions:
  - Logic follows the game's waves; full actsanity is postponed. Generation refuses act_order=actsanity with an OptionError.
  - A locked route sends you back to the picker ("Choose another route"); fixed transitions get a waiting menu.
- World: scena_regions.WAVES + CHAPTER_IDS. rules.py: each route needs its own item plus every item of the earlier waves.
  - 28 tests pass; a 2-player generation works.
- Game patch (`build_game_patch.py`) now also patches sys_event.dat:
  - APChapterUnlocked(c) = flag(41000 + c).
  - APLockedMenu(c, canPickOther): "This route is locked by Archipelago. Requires: <name>"
    + [Choose another route] / Check again / Return to title.
  - APSelectChapter(group) replaces ui_open_chapter_select(1|2|5|7): 2 call sites each.
  - APWaitChapter wraps the fixed transitions: 0→1 (Act I), group 3 (V3), group 6 (V5), → 19 (Finale). Intermission is not gated.
  - The sys_event.dat original round-trips byte-identically. Built archive vs installed: only sys_event.dat differs.
- Client: for every act item received, it sets flag 41000 + chapter live (game_memory.CHAPTER_FLAG_BASE).
- NOTE: with this patch, any chapter change without the flag is blocked, including a normal non-AP playthrough.
  Swap in the backup archive to play vanilla.

## Next steps
- [x] Gate patch installed (backup of the previous archive: p3a_backup_2026-10-08/script_eng_chests.p3a).
  - Verified in game: finishing the Prologue without flag 41001 shows the lock menu; the text renders correctly.
  - Setting 41001 from outside, then "Check again", starts Act I.
- [x] Real play session (solo seed, slot "Van", local server + client GUI). The Act I gate opened via the client; the player reached Act I.
  - BUG found by the user: with the game closed, the save fallback read the newest save of ANY playthrough, sending 2 wrong checks.
  - FIX: seed marker = crc32("seed:slot") stored in flags 50032-50063.
    - The client links an unmarked save on attach and ignores saves with a different marker (memory and fallback).
    - Unmarked saves on disk are ignored.
    - Verified live: marker written, counter at 13 deliveries.
- [x] User's full Act I playthrough: everything worked.
  - Act I → Act II: the locked route was refused, and "Choose another route" worked. Van Route 1 (unlocked) proceeded.
  - The user has a save at the Act I → Act II transition. Test run stopped.

## ROADMAP (user, 2026-10-08), with what we already know about each hook
1. **More checks: "sanities"**
   - **4SPG side quests (top priority):** system.ing has QuestRewardProcess, OnQuestStart/OnQuestEnd/OnQuestAddSP (called from map scripts), so quest completion probably sets flags we can map like the chests.
   - **Shopsanity:** the t_shop table (KuroTools decodes it). Shop stock could hold "Archipelago Item" slots; buying one = a check (needs an inventory/flag signal).
   - **Recipesanity:** recipes look like items (category 1, "Soul Chef: …"); learning one = check.
   - **Achievementsanity:** scripts call game_update_achieve(n) / trophy_unlock(n); t_achievement exists (decoded). Achievement state probably lives in the save or system data → find it like the chest flags.
   - **Story flags as checks:** chapter start/end flags are known (t_chapter long1, route-finished flags 32134/32180/32198/…).
2. **Split Act I into 3 items** (Part 1/2/3): same gate as now. EV_NEXT_CHAPTER_END transitions 1→2 and 2→3 are fixed, so wrap them in APWaitChapter(2/3) and add 2 story items.
3. **Grim Garten:** domain chest/clear checks exist in the world but nothing detects them yet.
   - Its chests are random-dungeon chests (empty table entries, not flags 1500+); find their flags and the domain-clear flags.
4. **Missable checks:** a way back to finished chapters' areas, or logic that only counts what is reachable.
5. **Fight logic:** progression shouldn't send players into fights they can't win
   (e.g. level/equipment expectations per route, or AP items that scale stats).
6. Also from earlier: an in-game popup when an item arrives, delivery without a map change,
   a "Save" option at the lock menu, Hillside chest flags, full actsanity (chapter skipping).

- [ ] User wish: a "Save" option in the lock menu (the game has savedata_inter_save_menu).
  - Loading that save must come back to the gate, not past it.
- [ ] Later (user): missable checks need a way back to finished chapters' areas (revisit / reopen).
- [ ] Not yet tested in game: Time Chart route picks (APSelectChapter, "Choose another route").
- [x] Installed (backups: p3a_backup_2026-10-08/script_eng.p3a = original, script_eng_hook_only.p3a = hook only).
  - Verified in game: chests say "Obtained Archipelago Item". VAR-halla Chest 5 set flag 1500+4, and the check reached the local server.
  - All three chest flag copies and the autosave agree.
- [ ] Story items (Act I…Finale) give nothing in game yet: decide what each sets (an AP-owned flag per act) and gate chapter starts on it.
- [ ] Stop chests giving their vanilla contents: patch t_tbox item_list (table_eng in script_eng.p3a).
  - NOTE: the user's live t_tbox may still have test edits (VAR-halla = 3802).
- [ ] Optional: a popup when an item arrives; deliver on menu open too, not only map change.
- [ ] Grim Garten and Hillside chest flags.
- [x] Generate LOCATION_NAME_TO_ID from t_tbox.json, and items from t_item.tbl.
- [x] Assign the remaining maps (user): Rare Metal Mine = Rean 2, Reserve Railway Track = Van 2, Hillside = Kevin 3.
  - Coral Archipelago: Alternate is excluded (likely a Daybreak II leftover).
  - All 187 flagged chests are now in seeds.
  - Chests without a known flag are skipped even when mapped (Hillside, until its flag is found).
- [ ] Step 3: receiving items. The client can't write to the save while the game runs, so this needs game memory or a script hook:
  find the flag array in kai.exe memory (it is the same layout as the save; search for the save's flag bytes),
  then have the client write a "pending item" into global_work / a reserved flag range, and a script hook (TBoxProcess, map load) calls item_add.
- [ ] Neutralize vanilla chest contents (t_tbox item_list → nothing/dummy) so chests only give AP items.
- [ ] Act gating: block chapters without the act item.
- [ ] Cheat Engine: find the scenario flag array in kai.exe (open a chest, diff).
- [ ] Vertical slice: one chest in VAR-halla -> client sees the check -> client sends an item -> the item appears in inventory.

## Restore path
- Before any modded launch: back up the save folder (find under `%USERPROFILE%\Saved Games` or Documents/My Games) and the original `.p3a` files.

## 2026-10-08: git + Act I split
- The world folder is its own git repo (branch main). .gitignore excludes tools/vanilla/ (decoded game data) and caches.
  This MODLOG copy in tools/ is now the canonical journal.
- Act I is split into "Act I - A/B/C" (chapters 1/2/3). Maps:
  - A: Seiden Waterworks, Western Outskirts, Lèvre;
  - B: Underground Culvert, Blacklight;
  - C: Junction Area + Grim Garten domains 1-2.
- Story item AP ids = chapter ids (1..19).
- Gate: sys_event EV_NEXT_CHAPTER_END transitions 1→2 ("65@var0 = 2;") and 2→3 ("70@var0 = 3;") are now wrapped in APWaitChapter.
- Installed. Previous archive backed up as p3a_backup_2026-10-08/script_eng_gate_actI_whole.p3a.
- NOTE: saves from the earlier test seed only have flag 41001. With this patch, Parts B and C need 41002/41003 too.
  A new seed sets them via the client.
- Next: 4SPG quest checks.

## 2026-10-08: 4SPG side quest checks (VERIFIED in game)
- t_quest.tbl (KuroTools, schema "Kai"), table QuestTitle: 86 quests.
  - Fields: id, quest_description (name), quest_giver, int2 = chapter (65535 = Grim Garten bounty), int1 = type.
  - Kinds: 8 = quest, 32 = topic quest, 2 = main.
  - Saved as tools/vanilla/t_quest_og.json (gitignored).
- Side quests 1-35, bounties 51-65 (49 total) all complete through system.OnQuestEnd(id),
  which ends with `13607@quest_set_state(arg0, 2)` (2 = completed; scripts test it with quest_check_state(id, 2)).
  Patch: `set_flag(42000 + arg0)` right before it. Client reads flags 42001-42065 like chest flags.
- Main requests 151-188: no script ever sets their state; the engine completes them at the chapter-end report
  (ChapterEnd → QuestRewardProcess(var3..var5) + system[24,9]). Not checks yet. Next: verify quest_check_state(id, 2)
  at chapter end in game, then hook QuestRewardProcess.
- Region = the quest's chapter (CHAPTER_REGION). GG bounties 57/59/62/64 → domains 1/3/5/7.
  - Option side_quest_checks (default on). Location ids 30_000_000 + quest id; location group "4SPG".
- 51 tests pass; the 2-player seed grows by 49 locations per player. Built archive vs installed: only system.dat differs.
- Installed (previous archive backed up as p3a_backup_2026-10-08/script_eng_actI_split.p3a).
  - Verified: user completed Waterworks Bounty (quest 51) from save 40. Live flag 42051 was set, and it was the only quest flag set.
  - User's save 45 = just before finishing that bounty (handy for re-testing).

## 2026-10-08: main 4SPG requests as checks
- Diagnostic build (temporary): recorded quest_check_state bits 1,2,4,8,16,32 for ChapterEnd's var3..var5,
  before and after the 4SPG report. Tested by the user on slot 51, end of Act I Part 1 (quests 153/154/155):
  - before the report: no bits set;
  - after `quest_report_wait_close()`: bits 2 (completed) and 4 (reported) set.
  - User's slot 52 = just before the Act I-A → B transition.
- Hook: `APMainRequestDone(var3/var4/var5)` right after `2119@var var6 = quest_report_wait_close();`
  sets flag 42000+id if quest_check_state(id, 2). So an optional request that was skipped does not count.
- 34 of 37 main requests are on a chapter-end report. 152, 172 and 188 are not (UNREPORTED_MAIN_REQUESTS) → not checks.
- Request 165 is the Intermission (chapter 9): new "Intermission" region, open once Wave 1 (R1/K1/V1) is unlocked.
  The Prologue request 151 is in the Prologue.
- Option main_request_checks (default on); location groups "4SPG", "Side Quests", "Main Requests".
- 61 tests pass; the 2-player seed is 612 items (+34 per player).
- VERIFIED in game with the real patch (slot 51 → end of Act I Part 1): flags 42153/42154/42155 set, no other main flags.
- User note for Grim Garten: it's a repeatable, randomly generated (roguelike) dungeon. Checks must count progress
  (Nth chest in a domain, domain clears, …), not fixed chests, and the final build needs adjustable YAML settings for how
  many/what kind of checks it sends.
