from pathlib import Path

from narou.site_setting import SiteSetting

WEBNOVEL_DIR = Path(__file__).parent.parent / "webnovel"


def test_load_ncode_yaml():
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    assert ss.get_raw("name") == "小説家になろう"
    assert ss.get_raw("scheme") == "https"
    assert ss.get_raw("domain") == "ncode.syosetu.com"


def test_group_value_expansion():
    """\\k<scheme>://\\k<domain> が https://ncode.syosetu.com に展開される"""
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    top_url = ss["top_url"]
    assert top_url == "https://ncode.syosetu.com"


def test_toc_url_expansion():
    """toc_urlが \\k<top_url>/\\k<ncode>/ に展開される（ncodeはマッチ後に設定）"""
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    ss["ncode"] = "n1234ab"
    toc_url = ss["toc_url"]
    assert toc_url == "https://ncode.syosetu.com/n1234ab/"


def test_multi_match_url():
    """URLパターンでncodeを抽出する"""
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    url = "https://ncode.syosetu.com/n9876cd/"
    match = ss.multi_match(url, "url")
    assert match is not None
    assert ss.matched("ncode") == "n9876cd"


def test_multi_match_subtitles():
    """目次HTMLからエピソード情報を抽出する"""
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    # 最初にncodeをマッチさせておく
    ss.multi_match("https://ncode.syosetu.com/n1234ab/", "url")

    toc_html = '''
    <div class="p-eplist__chapter-title">第一章 冒険の始まり</div>
    <div class="p-eplist__sublist">
    <a href="/n1234ab/1/" class="p-eplist__subtitle">
    第1話 旅立ちの日
    </a>
    <div class="p-eplist__update">
    2025/01/01 12:00
    </div>
    </div>
    '''
    match = ss.multi_match(toc_html, "subtitles")
    assert match is not None
    assert ss.matched("chapter") == "第一章 冒険の始まり"
    assert ss.matched("subtitle") == "第1話 旅立ちの日"
    assert ss.matched("index") == "1"
    assert "2025/01/01" in ss.matched("subdate")


def test_novel18_yaml():
    """R18サイトの定義がcookieを含むこと"""
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "novel18.syosetu.com.yaml")
    assert ss.get_raw("name") == "ノクターン・ムーンライト"
    assert ss.get_raw("confirm_over18") is True  # YAML 'yes' → bool True
    assert ss.get_raw("cookie") == "over18=yes"


def test_is_narou_flag():
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    assert ss.get_raw("is_narou") is True


def test_novel_info_url_expansion():
    """小説情報URLが正しく展開される"""
    ss = SiteSetting.load_file(WEBNOVEL_DIR / "ncode.syosetu.com.yaml")
    ss["ncode"] = "n5678ef"
    info_url = ss["novel_info_url"]
    assert info_url == "https://ncode.syosetu.com/novelview/infotop/ncode/n5678ef/"
