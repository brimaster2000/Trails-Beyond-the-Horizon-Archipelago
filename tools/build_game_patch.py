"""
Builds the Archipelago game patch: a script_eng.p3a with
- system.dat: APShowReceived (popup for items the client added live) after chests and conversations, and OnQuestEnd setting
  flag 42000 + quest id (4SPG checks);
- t_item.tbl: a new stackable "Archipelago Item" (ARCHIPELAGO_ITEM_ID);
- t_tbox.tbl: every hand-placed chest gives one Archipelago Item instead of its vanilla contents;
- sys_event.dat: act gating in EV_NEXT_CHAPTER_END (a chapter starts only once its AP flag is set);
- system.dat + d5190-d5990.dat: Grim Garten chest and clear counters per domain (flags 44000+).
Dev-only: Archipelago never imports this.

Usage (GAME = the game's install folder; KUROTOOLS = a KuroTools checkout with tbl2json.py/json2tbl.py/schemas;
SOURCE = an unpatched script_eng.p3a, default <GAME>/script_eng.p3a):
    py -3.13 tools/build_game_patch.py "<GAME>" "<KUROTOOLS>" "<work folder>" ["<SOURCE>"]
Then back up <GAME>/script_eng.p3a and copy <work folder>/script_eng.p3a over it (with the game closed).

Tools: ingert.exe, p3a_extract.exe and p3a_archive.exe are community tools the user keeps in the game folder.
Both ingert (system.dat) and KuroTools (t_item, t_tbox) round-trip the original files byte-identically.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Must match tools/build_data.py and the client.
ARCHIPELAGO_ITEM_ID = 4922  # first free id after the game's last item (4921)
ARCHIPELAGO_ITEM_TEMPLATE_ID = 107  # Workshop Points: stackable counter item (category 30)
FIXED_CHEST_COUNT = 187
QUEST_FLAG_BASE = 42000  # quest q completed -> flag 42000 + q (must match build_data.py)

# Mailbox flags, shared with game_memory.py. Flags above 37194 are unused by every script and every save.
HOOK = '''
// Archipelago: received items are added to the inventory live by the client; this only SHOWS a notification.
// The client writes the game item id into flags 40000-40015, the quantity into 40016-40031, how many other items
// arrived since the last popup into 40040-40055, and sets flag 40032. Called only where the game itself shows
// message boxes (after a chest, at the end of a conversation) - never while a map is loading (that softlocked).
fn APShowReceived() {
	if flag(40032) {
		var id = 0;
		var qty = 0;
		var more = 0;
		var bit = 1;
		var i = 0;
		while i < 16 {
			if flag(40000 + i) {
				id = id + bit;
			}
			if flag(40016 + i) {
				qty = qty + bit;
			}
			if flag(40040 + i) {
				more = more + bit;
			}
			bit = bit * 2;
			i = i + 1;
		}
		reset_flag(40032);
		sound_play_se(10009);
		if more > 0 {
			system[5,8](65535, "<C1>Received ", 17, id, "<C3> x", 18, qty, "<C1> from Archipelago.", 10, "<C3>(+", 18, more, " more - see your client)</C>", 16, 22);
		} else {
			system[5,8](65535, "<C1>Received ", 17, id, "<C3> x", 18, qty, "<C1> from Archipelago.</C>", 16, 22);
		}
		wait_prompt();
		mes_message_close();
	}
	return;
}

'''
CALL_SITE = "\t443@Patch101();\n\t445@return;\n}"

MAIN_REQUEST_HOOK = f'''// Archipelago: a main 4SPG request reported as completed at chapter end sets flag {QUEST_FLAG_BASE} + its id.
fn APMainRequestDone(arg0: num) {{
	if arg0 != 0 && quest_check_state(arg0, 2) {{
		set_flag({QUEST_FLAG_BASE} + arg0);
	}}
	return;
}}

'''


# Grim Garten (repeatable random dungeon): per-domain 8-bit counters in flags, which the client turns into checks.
# Domain d (1-9): chests opened = flags GG_FLAG_BASE + d*16 .. +7, clears = GG_FLAG_BASE + d*16 + 8 .. +15.
# Verified in game: Grim Garten chests go through system.TBoxProcess, and a repeat clear runs FD_BTL_0d_01_END.
GG_FLAG_BASE = 44000
GG_CLEAR_GUARD_FLAG = 44200  # set by a story (first) clear so the boss-win hook doesn't count the same clear twice
GG_MAPS = {d: [f"d5{d}{floor}0" for floor in "0123"] + [f"d5{d}90"] for d in range(1, 10)}
GG_MAPS[3].append("d5301")
GG_MAPS[9].append("d5980")


def grim_garten_functions() -> str:
    domain_checks = "".join(
        "\tif " + " || ".join(f'map_check_name("{m}")' for m in maps) + f" {{\n\t\treturn {d};\n\t}}\n"
        for d, maps in GG_MAPS.items())
    return f'''// Archipelago Grim Garten: which domain the current map belongs to (0 = not in the Grim Garten).
fn APGGDomain() {{
{domain_checks}	return 0;
}}

// Adds 1 to the 8-bit counter stored in flags arg0 .. arg0 + 7 (stops at 255).
fn APInc8(arg0: num) {{
	var i = 0;
	var j = 0;
	while i < 8 {{
		if !flag(arg0 + i) {{
			set_flag(arg0 + i);
			while j < i {{
				reset_flag(arg0 + j);
				j = j + 1;
			}}
			return;
		}}
		i = i + 1;
	}}
	return;
}}

fn APGGChestOpened() {{
	var domain = APGGDomain();
	if domain > 0 {{
		APInc8({GG_FLAG_BASE} + domain * 16);
	}}
	return;
}}

// First clear of a domain (story event).
fn APGGStoryCleared(arg0: num) {{
	APInc8({GG_FLAG_BASE} + arg0 * 16 + 8);
	set_flag({GG_CLEAR_GUARD_FLAG});
	return;
}}

// Boss of a domain run defeated (repeat clears).
fn APGGBossCleared(arg0: num) {{
	if !flag({GG_CLEAR_GUARD_FLAG}) {{
		APInc8({GG_FLAG_BASE} + arg0 * 16 + 8);
	}}
	reset_flag({GG_CLEAR_GUARD_FLAG});
	return;
}}

'''


def patch_boss_ing(source: str, domain: int) -> str:
    """d5X90: count the story (first) clear(s) and the repeatable boss win."""
    lines = source.split("\n")
    hits = 0
    for i, line in enumerate(lines):
        if line.strip().endswith("game_update_free_dungeon_clear_state();"):
            indent = line[:len(line) - len(line.lstrip("\t"))]
            lines[i] = f"{indent}system.APGGStoryCleared({domain});\n{line}"
            hits += 1
    assert hits >= 1, f"d5{domain}90: no story clear found"
    source = "\n".join(lines)
    boss_won = f"fn FD_BTL_0{domain}_01_END() {{\n"
    assert source.count(boss_won) == 1, f"d5{domain}90: boss win handler changed"
    return source.replace(boss_won, boss_won + f"\tsystem.APGGBossCleared({domain});\n")


def patch_system_ing(source: str) -> str:
    if "fn APShowReceived()" in source:
        raise SystemExit("system.dat already has the Archipelago hook; pass an unpatched script_eng.p3a as SOURCE")
    assert source.count(CALL_SITE) == 1, "OnMapReinit changed; find a new call site"
    source = source.replace(
        CALL_SITE, f"\t443@Patch101();\n\treset_flag({GG_CLEAR_GUARD_FLAG});\n\t445@return;\n}}")
    # Grim Garten chests: count right after the chest's contents are handed over.
    # Popup sites: after a chest (where TBoxProcess shows its own "Earned 1 SP." message) and at the end of a
    # conversation (still inside the talk event, before event_end).
    chest_fade_in = [line for line in source.split("\n") if line.endswith("4363@fade_in(0.5, 0, 0.0);")]
    assert len(chest_fade_in) == 1, "TBoxProcess changed; find its fade_in after the SP message"
    source = source.replace(chest_fade_in[0] + "\n", "\t\tAPShowReceived();\n" + chest_fade_in[0] + "\n")
    talk_ends = [line for line in source.split("\n") if line.endswith("@OnTalkEndCommon();")]
    assert len(talk_ends) == 2, "OnTalkEnd/OnTalkEndCam changed"
    for line in talk_ends:
        source = source.replace(line + "\n", line + "\n\tAPShowReceived();\n")
    tbox_lines = [line for line in source.split("\n") if line.endswith("@map_obj_tbox_get();")]
    assert len(tbox_lines) == 1, "TBoxProcess changed; find map_obj_tbox_get"
    source = source.replace(tbox_lines[0] + "\n", tbox_lines[0] + "\n\t\tAPGGChestOpened();\n")
    tbox_fn = "fn TBoxProcess(arg0: num, arg1: num) {"
    assert source.count(tbox_fn) == 1
    source = source.replace(tbox_fn, grim_garten_functions() + tbox_fn)
    # 4SPG checks: every side quest, topic quest and bounty completes through OnQuestEnd(quest id).
    quest_done = "\t13607@quest_set_state(arg0, 2);\n"
    assert source.count(quest_done) == 1, "OnQuestEnd changed; find where it marks the quest complete"
    source = source.replace(quest_done, f"\tset_flag({QUEST_FLAG_BASE} + arg0);\n" + quest_done)
    # Main requests: the engine marks them completed (state 2) on the chapter-end 4SPG report, so record them
    # right after it (verified in game: before the report no state bit is set, after it bits 2 and 4 are).
    report_closed = "\t\t2119@var var6 = quest_report_wait_close();\n"
    assert source.count(report_closed) == 1, "ChapterEnd changed; find the 4SPG report"
    source = source.replace(report_closed, report_closed + "".join(
        f"\t\tAPMainRequestDone({var});\n" for var in ("var3", "var4", "var5")))
    chapter_end = "fn ChapterEnd(arg0: num = 0) {"
    assert source.count(chapter_end) == 1
    source = source.replace(chapter_end, MAIN_REQUEST_HOOK + chapter_end)
    anchor = "fn OnMapLoadPre() {"
    assert anchor in source
    return source.replace(anchor, HOOK.lstrip("\n") + anchor, 1)


# Act gating, in sys_event.dat EV_NEXT_CHAPTER_END (the only place the game picks the next chapter).
# Chapter c may start only while flag CHAPTER_FLAG_BASE + c is set; the client sets it when the act item arrives.
# Must match scena_regions.CHAPTER_IDS and game_memory.CHAPTER_FLAG_BASE.
CHAPTER_FLAG_BASE = 41000
GATED_CHAPTERS = {
    1: "Act I - A", 2: "Act I - B", 3: "Act I - C", 4: "Act II - Rean Route 1", 5: "Act II - Kevin Route 1", 6: "Act II - Van Route 1",
    10: "Act II - Rean Route 2", 11: "Act II - Van Route 2", 12: "Act II - Van Route 3",
    13: "Act III - Kevin Route 2", 14: "Act III - Van Route 4", 15: "Act III - Van Route 5",
    16: "Act III - Rean Route 3", 17: "Act III - Kevin Route 3", 18: "Act III - Van Route 6", 19: "Finale",
}
CHOICE_GROUPS = (1, 2, 5, 7)  # Time Chart groups that offer several routes
SINGLE_GROUPS = (3, 6)  # Time Chart groups that lead to one gated route (Van 3, Van 5); group 4 = Intermission


def gate_functions() -> str:
    names = "\n".join(
        f'\t}} else if arg0 == {c} {{\n\t\tname = "{n}";' if i else f'\tif arg0 == {c} {{\n\t\tname = "{n}";'
        for i, (c, n) in enumerate(GATED_CHAPTERS.items())
    )
    return f'''// Archipelago act gating: chapter c needs flag {CHAPTER_FLAG_BASE} + c, set by the client when the act item arrives.
fn APChapterUnlocked(arg0: num) {{
	if arg0 < 0 || flag({CHAPTER_FLAG_BASE} + arg0) {{
		return 1;
	}}
	return 0;
}}

// Shows the lock message and a menu. Returns 0 = choose another route, 1 = check again (2 = title never returns).
fn APLockedMenu(arg0: num, arg1: num) {{
	var name = "";
{names}
	}}
	mes_coordinate(-1, 250, -1, -1);
	system[5,8](65535, "<C1>This route is locked by Archipelago.", 10, "<C3>Requires: ", name, "</C>", 16, 22);
	menu_create(1, 0, 0, 28);
	if arg1 {{
		menu_additem(1, "Choose another route", 0);
	}}
	menu_additem(1, "Check again", 1);
	menu_additem(1, "Return to title", 2);
	menu_open(1, -1, -1);
	var choice = menu_wait(1);
	menu_close(1);
	mes_message_close();
	mes_reset_coordinate();
	if menu_is_canceled(1) {{
		choice = 1 - arg1;
	}}
	if choice == 2 {{
		game_return_to_title();
	}}
	return choice;
}}

fn APSelectChapter(arg0: num) {{
	var chapter = ui_open_chapter_select(arg0);
	while !APChapterUnlocked(chapter) {{
		if APLockedMenu(chapter, 1) == 0 {{
			chapter = ui_open_chapter_select(arg0);
		}}
	}}
	return chapter;
}}

fn APWaitChapter(arg0: num) {{
	while !APChapterUnlocked(arg0) {{
		APLockedMenu(arg0, 0);
	}}
	return arg0;
}}

'''


def patch_sys_event_ing(source: str) -> str:
    if "fn APSelectChapter(" in source:
        raise SystemExit("sys_event.dat already has the Archipelago gate; pass an unpatched script_eng.p3a as SOURCE")
    edits = [
        # Prologue -> Act I Part 1 (A), Part 1 -> 2 (B), Part 2 -> 3 (C)
        ("\t\t60@var0 = 1;\n", "\t\t60@var0 = 1;\n\t\tAPWaitChapter(var0);\n", 1),
        ("\t\t65@var0 = 2;\n", "\t\t65@var0 = 2;\n\t\tAPWaitChapter(var0);\n", 1),
        ("\t\t70@var0 = 3;\n", "\t\t70@var0 = 3;\n\t\tAPWaitChapter(var0);\n", 1),
        # Finale
        ("\t\t\t277@var0 = 19;\n", "\t\t\t277@var0 = 19;\n\t\t\tAPWaitChapter(var0);\n", 1),
    ]
    for group in CHOICE_GROUPS:
        call = f"ui_open_chapter_select({group});"
        edits.append((call, f"APSelectChapter({group});", 2))
    for group in SINGLE_GROUPS:
        call = f"ui_open_chapter_select({group});"
        edits.append((call, f"APWaitChapter(ui_open_chapter_select({group}));", 1))
    for old, new, count in edits:
        assert source.count(old) == count, f"EV_NEXT_CHAPTER_END changed: {old!r} found {source.count(old)}x"
        source = source.replace(old, new)
    anchor = "fn EV_NEXT_CHAPTER_END() {"
    assert source.count(anchor) == 1
    source = source.replace(anchor, gate_functions() + anchor, 1)
    if "prelude fn game_return_to_title" not in source:
        source = "prelude fn game_return_to_title = system[28,2]();\n" + source
    return source


def run(*args: str | Path, cwd: Path | None = None, env: dict | None = None) -> None:
    subprocess.run([str(a) for a in args], check=True, cwd=cwd, env=env)


def add_archipelago_item(table: dict) -> None:
    items = next(t for t in table["data"] if t["name"] == "ItemTableData")["data"]
    if any(i["id"] == ARCHIPELAGO_ITEM_ID for i in items):
        raise SystemExit(f"t_item already has item {ARCHIPELAGO_ITEM_ID}; pass an unpatched script_eng.p3a as SOURCE")
    item = dict(next(i for i in items if i["id"] == ARCHIPELAGO_ITEM_TEMPLATE_ID))
    item.update(
        id=ARCHIPELAGO_ITEM_ID,
        text2="",
        price=0,
        name="Archipelago Item",
        description="Proof of a treasure sent across the multiworld.\nCheck your Archipelago client to see where it went.",
    )
    items.append(item)


def give_archipelago_item_from_chests(table: dict) -> None:
    chests = table["data"][0]["data"]
    for chest in chests[:FIXED_CHEST_COUNT]:
        chest["item_list"] = [ARCHIPELAGO_ITEM_ID, 1]


def patch_table(kurotools: Path, work: Path, tbl: Path, patch) -> None:
    """tbl2json/json2tbl read schemas/ and write output relative to the working directory, so use a scratch dir."""
    scratch = work / "tables" / tbl.stem
    scratch.mkdir(parents=True)
    shutil.copytree(kurotools / "schemas", scratch / "schemas")
    shutil.copy(tbl, scratch / tbl.name)
    env = dict(os.environ, PYTHONPATH=str(kurotools))
    run(sys.executable, kurotools / "tbl2json.py", tbl.name, cwd=scratch, env=env)
    json_path = scratch / f"{tbl.stem}.json"
    table = json.loads(json_path.read_text(encoding="utf-8"))
    patch(table)
    json_path.write_text(json.dumps(table, ensure_ascii=False, indent=4), encoding="utf-8")
    (scratch / tbl.name).unlink()
    run(sys.executable, kurotools / "json2tbl.py", json_path.name, cwd=scratch, env=env)
    shutil.copy(scratch / tbl.name, tbl)


def main(game: Path, kurotools: Path, work: Path, source_archive: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    extracted = work / "extract"
    run(game / "p3a_extract.exe", "-f", extracted, source_archive)

    system_dat = extracted / "script_eng" / "scena" / "system.dat"
    run(game / "ingert.exe", "-o", work / "system.ing", system_dat)
    (work / "system_ap.ing").write_text(patch_system_ing((work / "system.ing").read_text(encoding="utf-8")),
                                        encoding="utf-8")
    run(game / "ingert.exe", "-o", system_dat, work / "system_ap.ing")

    sys_event_dat = extracted / "script_eng" / "scena" / "sys_event.dat"
    run(game / "ingert.exe", "-o", work / "sys_event.ing", sys_event_dat)
    (work / "sys_event_ap.ing").write_text(
        patch_sys_event_ing((work / "sys_event.ing").read_text(encoding="utf-8")), encoding="utf-8")
    run(game / "ingert.exe", "-o", sys_event_dat, work / "sys_event_ap.ing")

    for domain in range(1, 10):
        boss_dat = extracted / "script_eng" / "scena" / f"d5{domain}90.dat"
        boss_ing = work / f"d5{domain}90.ing"
        run(game / "ingert.exe", "-o", boss_ing, boss_dat)
        patched = work / f"d5{domain}90_ap.ing"
        patched.write_text(patch_boss_ing(boss_ing.read_text(encoding="utf-8"), domain), encoding="utf-8")
        run(game / "ingert.exe", "-o", boss_dat, patched)

    tables = extracted / "table_eng"
    patch_table(kurotools, work, tables / "t_item.tbl", add_archipelago_item)
    patch_table(kurotools, work, tables / "t_tbox.tbl", give_archipelago_item_from_chests)

    # p3a_archive writes next to itself, naming the file after the output path; move it into the work folder.
    out = work / "script_eng.p3a"
    run(game / "p3a_archive.exe", "-c", "lz4", "-v", "1100", "-a", out, extracted)
    mangled = game / (str(out).replace(":", "_").replace("\\", "_").replace("/", "_"))
    if mangled.exists():
        shutil.move(mangled, out)
    print(f"built {out}")


if __name__ == "__main__":
    game_folder = Path(sys.argv[1])
    main(game_folder, Path(sys.argv[2]), Path(sys.argv[3]),
         Path(sys.argv[4]) if len(sys.argv) > 4 else game_folder / "script_eng.p3a")
