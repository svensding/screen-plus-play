from pathlib import Path

from screen_plus_play.core.data_store import load_data, save_data


def test_load_data_creates_defaults_for_missing_file(tmp_path: Path) -> None:
    data = load_data(tmp_path / "launcher_data.json")
    assert "config" in data and "apps" in data
    assert "__ANDROID_HOME__" in data["apps"]


def test_save_data_round_trips(tmp_path: Path) -> None:
    payload = {"config": {"library_layout": "detail_list"}, "apps": {"test.pkg": {"display_name": "Game"}}}
    target = tmp_path / "launcher_data.json"
    save_data(target, payload)
    loaded = load_data(target)
    assert loaded["config"]["library_layout"] == "detail_list"
    assert loaded["apps"]["test.pkg"]["display_name"] == "Game"


def test_load_data_migrates_v2_and_preserves_global_key(tmp_path: Path) -> None:
    current, v2, v1 = tmp_path / "launcher_data.json", tmp_path / "profiles_v2.json", tmp_path / "profiles.json"
    v2.write_text('{"_global":{"steamgriddb_api_key":"secret"},"apps":{"game.pkg":{"display_name":"Game"}}}', encoding="utf-8")
    v1.write_text('{"old.pkg":{"display_name":"Older"}}', encoding="utf-8")
    data = load_data(current, v2, v1)
    assert data["config"]["steamgriddb_api_key"] == "secret"
    assert data["apps"]["game.pkg"]["display_name"] == "Game"
    assert data["apps"]["game.pkg"]["pinned"] is True
    assert "old.pkg" not in data["apps"]
