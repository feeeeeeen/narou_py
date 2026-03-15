from narou.parser import parse_text


# ========== 基本変換 ==========

def test_plain_text():
    result = parse_text("　テスト文章です。")
    assert "<p>" in result.body_xhtml
    assert "テスト文章" in result.body_xhtml


def test_empty_line_to_br():
    result = parse_text("行1\n\n行2")
    assert "<br/>" in result.body_xhtml


# ========== 改ページ ==========

def test_page_break():
    result = parse_text("前文\n［＃改ページ］\n後文")
    assert 'class="pagebreak"' in result.body_xhtml


# ========== 区切り線 ==========

def test_separator():
    result = parse_text("前文\n［＃区切り線］\n後文")
    assert 'class="separator"' in result.body_xhtml


# ========== 挿絵 ==========

def test_illust_tag():
    result = parse_text("前文\n［＃挿絵（test.png）入る］\n後文")
    assert 'class="illustration"' in result.body_xhtml
    assert "../Images/test.png" in result.body_xhtml
    assert len(result.images) == 1
    assert result.images[0].filename == "test.png"


def test_illust_url():
    result = parse_text("［＃挿絵（https://example.com/img.jpg）入る］")
    assert "https://example.com/img.jpg" in result.body_xhtml
    assert len(result.images) == 0  # URL挿絵はimagesに追加しない


# ========== ゴシック体 ==========

def test_gothic():
    result = parse_text("　［＃ゴシック体］太字テスト［＃ゴシック体終わり］")
    assert "<b>" in result.body_xhtml
    assert "太字テスト" in result.body_xhtml


# ========== 縦中横 ==========

def test_tcy():
    result = parse_text("　［＃縦中横］42［＃縦中横終わり］人")
    assert 'class="tcy"' in result.body_xhtml
    assert "42" in result.body_xhtml


# ========== 濁点 ==========

def test_dakuten():
    result = parse_text("　［＃濁点］か［＃濁点終わり］")
    assert 'class="dakuten"' in result.body_xhtml


# ========== ルビ ==========

def test_ruby_with_bar():
    result = parse_text("　｜漢字《かんじ》テスト")
    assert "<ruby>" in result.body_xhtml
    assert "<rt>かんじ</rt>" in result.body_xhtml


def test_ruby_kanji_auto():
    result = parse_text("　漢字《かんじ》テスト")
    assert "<ruby>" in result.body_xhtml
    assert "<rt>かんじ</rt>" in result.body_xhtml


# ========== 縦線復元 ==========

def test_tatesen_restore():
    result = parse_text("　※［＃縦線］テスト")
    assert "｜" in result.body_xhtml


# ========== 前書き・後書き ==========

def test_preface_block():
    text = "［＃ここから前書き］\n前書きテスト\n［＃ここで前書き終わり］"
    result = parse_text(text)
    assert 'class="preface"' in result.body_xhtml
    assert "前書きテスト" in result.body_xhtml


def test_postscript_block():
    text = "［＃ここから後書き］\n後書きテスト\n［＃ここで後書き終わり］"
    result = parse_text(text)
    assert 'class="postscript"' in result.body_xhtml
    assert "後書きテスト" in result.body_xhtml


# ========== 二分アキ ==========

def test_half_indent():
    result = parse_text("［＃二分アキ］「セリフ」")
    assert 'class="hang-indent"' in result.body_xhtml
    assert "「セリフ」" in result.body_xhtml


# ========== HTMLエスケープ ==========

def test_html_escape():
    result = parse_text("　<script>alert(1)</script>")
    assert "&lt;script&gt;" in result.body_xhtml
    assert "<script>" not in result.body_xhtml


# ========== 未処理注記 ==========

def test_unknown_annotation():
    result = parse_text("　［＃未知の注記］")
    assert 'hidden=""' in result.body_xhtml
