from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


@dataclass
class AppProfile:
    display_name: str = ""
    description: str = ""
    github_info: str = ""
    github_url: str = ""
    pinned: bool = False
    last_played: int = 0
    resolution: str = "1368x912"
    dpi: str = "160"
    fps: str = "40"
    usb_bitrate: str = "16M"
    wifi_bitrate: str = "10M"
    input_mode: str = "uhid_kb_mouse"
    encoder: str = "auto"
    video_codec: str = "h264"
    audio_mode: str = "auto"
    turn_screen_off: bool = False
    stay_awake: bool = True
    no_vd_decorations: bool = True
    no_vd_destroy: bool = True
    auto_close_on_exit: bool = True
    custom_args: str = ""
    use_shaderglass: bool = False
    sgp_path: str = ""
    sg_fullscreen: bool = True
    sg_autoclose: bool = True
    sgdb_game_id: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppProfile":
        accepted = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in accepted})

    def to_dict(self) -> dict[str, Any]:
        return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass
class DeviceInfo:
    serial: str = "unknown"
    model: str = "No Device"
    soc: str = ""
    soc_vendor: str = "generic"
    recommended_encoder: str = "auto"
    recommended_input: str = "uhid_kb_mouse"
    is_handheld: bool = False


@dataclass(frozen=True)
class MetadataResult:
    title: str = ""
    description: str = ""
    github_info: str = ""
    github_url: str = ""
    art_cache: tuple[tuple[str, str], ...] = ()
    sgdb_game_id: int | None = None
