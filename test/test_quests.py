from . import TrailsBTHTestBase
from ..data import QUESTS
from ..locations import SIDE_QUESTS
from ..scena_regions import ACT_I_PARTS


class TestSideQuests(TrailsBTHTestBase):
    def test_all_side_quests_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertEqual(len(SIDE_QUESTS), 49)
        for quest in SIDE_QUESTS:
            self.assertIn(quest.name, names)

    def test_quest_needs_its_chapter(self) -> None:
        self.assertFalse(self.can_reach_location("4SPG - Waterworks Bounty"))
        self.collect_by_name("Act I - A")
        self.assertTrue(self.can_reach_location("4SPG - Waterworks Bounty"))
        self.assertFalse(self.can_reach_location("4SPG - Auge Canyon Bounty"))
        self.collect_by_name([*ACT_I_PARTS, "Act II - Rean Route 1"])
        self.assertTrue(self.can_reach_location("4SPG - Auge Canyon Bounty"))

    def test_grim_garten_bounties_are_in_the_route_that_offers_them(self) -> None:
        # Neoseeker 4SPG list. A playtest seed put Rean Route 1 on the Third Domain Bounty while logic thought any
        # wave 1 route reached it; the game only offers it in Van Route 3, which itself needs Rean Route 1.
        expected = {"First": "Act II - Rean Route 2", "Third": "Act II - Van Route 3",
                    "Fifth": "Act III - Van Route 5", "Seventh": "Act III - Van Route 6"}
        for domain, region in expected.items():
            location = self.multiworld.get_location(f"4SPG - {domain} Domain Bounty", self.player)
            self.assertEqual(location.parent_region.name, region)

    def test_blacklight_district_chests_need_van_route_2(self) -> None:
        # Playtest: every Blacklight District chest is only reachable during the fire in Van Route 2.
        chest = self.multiworld.get_location("Blacklight District Chest 1", self.player)
        self.assertEqual(chest.parent_region.name, "Act II - Van Route 2")
        # ...except the hack box, which only opens in Act I-B (user confirmed).
        hack_box = self.multiworld.get_location("Blacklight District Hack Box", self.player)
        self.assertEqual(hack_box.parent_region.name, "Act I - B")

    def test_third_domain_needs_all_of_wave_one(self) -> None:
        self.collect_by_name([*ACT_I_PARTS, "Act II - Kevin Route 1", "Act II - Van Route 1"])
        self.assertFalse(self.can_reach_region("Grim Garten - 3rd Domain"))
        self.collect_by_name("Act II - Rean Route 1")
        self.assertTrue(self.can_reach_region("Grim Garten - 3rd Domain"))


class TestSideQuestsOff(TrailsBTHTestBase):
    options = {"side_quest_checks": False, "main_request_checks": False}

    def test_no_quest_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(any(quest.name in names for quest in QUESTS))


class TestQuestFlags(TrailsBTHTestBase):
    def test_flags_stay_clear_of_other_ap_flags(self) -> None:
        flags = [quest.flag for quest in QUESTS]
        self.assertEqual(len(set(flags)), len(flags))
        # Mailbox 40000-40032, chapter gate 41000-41019, received counter / seed marker 50000-50063
        self.assertTrue(all(42000 < f < 43000 for f in flags))


class TestMainRequests(TrailsBTHTestBase):
    def test_reported_main_requests_are_locations(self) -> None:
        from ..locations import MAIN_REQUESTS
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertEqual(len(MAIN_REQUESTS), 34)
        self.assertIn("4SPG - Patrolling the Capital", names)
        self.assertNotIn("4SPG - Stargazing at the Observatory", names)  # never on a chapter-end report

    def test_prologue_request_is_free(self) -> None:
        self.assertTrue(self.can_reach_location("4SPG - Taking the VAR-halla Sector by Storm"))

    def test_intermission_request_needs_wave_one(self) -> None:
        name = "4SPG - Triple Teaming the Third Domain"
        self.collect_by_name([*ACT_I_PARTS, "Act II - Rean Route 1", "Act II - Kevin Route 1"])
        self.assertFalse(self.can_reach_location(name))
        self.collect_by_name("Act II - Van Route 1")
        self.assertTrue(self.can_reach_location(name))


class TestMainRequestsOff(TrailsBTHTestBase):
    options = {"main_request_checks": False}

    def test_no_main_request_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertNotIn("4SPG - Patrolling the Capital", names)
        self.assertIn("4SPG - Waterworks Bounty", names)
