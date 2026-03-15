from narou.helpers import (
    safe_filename,
    restore_entity,
    pretreatment_source,
    ampersand_to_entity,
    extract_illust_chuki,
)


def test_safe_filename_special_chars():
    assert safe_filename('test/file:name*?.txt') == "test／file：name＊？．txt"


def test_safe_filename_backslash():
    assert safe_filename("test\\path") == "test￥path"


def test_safe_filename_tabs_newlines():
    assert safe_filename("test\tname\n") == "testname"


def test_safe_filename_normal():
    assert safe_filename("普通のファイル名") == "普通のファイル名"


def test_restore_entity():
    assert restore_entity("&lt;div&gt;") == "<div>"
    assert restore_entity("&amp;") == "&"
    assert restore_entity("&quot;hello&quot;") == '"hello"'
    assert restore_entity("&#39;") == "'"
    assert restore_entity("&copy;") == "(c)"
    assert restore_entity("&nbsp;") == " "


def test_pretreatment_source():
    assert pretreatment_source("hello\r\nworld\r\n") == "hello\nworld\n"
    assert pretreatment_source("&lt;p&gt;") == "<p>"


def test_ampersand_to_entity():
    assert ampersand_to_entity("a & b") == "a &amp; b"
    assert ampersand_to_entity("&amp;") == "&amp;"


def test_extract_illust_chuki():
    text = "本文\n［＃挿絵（test.png）入る］\n続き"
    extracted, illust_list = extract_illust_chuki(text)
    assert len(illust_list) == 1
    assert illust_list[0] == "［＃挿絵（test.png）入る］"
    assert "挿絵" not in extracted
    assert "本文" in extracted


def test_extract_illust_chuki_multiple():
    text = "前文\n　［＃挿絵（a.png）入る］\n中間\n［＃挿絵（b.jpg）入る］\n後文"
    extracted, illust_list = extract_illust_chuki(text)
    assert len(illust_list) == 2
    assert "a.png" in illust_list[0]
    assert "b.jpg" in illust_list[1]


def test_extract_illust_chuki_none():
    text = "挿絵のないテキスト"
    extracted, illust_list = extract_illust_chuki(text)
    assert illust_list == []
    assert extracted == text
