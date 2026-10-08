import asyncio
import unittest

from ..game_memory import GG_FLAG_BASE
from ..options import Goal
from .test_delivery import FakeGame


def flags_with(*set_flags: int, cleared_domains: tuple[int, ...] = ()) -> bytes:
    flags = bytearray(0x2000)
    for flag in set_flags:
        flags[flag // 8] |= 1 << (flag % 8)
    for domain in cleared_domains:  # clear counter = 1
        flag = GG_FLAG_BASE + domain * 16 + 8
        flags[flag // 8] |= 1 << (flag % 8)
    return bytes(flags)


class TestGoalRules(unittest.TestCase):
    def test_nothing_before_the_final_boss(self) -> None:
        from ..Client import missing_for_goal
        self.assertIsNone(missing_for_goal(flags_with(), 0, Goal.option_all_acts))

    def test_all_acts_goal_on_final_boss(self) -> None:
        from ..Client import FINAL_BOSS_DEFEATED_FLAG, missing_for_goal
        self.assertEqual(missing_for_goal(flags_with(FINAL_BOSS_DEFEATED_FLAG), 0, Goal.option_all_acts), [])

    def test_grim_garten_goal_needs_every_domain(self) -> None:
        from ..Client import FINAL_BOSS_DEFEATED_FLAG, missing_for_goal
        goal = Goal.option_all_acts_and_grim_garten
        partial = flags_with(FINAL_BOSS_DEFEATED_FLAG, cleared_domains=tuple(range(1, 9)))
        self.assertEqual(missing_for_goal(partial, 0, goal), ["Grim Garten domain 9"])
        full = flags_with(FINAL_BOSS_DEFEATED_FLAG, cleared_domains=tuple(range(1, 10)))
        self.assertEqual(missing_for_goal(full, 0, goal), [])


class TestGoalDoor(unittest.TestCase):
    def run_sync(self, flags: bytes, goal: int) -> list[int]:
        from ..Client import TBTHContext

        game = FakeGame()
        game.read_flags = lambda: flags
        opened = []
        game.set_flag = lambda flag, value=True: opened.append(flag)

        async def run() -> None:
            ctx = TBTHContext(None, None)
            ctx.game_memory = game
            ctx.goal = goal
            ctx.items_received = []
            ctx.missing_locations = set()
            await ctx.sync_with_game()

        asyncio.run(run())
        return opened

    def test_all_acts_opens_door_right_away(self) -> None:
        from ..game_memory import GOAL_DOOR_FLAG
        self.assertIn(GOAL_DOOR_FLAG, self.run_sync(flags_with(), Goal.option_all_acts))

    def test_grim_garten_goal_keeps_door_shut_until_all_domains(self) -> None:
        from ..game_memory import GOAL_DOOR_FLAG
        goal = Goal.option_all_acts_and_grim_garten
        self.assertNotIn(GOAL_DOOR_FLAG, self.run_sync(flags_with(cleared_domains=tuple(range(1, 9))), goal))
        self.assertIn(GOAL_DOOR_FLAG, self.run_sync(flags_with(cleared_domains=tuple(range(1, 10))), goal))


class TestGoalSent(unittest.TestCase):
    def test_status_update_sent_once(self) -> None:
        from ..Client import FINAL_BOSS_DEFEATED_FLAG, TBTHContext

        game = FakeGame()
        game.read_flags = lambda: flags_with(FINAL_BOSS_DEFEATED_FLAG)
        sent = []

        async def run() -> None:
            ctx = TBTHContext(None, None)
            ctx.game_memory = game
            ctx.items_received = []
            ctx.missing_locations = set()

            async def capture(msgs):
                sent.extend(msgs)

            ctx.send_msgs = capture
            await ctx.sync_with_game()
            await ctx.sync_with_game()

        asyncio.run(run())
        self.assertEqual([m for m in sent if m["cmd"] == "StatusUpdate"], [{"cmd": "StatusUpdate", "status": 30}])
