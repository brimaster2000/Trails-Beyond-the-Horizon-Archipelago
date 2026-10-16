"""
Regenerates ../data.py from KuroTools JSON dumps of the game's tables.

Dev-only: Archipelago never imports this file.

Usage (any Python 3.10+):
    py -3.12 tools/build_data.py <t_tbox.json> <folder containing t_item.json and t_place.json> <t_quest.json>

The chest table must be decoded from the ORIGINAL t_tbox.tbl (e.g. Extracted/Scripteng-p3a/table_eng OG),
not an edited or randomized one, because each chest's vanilla contents become the item pool.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Location IDs: CHEST_BASE + scena letter * 1_000_000 + scena number * 100 + chest slot.
# hack_box gets slot 99. IDs depend only on (scena, chest name), so they stay stable if the table is reordered.
CHEST_BASE = 10_000_000
SCENA_LETTERS = "acdmt"  # a=debug, c=city, d=dungeon, m=field, t=town exterior
HACK_BOX_SLOT = 99

# Item IDs: ITEM_BASE + game item id * 1000 + quantity. Multi-item chests become bundles at BUNDLE_BASE + n.
ITEM_BASE = 1_000_000
BUNDLE_BASE = 9_000_000

# The first FIXED_CHEST_COUNT t_tbox entries are the hand-placed chests (187, matching the
# "Opened 187 treasure chests (other than those in the Grim Garten)" achievement).
# Opening entry i sets scenario flag CHEST_FLAG_BASE + i (verified against real saves).
# Later entries (Coral Archipelago: Alternate, Floating Isles, Grim Garten, debug, Hillside) don't use these flags.
FIXED_CHEST_COUNT = 187
CHEST_FLAG_BASE = 1500

# Quests (4SPG): location id QUEST_BASE + quest id. The game patch sets flag QUEST_FLAG_BASE + quest id when
# system.OnQuestEnd completes a side quest or bounty (ids < MAIN_REQUEST_MIN). Main requests (151+) are completed
# by the engine at chapter end and are not checks yet.
QUEST_BASE = 30_000_000
QUEST_FLAG_BASE = 42000
MAIN_REQUEST_MIN = 151

SEPITH_IDS = [310, 311, 312, 313, 314, 315, 316]
CURRENCY_CATEGORY = 0  # sepith, G-Tokens: table stack_size is 1 but counts go into the thousands
CURRENCY_CAP = 9999
FILLER_GAME_IDS = [2, 6, 31, 30]  # Teara Balm, EP Charge II, Curia Balm, S-Tablet


def load(folder: Path, name: str) -> list[dict]:
    return json.loads((folder / name).read_text(encoding="utf-8"))["data"]


def chest_slot(name: str) -> int:
    if name == "hack_box":
        return HACK_BOX_SLOT
    assert name.startswith("Treasure"), name
    return int(name[len("Treasure"):])


def main(tbox_path: Path, folder: Path, quest_path: Path) -> None:
    tboxes = json.loads(tbox_path.read_text(encoding="utf-8"))["data"][0]["data"]
    places = load(folder, "t_place.json")[0]["data"]
    item_rows = next(t for t in load(folder, "t_item.json") if t["name"] == "ItemTableData")["data"]

    place_names: dict[str, str] = {}
    for p in places:
        for scena in (p["text"], p["text2"]):
            if scena and p["text4"]:
                place_names.setdefault(scena, p["text4"])

    # Game item names, disambiguated by ID when two items share a name.
    raw_names = {row["id"]: row["name"].strip() for row in item_rows}
    name_counts: dict[str, int] = {}
    for n in raw_names.values():
        name_counts[n] = name_counts.get(n, 0) + 1
    game_item_name = {i: (n if n and name_counts[n] == 1 else f"{n or 'Item'} #{i}") for i, n in raw_names.items()}

    # Location names are "<Place> Chest N" (N counts from 1 in table order) and "<Place> Hack Box".
    # If two scenas share a place name, the scena code is added in brackets.
    scena_by_place: dict[str, set[str]] = {}
    for t in tboxes:
        scena_by_place.setdefault(place_names.get(t["scena"], t["scena"]), set()).add(t["scena"])

    items: dict[str, tuple[int, list[tuple[int, int]]]] = {}
    bundles: list[tuple[tuple[int, int], ...]] = []

    def item_for(contents: list[int]) -> str:
        pairs = tuple((contents[i], contents[i + 1]) for i in range(0, len(contents), 2))
        if not pairs:
            return ""  # empty in the table: filled at runtime (random dungeons) or unused
        if len(pairs) == 1:
            game_id, qty = pairs[0]
            name = game_item_name.get(game_id, f"Item #{game_id}") + (f" x{qty}" if qty > 1 else "")
            items.setdefault(name, (ITEM_BASE + game_id * 1000 + qty, list(pairs)))
            return name
        if [p[0] for p in pairs] == SEPITH_IDS and len({p[1] for p in pairs}) == 1:
            name = f"All-Element Sepith x{pairs[0][1]}"
        else:
            name = " + ".join(
                game_item_name.get(g, f"Item #{g}") + (f" x{q}" if q > 1 else "") for g, q in pairs
            )
        if pairs not in bundles:
            bundles.append(pairs)
        items.setdefault(name, (BUNDLE_BASE + bundles.index(pairs), list(pairs)))
        return name

    chests = []
    counter: dict[str, int] = {}
    for index, t in enumerate(tboxes):
        scena = t["scena"]
        place = place_names.get(scena, scena)
        if len(scena_by_place[place]) > 1:
            place = f"{place} [{scena}]"
        if t["name"] == "hack_box":
            loc_name = f"{place} Hack Box"
        else:
            counter[scena] = counter.get(scena, 0) + 1
            loc_name = f"{place} Chest {counter[scena]}"
        loc_id = CHEST_BASE + SCENA_LETTERS.index(scena[0]) * 1_000_000 + int(scena[1:]) * 100 + chest_slot(t["name"])
        flag = CHEST_FLAG_BASE + index if index < FIXED_CHEST_COUNT else None
        chests.append((loc_name, loc_id, scena, t["name"], item_for(t["item_list"]), flag))

    filler = [item_for([game_id, 1]) for game_id in FILLER_GAME_IDS]

    titles = next(t for t in json.loads(quest_path.read_text(encoding="utf-8"))["data"] if t["name"] == "QuestTitle")
    quests = []
    for q in titles["data"]:
        qid = q["id"]
        kind = "main" if qid >= MAIN_REQUEST_MIN else "side"
        # int2 is the chapter the quest belongs to (65535 = Grim Garten bounty, available whenever its domain is)
        quests.append((f"4SPG - {q['quest_description'].strip()}", QUEST_BASE + qid, qid, q["int2"], kind,
                       QUEST_FLAG_BASE + qid))
    assert len({q[0] for q in quests}) == len(quests), "duplicate quest names"

    assert len({c[0] for c in chests}) == len(chests), "duplicate chest location names"
    assert len({c[1] for c in chests}) == len(chests), "duplicate chest location ids"
    assert len({v[0] for v in items.values()}) == len(items), "duplicate item ids"

    out = Path(__file__).resolve().parent.parent / "data.py"
    lines = [
        "# Generated by tools/build_data.py from the game's t_tbox / t_item / t_place / t_quest tables. Do not edit by hand.",
        "from typing import NamedTuple",
        "",
        "",
        "class ChestData(NamedTuple):",
        "    name: str",
        "    id: int",
        "    scena: str",
        "    tbox_name: str",
        "    vanilla_item: str",
        "    flag: int | None  # scenario flag set when opened",
        "",
        "",
        "# (location name, AP location id, scena, t_tbox entry name, vanilla AP item name, opened flag)",
        "CHESTS: list[ChestData] = [",
    ]
    lines += [f"    ChestData({n!r}, {i}, {s!r}, {tb!r}, {v!r}, {f!r})," for n, i, s, tb, v, f in chests]
    lines += [
        "]",
        "",
        "class QuestData(NamedTuple):",
        "    name: str",
        "    id: int",
        "    quest_id: int",
        "    chapter: int  # t_quest QuestTitle int2; 65535 = Grim Garten bounty",
        "    kind: str  # 'side' (side quests, topic quests, bounties) or 'main' (story 4SPG requests)",
        "    flag: int  # set by the game patch when the quest is completed",
        "",
        "",
        "QUESTS: list[QuestData] = [",
    ]
    lines += [f"    QuestData({n!r}, {i}, {q}, {c}, {k!r}, {f})," for n, i, q, c, k, f in quests]
    lines += [
        "]",
        "",
        "# AP item name -> (AP item id, [(game item id, quantity), ...])",
        "GAME_ITEMS: dict[str, tuple[int, list[tuple[int, int]]]] = {",
    ]
    lines += [f"    {n!r}: ({i}, {c!r})," for n, (i, c) in sorted(items.items(), key=lambda kv: kv[1][0])]
    pool_ids = sorted({game_id for _, pairs in items.values() for game_id, _ in pairs})
    rows = {row["id"]: row for row in item_rows}
    caps = {g: CURRENCY_CAP if rows[g]["category"] == CURRENCY_CATEGORY else rows[g]["stack_size"] for g in pool_ids}
    lines += ["}", "", "# Repeatable filler (single consumables)", f"FILLER_ITEMS: list[str] = {filler!r}", ""]
    lines += ["# Game item id -> the most the inventory can hold (t_item stack_size; currencies like sepith use 9999)",
              f"ITEM_STACK_LIMITS: dict[int, int] = {caps!r}", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}: {len(chests)} chests, {len(quests)} quests, {len(items)} items ({len(bundles)} bundles)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
