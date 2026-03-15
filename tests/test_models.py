from datetime import datetime
from narou.models import Novel, Chapter, Section


def test_novel_defaults():
    novel = Novel()
    assert novel.id == 0
    assert novel.title == ""
    assert novel.novel_type == 1
    assert novel.is_end is False
    assert novel.tags == []
    assert novel.last_update is None


def test_novel_creation():
    now = datetime.now()
    novel = Novel(
        id=1,
        title="テスト小説",
        author="テスト著者",
        toc_url="https://ncode.syosetu.com/n1234ab/",
        sitename="小説家になろう",
        novel_type=1,
        is_end=False,
        last_update=now,
        general_all_no=100,
        tags=["異世界", "ファンタジー"],
    )
    assert novel.title == "テスト小説"
    assert novel.author == "テスト著者"
    assert novel.general_all_no == 100
    assert novel.tags == ["異世界", "ファンタジー"]


def test_chapter_creation():
    ch = Chapter(index=1, subtitle="第1話 始まり", href="/n1234ab/1/")
    assert ch.index == 1
    assert ch.subtitle == "第1話 始まり"
    assert ch.chapter == ""


def test_section_creation():
    sec = Section(
        subtitle="第1話",
        chapter="第一章",
        element={"introduction": "前書き", "body": "本文", "postscript": "後書き"},
    )
    assert sec.element["body"] == "本文"
    assert sec.element["introduction"] == "前書き"


def test_novel_tags_are_independent():
    """tagsのdefault_factoryが各インスタンスで独立していること"""
    a = Novel()
    b = Novel()
    a.tags.append("test")
    assert b.tags == []
