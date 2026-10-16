import unittest

from . import TrailsBTHTestBase
from ..world import trailsbthWorld
from ..scena_regions import ACT_I_PARTS, ACT_II_ROUTES, ACT_III_ROUTES


class TestOrdered(TrailsBTHTestBase):
    options = {"act_order": "ordered"}

    def test_act_ii_needs_act_i(self) -> None:
        self.collect_by_name("Act II - Rean Route 1")
        self.assertFalse(self.can_reach_location("Auge Canyon Chest 1"))
        self.collect_by_name(ACT_I_PARTS)
        self.assertTrue(self.can_reach_location("Auge Canyon Chest 1"))

    def test_finale_needs_every_act(self) -> None:
        self.collect_by_name([*ACT_I_PARTS, "Finale", *ACT_II_ROUTES, *ACT_III_ROUTES[:-1]])
        self.assertFalse(self.can_reach_region("Finale"))
        self.collect_by_name(ACT_III_ROUTES[-1])
        self.assertTrue(self.can_reach_region("Finale"))
        self.assertBeatable(True)


class TestWaves(TrailsBTHTestBase):
    options = {"act_order": "ordered"}

    def test_second_wave_needs_first_wave_items(self) -> None:
        self.collect_by_name([*ACT_I_PARTS, "Act II - Rean Route 2"])
        self.assertFalse(self.can_reach_location("Astrological Workshop Ruins Chest 1"))
        self.collect_by_name(["Act II - Rean Route 1", "Act II - Kevin Route 1"])
        self.assertFalse(self.can_reach_location("Astrological Workshop Ruins Chest 1"))
        self.collect_by_name("Act II - Van Route 1")
        self.assertTrue(self.can_reach_location("Astrological Workshop Ruins Chest 1"))

    def test_route_in_wave_needs_own_item(self) -> None:
        self.collect_by_name([*ACT_I_PARTS, "Act II - Kevin Route 1"])
        self.assertFalse(self.can_reach_location("Auge Canyon Chest 1"))
        self.assertTrue(self.can_reach_location("Sandsea Chest 1"))

    def test_finale_item_alone_does_not_open_finale(self) -> None:
        self.collect_by_name("Finale")
        self.assertFalse(self.can_reach_region("Finale"))
        self.assertBeatable(False)


class TestGrimGarten(TrailsBTHTestBase):
    options = {"grim_garten_chest_checks": 5, "grim_garten_domain_clears": True}

    def test_domain_locations_exist(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertIn("Grim Garten - 1st Domain Chest 5", names)
        self.assertNotIn("Grim Garten - 1st Domain Chest 6", names)
        self.assertIn("Grim Garten - 2nd Domain Cleared", names)
        self.assertFalse(self.can_reach_location("Grim Garten - 1st Domain Cleared"))
        self.collect_by_name(ACT_I_PARTS)
        self.assertTrue(self.can_reach_location("Grim Garten - 1st Domain Cleared"))


class TestGrimGartenGoal(TrailsBTHTestBase):
    options = {"goal": "all_acts_and_grim_garten"}


class TestActsanityRefused(unittest.TestCase):
    def test_generation_refuses_actsanity(self) -> None:
        from Options import OptionError
        from test.general import setup_solo_multiworld
        multiworld = setup_solo_multiworld(trailsbthWorld, steps=())
        world = multiworld.worlds[1]
        world.options.act_order.value = world.options.act_order.option_actsanity
        with self.assertRaises(OptionError):
            world.generate_early()


class TestActIParts(TrailsBTHTestBase):
    def test_parts_open_in_order(self) -> None:
        self.collect_by_name("Act I - A")
        self.assertTrue(self.can_reach_location("Seiden Waterworks Chest 1"))
        self.assertFalse(self.can_reach_location("Underground Culvert Chest 1"))
        self.collect_by_name("Act I - C")
        self.assertFalse(self.can_reach_location("Junction Area Chest 1"))  # C also needs B
        self.collect_by_name("Act I - B")
        self.assertTrue(self.can_reach_location("Underground Culvert Chest 1"))
        self.assertTrue(self.can_reach_location("Junction Area Chest 1"))
        self.assertTrue(self.can_reach_location("Grim Garten - 1st Domain Cleared"))

    def test_story_item_ids_are_chapter_ids(self) -> None:
        from ..items import ITEM_NAME_TO_ID
        self.assertEqual(ITEM_NAME_TO_ID["Act I - A"], 1)
        self.assertEqual(ITEM_NAME_TO_ID["Act I - C"], 3)
        self.assertEqual(ITEM_NAME_TO_ID["Finale"], 19)


class TestChestOverrides(TrailsBTHTestBase):
    def test_late_sandsea_chests_need_kevin_route_2(self) -> None:
        early = [*ACT_I_PARTS, "Act II - Kevin Route 1"]
        self.collect_by_name(early)
        self.assertTrue(self.can_reach_location("Sandsea Chest 7"))
        self.assertFalse(self.can_reach_location("Sandsea Chest 8"))
        self.assertEqual(self.multiworld.get_location("Sandsea Chest 9", self.player).parent_region.name,
                         "Act III - Kevin Route 2")
