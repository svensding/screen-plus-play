from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DEFAULT_APP_PROFILE, DEFAULT_CONFIG

ANDROID_HOME_PROFILE = {
    **DEFAULT_APP_PROFILE,
    "display_name": "Android Full Screen",
    "description": "Mirror or hand off your active phone screen to a larger display.",
    "pinned": True,
    "last_played": 1,
}


def _fresh_defaults() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    try:
        from .platform_win import detect_host_display_preset
        config["active_display_preset"] = detect_host_display_preset()
    except Exception:
        pass
    return {"config": config, "apps": {"__ANDROID_HOME__": ANDROID_HOME_PROFILE.copy()}}


def _merge_profiles(target: dict[str, Any], old_apps: Any, *, pin: bool = False) -> None:
    if not isinstance(old_apps, dict):
        return
    for package, profile in old_apps.items():
        if package in ("_global", "devices", "apps") or not isinstance(profile, dict):
            continue
        merged = DEFAULT_APP_PROFILE.copy()
        merged.update(profile)
        if pin:
            merged["pinned"] = True
        target[package] = merged


def load_data(data_file: Path | str, legacy_v2_file: Path | str | None = None,
              legacy_v1_file: Path | str | None = None) -> dict[str, Any]:
    path = Path(data_file)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return _fresh_defaults()
        data = _fresh_defaults()
        config = data["config"]
        config.update(raw.get("config", {}) if isinstance(raw, dict) else {})
        apps = raw.get("apps", {}) if isinstance(raw, dict) else {}
        _merge_profiles(data["apps"], apps)
        return data

    data = _fresh_defaults()
    for legacy_path in (legacy_v2_file, legacy_v1_file):
        if legacy_path is None:
            continue
        legacy = Path(legacy_path)
        if not legacy.exists():
            continue
        try:
            old = json.loads(legacy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(old, dict):
            continue
        global_settings = old.get("_global", {})
        if isinstance(global_settings, dict) and global_settings.get("steamgriddb_api_key"):
            data["config"]["steamgriddb_api_key"] = global_settings["steamgriddb_api_key"]
        old_apps = old.get("apps", old)
        _merge_profiles(data["apps"], old_apps, pin=True)
        break
    return data


def save_data(data_file: Path | str, payload: dict[str, Any]) -> None:
    path = Path(data_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)
