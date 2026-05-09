import re
import tempfile
from pathlib import Path

from narou.database import Database
from narou.downloader import NovelDownloader
from narou.site_setting import SiteSetting, _ruby_regex_to_python

WEBNOVEL_DIR = Path(__file__).parent.parent / "webnovel"


def test_resolve_target_url():
    """URLからサイト設定を解決できること"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)
    setting = dl._resolve_target("https://ncode.syosetu.com/n1234ab/")
    assert setting is not None
    assert setting.matched("ncode") == "n1234ab"
    db.close()


def test_resolve_target_ncode():
    """Nコードからサイト設定を解決できること"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)
    setting = dl._resolve_target("n9999zz")
    assert setting is not None
    assert setting["ncode"] == "n9999zz"
    db.close()


def test_resolve_target_uppercase_ncode():
    """大文字Nコードが小文字に正規化されること"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)
    setting = dl._resolve_target("N1234AB")
    assert setting is not None
    assert setting["ncode"] == "n1234ab"
    db.close()


def test_extract_elements_from_narou_html():
    """なろうHTML本文からテキストを抽出できること"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)

    html = '''
    <div class="js-novel-text p-novel__text p-novel__text--preface">
    <p id="Lp1">前書きテスト</p>
    </div>
    <div class="js-novel-text p-novel__text">
    <p id="L1">本文1行目</p>
    <p id="L2">本文2行目</p>
    </div>
    <div class="js-novel-text p-novel__text p-novel__text--afterword">
    <p id="La1">後書きテスト</p>
    </div>
    '''
    element = dl._extract_elements_from_narou_html(html)
    assert "前書きテスト" in element["introduction"]
    assert "本文1行目" in element["body"]
    assert "本文2行目" in element["body"]
    assert "後書きテスト" in element["postscript"]
    db.close()


def test_html_to_text_ruby():
    """HTML内のルビがテキスト形式に変換されること"""
    html = '<ruby>漢字<rt>かんじ</rt></ruby>'
    result = NovelDownloader._html_to_text(html)
    assert result == "｜漢字《かんじ》"


def test_html_to_text_br():
    html = '1行目<br />2行目<br>3行目'
    result = NovelDownloader._html_to_text(html)
    assert "1行目\n2行目\n3行目" == result


def test_html_to_text_entities():
    html = '&lt;tag&gt; &amp; &quot;quoted&quot;'
    result = NovelDownloader._html_to_text(html)
    assert result == '<tag> & "quoted"'


def test_parse_subtitles():
    """目次パース（実際のYAML定義を使用）"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)
    setting = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")

    toc_html = '''
    <div class="p-eplist__chapter-title">第一章</div>
    <div class="p-eplist__sublist">
    <a href="/n1234ab/1/" class="p-eplist__subtitle">
    第1話 始まり
    </a>
    <div class="p-eplist__update">
    2025/01/01 12:00
    </div>
    </div>
    <div class="p-eplist__sublist">
    <a href="/n1234ab/2/" class="p-eplist__subtitle">
    第2話 展開
    </a>
    <div class="p-eplist__update">
    2025/01/02 12:00
    </div>
    </div>
    '''
    subtitles = dl._parse_subtitles(toc_html, setting)
    assert len(subtitles) == 2
    assert subtitles[0]["index"] == "1"
    assert subtitles[0]["subtitle"] == "第1話 始まり"
    assert subtitles[0]["chapter"] == "第一章"
    assert subtitles[1]["index"] == "2"
    assert subtitles[1]["subtitle"] == "第2話 展開"
    db.close()


def test_update_body_check():
    """差分チェック: 更新があった話のみが返ること"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)

    old = [
        {"index": "1", "subtitle": "第1話", "chapter": "", "subdate": "2025/01/01", "subupdate": ""},
        {"index": "2", "subtitle": "第2話", "chapter": "", "subdate": "2025/01/02", "subupdate": ""},
    ]
    latest = [
        {"index": "1", "subtitle": "第1話", "chapter": "", "subdate": "2025/01/01", "subupdate": ""},
        {"index": "2", "subtitle": "第2話 改", "chapter": "", "subdate": "2025/01/02", "subupdate": ""},  # タイトル変更
        {"index": "3", "subtitle": "第3話", "chapter": "", "subdate": "2025/01/03", "subupdate": ""},     # 新規
    ]
    updates = dl._update_body_check(old, latest)
    assert len(updates) == 2
    assert updates[0]["index"] == "2"  # タイトル変更
    assert updates[1]["index"] == "3"  # 新規
    db.close()


def test_ruby_regex_conversion():
    """Ruby正規表現のnamed groupがPython構文に変換されること"""
    ruby_pattern = r"(?<name>.+?)(?<index>\d+)"
    py_pattern = _ruby_regex_to_python(ruby_pattern)
    assert "(?P<name>" in py_pattern
    assert "(?P<index>" in py_pattern

    # 先読み/後読みは変換されないこと
    assert _ruby_regex_to_python("(?<=foo)") == "(?<=foo)"
    assert _ruby_regex_to_python("(?<!bar)") == "(?<!bar)"


def test_fetch_novel_metadata_returns_none_for_unknown_url():
    """対応していないURLでは fetch_novel_metadata() が None を返すこと"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)
    result = dl.fetch_novel_metadata("https://example.invalid/foo/")
    assert result is None
    dl.close()
    db.close()


def test_close_releases_connections():
    """close() で持続接続キャッシュが解放されること"""
    db = Database(Path(tempfile.mkdtemp()) / "test.db")
    dl = NovelDownloader(db, Path(__file__).parent.parent)

    # 接続キャッシュにダミーを直接登録（実HTTP呼び出しを避けるため）
    class _DummyConn:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    dummy = _DummyConn()
    dl._connections["https://example.test:443"] = dummy

    dl.close()
    assert dummy.closed
    assert dl._connections == {}
    db.close()
