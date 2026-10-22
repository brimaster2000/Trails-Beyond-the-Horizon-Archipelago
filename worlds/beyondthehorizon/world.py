from collections.abc import Mapping
from typing import Any, ClassVar

import settings
from Options import OptionError
from worlds.AutoWorld import World

from . import items, locations, regions, rules, web_world
from . import options as trailsbth_options  # rename due to a name conflict with World.options
from .scena_regions import PROLOGUE


class trailsbthSettings(settings.Group):
    class GameExe(settings.OptionalUserFilePath):
        """
        Trails beyond the Horizon's kai.exe (Steam, GOG or another store). The client installs the game patch next to
        it. Leave empty to find a Steam install automatically, or to be asked once.
        """
        is_exe = True
        description = "Trails beyond the Horizon (kai.exe)"

        @classmethod
        def validate(cls, path: str) -> None:
            from .patcher import folder_from_path, folder_problem

            problem = folder_problem(folder_from_path(path))
            if problem:
                raise ValueError(problem)

    game_exe: GameExe = GameExe("")


class trailsbthWorld(World):
    """
    The Legend of Heroes: Trails beyond the Horizon. Van, Rean and Kevin's routes are unlocked by items,
    and chests, Grim Garten domains and more become checks.
    """

    game = "Trails Beyond the Horizon"
    web = web_world.trailsbthWebWorld()
    settings_key = "trails_beyond_the_horizon_options"
    settings: ClassVar[trailsbthSettings]

    options_dataclass = trailsbth_options.trailsbthOptions
    options: trailsbth_options.trailsbthOptions

    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_to_id = items.ITEM_NAME_TO_ID
    item_name_groups = {"Acts": set(items.STORY_ITEMS)}
    location_name_groups = {
        "4SPG": {quest.name for quest in locations.SIDE_QUESTS + locations.MAIN_REQUESTS},
        "Side Quests": {quest.name for quest in locations.SIDE_QUESTS},
        "Main Requests": {quest.name for quest in locations.MAIN_REQUESTS},
    }

    origin_region_name = PROLOGUE

    def __init__(self, multiworld, player):
        super().__init__(multiworld, player)
        self.included_chest_vanilla_items: list[str] = []

    def generate_early(self) -> None:
        if self.options.act_order == self.options.act_order.option_actsanity:
            raise OptionError(f"{self.player_name}: act_order 'actsanity' is not supported yet; use 'ordered'.")

    def create_regions(self) -> None:
        regions.create_and_connect_regions(self)
        locations.create_all_locations(self)

    def set_rules(self) -> None:
        rules.set_all_rules(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.trailsbthItem:
        return items.create_item_with_correct_classification(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_random_filler_item_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        return self.options.as_dict(
            "act_order", "grim_garten_chest_checks", "grim_garten_domain_clears", "grim_garten_repeat_clears",
            "side_quest_checks",
            "main_request_checks", "goal"
        )
