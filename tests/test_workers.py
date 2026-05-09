"""GUI ワーカーの例外ロギング・リソースクローズに関する回帰テスト。"""
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

import gui.workers as workers_module
from gui.workers import AddNovelWorker, DownloadWorker
from narou.models import Novel


@pytest.fixture(scope="module")
def qapp():
    """QThread/Signal を使うため QCoreApplication を最低1つ用意する"""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def tmp_output_dir(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    return out


def test_download_worker_logs_unexpected_exception(
    qapp, tmp_db_path, tmp_output_dir, monkeypatch, caplog
):
    """ダウンロード中に予期せぬ例外が出たら logger.exception() でスタックトレースが残ること（P1-新1 の回帰）"""
    fake_downloader = MagicMock()
    fake_downloader.download.side_effect = RuntimeError("意図的な例外")

    def fake_constructor(db, base_dir):
        return fake_downloader

    monkeypatch.setattr(workers_module, "NovelDownloader", fake_constructor)

    novel = Novel(id=1, title="テスト小説", toc_url="https://example.invalid/n1/")
    worker = DownloadWorker([novel], tmp_db_path, str(tmp_output_dir))

    with caplog.at_level(logging.ERROR, logger="gui.workers"):
        worker.run()

    # 例外メッセージとトレースバックの両方がキャプチャされていること
    matching = [r for r in caplog.records if "ダウンロード処理で予期せぬ例外" in r.message]
    assert matching, "logger.exception() が呼ばれていない"
    assert matching[0].exc_info is not None, "スタックトレースが添付されていない"


def test_download_worker_closes_downloader_on_normal_exit(
    qapp, tmp_db_path, tmp_output_dir, monkeypatch
):
    """正常終了時に NovelDownloader.close() が呼ばれること（P2-新2 の回帰）"""
    fake_downloader = MagicMock()
    fake_downloader.download.return_value = MagicMock(status="failed", novel_id=0)

    def fake_constructor(db, base_dir):
        return fake_downloader

    monkeypatch.setattr(workers_module, "NovelDownloader", fake_constructor)

    novel = Novel(id=1, title="テスト小説", toc_url="https://example.invalid/n1/")
    worker = DownloadWorker([novel], tmp_db_path, str(tmp_output_dir))
    worker.run()

    fake_downloader.close.assert_called_once()


def test_add_novel_worker_closes_resources_when_init_fails(
    qapp, tmp_db_path, monkeypatch
):
    """NovelDownloader 初期化失敗時にも DB 接続が閉じられること（P3-新4 の回帰）"""
    db_close_called = []

    def fake_init_raises(db, base_dir):
        raise FileNotFoundError("webnovel/ ディレクトリが見つかりません")

    monkeypatch.setattr(workers_module, "NovelDownloader", fake_init_raises)

    # Database.close を spy する
    original_database = workers_module.Database

    class _SpyDatabase(original_database):
        def close(self):
            db_close_called.append(True)
            super().close()

    monkeypatch.setattr(workers_module, "Database", _SpyDatabase)

    worker = AddNovelWorker("https://example.invalid/n1/", tmp_db_path)
    worker.run()

    assert db_close_called, "NovelDownloader 初期化失敗時に db.close() が呼ばれていない"
