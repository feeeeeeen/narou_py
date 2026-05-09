"""narou_api.py の防御的型ガードに関する回帰テスト。"""
from unittest.mock import MagicMock

from narou.narou_api import NarouAPI
from narou.site_setting import SiteSetting


def _make_setting() -> SiteSetting:
    """yaml_path を必須としない最小構成の SiteSetting を作る"""
    s = SiteSetting.__new__(SiteSetting)
    s._yaml = {
        "name": "小説家になろう",
        "narou_api_url": "https://api.syosetu.com/novelapi/api/",
    }
    s._match_values = {}
    s["narou_api_url"] = "https://api.syosetu.com/novelapi/api/"
    s["ncode"] = "n9999zz"
    return s


def _make_session_with_text(text: str) -> MagicMock:
    session = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    session.get = MagicMock(return_value=resp)
    session.headers = {}
    return session


def test_fetch_novel_info_handles_html_error_page():
    """HTMLエラーページなど list 以外を返した場合に None を返す（TypeError 回避）"""
    session = _make_session_with_text("<html><body>Service Unavailable</body></html>")
    api = NarouAPI(session=session)
    setting = _make_setting()
    result = api.fetch_novel_info(setting)
    assert result is None


def test_fetch_novel_info_handles_short_list():
    """要素数が 2 未満のリストでも None を返す"""
    session = _make_session_with_text("[{allcount: 0}]")
    api = NarouAPI(session=session)
    setting = _make_setting()
    result = api.fetch_novel_info(setting)
    assert result is None


def test_fetch_novel_info_handles_non_dict_first_element():
    """先頭要素が dict でない場合も None を返す"""
    session = _make_session_with_text("[1, 2]")
    api = NarouAPI(session=session)
    setting = _make_setting()
    result = api.fetch_novel_info(setting)
    assert result is None


def test_fetch_novel_info_handles_allcount_not_one():
    """allcount が 1 でない場合（小説が見つからない）も None を返す"""
    session = _make_session_with_text("- {allcount: 0}\n- {}\n")
    api = NarouAPI(session=session)
    setting = _make_setting()
    result = api.fetch_novel_info(setting)
    assert result is None


def test_fetch_novel_info_returns_data_when_valid():
    """正常な YAML レスポンスはデータ辞書を返す"""
    yaml_text = (
        "- {allcount: 1}\n"
        "- {title: 'テスト小説', writer: '作者A', noveltype: 1, end: 0}\n"
    )
    session = _make_session_with_text(yaml_text)
    api = NarouAPI(session=session)
    setting = _make_setting()
    result = api.fetch_novel_info(setting)
    assert result is not None
    assert result["title"] == "テスト小説"
    assert result["novel_type"] == 1
    assert result["end"] is True  # end:0 → 完結
