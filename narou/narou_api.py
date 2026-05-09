import logging

import requests
import yaml

from narou.http_utils import USER_AGENT
from narou.site_setting import SiteSetting

logger = logging.getLogger(__name__)


class NarouAPI:
    """小説家になろうデベロッパーAPIクライアント"""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def fetch_novel_info(self, setting: SiteSetting) -> dict | None:
        """なろうAPIから小説メタデータを取得する

        Returns:
            メタデータ辞書。取得失敗時はNone。
        """
        api_url = setting["narou_api_url"]
        ncode = setting["ncode"]
        if not api_url or not ncode:
            return None

        of = "t-n-ga-s-gf-nu-gl-w-e"
        url = f"{api_url}?gzip=5&ncode={ncode}&of={of}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("なろうAPI取得失敗: %s - %s", url, e)
            return None

        try:
            result = yaml.safe_load(resp.text)
        except yaml.YAMLError as e:
            logger.error("なろうAPIレスポンスのパースエラー: %s", e)
            return None

        # 防御的型ガード: HTML エラーページなど予期せぬレスポンスで result が
        # list でなかったり要素数不足のケースに備える
        if (not isinstance(result, list)
                or len(result) < 2
                or not isinstance(result[0], dict)
                or not isinstance(result[1], dict)):
            logger.warning("なろうAPIレスポンスが想定形式と異なります: %s", url)
            return None

        if result[0].get("allcount") != 1:
            return None

        data = result[1]
        # フィールド名の正規化
        data["novel_type"] = data.get("noveltype", 1)
        data["writer"] = str(data.get("writer", ""))
        # end: 0 → True（完結）、その他 → False
        stat_end = data.get("end")
        if stat_end is not None:
            data["end"] = stat_end == 0
        return data
