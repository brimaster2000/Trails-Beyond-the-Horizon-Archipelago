from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data import FILLER_ITEMS, GAME_ITEMS
from .scena_regions import STORY_REGIONS

if TYPE_CHECKING:
    from .world import trailsbthWorld

# Story items: one per chapter after the Prologue ("Act I", "Act II - Rean Route 1", ..., "Finale"). IDs 1..14.
STORY_ITEMS = STORY_REGIONS[1:]

# Game items keep IDs derived from the game's own item IDs (see tools/build_data.py), so the client can
# turn an AP item ID straight back into the game items to give.
ITEM_NAME_TO_ID = {name: i for i, name in enumerate(STORY_ITEMS, start=1)}
ITEM_NAME_TO_ID |= {name: ap_id for name, (ap_id, _) in GAME_ITEMS.items()}

FILLER_KEYWORDS = ("Balm", "Tablet", "EP Charge", "Sepith", "G-Tokens", "U-Material")


class trailsbthItem(Item):
    game = "Trails Beyond the Horizon"


def get_random_filler_item_name(world: trailsbthWorld) -> str:
    return world.random.choice(FILLER_ITEMS)


def create_item_with_correct_classification(world: trailsbthWorld, name: str) -> trailsbthItem:
    if name in STORY_ITEMS:
        classification = ItemClassification.progression
    elif any(keyword in name for keyword in FILLER_KEYWORDS):
        classification = ItemClassification.filler
    else:
        classification = ItemClassification.useful
    return trailsbthItem(name, classification, ITEM_NAME_TO_ID[name], world.player)


def create_all_items(world: trailsbthWorld) -> None:
    itempool: list[Item] = [world.create_item(name) for name in STORY_ITEMS]

    # The rest of the pool is the vanilla contents of every chest in the seed.
    # Story items take the place of randomly chosen vanilla items; empty slots become filler.
    vanilla = [name for name in world.included_chest_vanilla_items if name]
    world.random.shuffle(vanilla)
    number_of_unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))
    vanilla = vanilla[:max(0, number_of_unfilled_locations - len(itempool))]
    itempool += [world.create_item(name) for name in vanilla]

    itempool += [world.create_filler() for _ in range(number_of_unfilled_locations - len(itempool))]
    world.multiworld.itempool += itempool
