"""HTTP共通ユーティリティ"""
import logging
import time

import requests

logger = logging.getLogger(__name__)

# プロジェクト全体で共有する User-Agent。
# narou.rb 同様に Chrome 系 UA を装う必要があり、syosetu.com は UA 無しでは 403 を返す。
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = 3,
    headers: dict | None = None,
    timeout: int = 30,
) -> requests.Response:
    """503リトライ付きHTTP GET

    Args:
        session: requestsセッション
        url: 取得先URL
        max_retries: 最大リトライ回数
        headers: 追加ヘッダ
        timeout: タイムアウト（秒）

    Returns:
        レスポンスオブジェクト

    Raises:
        requests.RequestException: リトライ上限超過時
    """
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, headers=headers or {}, timeout=timeout)
            if resp.status_code == 503 and attempt < max_retries:
                wait = 2 ** attempt
                logger.info("503応答、%d秒後にリトライ (%d/%d): %s", wait, attempt + 1, max_retries, url)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise
            wait = 2 ** attempt
            logger.warning("リクエスト失敗、%d秒後にリトライ (%d/%d): %s - %s", wait, attempt + 1, max_retries, url, e)
            time.sleep(wait)
    # 到達不能: 最終 attempt では status==503 でも raise_for_status() が HTTPError を投げ
    # except 節で再 raise されるため。型チェッカ向けに RuntimeError を保険として置く。
    raise RuntimeError(f"fetch_with_retry: unreachable ({url})")  # pragma: no cover
