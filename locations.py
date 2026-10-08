from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location

from . import items
from .data import CHESTS, QUESTS
from .options import GrimGartenChestChecks
from .regions import grim_garten_region_name
from .scena_regions import CHAPTER_REGION, FINALE, GRIM_GARTEN_BOUNTY_DOMAIN, GRIM_GARTEN_DOMAIN_REGIONS, SCENA_REGION

if TYPE_CHECKING:
    from .world import trailsbthWorld

# Chest IDs come from tools/build_data.py (10_000_000 + scena code * 100 + chest slot).
# Grim Garten: 20_000_000 + domain * 100 + chest number; the domain clear uses chest number 99.
GRIM_GARTEN_BASE = 20_000_000
GRIM_GARTEN_CLEAR_SLOT = 99


def grim_garten_chest_name(domain: int, n: int) -> str:
    return f"{grim_garten_region_name(domain)} Chest {n}"


def grim_garten_clear_name(domain: int) -> str:
    return f"{grim_garten_region_name(domain)} Cleared"


LOCATION_NAME_TO_ID = {chest.name: chest.id for chest in CHESTS}
for _domain in GRIM_GARTEN_DOMAIN_REGIONS:
    for _n in range(1, GrimGartenChestChecks.range_end + 1):
        LOCATION_NAME_TO_ID[grim_garten_chest_name(_domain, _n)] = GRIM_GARTEN_BASE + _domain * 100 + _n
    LOCATION_NAME_TO_ID[grim_garten_clear_name(_domain)] = GRIM_GARTEN_BASE + _domain * 100 + GRIM_GARTEN_CLEAR_SLOT
# Quest ids come from tools/build_data.py (30_000_000 + quest id); main requests are listed for id stability only.
LOCATION_NAME_TO_ID |= {quest.name: quest.id for quest in QUESTS}
SIDE_QUESTS = [quest for quest in QUESTS if quest.kind == "side"]


def quest_region_name(quest) -> str:
    if quest.quest_id in GRIM_GARTEN_BOUNTY_DOMAIN:
        return grim_garten_region_name(GRIM_GARTEN_BOUNTY_DOMAIN[quest.quest_id])
    return CHAPTER_REGION[quest.chapter]


class trailsbthLocation(Location):
    game = "Trails Beyond the Horizon"


def create_all_locations(world: trailsbthWorld) -> None:
    for chest in CHESTS:
        region_name = SCENA_REGION.get(chest.scena)
        if region_name is None or chest.flag is None:  # no known opened flag means the client can't detect it
            continue
        world.get_region(region_name).add_locations({chest.name: chest.id}, trailsbthLocation)
        world.included_chest_vanilla_items.append(chest.vanilla_item)

    for domain in GRIM_GARTEN_DOMAIN_REGIONS:
        region = world.get_region(grim_garten_region_name(domain))
        names = [grim_garten_chest_name(domain, n) for n in range(1, world.options.grim_garten_chest_checks + 1)]
        if world.options.grim_garten_domain_clears:
            names.append(grim_garten_clear_name(domain))
        region.add_locations({name: LOCATION_NAME_TO_ID[name] for name in names}, trailsbthLocation)

    if world.options.side_quest_checks:
        for quest in SIDE_QUESTS:
            world.get_region(quest_region_name(quest)).add_locations({quest.name: quest.id}, trailsbthLocation)

    world.get_region(FINALE).add_event(
        "Final Boss Defeated", "Victory", location_type=trailsbthLocation, item_type=items.trailsbthItem
    )
