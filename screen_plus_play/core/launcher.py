from __future__ import annotations

import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .config import DISPLAY_PRESETS
from .platform_win import wait_for_window


def sanitize_custom_scrcpy_args(raw_args: str) -> list[str]:
    if not raw_args.strip():
        return []
    tokens = shlex.split(raw_args.strip(), posix=False)
    cleaned = []
    for token in tokens:
        if token.startswith("-") and not token.startswith("--") and len(token) > 2 and token[1].isalpha():
            token = "-" + token
        if token.startswith("--orientation="):
            token = token.replace("--orientation=", "--display-orientation=", 1)
        cleaned.append(token)
    return cleaned


def resolve_encoder(requested_encoder: str, video_codec: str, soc_vendor: str = "generic") -> str | None:
    if requested_encoder == "auto":
        codec = "hevc" if video_codec == "h265" else "avc" if video_codec == "h264" else None
        if codec and soc_vendor == "mtk":
            return f"c2.mtk.{codec}.encoder"
        if codec and soc_vendor == "qti":
            return f"c2.qti.{codec}.encoder"
        return None
    if video_codec == "h265" and ".avc." in requested_encoder:
        return requested_encoder.replace(".avc.", ".hevc.")
    if video_codec == "h264" and ".hevc." in requested_encoder:
        return requested_encoder.replace(".hevc.", ".avc.")
    return requested_encoder


def build_scrcpy_cmd(*, scrcpy_exe: str, adb_flag: str, app_name: str,
                     profile: dict[str, Any], config: dict[str, Any], source_mode: str,
                     resolution: str, dpi: str, bitrate: str, soc_vendor: str = "generic") -> list[str]:
    codec = profile.get("video_codec", "h264")
    encoder = resolve_encoder(profile.get("encoder", "auto"), codec, soc_vendor)
    audio = profile.get("audio_mode", "auto")
    if audio == "disabled":
        audio_opts = ["--no-audio"]
    elif audio == "raw":
        audio_opts = ["--audio-codec=raw", "--audio-buffer=35"]
    elif audio == "opus" or (audio == "auto" and adb_flag == "-e"):
        audio_opts = ["--audio-codec=opus", "--audio-bit-rate=128K", "--audio-buffer=50"]
    else:
        audio_opts = ["--audio-codec=raw", "--audio-buffer=35"]
    input_mode = profile.get("input_mode", "uhid_kb_mouse")
    input_opts = ["--mouse=uhid", "--keyboard=uhid"] if input_mode == "uhid_kb_mouse" else ["--gamepad=uhid"] if input_mode == "uhid_gamepad" else []
    cmd = [scrcpy_exe, adb_flag, f"--window-title=ScreenPlusPlay_{app_name}", f"--video-codec={codec}",
           f"--max-fps={profile.get('fps', '40')}", f"-b{bitrate}",
           "--video-codec-options=i-frame-interval=1,bitrate-mode=2", *audio_opts, *input_opts]
    if source_mode == "android_home":
        cmd.append(f"--max-size={max(map(int, resolution.split('x')))}")
    else:
        cmd.extend((f"--new-display={resolution}/{dpi}", f"--start-app={source_mode}"))
        if profile.get("no_vd_decorations", True): cmd.append("--no-vd-system-decorations")
        if profile.get("no_vd_destroy", True): cmd.append("--no-vd-destroy-content")
    if encoder: cmd.append(f"--video-encoder={encoder}")
    driver = config.get("default_render_driver", "auto")
    if driver and driver != "auto": cmd.append(f"--render-driver={driver}")
    if profile.get("stay_awake", True): cmd.append("--stay-awake")
    if profile.get("turn_screen_off", False) or config.get("default_turn_screen_off", False): cmd.append("--turn-screen-off")
    if config.get("default_power_off_on_close", False): cmd.append("--power-off-on-close")
    cmd.extend(sanitize_custom_scrcpy_args(profile.get("custom_args", "")))
    return cmd


class SessionRunner:
    """Runs one scrcpy session on a worker thread and reports lifecycle events via callbacks."""
    def __init__(self, android, scrcpy_dir: str, shaderglass_exe: str = "", default_sgp: str = ""):
        self.android = android
        self.scrcpy_dir = scrcpy_dir
        self.shaderglass_exe = shaderglass_exe
        self.default_sgp = default_sgp
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self, command: list[str], *, package: str, app_name: str, profile: dict[str, Any],
              on_handoff_ready: Callable[[], None] | None = None,
              on_session_end: Callable[[], None] | None = None,
              on_status: Callable[[str], None] | None = None) -> threading.Thread:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("A stream session is already running")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(command, package, app_name, profile,
            on_handoff_ready, on_session_end, on_status), daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _notify(callback, *args) -> None:
        if callback:
            try: callback(*args)
            except Exception: pass

    def _run(self, command, package, app_name, profile, on_handoff_ready, on_session_end, on_status) -> None:
        scrcpy_proc = sg_proc = None
        title = next((arg.split("=", 1)[1] for arg in command if arg.startswith("--window-title=")), "")
        try:
            self._notify(on_status, f"Starting stream for {app_name}...")
            scrcpy_proc = subprocess.Popen(command, cwd=self.scrcpy_dir)
            actual_title = wait_for_window(title, timeout=15) if title else None
            if actual_title and profile.get("use_shaderglass") and self.shaderglass_exe and Path(self.shaderglass_exe).exists():
                sg_command = [self.shaderglass_exe, "-f", "-i", actual_title, "-ac"]
                sgp = profile.get("sgp_path") or self.default_sgp
                if sgp and Path(sgp).exists(): sg_command.append(sgp)
                sg_proc = subprocess.Popen(sg_command)
            self._notify(on_handoff_ready)
            if package == "__ANDROID_HOME__" or not profile.get("auto_close_on_exit", True):
                while scrcpy_proc.poll() is None and not self._stop.wait(0.25):
                    pass
            else:
                started = False
                for _ in range(25):
                    if scrcpy_proc.poll() is not None or self._stop.wait(1): break
                    if self.android.is_app_active(package):
                        started = True
                        break
                if started:
                    misses = 0
                    while scrcpy_proc.poll() is None and not self._stop.is_set():
                        if self.android.is_app_active(package): misses = 0
                        else:
                            misses += 1
                            if misses >= 2:
                                scrcpy_proc.terminate()
                                break
                        self._stop.wait(2)
                elif scrcpy_proc.poll() is None:
                    scrcpy_proc.wait()
            if self._stop.is_set() and scrcpy_proc.poll() is None:
                scrcpy_proc.terminate()
            self._notify(on_status, f"Stream ended for {app_name}.")
        except Exception as exc:
            self._notify(on_status, f"Stream failed: {exc}")
        finally:
            for process in (sg_proc, scrcpy_proc):
                if process and process.poll() is None:
                    try: process.terminate()
                    except OSError: pass
            self._notify(on_session_end)
