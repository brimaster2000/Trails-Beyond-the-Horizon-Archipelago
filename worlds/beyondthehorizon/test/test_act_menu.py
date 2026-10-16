import asyncio
import unittest
from unittest import mock

from ..game_memory import ACT_MENU_REQUEST_FLAG


class ScriptedPads:
    """Plays back one 'held?' answer per poll, then stops the client."""

    available = True

    def __init__(self, ctx, presses: list[bool], attach_at: int | None = None, game=None) -> None:
        self.ctx, self.presses, self.attach_at, self.game, self.polls = ctx, presses, attach_at, game, 0

    def act_menu_held(self) -> bool:
        if self.polls == self.attach_at:
            self.ctx.game_memory = self.game
        if self.polls >= len(self.presses):
            self.ctx.exit_event.set()
            return self.presses[-1]
        self.polls += 1
        return self.presses[self.polls - 1]


class FakeGame:
    def __init__(self) -> None:
        self.writes: list[tuple[int, bool]] = []

    def set_flag(self, flag: int, value: bool = True) -> None:
        self.writes.append((flag, value))


def run_watcher(presses: list[bool], attach_at: int | None = 0) -> FakeGame:
    from .. import Client

    game = FakeGame()

    async def run() -> None:
        ctx = Client.TBTHContext(None, None)
        ctx.game_memory = None
        pads = ScriptedPads(ctx, presses, attach_at, game)
        with mock.patch.object(Client, "ACT_MENU_POLL_SECONDS", 0):
            await Client.act_menu_button_watcher(ctx, pads)

    asyncio.run(run())
    return game


class TestActMenuButton(unittest.TestCase):
    def test_press_sets_and_release_clears_once_each(self) -> None:
        game = run_watcher([False, True, True, True, False, False])
        self.assertEqual(game.writes, [(ACT_MENU_REQUEST_FLAG, True), (ACT_MENU_REQUEST_FLAG, False)])

    def test_press_before_the_game_is_attached_is_applied_once_it_is(self) -> None:
        game = run_watcher([True, True, True], attach_at=2)
        self.assertEqual(game.writes, [(ACT_MENU_REQUEST_FLAG, True)])

    def test_nothing_written_without_a_press(self) -> None:
        self.assertEqual(run_watcher([False, False, False]).writes, [])

    def test_no_xinput_returns_quietly(self) -> None:
        from .. import Client

        async def run() -> None:
            ctx = Client.TBTHContext(None, None)
            await Client.act_menu_button_watcher(ctx, mock.Mock(available=False))

        asyncio.run(run())  # must not hang or raise


class TestActMenuKey(unittest.TestCase):
    def test_key_names(self) -> None:
        from ..controller import key_code

        self.assertEqual(key_code("F1"), 0x70)
        self.assertEqual(key_code(" f12 "), 0x7B)
        self.assertEqual(key_code("q"), ord("Q"))
        self.assertIsNone(key_code("SPACEBAR"))

    def test_changing_the_key_updates_the_watcher_and_is_remembered(self) -> None:
        import Utils
        from .. import Client
        from ..controller import Controllers

        async def run() -> tuple:
            with mock.patch.object(Utils, "persistent_load", return_value={}), \
                    mock.patch.object(Utils, "persistent_store") as store:
                ctx = Client.TBTHContext(None, None)
                self.assertEqual(ctx.act_menu_key, "F1")  # default
                ctx.act_menu_pads = Controllers(ctx.act_menu_key)
                ctx.set_act_menu_key("tab")
                return ctx, store

        ctx, store = asyncio.run(run())
        self.assertEqual(ctx.act_menu_key, "TAB")
        self.assertEqual(ctx.act_menu_pads.key, 0x09)
        store.assert_called_once_with("tbth", "act_menu_key", "TAB")

    def test_saved_key_is_used_and_bad_values_fall_back(self) -> None:
        import Utils
        from .. import Client

        with mock.patch.object(Utils, "persistent_load", return_value={"tbth": {"act_menu_key": "f2"}}):
            self.assertEqual(Client.TBTHContext.saved_act_menu_key(), "F2")
        with mock.patch.object(Utils, "persistent_load", return_value={"tbth": {"act_menu_key": "nonsense"}}):
            self.assertEqual(Client.TBTHContext.saved_act_menu_key(), "F1")


class TestControllerModule(unittest.TestCase):
    def test_right_stick_bit(self) -> None:
        from ..controller import XINPUT_GAMEPAD_RIGHT_THUMB, XInputGamepad, XInputState
        import ctypes

        self.assertEqual(XINPUT_GAMEPAD_RIGHT_THUMB, 0x0080)
        self.assertEqual(ctypes.sizeof(XInputGamepad), 12)  # XINPUT_GAMEPAD
        self.assertEqual(ctypes.sizeof(XInputState), 16)  # XINPUT_STATE
