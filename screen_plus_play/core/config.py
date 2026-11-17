from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def _which_or_local(executable: str, candidates: tuple[str, ...], base_dir: Path | None = None) -> str:
    """Find an executable via PATH, then common project-local locations."""
    found = shutil.which(executable)
    if found:
        return str(Path(found).resolve())
    root = base_dir or Path(__file__).resolve().parents[2]
    for relative in candidates:
        candidate = root / relative
        if candidate.is_file():
            return str(candidate.resolve())
    return ""


def discover_tool_paths(base_dir: Path | None = None) -> dict[str, str]:
    scrcpy = _which_or_local("scrcpy", ("scrcpy/scrcpy.exe", "scrcpy/scrcpy", "tools/scrcpy/scrcpy.exe"), base_dir)
    shaderglass = _which_or_local(
        "ShaderGlass", ("ShaderGlass/ShaderGlass.exe", "tools/ShaderGlass/ShaderGlass.exe"), base_dir
    )
    sgp_candidates = ("ShaderGlass/OpenMVonAndroid.sgp", "tools/ShaderGlass/OpenMVonAndroid.sgp")
    root = base_dir or Path(__file__).resolve().parents[2]
    sgp = next((str((root / p).resolve()) for p in sgp_candidates if (root / p).is_file()), "")
    return {
        "scrcpy_dir": str(Path(scrcpy).parent) if scrcpy else "",
        "shaderglass_exe": shaderglass,
        "default_sgp": sgp,
    }


DEFAULT_CONFIG: dict[str, Any] = {
    **discover_tool_paths(),
    "wifi_target": "",
    "steamgriddb_api_key": "",
    "active_display_preset": "Surface Pro 7 (3:2 • 1368x912)",
    "follow_display_preset": True,
    "default_turn_screen_off": False,
    "default_power_off_on_close": False,
    "default_render_driver": "auto",
    "borderless_mode": True,
    "library_layout": "poster_wall",
}

DISPLAY_PRESETS: dict[str, dict[str, str]] = {
    "Surface Pro 7 (3:2 • 1368x912)": {"resolution": "1368x912", "dpi": "160"},
    "Surface Pro 7 Sharp (3:2 • 1824x1216)": {"resolution": "1824x1216", "dpi": "200"},
    "TV / Projector 1080p (16:9 • 1920x1080)": {"resolution": "1920x1080", "dpi": "240"},
    "TV / Projector 720p Perf (16:9 • 1280x720)": {"resolution": "1280x720", "dpi": "160"},
    "Retro 4:3 CRT (1280x960)": {"resolution": "1280x960", "dpi": "160"},
}

DEFAULT_APP_PROFILE: dict[str, Any] = {
    "display_name": "", "description": "", "github_info": "", "github_url": "",
    "pinned": False, "last_played": 0, "resolution": "1368x912", "dpi": "160",
    "fps": "40", "usb_bitrate": "16M", "wifi_bitrate": "10M",
    "input_mode": "uhid_kb_mouse", "encoder": "auto", "video_codec": "h264",
    "audio_mode": "auto", "turn_screen_off": False, "stay_awake": True,
    "no_vd_decorations": True, "no_vd_destroy": True, "auto_close_on_exit": True,
    "custom_args": "", "use_shaderglass": False, "sgp_path": DEFAULT_CONFIG["default_sgp"],
    "sg_fullscreen": True, "sg_autoclose": True, "sgdb_game_id": None,
}
