import tempfile
from datetime import datetime
from pathlib import Path

from narou.database import Database
from narou.models import Novel


def _make_db() -> Database:
    """インメモリ風にtempfileでDBを作成"""
    tmp = tempfile.mkdtemp()
    return Database(Path(tmp) / "test.db")


def test_add_and_get_novel():
    db = _make_db()
    novel = Novel(
        title="テスト小説",
        author="テスト著者",
        toc_url="https://ncode.syosetu.com/n1234ab/",
        sitename="小説家になろう",
        novel_type=1,
        general_all_no=50,
    )
    novel_id = db.add_novel(novel)
    assert novel_id > 0

    loaded = db.get_novel(novel_id)
    assert loaded is not None
    assert loaded.title == "テスト小説"
    assert loaded.author == "テスト著者"
    assert loaded.general_all_no == 50
    db.close()


def test_get_novel_by_url():
    db = _make_db()
    novel = Novel(title="URL検索テスト", author="著者", toc_url="https://ncode.syosetu.com/n9999zz/")
    db.add_novel(novel)

    found = db.get_novel_by_url("https://ncode.syosetu.com/n9999zz/")
    assert found is not None
    assert found.title == "URL検索テスト"

    not_found = db.get_novel_by_url("https://ncode.syosetu.com/n0000aa/")
    assert not_found is None
    db.close()


def test_update_novel():
    db = _make_db()
    novel = Novel(title="更新前", author="著者", toc_url="https://ncode.syosetu.com/n1111aa/")
    novel_id = db.add_novel(novel)

    novel.id = novel_id
    novel.title = "更新後"
    novel.is_end = True
    novel.last_update = datetime(2025, 1, 1, 12, 0, 0)
    db.update_novel(novel)

    loaded = db.get_novel(novel_id)
    assert loaded.title == "更新後"
    assert loaded.is_end is True
    assert loaded.last_update == datetime(2025, 1, 1, 12, 0, 0)
    db.close()


def test_delete_novel():
    db = _make_db()
    novel = Novel(title="削除テスト", author="著者", toc_url="https://ncode.syosetu.com/n2222bb/")
    novel_id = db.add_novel(novel)
    db.delete_novel(novel_id)
    assert db.get_novel(novel_id) is None
    db.close()


def test_list_novels():
    db = _make_db()
    for i in range(3):
        db.add_novel(Novel(
            title=f"小説{i}",
            author="著者",
            toc_url=f"https://ncode.syosetu.com/n{i}aaa/",
            last_update=datetime(2025, 1, i + 1),
        ))
    novels = db.list_novels()
    assert len(novels) == 3
    # last_update DESC なので最新が先頭
    assert novels[0].title == "小説2"
    db.close()


def test_search_novels():
    db = _make_db()
    db.add_novel(Novel(title="異世界転生物語", author="田中太郎", toc_url="https://example.com/1/"))
    db.add_novel(Novel(title="魔法学園ラブコメ", author="佐藤花子", toc_url="https://example.com/2/"))
    db.add_novel(Novel(title="日常系コメディ", author="田中次郎", toc_url="https://example.com/3/"))

    results = db.search_novels("田中")
    assert len(results) == 2

    results = db.search_novels("魔法")
    assert len(results) == 1
    assert results[0].title == "魔法学園ラブコメ"
    db.close()


def test_tags_roundtrip():
    db = _make_db()
    novel = Novel(title="タグテスト", author="著者", toc_url="https://example.com/tags/", tags=["異世界", "チート", "ハーレム"])
    novel_id = db.add_novel(novel)
    loaded = db.get_novel(novel_id)
    assert loaded.tags == ["異世界", "チート", "ハーレム"]
    db.close()
