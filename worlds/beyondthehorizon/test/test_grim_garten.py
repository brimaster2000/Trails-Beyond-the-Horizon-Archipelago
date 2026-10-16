from . import TrailsBTHTestBase
from ..locations import LOCATION_NAME_TO_ID


def set_counter(flags: bytearray, first_flag: int, value: int) -> None:
    for i in range(8):
        if value >> i & 1:
            flags[(first_flag + i) // 8] |= 1 << ((first_flag + i) % 8)


class TestRepeatClears(TrailsBTHTestBase):
    options = {"grim_garten_chest_checks": 2, "grim_garten_repeat_clears": 3}

    def test_repeat_clear_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertIn("Grim Garten - 1st Domain Cleared", names)
        self.assertIn("Grim Garten - 1st Domain Cleared 4", names)
        self.assertNotIn("Grim Garten - 1st Domain Cleared 5", names)
        self.assertNotIn("Grim Garten - 1st Domain Chest 3", names)

    def test_ids_are_distinct(self) -> None:
        ids = [LOCATION_NAME_TO_ID[f"Grim Garten - 2nd Domain Cleared {k}"] for k in range(2, 12)]
        ids += [LOCATION_NAME_TO_ID[f"Grim Garten - 2nd Domain Chest {n}"] for n in range(1, 21)]
        ids.append(LOCATION_NAME_TO_ID["Grim Garten - 2nd Domain Cleared"])
        self.assertEqual(len(set(ids)), len(ids))


class TestClientCounters(TrailsBTHTestBase):
    def test_counters_become_checks(self) -> None:
        from ..Client import grim_garten_checks
        from ..game_memory import GG_FLAG_BASE

        flags = bytearray(0x2000)
        set_counter(flags, GG_FLAG_BASE + 1 * 16, 5)      # 5 chests in the 1st domain
        set_counter(flags, GG_FLAG_BASE + 1 * 16 + 8, 2)  # cleared the 1st domain twice
        found = grim_garten_checks(bytes(flags), 0)
        expected = {LOCATION_NAME_TO_ID[f"Grim Garten - 1st Domain Chest {n}"] for n in range(1, 6)}
        expected |= {LOCATION_NAME_TO_ID["Grim Garten - 1st Domain Cleared"],
                     LOCATION_NAME_TO_ID["Grim Garten - 1st Domain Cleared 2"]}
        self.assertEqual(found, expected)
