from __future__ import annotations

import re
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from .models import DeviceInfo


class AndroidManager:
    def __init__(self, get_cfg, cache_dir: Path | str):
        self.get_cfg = get_cfg
        self.cache_dir = Path(cache_dir)
        self.conn_flag: str | None = None
        self.conn_type = "Disconnected"
        self.device_info = DeviceInfo()

    @property
    def scrcpy_exe(self) -> str:
        return str(Path(self.get_cfg("scrcpy_dir")) / ("scrcpy.exe" if __import__("os").name == "nt" else "scrcpy"))

    @property
    def adb_exe(self) -> str:
        return str(Path(self.get_cfg("scrcpy_dir")) / ("adb.exe" if __import__("os").name == "nt" else "adb"))

    def run_cmd(self, args: list[str], timeout: float = 15) -> subprocess.CompletedProcess[str]:
        kwargs: dict[str, Any] = {}
        if __import__("os").name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startup
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, **kwargs)

    def get_prop(self, prop_name: str) -> str:
        if not self.conn_flag:
            return ""
        result = self.run_cmd([self.adb_exe, self.conn_flag, "shell", "getprop", prop_name], timeout=4)
        return result.stdout.strip()

    def detect_connection(self, preferred_mode: str = "auto") -> bool:
        if not Path(self.adb_exe).exists():
            self.conn_flag, self.conn_type = None, "ADB Path Missing"
            return False
        if preferred_mode in ("auto", "usb"):
            result = self.run_cmd([self.adb_exe, "-d", "get-state"], timeout=4)
            if result.returncode == 0 and "device" in result.stdout:
                self.conn_flag, self.conn_type = "-d", "USB"
                self._identify_device()
                return True
        if preferred_mode in ("auto", "wifi"):
            target = self.get_cfg("wifi_target").strip()
            if target:
                self.run_cmd([self.adb_exe, "connect", target], timeout=4)
            result = self.run_cmd([self.adb_exe, "-e", "get-state"], timeout=4)
            if result.returncode == 0 and "device" in result.stdout:
                self.conn_flag, self.conn_type = "-e", "Wi-Fi"
                self._identify_device()
                return True
        self.conn_flag, self.conn_type = None, "Disconnected"
        self.device_info = DeviceInfo()
        return False

    def enable_tcpip_from_usb(self) -> str | None:
        result = self.run_cmd([self.adb_exe, "-d", "tcpip", "5555"], timeout=8)
        if result.returncode:
            return None
        import time
        time.sleep(0.8)
        ip_result = self.run_cmd([self.adb_exe, "-d", "shell", "ip", "route"], timeout=5)
        match = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", ip_result.stdout)
        return f"{match.group(1)}:5555" if match else None

    def _identify_device(self) -> None:
        serial = self.get_prop("ro.serialno") or "default_device"
        market_name = self.get_prop("ro.product.marketname")
        model = market_name or self.get_prop("ro.product.model") or "Android Device"
        brand = self.get_prop("ro.product.brand").lower()
        platform = self.get_prop("ro.board.platform").lower()
        hardware = self.get_prop("ro.hardware").lower()
        handheld = any(token in (model + brand).lower() for token in ("retroid", "odin", "ayn", "anbernic", "rg"))
        if "mt" in platform or "mt" in hardware:
            vendor, encoder = "mtk", "c2.mtk.avc.encoder"
        elif any(token in platform for token in ("kona", "sm", "msmnile", "lahaina", "taro", "kalama", "qcom")):
            vendor, encoder = "qti", "c2.qti.avc.encoder"
        else:
            vendor, encoder = "generic", "auto"
        self.device_info = DeviceInfo(
            serial=re.sub(r"[^a-zA-Z0-9_-]", "_", serial), model=model, soc=platform,
            soc_vendor=vendor, recommended_encoder=encoder,
            recommended_input="uhid_gamepad" if handheld else "uhid_kb_mouse", is_handheld=handheld,
        )

    def resolve_encoder(self, requested_encoder: str, video_codec: str) -> str | None:
        from .launcher import resolve_encoder
        return resolve_encoder(requested_encoder, video_codec, self.device_info.soc_vendor)

    def is_app_active(self, package: str) -> bool:
        if not self.conn_flag:
            return False
        pid = self.run_cmd([self.adb_exe, self.conn_flag, "shell", "pidof", package], timeout=4)
        if not pid.stdout.strip():
            return False
        result = self.run_cmd([self.adb_exe, self.conn_flag, "shell", "dumpsys", "activity", "activities"], timeout=5)
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.splitlines():
                if package in line and any(s in line for s in ("ResumedActivity", "topResumedActivity", "visible=true", "mResumed=true")):
                    return True
            if "ResumedActivity" in result.stdout or "topResumedActivity" in result.stdout:
                return False
        return True

    def fetch_all_device_apps(self) -> list[dict[str, str]]:
        if not self.conn_flag:
            return []
        result = self.run_cmd([self.scrcpy_exe, self.conn_flag, "--list-apps"], timeout=20)
        pattern = re.compile(r"^\s*[\*-]\s+(.+?)\s{2,}([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)\s*$")
        apps = []
        for line in result.stdout.splitlines():
            match = pattern.match(line)
            if match:
                name, package = match.group(1).strip(), match.group(2).strip()
                if not package.startswith(("com.android.", "com.google.android.overlay", "com.miui.", "com.xiaomi.")):
                    apps.append({"name": name, "package": package})
        if not apps:
            fallback = self.run_cmd([self.adb_exe, self.conn_flag, "shell", "pm", "list", "packages", "-3"])
            for line in fallback.stdout.splitlines():
                if line.startswith("package:"):
                    package = line.removeprefix("package:").strip()
                    apps.append({"name": package.split(".")[-1].capitalize(), "package": package})
        return sorted(apps, key=lambda item: item["name"].lower())

    def extract_apk_icon(self, package: str) -> Path | None:
        if package == "__ANDROID_HOME__" or not self.conn_flag:
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        icon = self.cache_dir / f"{package}_icon.png"
        if icon.exists():
            return icon
        result = self.run_cmd([self.adb_exe, self.conn_flag, "shell", "pm", "path", package], timeout=8)
        apk_paths = [line.removeprefix("package:").strip() for line in result.stdout.splitlines() if line.startswith("package:")]
        if not apk_paths:
            return None
        temp = self.cache_dir / f"{package}_temp.apk"
        try:
            pulled = self.run_cmd([self.adb_exe, self.conn_flag, "pull", next((p for p in apk_paths if "base.apk" in p), apk_paths[0]), str(temp)], timeout=25)
            if pulled.returncode or not temp.exists():
                return None
            best_data, best_score = None, -1
            with zipfile.ZipFile(temp) as archive:
                for item in archive.infolist():
                    name = item.filename.lower()
                    if not name.endswith((".png", ".webp")) or not any(k in name for k in ("ic_launcher", "app_icon", "icon")):
                        continue
                    score = item.file_size + (500000 if "xxxhdpi" in name else 300000 if "xxhdpi" in name else 150000 if "xhdpi" in name else 0)
                    if "round" in name: score -= 5000
                    if score > best_score:
                        best_data, best_score = archive.read(item.filename), score
            if best_data:
                Image.open(BytesIO(best_data)).convert("RGBA").save(icon, "PNG")
                return icon
        except (OSError, zipfile.BadZipFile, ValueError):
            return None
        finally:
            temp.unlink(missing_ok=True)
        return None
