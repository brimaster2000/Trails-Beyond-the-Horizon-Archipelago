"""
Builds the Archipelago game patch: a script_eng.p3a with
- system.dat: APGrantItems (gives items queued by the client), called from OnMapReinit, and OnQuestEnd setting
  flag 42000 + quest id (4SPG checks);
- t_item.tbl: a new stackable "Archipelago Item" (ARCHIPELAGO_ITEM_ID);
- t_tbox.tbl: every hand-placed chest gives one Archipelago Item instead of its vanilla contents;
- sys_event.dat: act gating in EV_NEXT_CHAPTER_END (a chapter starts only once its AP flag is set).
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
// Archipelago: one pending item per map load. The client writes the game item id into flags 40000-40015,
// the quantity into flags 40016-40031, and sets flag 40032; we give the item and clear 40032 as the acknowledgement.
fn APGrantItems() {
	if flag(40032) {
		var id = 0;
		var qty = 0;
		var bit = 1;
		var i = 0;
		while i < 16 {
			if flag(40000 + i) {
				id = id + bit;
			}
			if flag(40016 + i) {
				qty = qty + bit;
			}
			bit = bit * 2;
			i = i + 1;
		}
		if qty > 0 {
			item_add(id, qty);
		}
		reset_flag(40032);
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


def patch_system_ing(source: str) -> str:
    if "fn APGrantItems()" in source:
        raise SystemExit("system.dat already has the Archipelago hook; pass an unpatched script_eng.p3a as SOURCE")
    assert source.count(CALL_SITE) == 1, "OnMapReinit changed; find a new call site"
    source = source.replace(CALL_SITE, "\t443@Patch101();\n\tAPGrantItems();\n\t445@return;\n}")
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
