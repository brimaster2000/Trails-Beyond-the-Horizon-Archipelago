"""
Reads Xbox-style controllers (XInput) for the Act Menu button.

Game scripts can't read the controller (2026-10-15: no input command in any of the 1311 scripts), so the client
watches it: while the right stick is pressed in (R3), it sets the game patch's Act Menu request flag, and opening the
pause menu then shows the Act Menu (system.OnCampMenuOpen(0)).
"""
from __future__ import annotations

import ctypes
import sys

XINPUT_GAMEPAD_RIGHT_THUMB = 0x0080  # the right stick pressed in (R3)
ERROR_SUCCESS = 0
MAX_CONTROLLERS = 4


class XInputGamepad(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


class XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint32), ("Gamepad", XInputGamepad)]


def _load_xinput():
    if sys.platform != "win32":
        return None
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(name)
        except OSError:
            continue
        dll.XInputGetState.argtypes = [ctypes.c_uint32, ctypes.POINTER(XInputState)]
        dll.XInputGetState.restype = ctypes.c_uint32
        return dll
    return None


class Controllers:
    def __init__(self) -> None:
        self._xinput = _load_xinput()

    @property
    def available(self) -> bool:
        return self._xinput is not None

    def buttons(self) -> int:
        """The buttons held on any connected controller, OR-ed together."""
        held = 0
        state = XInputState()
        for index in range(MAX_CONTROLLERS):
            if self._xinput.XInputGetState(index, ctypes.byref(state)) == ERROR_SUCCESS:
                held |= state.Gamepad.wButtons
        return held

    def act_menu_held(self) -> bool:
        return bool(self.buttons() & XINPUT_GAMEPAD_RIGHT_THUMB)
