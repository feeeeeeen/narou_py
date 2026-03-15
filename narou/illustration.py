import logging
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

from narou.http_utils import fetch_with_retry
from narou.narou_api import USER_AGENT

ILLUST_DIR = "挿絵"
NAROU_ILLUST_URL = "http://{}.mitemin.net/userpageimage/viewimage/icode/{}/"
NAROU_ILLUST_TAG_RE = re.compile(r"[ 　\t]*?<(i[0-9]+)\|([0-9]+)>\n?", re.MULTILINE)

MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/webp": "webp",
}


class IllustrationManager:
    """挿絵のダウンロードと管理"""

    def __init__(self, archive_path: Path, session: requests.Session | None = None):
        self.archive_path = archive_path
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.illust_dir = archive_path / ILLUST_DIR

    def scan_and_download(self, text: str) -> str:
        """テキスト中の挿絵タグを検出し、画像をDLして注記を更新する"""
        # ［＃挿絵（URL）入る］ パターン
        def _replace_illust(m: re.Match) -> str:
            url = m.group(1)
            if url.startswith(("http://", "https://")):
                path = self.download_image(url)
                if path:
                    rel = path.relative_to(self.archive_path)
                    return f"［＃挿絵（{rel}）入る］"
                return ""
            return m.group(0)

        text = re.sub(r"［＃挿絵（(.+?)）入る］", _replace_illust, text)

        # なろう固有の挿絵タグ <iXXXX|YYYY>
        def _replace_narou_illust(m: re.Match) -> str:
            id1, id2 = m.group(1), m.group(2)
            url = NAROU_ILLUST_URL.format(id2, id1)
            path = self.download_image(url, basename=f"{id1},{id2}")
            if path:
                rel = path.relative_to(self.archive_path)
                return f"［＃挿絵（{rel}）入る］"
            return ""

        text = NAROU_ILLUST_TAG_RE.sub(_replace_narou_illust, text)
        return text

    def download_image(self, url: str, basename: str | None = None) -> Path | None:
        """画像URLからDLして保存。既存ファイルがあればそれを返す。"""
        if basename is None:
            basename = Path(url.split("?")[0].split("#")[0]).stem

        # 既存ファイル検索
        existing = self._search_image(basename)
        if existing:
            return existing

        try:
            resp = fetch_with_retry(self.session, url)
            content_type = resp.headers.get("content-type", "").split(";")[0].strip()
            ext = MIME_TO_EXT.get(content_type)
            if not ext:
                return None

            self.illust_dir.mkdir(parents=True, exist_ok=True)
            save_path = self.illust_dir / f"{basename}.{ext}"
            save_path.write_bytes(resp.content)
            return save_path
        except (requests.RequestException, OSError) as e:
            logger.warning("挿絵のダウンロード失敗: %s - %s", url, e)
            return None

    def _search_image(self, basename: str) -> Path | None:
        """既にDL済みの画像を検索"""
        if not self.illust_dir.exists():
            return None
        for ext in MIME_TO_EXT.values():
            path = self.illust_dir / f"{basename}.{ext}"
            if path.exists():
                return path
        return None
