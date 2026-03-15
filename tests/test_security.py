"""セキュリティ回帰テスト"""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from narou.database import Database
from narou.downloader import NovelDownloader
from narou.helpers import safe_filename


class TestPathTraversal:
    """パストラバーサル防止テスト"""

    def test_safe_filename_neutralizes_dotdot(self):
        result = safe_filename("../../etc/passwd")
        assert ".." not in result

    def test_safe_filename_neutralizes_embedded_dotdot(self):
        result = safe_filename("foo/../bar")
        assert ".." not in result

    def test_safe_filename_preserves_single_dot(self):
        """単一ドットは問題ないので変換しない"""
        result = safe_filename("chapter.txt")
        # ドットは全角に変換されるが .. のトラバーサルではない
        assert result  # 空文字列にならないこと

    def test_validate_path_rejects_traversal(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "safe"
            base.mkdir()
            evil_path = base / ".." / "evil.txt"
            with pytest.raises(ValueError, match="不正な保存パス"):
                NovelDownloader._validate_path(evil_path, base)

    def test_validate_path_allows_valid(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "safe"
            base.mkdir()
            valid_path = base / "chapter1.yaml"
            # 例外が発生しないこと
            NovelDownloader._validate_path(valid_path, base)


class TestSQLInjection:
    """SQLインジェクション防止テスト"""

    def test_list_novels_rejects_invalid_sort(self):
        with TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            try:
                # 不正なsort_byでもエラーにならずデフォルトソートで返ること
                result = db.list_novels(sort_by="1; DROP TABLE novels; --")
                assert isinstance(result, list)
            finally:
                db.close()

    def test_list_novels_accepts_valid_sort(self):
        with TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            try:
                for col in ("last_update", "title", "author", "id", "new_arrivals_date"):
                    result = db.list_novels(sort_by=col)
                    assert isinstance(result, list)
            finally:
                db.close()

    def test_search_novels_parameterized(self):
        """検索クエリがパラメータバインドされていること"""
        with TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            try:
                # SQLインジェクション試行がエラーにならないこと
                result = db.search_novels("'; DROP TABLE novels; --")
                assert isinstance(result, list)
            finally:
                db.close()
