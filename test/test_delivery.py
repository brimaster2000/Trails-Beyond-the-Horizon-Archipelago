import asyncio
import unittest
from types import SimpleNamespace
from unittest import mock

from ..data import GAME_ITEMS
from ..game_memory import POPUP_PENDING_FLAG, add_to_stack

# In-game popups are switched off for now (Client.IN_GAME_POPUPS); the popup tests switch them back on.
popups_on = mock.patch(f"{__package__.rpartition('.')[0]}.Client.IN_GAME_POPUPS", True)


class FakeGame:
    """Stands in for GameMemory: an inventory dict and the saved received counter."""

    def __init__(self, received: int = 0) -> None:
        self.inventory: dict[int, int] = {}
        self.received = received
        self.popups: list[tuple[int, int, int]] = []
        self.flags_cleared: list[int] = []
        self.stale_popup = False

    def read_flags(self) -> bytes:
        flags = bytearray(0x2000)
        flags[32000 // 8] |= 1 << (32000 % 8)  # a real save: the Prologue has started
        if self.stale_popup:
            flags[POPUP_PENDING_FLAG // 8] |= 1 << (POPUP_PENDING_FLAG % 8)
        return bytes(flags)

    def write_marker(self, marker: int) -> None:
        pass

    def set_flag(self, flag: int, value: bool = True) -> None:
        if not value:
            self.flags_cleared.append(flag)

    def popup_pending(self) -> bool:
        return False

    def queue_popup(self, game_item_id: int, quantity: int, more: int, kind: int = 0, replace: bool = False) -> None:
        entry = (game_item_id, quantity, more) if kind == 0 else (kind, game_item_id, quantity, more)
        if replace and self.popups:
            self.popups[-1] = entry
        else:
            self.popups.append(entry)

    def read_popup(self) -> tuple[int, int, int, int]:
        last = self.popups[-1]
        return (0, *last) if len(last) == 3 else last

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
            ctx.items_received = [SimpleNamespace(item=i, player=2, location=0) for i in received_ap_ids]
            ctx.missing_locations = set()
            await ctx.sync_with_game()

        asyncio.run(sync())

    @popups_on
    def test_delivers_everything_and_counts(self) -> None:
        balm, _ = GAME_ITEMS["Teara Balm"]
        sepith, contents = GAME_ITEMS["All-Element Sepith x100"]
        game = FakeGame()
        self.run_sync(game, [balm, sepith, balm])
        self.assertEqual(game.inventory[2], 2)  # Teara Balm twice
        self.assertEqual({g: game.inventory[g] for g, _ in contents}, {g: 100 for g, _ in contents})
        self.assertEqual(game.received, 2 + len(contents))  # one per (item, quantity) delivery
        self.assertEqual(game.popups, [(2, 1, 1 + len(contents))])  # one popup: the first item, +N more

    def test_no_popups_while_switched_off(self) -> None:
        balm, _ = GAME_ITEMS["Teara Balm"]
        game = FakeGame()
        game.stale_popup = True  # a popup left waiting in a save from an older build
        self.run_sync(game, [balm])
        self.assertEqual(game.inventory[2], 1)  # the item still arrives
        self.assertEqual(game.popups, [])
        self.assertEqual(game.flags_cleared, [POPUP_PENDING_FLAG])

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
            ctx.items_received = [SimpleNamespace(item=balm, player=2, location=0)]
            ctx.missing_locations = set()
            await ctx.sync_with_game()

        asyncio.run(run())
        self.assertEqual(written, [])
        self.assertEqual(game.inventory, {})


class TestEventLoopStaysFree(unittest.TestCase):
    def test_slow_game_access_does_not_block(self) -> None:
        import time
        from ..Client import TBTHContext

        game = FakeGame()
        slow_read = game.read_flags
        game.read_flags = lambda: (time.sleep(0.5), slow_read())[1]  # e.g. Windows stalling during a load
        ticks = []

        async def run() -> None:
            ctx = TBTHContext(None, None)
            ctx.game_memory = game
            ctx.items_received = []
            ctx.missing_locations = set()

            async def ticker() -> None:  # stands in for answering the server's keepalive pings
                for _ in range(5):
                    ticks.append(time.monotonic())
                    await asyncio.sleep(0.05)

            await asyncio.gather(ctx.sync_with_game(), ticker())

        asyncio.run(run())
        self.assertEqual(len(ticks), 5)
        self.assertLess(ticks[-1] - ticks[0], 0.4)  # kept ticking while the read was still sleeping


@popups_on
class TestChestPopups(unittest.TestCase):
    def run_found(self, scouted: dict, slot: int = 1) -> tuple[FakeGame, list]:
        from ..Client import TBTHContext, CHEST_LOCATION_FLAGS

        location = next(iter(CHEST_LOCATION_FLAGS))
        game = FakeGame()
        flags = bytearray(game.read_flags())
        flag = CHEST_LOCATION_FLAGS[location]
        flags[flag // 8] |= 1 << (flag % 8)
        game.read_flags = lambda: bytes(flags)
        sent = []

        async def run() -> None:
            ctx = TBTHContext(None, None)
            ctx.slot = slot
            ctx.game_memory = game
            ctx.items_received = []
            ctx.missing_locations = {location}
            ctx.scouted = {location: scouted} if scouted else {}

            async def capture(msgs):
                sent.extend(msgs)

            ctx.send_msgs = capture
            await ctx.sync_with_game()
            # the server then sends our own item back: it must not be announced a second time
            ctx.items_received = [SimpleNamespace(item=scouted.item, player=scouted.player, location=location)]                 if scouted and scouted.player == slot else []
            game.popup_pending = lambda: False
            await ctx.sync_with_game()

        asyncio.run(run())
        return game, sent

    def test_own_item_shows_at_its_chest_once(self) -> None:
        from ..data import GAME_ITEMS
        balm, _ = GAME_ITEMS["Teara Balm"]
        game, _ = self.run_found(SimpleNamespace(item=balm, player=1))
        self.assertEqual(game.popups, [(1, 2, 1, 0)])  # "Found Teara Balm x1", and no second "Received" popup
        self.assertEqual(game.inventory[2], 1)

    def test_other_players_item(self) -> None:
        game, _ = self.run_found(SimpleNamespace(item=12345, player=2))
        self.assertEqual(game.popups, [(2, 0, 0, 0)])

    def test_act_item(self) -> None:
        game, _ = self.run_found(SimpleNamespace(item=4, player=1))
        self.assertEqual(game.popups, [(3, 0, 0, 0)])


@popups_on
class TestChestPopupPreemptsStaleReceived(unittest.TestCase):
    def test_found_replaces_waiting_received_popup(self) -> None:
        from ..Client import TBTHContext, CHEST_LOCATION_FLAGS
        from ..data import GAME_ITEMS

        balm, _ = GAME_ITEMS["Teara Balm"]
        location = next(iter(CHEST_LOCATION_FLAGS))
        game = FakeGame()
        game.popups = [(31, 1, 0)]  # an older "Received Curia Balm" popup still waiting
        game.popup_pending = lambda: True
        flags = bytearray(game.read_flags())
        flag = CHEST_LOCATION_FLAGS[location]
        flags[flag // 8] |= 1 << (flag % 8)
        game.read_flags = lambda: bytes(flags)

        async def run() -> TBTHContext:
            ctx = TBTHContext(None, None)
            ctx.slot = 1
            ctx.game_memory = game
            ctx.items_received = []
            ctx.missing_locations = {location}
            ctx.scouted = {location: SimpleNamespace(item=balm, player=1)}

            async def capture(msgs):
                pass

            ctx.send_msgs = capture
            await ctx.sync_with_game()
            return ctx

        ctx = asyncio.run(run())
        self.assertEqual(game.popups, [(1, 2, 1, 0)])  # the chest shows what it held
        self.assertEqual(ctx.popup_backlog, [(31, 1)])  # the older one waits for the next moment
