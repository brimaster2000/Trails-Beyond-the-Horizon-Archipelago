import asyncio
from pathlib import Path
from typing import Optional

import colorama

from CommonClient import CommonContext, gui_enabled, logger, server_loop, get_base_parser, ClientCommandProcessor, handle_url_arg

from . import save_reader
from .data import CHESTS, GAME_ITEMS
from .items import ITEM_NAME_TO_ID
from .game_memory import CHAPTER_FLAG_BASE, read_marker, seed_marker
from .scena_regions import CHAPTER_IDS

# AP location id -> scenario flag the game sets when that chest is opened.
CHEST_LOCATION_FLAGS = {chest.id: chest.flag for chest in CHESTS if chest.flag is not None}
# AP item id -> [(game item id, quantity), ...]. Story items (Acts) give nothing in game yet.
ITEM_CONTENTS = {ap_id: contents for ap_id, contents in GAME_ITEMS.values()}
# AP item id of each act item -> the chapter it unlocks.
STORY_ITEM_CHAPTERS = {ITEM_NAME_TO_ID[name]: chapter for name, chapter in CHAPTER_IDS.items()}
POLL_SECONDS = 0.5


def deliveries(items_received) -> list[tuple[int, int]]:
    """Every (game item, quantity) the game should have been given, in the order AP sent them."""
    return [pair for item in items_received for pair in ITEM_CONTENTS.get(item.item, [])]


class TBTHCommandProcessor(ClientCommandProcessor):
    def _cmd_tbth(self):
        """Show the game connection state"""
        if isinstance(self.ctx, TBTHContext):
            logger.info(f"Game: {'attached' if self.ctx.game_memory else 'not attached (start the game and load a save)'}")
            logger.info(f"Save folder: {self.ctx.save_dir}")


class TBTHContext(CommonContext):
    game = "Trails Beyond the Horizon"
    command_processor = TBTHCommandProcessor
    items_handling = 0b111

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.save_dir: Path = save_reader.DEFAULT_SAVE_DIR
        self.last_save: Optional[Path] = None
        self.last_save_mtime = 0
        self.game_memory = None  # game_memory.GameMemory while attached to kai.exe
        self.warned_marker = 0  # marker of a foreign save we already warned about

    def run_gui(self):
        """Import kivy UI system and start running it as self.ui_task."""
        from kvui import GameManager

        class TBTHManager(GameManager):
            logging_pairs = [
                ("Client", "Archipelago")
            ]
            base_title = "Archipelago TBTH Client"

        self.ui = TBTHManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    async def server_auth(self, password_requested: bool = False):
        """Wrapper for login."""
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    @property
    def marker(self) -> int:
        """Identifies this seed + slot; written into a save the first time the client sees it."""
        return seed_marker(self.seed_name or "", self.slot or 0)

    def save_is_ours(self, marker: int, where: str) -> bool:
        if marker == self.marker:
            return True
        if marker and marker != self.warned_marker:
            self.warned_marker = marker
            logger.warning(f"{where} belongs to a different seed or slot; ignoring it. Load a save from this seed "
                           f"or start a new game.")
        return False

    async def report_checks(self, found: set[int], source: str) -> None:
        found = (found & self.missing_locations) - self.locations_checked
        if found:
            logger.info(f"Found {len(found)} new check(s) ({source})")
            self.locations_checked |= found
            await self.send_msgs([{"cmd": "LocationChecks", "locations": list(found)}])

    async def check_newest_save(self) -> None:
        """Fallback while not attached to the game: it autosaves after every chest."""
        save = save_reader.newest_save(self.save_dir)
        if save is None:
            return
        mtime = save.stat().st_mtime_ns
        if save == self.last_save and mtime == self.last_save_mtime:
            return
        try:
            data = save_reader.decompress_save(save)
        except Exception as e:  # the game may still be writing it; try again next poll
            logger.debug(f"Could not read {save}: {e}")
            return
        self.last_save, self.last_save_mtime = save, mtime
        # Only saves the client has linked to this seed; anything else may be another playthrough.
        if self.save_is_ours(read_marker(data[save_reader.FLAG_ARRAY_OFFSET:]), save.parent.name):
            await self.report_checks(save_reader.checked_locations(data, CHEST_LOCATION_FLAGS), save.parent.name)

    def attach(self) -> None:
        from . import game_memory

        pid = game_memory.find_game_pid()
        if pid is not None:
            self.game_memory = game_memory.GameMemory(pid, writable=True)
            logger.info(f"Attached to the game (pid {pid})")

    def detach(self) -> None:
        if self.game_memory:
            self.game_memory.close()
            self.game_memory = None
            logger.info("Lost the game; waiting for it to start again")

    async def sync_with_game(self) -> None:
        flags = self.game_memory.read_flags()
        if flags is None:  # title screen, no save loaded
            return
        marker = read_marker(flags)
        if marker == 0:  # a save this client hasn't seen: link it to this seed
            self.game_memory.write_marker(self.marker)
            logger.info("Linked the loaded save to this seed")
        elif not self.save_is_ours(marker, "The loaded save"):
            return
        await self.report_checks(save_reader.checked_locations(flags, CHEST_LOCATION_FLAGS, offset=0), "game")

        # Act items unlock their chapter at once (the gate's "Check again" sees it live).
        for item in self.items_received:
            chapter = STORY_ITEM_CHAPTERS.get(item.item)
            if chapter is not None and not save_reader.flag_is_set(flags, CHAPTER_FLAG_BASE + chapter, offset=0):
                self.game_memory.set_flag(CHAPTER_FLAG_BASE + chapter)
                logger.info(f"Unlocked chapter {chapter} in game")

        if self.game_memory.delivery_pending():
            return  # the game hands it over on the next map change
        pending = deliveries(self.items_received)
        count = self.game_memory.received_count()
        if count < len(pending):
            game_item_id, quantity = pending[count]
            self.game_memory.deliver_item(game_item_id, quantity, new_received_count=count + 1)
            logger.info(f"Sending game item {game_item_id} x{quantity} (arrives on the next map change)")


async def game_watcher(ctx: TBTHContext) -> None:
    while not ctx.exit_event.is_set():
        if ctx.server and ctx.slot is not None:
            try:
                if ctx.game_memory is None:
                    ctx.attach()
                if ctx.game_memory is not None:
                    await ctx.sync_with_game()
                else:
                    await ctx.check_newest_save()
            except OSError as e:  # game closed or memory unreadable
                logger.debug(f"Game access failed: {e}")
                ctx.detach()
        await asyncio.sleep(POLL_SECONDS)


def launch(*launch_args: str):
    async def main():
        parser = get_base_parser(description="Trails Beyond the Horizon Client")
        parser.add_argument("--name", default=None, help="Slot name to connect as.")
        parser.add_argument("--save-dir", default=None, help="Save folder to watch (default: Saved Games/FALCOM/Kai)")
        parser.add_argument("url", nargs="?", help="Archipelago connection url")
        args = handle_url_arg(parser.parse_args(launch_args), parser=parser)
        ctx = TBTHContext(args.connect, args.password)
        ctx.auth = args.name
        if args.save_dir:
            ctx.save_dir = Path(args.save_dir)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="TBTHServerLoop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_watcher(ctx), name="TBTHGameWatcher")
        await ctx.exit_event.wait()
        await watcher
        await ctx.shutdown()

    colorama.just_fix_windows_console()
    asyncio.run(main())
    colorama.deinit()
