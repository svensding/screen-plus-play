from screen_plus_play.core.launcher import build_scrcpy_cmd, resolve_encoder, sanitize_custom_scrcpy_args


def test_sanitize_custom_scrcpy_args_rewrites_orientation() -> None:
    args = sanitize_custom_scrcpy_args("--orientation=90 --crop=1280:720:0:0")
    assert "--display-orientation=90" in args
    assert "--crop=1280:720:0:0" in args


def test_build_scrcpy_cmd_for_android_home() -> None:
    cmd = build_scrcpy_cmd(scrcpy_exe="scrcpy", adb_flag="-d", app_name="Home",
        profile={"video_codec": "h264", "encoder": "auto", "fps": "60", "custom_args": ""},
        config={"default_render_driver": "auto"}, source_mode="android_home",
        resolution="1920x1080", dpi="240", bitrate="16M")
    assert "--max-size=1920" in cmd
    assert "--video-codec=h264" in cmd


def test_auto_encoder_uses_soc_vendor() -> None:
    assert resolve_encoder("auto", "h264", "mtk") == "c2.mtk.avc.encoder"
    assert resolve_encoder("auto", "h265", "qti") == "c2.qti.hevc.encoder"


def test_wifi_auto_audio_uses_opus() -> None:
    cmd = build_scrcpy_cmd(scrcpy_exe="scrcpy", adb_flag="-e", app_name="Game",
        profile={"audio_mode": "auto", "video_codec": "h264", "encoder": "auto"},
        config={}, source_mode="com.example.game", resolution="1368x912", dpi="160", bitrate="10M")
    assert "--audio-codec=opus" in cmd
    assert "--audio-bit-rate=128K" in cmd
    assert "--audio-buffer=50" in cmd
