from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location

from . import items
from .data import CHESTS, QUESTS
from .options import GrimGartenChestChecks, GrimGartenRepeatClears
from .regions import grim_garten_region_name
from .scena_regions import CHAPTER_REGION, CHEST_REGION_OVERRIDES, FINALE, GRIM_GARTEN_BOUNTY_DOMAIN, GRIM_GARTEN_DOMAIN_REGIONS, SCENA_REGION

if TYPE_CHECKING:
    from .world import trailsbthWorld

# Chest IDs come from tools/build_data.py (10_000_000 + scena code * 100 + chest slot).
# Grim Garten: 20_000_000 + domain * 100 + chest number; the first clear uses 99, the k-th clear (k >= 2) uses 60 + k.
GRIM_GARTEN_BASE = 20_000_000
GRIM_GARTEN_CLEAR_SLOT = 99
GRIM_GARTEN_REPEAT_SLOT = 60


def grim_garten_chest_name(domain: int, n: int) -> str:
    return f"{grim_garten_region_name(domain)} Chest {n}"


def grim_garten_clear_name(domain: int, clear: int = 1) -> str:
    return f"{grim_garten_region_name(domain)} Cleared" + (f" {clear}" if clear > 1 else "")


def grim_garten_clear_id(domain: int, clear: int = 1) -> int:
    return GRIM_GARTEN_BASE + domain * 100 + (GRIM_GARTEN_CLEAR_SLOT if clear == 1 else GRIM_GARTEN_REPEAT_SLOT + clear)


def grim_garten_chest_id(domain: int, chest: int) -> int:
    return GRIM_GARTEN_BASE + domain * 100 + chest


LOCATION_NAME_TO_ID = {chest.name: chest.id for chest in CHESTS}
for _domain in GRIM_GARTEN_DOMAIN_REGIONS:
    for _n in range(1, GrimGartenChestChecks.range_end + 1):
        LOCATION_NAME_TO_ID[grim_garten_chest_name(_domain, _n)] = grim_garten_chest_id(_domain, _n)
    for _k in range(1, GrimGartenRepeatClears.range_end + 2):
        LOCATION_NAME_TO_ID[grim_garten_clear_name(_domain, _k)] = grim_garten_clear_id(_domain, _k)
# Quest ids come from tools/build_data.py (30_000_000 + quest id); main requests are listed for id stability only.
LOCATION_NAME_TO_ID |= {quest.name: quest.id for quest in QUESTS}
SIDE_QUESTS = [quest for quest in QUESTS if quest.kind == "side"]
# Main requests are completed by the engine on the chapter-end 4SPG report (ChapterEnd), where the game patch
# sets their flag. These three are never on a chapter-end report, so they can't be detected that way.
UNREPORTED_MAIN_REQUESTS = {152, 172, 188}
MAIN_REQUESTS = [q for q in QUESTS if q.kind == "main" and q.quest_id not in UNREPORTED_MAIN_REQUESTS]


def quest_region_name(quest) -> str:
    if quest.quest_id in GRIM_GARTEN_BOUNTY_DOMAIN:
        return grim_garten_region_name(GRIM_GARTEN_BOUNTY_DOMAIN[quest.quest_id])
    return CHAPTER_REGION[quest.chapter]


class trailsbthLocation(Location):
    game = "Trails Beyond the Horizon"


def create_all_locations(world: trailsbthWorld) -> None:
    for chest in CHESTS:
        region_name = CHEST_REGION_OVERRIDES.get(chest.name, SCENA_REGION.get(chest.scena))
        if region_name is None or chest.flag is None:  # no known opened flag means the client can't detect it
            continue
        world.get_region(region_name).add_locations({chest.name: chest.id}, trailsbthLocation)
        world.included_chest_vanilla_items.append(chest.vanilla_item)

    for domain in GRIM_GARTEN_DOMAIN_REGIONS:
        region = world.get_region(grim_garten_region_name(domain))
        names = [grim_garten_chest_name(domain, n) for n in range(1, world.options.grim_garten_chest_checks + 1)]
        if world.options.grim_garten_domain_clears:
            names.append(grim_garten_clear_name(domain))
        names += [grim_garten_clear_name(domain, k) for k in range(2, world.options.grim_garten_repeat_clears + 2)]
        region.add_locations({name: LOCATION_NAME_TO_ID[name] for name in names}, trailsbthLocation)

    quests = (SIDE_QUESTS if world.options.side_quest_checks else []) + (
        MAIN_REQUESTS if world.options.main_request_checks else [])
    for quest in quests:
        world.get_region(quest_region_name(quest)).add_locations({quest.name: quest.id}, trailsbthLocation)

    world.get_region(FINALE).add_event(
        "Final Boss Defeated", "Victory", location_type=trailsbthLocation, item_type=items.trailsbthItem
    )
