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

    def test_grim_garten_bounty_is_in_its_domain(self) -> None:
        location = self.multiworld.get_location("4SPG - Third Domain Bounty", self.player)
        self.assertEqual(location.parent_region.name, "Grim Garten - 3rd Domain")


class TestSideQuestsOff(TrailsBTHTestBase):
    options = {"side_quest_checks": False}

    def test_no_quest_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(any(quest.name in names for quest in QUESTS))


class TestQuestFlags(TrailsBTHTestBase):
    def test_flags_stay_clear_of_other_ap_flags(self) -> None:
        flags = [quest.flag for quest in QUESTS]
        self.assertEqual(len(set(flags)), len(flags))
        # Mailbox 40000-40032, chapter gate 41000-41019, received counter / seed marker 50000-50063
        self.assertTrue(all(42000 < f < 43000 for f in flags))
