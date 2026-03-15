"""GUIのテーブルモデルのテスト（PySide6不要な部分のみ）。"""

import pytest
from narou.models import Novel


def test_novel_display_fields():
    """NovelモデルがGUI表示に必要なフィールドを持つこと"""
    novel = Novel(
        id=1,
        title="テスト小説",
        author="テスト著者",
        toc_url="https://ncode.syosetu.com/n1234ab/",
        sitename="小説家になろう",
        novel_type=1,
        general_all_no=50,
        is_end=False,
    )
    assert novel.id == 1
    assert novel.title == "テスト小説"
    assert novel.author == "テスト著者"
    assert novel.sitename == "小説家になろう"
    assert novel.general_all_no == 50
    assert novel.is_end is False


def test_novel_completed_status():
    """完結状態の表示"""
    novel = Novel(title="完結小説", author="著者", toc_url="https://example.com/", is_end=True)
    assert novel.is_end is True


def test_novel_default_values():
    """デフォルト値の確認"""
    novel = Novel(title="テスト", author="著者", toc_url="https://example.com/")
    assert novel.sitename == ""
    assert novel.general_all_no == 0
    assert novel.is_end is False
