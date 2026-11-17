from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable

DEFAULT_DISPLAY_PRESET = "Surface Pro 7 (3:2 • 1368x912)"
WIDE_DISPLAY_PRESET = "TV / Projector 1080p (16:9 • 1920x1080)"


def wait_for_window(title_substring: str, timeout: float = 15.0) -> str | None:
    if not hasattr(ctypes, "windll"):
        return None
    user32 = ctypes.windll.user32
    enum_windows = user32.EnumWindows
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    get_text = user32.GetWindowTextW
    get_length = user32.GetWindowTextLengthW
    is_visible = user32.IsWindowVisible
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        titles: list[str] = []

        def visit(hwnd: int, _param: int) -> bool:
            if is_visible(hwnd):
                length = get_length(hwnd)
                if length:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    get_text(hwnd, buffer, length + 1)
                    if title_substring in buffer.value:
                        titles.append(buffer.value)
            return True

        enum_windows(enum_proc_type(visit), 0)
        if titles:
            return titles[0]
        time.sleep(0.25)
    return None


def detect_host_display_preset() -> str:
    if not hasattr(ctypes, "windll"):
        return DEFAULT_DISPLAY_PRESET
    try:
        user32 = ctypes.windll.user32
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not height or abs(round(width / height, 2) - 1.50) < 0.08:
            return DEFAULT_DISPLAY_PRESET
        return WIDE_DISPLAY_PRESET
    except (AttributeError, OSError):
        return DEFAULT_DISPLAY_PRESET


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", XINPUT_GAMEPAD)]


class JOYINFOEX(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulong) for name in (
        "dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos",
        "dwButtons", "dwButtonNumber", "dwPOV", "dwReserved1", "dwReserved2")]


class GamepadPoller:
    """Windows XInput/WinMM edge-triggered poller; safe to instantiate elsewhere."""
    DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 0x0001, 0x0002, 0x0004, 0x0008
    START, BACK, LB, RB = 0x0010, 0x0020, 0x0100, 0x0200
    A, B, X, Y = 0x1000, 0x2000, 0x4000, 0x8000

    def __init__(self, on_action: Callable[[str], None], poll_interval: float = 0.025):
        self.on_action = on_action
        self.poll_interval = poll_interval
        self.xinput = None
        self.winmm = None
        self.prev_mask = 0
        self.last_nav_time = 0.0
        self.running = False
        self.paused = False
        self._thread: threading.Thread | None = None
        if hasattr(ctypes, "windll"):
            for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
                try:
                    lib = ctypes.windll.LoadLibrary(name)
                    lib.XInputGetState.argtypes = [ctypes.c_ulong, ctypes.POINTER(XINPUT_STATE)]
                    lib.XInputGetState.restype = ctypes.c_ulong
                    self.xinput = lib
                    break
                except (OSError, AttributeError):
                    continue
            try:
                lib = ctypes.windll.winmm
                lib.joyGetPosEx.argtypes = [ctypes.c_uint, ctypes.POINTER(JOYINFOEX)]
                lib.joyGetPosEx.restype = ctypes.c_uint
                self.winmm = lib
            except (OSError, AttributeError):
                pass

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if not paused:
            mask, _, _, _ = self._read_unified_mask()
            self.prev_mask = mask
            self.last_nav_time = time.monotonic() + 0.25

    def _read_unified_mask(self) -> tuple[int, float, float, bool]:
        if self.xinput:
            state = XINPUT_STATE()
            for index in range(4):
                if self.xinput.XInputGetState(index, ctypes.byref(state)) == 0:
                    pad = state.Gamepad
                    return pad.wButtons, pad.sThumbLX / 32768.0, pad.sThumbLY / 32768.0, True
        if self.winmm:
            info = JOYINFOEX()
            info.dwSize = ctypes.sizeof(JOYINFOEX)
            info.dwFlags = 0xFF
            for index in range(4):
                if self.winmm.joyGetPosEx(index, ctypes.byref(info)) == 0:
                    mask, buttons = 0, info.dwButtons
                    for button, bit in ((0x01, self.A), (0x02, self.B), (0x04, self.X), (0x08, self.Y),
                                        (0x10, self.LB), (0x20, self.RB), (0x40, self.BACK), (0x80, self.START)):
                        if buttons & button:
                            mask |= bit
                    pov = info.dwPOV
                    if pov != 65535:
                        if pov in (0, 4500, 31500): mask |= self.DPAD_UP
                        if 4500 <= pov <= 13500: mask |= self.DPAD_RIGHT
                        if 13500 <= pov <= 22500: mask |= self.DPAD_DOWN
                        if 22500 <= pov <= 31500: mask |= self.DPAD_LEFT
                    return mask, (info.dwXpos - 32768.0) / 32768.0, -(info.dwYpos - 32768.0) / 32768.0, True
        return 0, 0.0, 0.0, False

    def _poll_loop(self) -> None:
        while self.running:
            if self.paused:
                time.sleep(0.08)
                continue
            mask, nx, ny, ok = self._read_unified_mask()
            if ok:
                now = time.monotonic()
                if (abs(nx) > 0.52 or abs(ny) > 0.52) and now - self.last_nav_time > 0.19:
                    action = "LEFT" if nx < -0.52 else "RIGHT" if nx > 0.52 else "UP" if ny > 0.52 else "DOWN"
                    self.on_action(action)
                    self.last_nav_time = now
                pressed = mask & ~self.prev_mask
                for bit, action in ((self.DPAD_LEFT, "LEFT"), (self.DPAD_RIGHT, "RIGHT"),
                                    (self.DPAD_UP, "UP"), (self.DPAD_DOWN, "DOWN"), (self.A, "A"),
                                    (self.B, "B"), (self.X, "X"), (self.Y, "Y"), (self.LB, "LB"),
                                    (self.RB, "RB"), (self.START, "START"), (self.BACK, "BACK")):
                    if pressed & bit:
                        self.on_action(action)
                self.prev_mask = mask
            else:
                self.prev_mask = 0
            time.sleep(self.poll_interval)
