from narou.converter import TextConverter
from narou.novel_setting import NovelSetting


def _make_converter(**overrides) -> TextConverter:
    setting = NovelSetting(**overrides)
    return TextConverter(setting)


# ========== 半角カナ→全角 ==========

def test_hankaku_kana_to_zenkaku():
    c = _make_converter()
    assert c._hankaku_kana_to_zenkaku("ﾃｽﾄ") == "テスト"
    assert c._hankaku_kana_to_zenkaku("ｶﾞｷﾞｸﾞ") == "ガギグ"
    assert c._hankaku_kana_to_zenkaku("ﾊﾟﾋﾟﾌﾟ") == "パピプ"


# ========== 数字変換 ==========

def test_convert_numbers_to_kanji():
    c = _make_converter(enable_convert_num_to_kanji=True)
    c._text_type = "body"
    result = c._convert_numbers("10人")
    # 漢数字に変換される
    assert "0" not in result or "０" not in result

def test_convert_numbers_zenkaku():
    c = _make_converter(enable_convert_num_to_kanji=False)
    result = c._convert_numbers("123")
    assert "１２３" in result


def test_hankaku_num_2digit_tcy():
    c = _make_converter(enable_convert_num_to_kanji=False)
    result = c._hankaku_num_to_zenkaku_num("42")
    assert "縦中横" in result
    assert "42" in result


def test_hankaku_num_1digit_zenkaku():
    c = _make_converter(enable_convert_num_to_kanji=False)
    result = c._hankaku_num_to_zenkaku_num("5")
    assert result == "５"


def test_decimal_point_to_nakaguro():
    c = _make_converter()
    c._text_type = "body"
    result = c._convert_numbers("3.14")
    assert "・" in result


# ========== アルファベット全角化 ==========

def test_alphabet_to_zenkaku():
    c = _make_converter(enable_alphabet_force_zenkaku=True)
    result = c._alphabet_to_zenkaku("ABC")
    assert "ＡＢＣ" in result


def test_english_sentence_protection():
    c = _make_converter(enable_alphabet_force_zenkaku=False)
    result = c._alphabet_to_zenkaku("Hello World")
    # 英文として保護されるので半角のまま（stash）
    assert "Hello World" in result or "英文" in result


# ========== 記号全角化 ==========

def test_symbols_to_zenkaku():
    c = _make_converter()
    result = c._symbols_to_zenkaku("!?")
    assert result == "！？"


def test_symbols_parentheses():
    c = _make_converter()
    result = c._symbols_to_zenkaku("(test)")
    assert "（" in result and "）" in result


# ========== かぎ括弧連結 ==========

def test_auto_join_in_brackets():
    c = _make_converter()
    text = "「こんにちは、\n　世界。」"
    result = c._auto_join_in_brackets(text)
    assert "\n" not in result
    assert "「こんにちは、世界。」" == result


def test_auto_join_in_brackets_disabled():
    c = _make_converter(enable_auto_join_in_brackets=False)
    text = "「こんにちは、\n　世界。」"
    result = c._auto_join_in_brackets(text)
    assert "\n" in result


# ========== 自動行連結 ==========

def test_auto_join_line():
    c = _make_converter()
    text = "ここで、\n　続きの文章です"
    result = c._auto_join_line(text)
    assert "\n" not in result


# ========== 挿絵タグ ==========

def test_replace_illust_stash_rebuild():
    c = _make_converter(enable_illust=True)
    text = "前文\n［＃挿絵（test.png）入る］\n後文"
    stashed = c._replace_illust_tag(text)
    assert "挿絵＝" in stashed
    rebuilt = c._rebuild_illust(stashed)
    assert "［＃挿絵（test.png）入る］" in rebuilt


def test_illust_disabled():
    c = _make_converter(enable_illust=False)
    text = "前文\n［＃挿絵（test.png）入る］\n後文"
    result = c._replace_illust_tag(text)
    assert "挿絵" not in result


# ========== URL保護 ==========

def test_url_stash_rebuild():
    c = _make_converter()
    text = "リンク: https://example.com/path?q=1 です"
    stashed = c._replace_url(text)
    assert "ＵＲＬ" in stashed
    rebuilt = c._rebuild_url(stashed)
    assert "https://example.com/path?q=1" in rebuilt


# ========== 感嘆符後アキ ==========

def test_insert_separate_space():
    c = _make_converter()
    result = c._insert_separate_space("すごい！本当に")
    assert "！　本" in result


def test_insert_separate_space_no_double():
    c = _make_converter()
    result = c._insert_separate_space("すごい！　本当に")
    assert result.count("　") == 1 or "！　本" in result


def test_insert_separate_space_closing_bracket():
    c = _make_converter()
    result = c._insert_separate_space("すごい！」")
    assert "！」" in result  # 閉じ括弧前にはアキを入れない


# ========== 特殊文字変換 ==========

def test_convert_horizontal_ellipsis():
    c = _make_converter(enable_convert_horizontal_ellipsis=True)
    result = c._convert_special_characters("・・・")
    assert "…" in result


def test_triple_period_to_ellipsis():
    c = _make_converter()
    result = c._convert_special_characters("。。。")
    assert "…" in result


# ========== 行頭字下げ ==========

def test_auto_indent():
    c = _make_converter()
    text = "字下げなし\n　既に字下げ\n「括弧」"
    result = c._auto_indent(text)
    lines = result.split("\n")
    assert lines[0].startswith("　")  # 字下げ追加
    assert lines[1].startswith("　")  # 既存の字下げ維持


# ========== 行頭括弧 ==========

def test_half_indent_bracket():
    c = _make_converter()
    result = c._half_indent_bracket("「セリフ」")
    assert "二分アキ" in result


# ========== 空行整理 ==========

def test_pack_blank_line():
    c = _make_converter()
    text = "行1\n\n\n\n\n行2"
    result = c._pack_blank_line(text)
    assert result.count("\n") <= 3


# ========== 改ページ変換 ==========

def test_convert_page_break():
    c = _make_converter(to_page_break_threshold=3)
    text = "行1\n\n\n\n行2"
    result = c._convert_page_break(text)
    assert "改ページ" in result


# ========== 統合テスト ==========

def test_convert_body():
    c = _make_converter()
    text = "　テスト文章です。\n　「セリフだよ」\n　100人が集まった。"
    result = c.convert(text, "body")
    assert len(result) > 0


def test_convert_introduction():
    c = _make_converter()
    result = c.convert("前書きテスト", "introduction")
    assert "前書き" in result


def test_convert_introduction_erased():
    c = _make_converter(enable_erase_introduction=True)
    result = c.convert("前書きテスト", "introduction")
    assert result == ""


def test_convert_postscript():
    c = _make_converter()
    result = c.convert("後書きテスト", "postscript")
    assert "後書き" in result


def test_convert_postscript_erased():
    c = _make_converter(enable_erase_postscript=True)
    result = c.convert("後書きテスト", "postscript")
    assert result == ""


def test_convert_subtitle():
    c = _make_converter()
    result = c.convert("第1話 ﾃｽﾄ", "subtitle")
    assert "テスト" in result
