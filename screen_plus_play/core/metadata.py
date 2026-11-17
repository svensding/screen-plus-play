from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image
from io import BytesIO

from .models import MetadataResult


class GameMetadataCrawler:
    SGDB_BASE = "https://www.steamgriddb.com/api/v2"
    WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
    WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    GITHUB_SEARCH = "https://api.github.com/search/repositories"

    def __init__(self, api_key: str = "", session: requests.Session | None = None, cache_dir: Path | str = "art_cache"):
        self.api_key = api_key.strip()
        self.session = session or requests.Session()
        self.cache_dir = Path(cache_dir)

    def fetch_flavor_text(self, title: str) -> str:
        if not title or title.lower() in ("android full screen", "resume phone screen"):
            return "Mirror or hand off your active Android launcher and apps straight onto a larger display."
        headers = {"User-Agent": "ScreenPlusPlayLauncher/1.0"}
        for query in (f"{title} video game", title):
            try:
                response = self.session.get(self.WIKI_SEARCH, params={"action": "opensearch", "search": query,
                    "limit": 1, "namespace": 0, "format": "json"}, headers=headers, timeout=5)
                response.raise_for_status()
                data = response.json()
                if len(data) < 2 or not data[1]:
                    continue
                summary = self.session.get(f"{self.WIKI_SUMMARY}{quote(data[1][0])}", headers=headers, timeout=5)
                summary.raise_for_status()
                extract = summary.json().get("extract", "").strip()
                if extract:
                    snippet = " ".join(re.split(r"(?<=[.!?])\s+", extract)[:2]).strip()
                    return snippet[:217].rsplit(" ", 1)[0] + "..." if len(snippet) > 220 else snippet
            except (requests.RequestException, ValueError, KeyError, TypeError):
                continue
        return ""

    def fetch_github_info(self, package: str, title: str = "") -> tuple[str, str]:
        if not package or package == "__ANDROID_HOME__":
            return "", ""
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ScreenPlusPlayLauncher/1.0"}
        parts = [part for part in package.split(".") if part not in ("com", "org", "net", "io", "xyz", "app", "android", "foss")]
        slug = parts[-1] if parts else title
        queries = [f'"{package}" in:readme,description,name']
        if slug and len(slug) >= 4:
            queries.append(f"{slug} android in:name,description")
        for query in queries:
            try:
                response = self.session.get(self.GITHUB_SEARCH, params={"q": query, "sort": "stars", "order": "desc", "per_page": 1}, headers=headers, timeout=6)
                if response.status_code != 200:
                    continue
                items = response.json().get("items", [])
                if not items:
                    continue
                repo = items[0]
                full_name = repo.get("full_name", "")
                desc = (repo.get("description") or "").strip()
                haystack = f"{full_name} {desc}".lower()
                if package.lower() not in haystack and not (slug and slug.lower() in haystack):
                    continue
                stars = int(repo.get("stargazers_count", 0))
                license_name = (repo.get("license") or {}).get("spdx_id") or "OSS"
                stars_text = f"{stars / 1000:.1f}k" if stars >= 1000 else str(stars)
                info = f"GitHub: {full_name} (★ {stars_text} • {license_name})"
                if desc:
                    info += f" — {desc[:117].rsplit(' ', 1)[0]}{'...' if len(desc) > 120 else ''}"
                return info, repo.get("html_url", "")
            except (requests.RequestException, ValueError, TypeError):
                continue
        return "", ""

    def search_sgdb(self, query: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None
        try:
            response = self.session.get(f"{self.SGDB_BASE}/search/autocomplete/{quote(query)}",
                headers={"Authorization": f"Bearer {self.api_key}"}, timeout=7)
            response.raise_for_status()
            data = response.json()
            return data["data"][0] if data.get("success") and data.get("data") else None
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    def fetch_artwork(self, package: str, game_id: int) -> dict[str, str]:
        if not self.api_key or not game_id:
            return {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        outputs: dict[str, str] = {}
        for kind, endpoint in (("poster", "grids"), ("hero", "heroes"), ("sgdb_icon", "icons")):
            try:
                response = self.session.get(f"{self.SGDB_BASE}/{endpoint}/game/{game_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"}, timeout=8)
                response.raise_for_status()
                data = response.json()
                if not data.get("success") or not data.get("data"):
                    continue
                image_response = self.session.get(data["data"][0]["url"], timeout=12)
                image_response.raise_for_status()
                output = self.cache_dir / f"{package}_{kind}.png"
                Image.open(BytesIO(image_response.content)).convert("RGBA").save(output, "PNG")
                outputs[kind] = str(output)
            except (requests.RequestException, ValueError, KeyError, OSError):
                continue
        return outputs

    def fetch_metadata(self, package: str, title: str) -> MetadataResult:
        description = self.fetch_flavor_text(title)
        github_info, github_url = self.fetch_github_info(package, title)
        artwork: dict[str, str] = {}
        game_id = None
        game = self.search_sgdb(title)
        if game:
            try:
                game_id = int(game["id"])
                artwork = self.fetch_artwork(package, game_id)
            except (KeyError, TypeError, ValueError):
                game_id = None
        return MetadataResult(title=title, description=description, github_info=github_info,
                              github_url=github_url, art_cache=tuple(artwork.items()), sgdb_game_id=game_id)
