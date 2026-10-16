"""
Reads controllers (XInput, plus winmm for PlayStation-layout pads) and the keyboard for the Act Menu button.

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
# PlayStation-layout pads (and others passed through as one) are invisible to XInput, but the older winmm joystick API
# sees them. There R3 is button 12 (DualShock 4 order; verified 2026-10-16 with the user's Switch 2 Pro controller
# passed through as a PS4 pad). Xbox pads also show up in winmm, but with R3 as button 10 and no button 12.
WINMM_R3_BUTTON = 12
MAX_JOYSTICKS = 16
JOY_RETURNBUTTONS = 0x80
# Keyboard players hold this key instead (any window may have focus). Windows virtual-key codes.
DEFAULT_ACT_MENU_KEY = "F1"
KEY_CODES = {f"F{n}": 0x6F + n for n in range(1, 13)} | {c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"} | {
    "TAB": 0x09, "BACKSPACE": 0x08, "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21,
    "PAGEDOWN": 0x22, "BACKQUOTE": 0xC0}


def key_code(name: str) -> int | None:
    return KEY_CODES.get(name.strip().upper())


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


class JoyInfoEx(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos", "dwButtons",
        "dwButtonNumber", "dwPOV", "dwReserved1", "dwReserved2")]


def _load_winmm():
    if sys.platform != "win32":
        return None
    try:
        dll = ctypes.WinDLL("winmm")
    except OSError:
        return None
    dll.joyGetPosEx.argtypes = [ctypes.c_uint32, ctypes.POINTER(JoyInfoEx)]
    dll.joyGetPosEx.restype = ctypes.c_uint32
    return dll


def _load_user32():
    if sys.platform != "win32":
        return None
    dll = ctypes.WinDLL("user32")
    dll.GetAsyncKeyState.argtypes = [ctypes.c_int]
    dll.GetAsyncKeyState.restype = ctypes.c_short
    return dll


class Controllers:
    def __init__(self, key: str = DEFAULT_ACT_MENU_KEY) -> None:
        self._xinput = _load_xinput()
        self._winmm = _load_winmm()
        self._user32 = _load_user32()
        self.key = key_code(key)

    @property
    def available(self) -> bool:
        return self._xinput is not None or self._winmm is not None or self._user32 is not None

    def key_held(self) -> bool:
        return bool(self._user32 is not None and self.key is not None
                    and self._user32.GetAsyncKeyState(self.key) & 0x8000)

    def buttons(self) -> int:
        """The XInput buttons held on any connected controller, OR-ed together."""
        held = 0
        if self._xinput is None:
            return held
        state = XInputState()
        for index in range(MAX_CONTROLLERS):
            if self._xinput.XInputGetState(index, ctypes.byref(state)) == ERROR_SUCCESS:
                held |= state.Gamepad.wButtons
        return held

    def joystick_buttons(self) -> int:
        """The winmm buttons held on any joystick, OR-ed together (bit n = button n + 1)."""
        held = 0
        if self._winmm is None:
            return held
        info = JoyInfoEx()
        for index in range(MAX_JOYSTICKS):
            info.dwSize, info.dwFlags = ctypes.sizeof(info), JOY_RETURNBUTTONS
            if self._winmm.joyGetPosEx(index, ctypes.byref(info)) == ERROR_SUCCESS:
                held |= info.dwButtons
        return held

    def act_menu_held(self) -> bool:
        return bool(self.key_held() or self.buttons() & XINPUT_GAMEPAD_RIGHT_THUMB
                    or self.joystick_buttons() >> (WINMM_R3_BUTTON - 1) & 1)
