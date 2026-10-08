from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import CollectionState
from worlds.generic.Rules import set_rule

from .regions import grim_garten_region_name
from .scena_regions import ACT_I, ACT_II_ROUTES, ACT_III_ROUTES, GRIM_GARTEN_DOMAIN_REGIONS, WAVES

if TYPE_CHECKING:
    from .world import trailsbthWorld


def set_all_rules(world: trailsbthWorld) -> None:
    player = world.player

    # The game only offers a wave's routes once every route of the earlier waves is finished,
    # so a route needs its own item plus every item of the waves before it.
    prerequisites: dict[str, list[str]] = {}
    earlier: list[str] = []
    for wave in WAVES:
        for route in wave:
            prerequisites[route] = list(earlier)
        earlier += wave

    for name, needed in prerequisites.items():
        required = [name, *needed]
        set_rule(world.get_entrance(f"To {name}"), lambda state, r=required: state.has_all(r, player))

    all_acts = [ACT_I, *ACT_II_ROUTES, *ACT_III_ROUTES]
    grim_garten_regions = [grim_garten_region_name(d) for d in GRIM_GARTEN_DOMAIN_REGIONS]
    need_grim_garten = world.options.goal == world.options.goal.option_all_acts_and_grim_garten

    def can_open_final_boss_door(state: CollectionState) -> bool:
        if not state.has_all(all_acts, player):
            return False
        return not need_grim_garten or all(state.can_reach_region(r, player) for r in grim_garten_regions)

    set_rule(world.get_location("Final Boss Defeated"), can_open_final_boss_door)
    world.multiworld.completion_condition[player] = lambda state: state.has("Victory", player)
