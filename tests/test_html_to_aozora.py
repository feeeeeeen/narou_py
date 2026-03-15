from narou.html_to_aozora import html_to_aozora


def test_br_conversion():
    # <br> は改行に変換、既存の改行は除去
    assert html_to_aozora("hello<br>world") == "hello\nworld"
    # 既存の改行は除去されて <br> が改行になる
    result = html_to_aozora("line1\nline2<br />line3")
    assert "line1line2\nline3" == result


def test_ruby_conversion():
    html = "<ruby>漢字<rt>かんじ</rt></ruby>"
    assert html_to_aozora(html) == "｜漢字《かんじ》"


def test_ruby_with_rp():
    html = "<ruby>漢字<rb>漢字</rb><rp>(</rp><rt>かんじ</rt><rp>)</rp></ruby>"
    # HTMLパーサーはシンプルなので<rb>の前のテキスト含む
    result = html_to_aozora(html)
    assert "《かんじ》" in result


def test_bold_conversion():
    html = "<b>太字テスト</b>"
    result = html_to_aozora(html)
    assert "［＃太字］太字テスト［＃太字終わり］" == result


def test_italic_conversion():
    html = "<i>斜体テスト</i>"
    result = html_to_aozora(html)
    assert "［＃斜体］斜体テスト［＃斜体終わり］" == result


def test_strikethrough_conversion():
    html = "<s>取消テスト</s>"
    result = html_to_aozora(html)
    assert "［＃取消線］取消テスト［＃取消線終わり］" == result


def test_img_conversion():
    html = '<img src="https://example.com/img.png" alt="test">'
    result = html_to_aozora(html)
    assert result == "［＃挿絵（https://example.com/img.png）入る］"


def test_img_with_current_url():
    html = '<img src="/images/test.jpg" alt="">'
    result = html_to_aozora(html, current_url="https://example.com/novel/1/")
    assert "https://example.com/images/test.jpg" in result


def test_tag_removal():
    html = "<div><span>テキスト</span></div>"
    assert html_to_aozora(html) == "テキスト"


def test_guillemet_escape():
    """元テキスト中の《》が≪≫にエスケープされること"""
    html = "テスト《ルビ風》テキスト"
    result = html_to_aozora(html)
    assert "≪ルビ風≫" in result


def test_combined():
    html = 'こんにちは<br><b>太字</b>と<ruby>漢字<rt>かんじ</rt></ruby>のテスト'
    result = html_to_aozora(html)
    assert "［＃太字］太字［＃太字終わり］" in result
    assert "｜漢字《かんじ》" in result
