import asyncio
import unittest

from ..game_memory import SEED_MARKER_FLAG, seed_marker
from .test_delivery import FakeGame


def flags_with_marker(marker: int) -> bytes:
    flags = bytearray(0x2000)
    flags[32000 // 8] |= 1 << (32000 % 8)  # a real save
    flags[SEED_MARKER_FLAG // 8:SEED_MARKER_FLAG // 8 + 4] = marker.to_bytes(4, "little")
    return bytes(flags)


class TestSeedName(unittest.TestCase):
    def test_room_info_seed_name_is_kept(self) -> None:
        # 0.1.0/0.1.1 never stored it, so every seed's marker was crc32(":1") and other seeds' saves were accepted.
        from ..Client import TBTHContext

        async def run() -> tuple[int, int]:
            ctx = TBTHContext(None, None)
            ctx.slot = 1
            ctx.on_package("RoomInfo", {"seed_name": "11111"})
            first = ctx.marker
            ctx.on_package("RoomInfo", {"seed_name": "22222"})
            return first, ctx.marker

        first, second = asyncio.run(run())
        self.assertNotEqual(first, second)
        self.assertEqual(first, seed_marker("11111", 1))


class TestSaveLinking(unittest.TestCase):
    def sync(self, marker: int, seed_name: str | None = "11111") -> tuple[FakeGame, list]:
        from ..Client import TBTHContext

        game = FakeGame(received=7)
        game.read_flags = lambda: flags_with_marker(marker)
        written = []
        game.write_marker = lambda m: written.append(m)

        async def run() -> None:
            ctx = TBTHContext(None, None)
            ctx.slot, ctx.seed_name = 1, seed_name
            ctx.game_memory = game
            ctx.items_received = []
            ctx.missing_locations = set()
            await ctx.sync_with_game()

        asyncio.run(run())
        return game, written

    def test_old_version_save_is_adopted_without_redelivering(self) -> None:
        game, written = self.sync(seed_marker("", 1))
        self.assertEqual(written, [seed_marker("11111", 1)])
        self.assertEqual(game.received, 7)

    def test_other_seeds_save_is_left_alone(self) -> None:
        game, written = self.sync(seed_marker("99999", 1))
        self.assertEqual(written, [])

    def test_nothing_is_linked_before_the_seed_is_known(self) -> None:
        game, written = self.sync(0, seed_name=None)
        self.assertEqual(written, [])
