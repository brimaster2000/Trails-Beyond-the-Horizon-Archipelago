"""
Live access to the running game's scenario flags (Windows, Steam/NISA kai.exe).

Found 2026-10-08 on the Steam build 3316940 (kai.exe dated 2026-01-28):
- kai.exe loads at its preferred base 0x140000000 (no ASLR relocation observed).
- [kai.exe + 0xD60258] -> the game state object; its first qword is a vtable inside kai.exe (0x140B58070).
- The scenario flag bit array lives at that object + 0x110, same layout as in saves (flag n = bit n % 8 of byte n // 8).
- The game keeps other copies of the array (load buffer, autosave buffer); only this one is live.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct

EXE_NAME = "kai.exe"
STATE_POINTER_RVA = 0xD60258
FLAGS_OFFSET_IN_STATE = 0x110
FLAG_ARRAY_BYTES = 0x2000

# Mailbox read by system.APGrantItems (our hook in script_eng.p3a's system.dat, called from OnMapLoadPost and shown with a popup).
# No script references flags above 37194, and no save sets one.
MAILBOX_ITEM_FLAG = 40000  # 40000-40015 item id, 40016-40031 quantity
MAILBOX_PENDING_FLAG = 40032
# How many (game item, quantity) deliveries this save has been given, as a 32-bit number in flags 50000-50031.
# Flags this high are saved (verified), so the count follows whichever save is loaded.
RECEIVED_COUNTER_FLAG = 50000
# Act gating (sys_event.dat EV_NEXT_CHAPTER_END): chapter c may start only while flag CHAPTER_FLAG_BASE + c is set.
CHAPTER_FLAG_BASE = 41000
# Grim Garten counters kept by the game patch: domain d chests opened at GG_FLAG_BASE + d*16, clears at + 8.
GG_FLAG_BASE = 44000
# Which seed + slot a save belongs to, as a 32-bit marker in flags 50032-50063 (0 = not linked yet).
SEED_MARKER_FLAG = 50032


def seed_marker(seed_name: str, slot: int) -> int:
    import zlib

    return zlib.crc32(f"{seed_name}:{slot}".encode()) or 1


def read_marker(flags: bytes) -> int:
    return int.from_bytes(flags[SEED_MARKER_FLAG // 8:SEED_MARKER_FLAG // 8 + 4], "little")

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_k32.OpenProcess.restype = wt.HANDLE
_k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]
_k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_size_t)]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_psapi.EnumProcesses.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.POINTER(wt.DWORD)]
_psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
_psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]


def find_game_pid() -> int | None:
    pids = (wt.DWORD * 4096)()
    needed = wt.DWORD()
    _psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed))
    for pid in pids[:needed.value // ctypes.sizeof(wt.DWORD)]:
        handle = _k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            continue
        try:
            name = ctypes.create_unicode_buffer(260)
            if _psapi.GetModuleBaseNameW(handle, None, name, 260) and name.value.lower() == EXE_NAME:
                return pid
        finally:
            _k32.CloseHandle(handle)
    return None


class GameMemory:
    def __init__(self, pid: int, writable: bool = False) -> None:
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if writable:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = _k32.OpenProcess(access, False, pid)
        if not self.handle:
            raise OSError(f"Could not open {EXE_NAME} (pid {pid}): error {ctypes.get_last_error()}")
        self.exe_base = self._exe_base()

    def close(self) -> None:
        if self.handle:
            _k32.CloseHandle(self.handle)
            self.handle = None

    def _exe_base(self) -> int:
        modules = (ctypes.c_void_p * 1)()
        needed = wt.DWORD()
        if not _psapi.EnumProcessModulesEx(self.handle, modules, ctypes.sizeof(modules), ctypes.byref(needed), 3):
            raise OSError(f"Could not list modules: error {ctypes.get_last_error()}")
        return modules[0]

    def read(self, address: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        done = ctypes.c_size_t()
        if not _k32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(done)):
            raise OSError(f"Read of 0x{address:X} failed: error {ctypes.get_last_error()}")
        return buf.raw[:done.value]

    def write(self, address: int, data: bytes) -> None:
        done = ctypes.c_size_t()
        if not _k32.WriteProcessMemory(self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(done)):
            raise OSError(f"Write to 0x{address:X} failed: error {ctypes.get_last_error()}")

    def flag_array_address(self) -> int | None:
        """None while no game is loaded (e.g. on the title screen)."""
        state = struct.unpack("<Q", self.read(self.exe_base + STATE_POINTER_RVA, 8))[0]
        return state + FLAGS_OFFSET_IN_STATE if state else None

    def read_flags(self) -> bytes | None:
        address = self.flag_array_address()
        return self.read(address, FLAG_ARRAY_BYTES) if address else None

    def flag(self, flag: int) -> bool:
        flags = self.read_flags()
        return bool(flags and flags[flag // 8] >> (flag % 8) & 1)

    def write_marker(self, marker: int) -> None:
        address = self.flag_array_address()
        if address is None:
            raise RuntimeError("No game loaded")
        self.write(address + SEED_MARKER_FLAG // 8, marker.to_bytes(4, "little"))

    def delivery_pending(self) -> bool:
        return self.flag(MAILBOX_PENDING_FLAG)

    def received_count(self) -> int:
        address = self.flag_array_address()
        if address is None:
            raise RuntimeError("No game loaded")
        return int.from_bytes(self.read(address + RECEIVED_COUNTER_FLAG // 8, 4), "little")

    def deliver_item(self, game_item_id: int, quantity: int, new_received_count: int | None = None) -> None:
        """
        Queue one item for system.APGrantItems, which gives it on the next map load and clears the pending flag.
        The counter is bumped in the same step, so any save holds either neither change or both
        (and a save with the item still pending delivers it again after loading).
        """
        if self.delivery_pending():
            raise RuntimeError("Previous item not collected yet")
        address = self.flag_array_address()
        if address is None:
            raise RuntimeError("No game loaded")
        word = (game_item_id & 0xFFFF) | (quantity & 0xFFFF) << 16
        self.write(address + MAILBOX_ITEM_FLAG // 8, word.to_bytes(4, "little"))  # flags 40000-40031
        if new_received_count is not None:
            self.write(address + RECEIVED_COUNTER_FLAG // 8, new_received_count.to_bytes(4, "little"))
        self.set_flag(MAILBOX_PENDING_FLAG)

    def set_flag(self, flag: int, value: bool = True) -> None:
        address = self.flag_array_address()
        if address is None:
            raise RuntimeError("No game loaded")
        byte_address = address + flag // 8
        byte = self.read(byte_address, 1)[0]
        byte = byte | (1 << flag % 8) if value else byte & ~(1 << flag % 8)
        self.write(byte_address, bytes([byte]))
