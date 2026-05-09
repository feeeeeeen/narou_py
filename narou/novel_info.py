import logging
import re
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

from narou.helpers import pretreatment_source
from narou.html_to_aozora import html_to_aozora
from narou.http_utils import USER_AGENT, fetch_with_retry
from narou.site_setting import SiteSetting


class NovelInfo:
    """小説情報ページから直接メタデータを取得する（APIフォールバック用）"""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._cache: dict[str, dict | None] = {}

    def load(self, setting: SiteSetting) -> dict | None:
        """小説情報ページをHTMLパースしてメタデータを取得する"""
        info_url = setting["novel_info_url"]
        if not info_url:
            return None

        # キャッシュチェック（同一URLは再取得しない）
        if info_url in self._cache:
            return self._cache[info_url]

        cookie = setting.get_raw("cookie") or ""
        headers = {}
        if cookie:
            headers["Cookie"] = cookie

        try:
            resp = fetch_with_retry(self.session, info_url, headers=headers)
            source = pretreatment_source(resp.text)
        except requests.RequestException as e:
            logger.warning("小説情報ページの取得に失敗: %s - %s", info_url, e)
            return None

        # YAML定義の正規表現でHTMLパース
        of_keys = ["t", "nt", "ga", "s", "gf", "nu", "gl", "w"]
        setting.multi_match(source, *of_keys)

        result: dict = {}
        result["title"] = setting.matched("title") or ""

        # novel_type 判定
        novel_type_str = setting.matched("novel_type") or ""
        novel_type_map = setting.get_raw("novel_type_string") or {}
        novel_status = novel_type_map.get(novel_type_str, 1)
        result["end"] = novel_status == 3
        if novel_status in (1, 3):
            result["novel_type"] = 1  # 連載
        elif novel_status == 2:
            ga = setting.matched("general_all_no")
            result["novel_type"] = 1 if ga and int(ga) > 1 else 2  # 短編
        else:
            result["novel_type"] = 1

        story = setting.matched("story")
        result["story"] = html_to_aozora(story) if story else ""
        result["writer"] = setting.matched("writer") or ""

        # 日付フィールド
        for key in ("general_firstup", "novelupdated_at", "general_lastup"):
            date_str = setting.matched(key)
            result[key] = self._parse_date(date_str) if date_str else None

        self._cache[info_url] = result
        return result

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """日付文字列をパースする（括弧内の情報を除去し、年月日時分秒を変換）"""
        # 括弧内を削除
        cleaned = re.sub(r"[（(].+?[）)]", "", date_str)
        # 年月日時分秒 → スラッシュ・コロンに置換
        cleaned = cleaned.translate(str.maketrans("年月日時分秒", "///:::"))
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned.strip(), fmt)
            except ValueError:
                continue
        return None
