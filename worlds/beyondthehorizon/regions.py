from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from .scena_regions import GRIM_GARTEN_DOMAIN_REGIONS, GRIM_GARTEN_DOMAINS, INTERMISSION, PROLOGUE, STORY_REGIONS

if TYPE_CHECKING:
    from .world import trailsbthWorld


def grim_garten_region_name(domain: int) -> str:
    return f"Grim Garten - {GRIM_GARTEN_DOMAINS[domain - 1]} Domain"


def create_and_connect_regions(world: trailsbthWorld) -> None:
    # Every story chapter hangs off the Prologue; the entrance rules in rules.py decide what each one needs.
    prologue = Region(PROLOGUE, world.player, world.multiworld)
    world.multiworld.regions.append(prologue)
    for name in [*STORY_REGIONS[1:], INTERMISSION]:
        region = Region(name, world.player, world.multiworld)
        world.multiworld.regions.append(region)
        prologue.connect(region, f"To {name}")

    # Grim Garten domains hang off every chapter that opens them.
    for domain, parents in GRIM_GARTEN_DOMAIN_REGIONS.items():
        region = Region(grim_garten_region_name(domain), world.player, world.multiworld)
        world.multiworld.regions.append(region)
        for parent in parents:
            world.get_region(parent).connect(region, f"{parent} to {region.name}")
