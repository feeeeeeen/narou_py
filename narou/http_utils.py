"""HTTP共通ユーティリティ"""
import logging
import time

import requests

logger = logging.getLogger(__name__)


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
    last_exc: Exception | None = None
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
            last_exc = e
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("リクエスト失敗、%d秒後にリトライ (%d/%d): %s - %s", wait, attempt + 1, max_retries, url, e)
                time.sleep(wait)
            else:
                raise
    raise last_exc  # ここには到達しないはずだが念のため
