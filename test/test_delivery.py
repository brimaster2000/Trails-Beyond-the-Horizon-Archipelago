import asyncio
import unittest
from types import SimpleNamespace

from ..data import GAME_ITEMS
from ..game_memory import add_to_stack


class FakeGame:
    """Stands in for GameMemory: an inventory dict and the saved received counter."""

    def __init__(self, received: int = 0) -> None:
        self.inventory: dict[int, int] = {}
        self.received = received
        self.popups: list[tuple[int, int, int]] = []

    def read_flags(self) -> bytes:
        flags = bytearray(0x2000)
        flags[32000 // 8] |= 1 << (32000 % 8)  # a real save: the Prologue has started
        return bytes(flags)

    def write_marker(self, marker: int) -> None:
        pass

    def set_flag(self, flag: int, value: bool = True) -> None:
        pass

    def popup_pending(self) -> bool:
        return False

    def queue_popup(self, game_item_id: int, quantity: int, more: int) -> None:
        self.popups.append((game_item_id, quantity, more))

    def received_count(self) -> int:
        return self.received

    def set_received_count(self, count: int) -> None:
        self.received = count

    def add_item(self, game_item_id: int, quantity: int, limit: int) -> int:
        before = self.inventory.get(game_item_id, 0)
        self.inventory[game_item_id] = add_to_stack(before, quantity, limit)
        return self.inventory[game_item_id] - before


class TestStackLimits(unittest.TestCase):
    def test_caps(self) -> None:
        self.assertEqual(add_to_stack(98, 5, 99), 99)
        self.assertEqual(add_to_stack(0, 300, 9999), 300)
        self.assertEqual(add_to_stack(1, 1, 1), 1)


class TestLiveDelivery(unittest.TestCase):
    def run_sync(self, game: FakeGame, received_ap_ids: list[int]) -> None:
        from ..Client import TBTHContext

        async def sync() -> None:
            ctx = TBTHContext(None, None)  # needs a running event loop
            ctx.game_memory = game
            ctx.items_received = [SimpleNamespace(item=i) for i in received_ap_ids]
            ctx.missing_locations = set()
            await ctx.sync_with_game()

        asyncio.run(sync())

    def test_delivers_everything_and_counts(self) -> None:
        balm, _ = GAME_ITEMS["Teara Balm"]
        sepith, contents = GAME_ITEMS["All-Element Sepith x100"]
        game = FakeGame()
        self.run_sync(game, [balm, sepith, balm])
        self.assertEqual(game.inventory[2], 2)  # Teara Balm twice
        self.assertEqual({g: game.inventory[g] for g, _ in contents}, {g: 100 for g, _ in contents})
        self.assertEqual(game.received, 2 + len(contents))  # one per (item, quantity) delivery
        self.assertEqual(game.popups, [(2, 1, 1 + len(contents))])  # one popup: the first item, +N more

    def test_older_save_gets_the_rest_again(self) -> None:
        balm, _ = GAME_ITEMS["Teara Balm"]
        game = FakeGame(received=1)  # this save already had the first delivery
        self.run_sync(game, [balm, balm, balm])
        self.assertEqual(game.inventory[2], 2)
        self.assertEqual(game.received, 3)


class TestTitleScreen(unittest.TestCase):
    def test_title_screen_state_is_left_alone(self) -> None:
        from ..Client import TBTHContext
        from ..data import GAME_ITEMS

        balm, _ = GAME_ITEMS["Teara Balm"]
        game = FakeGame()
        game.read_flags = lambda: bytes(0x2000)  # no Prologue flag: title screen
        written = []
        game.write_marker = lambda marker: written.append(marker)

        async def run() -> None:
            ctx = TBTHContext(None, None)
            ctx.game_memory = game
            ctx.items_received = [SimpleNamespace(item=balm)]
            ctx.missing_locations = set()
            await ctx.sync_with_game()

        asyncio.run(run())
        self.assertEqual(written, [])
        self.assertEqual(game.inventory, {})
