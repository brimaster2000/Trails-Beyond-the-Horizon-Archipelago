from dataclasses import dataclass

from Options import Choice, OptionGroup, PerGameCommonOptions, Range, Toggle


class ActOrder(Choice):
    """
    Ordered: follows the game's Time Chart. Each route needs its own item, and routes open in waves:
    Act I - A -> Act I - B -> Act I - C -> Rean 1 / Kevin 1 / Van 1 -> Rean 2 / Van 2 -> Van 3
    -> Kevin 2 / Van 4 -> Van 5 -> Rean 3 / Kevin 3 / Van 6 -> Finale. Within a wave the routes can be played in any order.
    Actsanity (experimental, not supported yet): any route at any time. This needs skipping chapters in game,
    so generation refuses it for now.
    """
    display_name = "Act Order"
    option_ordered = 0
    option_actsanity = 1
    default = option_ordered


class GrimGartenChestChecks(Range):
    """
    The first N chests opened in each Grim Garten domain are checks.
    """
    display_name = "Grim Garten Chest Checks"
    range_start = 0
    range_end = 20
    default = 3


class GrimGartenDomainClears(Toggle):
    """
    Clearing a Grim Garten domain is a check.
    """
    display_name = "Grim Garten Domain Clears"
    default = 1


class Goal(Choice):
    """
    What unlocks the final boss door in the Finale.
    All Acts: have every act route.
    All Acts and Grim Garten: also be able to clear every Grim Garten domain.
    """
    display_name = "Goal"
    option_all_acts = 0
    option_all_acts_and_grim_garten = 1
    default = option_all_acts


@dataclass
class trailsbthOptions(PerGameCommonOptions):
    act_order: ActOrder
    grim_garten_chest_checks: GrimGartenChestChecks
    grim_garten_domain_clears: GrimGartenDomainClears
    goal: Goal


option_groups = [
    OptionGroup("Progression", [ActOrder, Goal]),
    OptionGroup("Grim Garten", [GrimGartenChestChecks, GrimGartenDomainClears]),
]
