"""バックグラウンド処理用のQThreadワーカー。"""

import logging
import threading
from pathlib import Path

import yaml
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

from narou.converter import TextConverter
from narou.database import Database
from narou.downloader import NovelDownloader, DownloadResult
from narou.epub_writer import EpubSection, write_epub
from narou.helpers import safe_filename
from narou.models import Novel
from narou.novel_setting import NovelSetting
from narou.parser import parse_text


SECTION_SAVE_DIR = "本文"


class DownloadWorker(QThread):
    """小説のダウンロード→変換→EPUB生成を実行するワーカー。"""

    progress = Signal(int, str)       # (percent, message)
    finished_one = Signal(int, bool, str)  # (novel_id, success, message)
    finished_all = Signal(int, int)   # (success_count, error_count)

    def __init__(
        self,
        novels: list[Novel],
        db_path: Path,
        output_dir: str,
        force: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.novels = novels
        self.db_path = db_path
        self.output_dir = output_dir
        self.force = force
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        total = len(self.novels)
        success = 0
        errors = 0
        # ワーカースレッド内で新しいDB接続を作成（SQLiteスレッド安全性）
        db = Database(self.db_path)
        downloader: NovelDownloader | None = None
        try:
            # NovelDownloader.__init__() は webnovel/ が無いと FileNotFoundError を投げる。
            # その場合でも下の finally で必ず db.close() できるよう、構築は try 内で行う。
            downloader = NovelDownloader(db, Path(self.output_dir))

            for i, novel in enumerate(self.novels):
                if self._cancel_event.is_set():
                    break

                pct = int((i / total) * 100)
                self.progress.emit(pct, f"ダウンロード中: {novel.title}")

                try:
                    # ダウンロード
                    def _progress_cb(current: int, total_sections: int, msg: str):
                        self.progress.emit(pct, f"[{current}/{total_sections}] {msg}")

                    result = downloader.download(
                        novel.toc_url,
                        force=self.force,
                        progress_callback=_progress_cb,
                    )

                    if result.status == "failed":
                        errors += 1
                        self.finished_one.emit(novel.id, False, "ダウンロード失敗")
                        continue

                    # EPUB変換（更新なしの場合も設定変更に対応するため常に実行）
                    self.progress.emit(pct, f"変換中: {novel.title}")
                    # DB再取得（ダウンロードでarchive_pathが更新されている場合がある）
                    updated_novel = db.get_novel(novel.id) or novel
                    archive_path = Path(updated_novel.archive_path) if updated_novel.archive_path else None

                    if archive_path and (archive_path / SECTION_SAVE_DIR).exists():
                        epub_path = self._convert_to_epub(updated_novel, archive_path)
                        status_msg = "完了" if result.status == "ok" else "変換完了（更新なし）"
                        self.finished_one.emit(novel.id, True, f"{status_msg}: {epub_path.name}")
                    else:
                        self.finished_one.emit(novel.id, True, f"更新なし: {novel.title}")

                    success += 1

                except Exception as e:
                    errors += 1
                    logger.exception("ダウンロード処理で予期せぬ例外: %s", novel.title)
                    self.finished_one.emit(novel.id, False, str(e))
        finally:
            try:
                if downloader is not None:
                    downloader.close()
            finally:
                db.close()
        self.progress.emit(100, "完了")
        self.finished_all.emit(success, errors)

    def _convert_to_epub(self, novel: Novel, archive_path: Path) -> Path:
        """archive_pathに保存済みのセクションデータからEPUBを生成する"""
        section_dir = archive_path / SECTION_SAVE_DIR
        setting = NovelSetting.load(archive_path) if archive_path.exists() else NovelSetting()
        converter = TextConverter(setting)

        # セクションYAMLファイルを番号順に読み込む
        yaml_files = sorted(section_dir.glob("*.yaml"),
                            key=lambda p: int(p.name.split(" ", 1)[0]))
        sections: list[EpubSection] = []

        for idx, yaml_path in enumerate(yaml_files, 1):
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except (OSError, yaml.YAMLError) as e:
                logger.warning("セクションファイルの読み込み失敗: %s - %s", yaml_path, e)
                continue

            if not isinstance(data, dict):
                logger.warning("不正なセクションデータ: %s", yaml_path)
                continue

            element = data.get("element", {})
            subtitle = data.get("subtitle", f"第{idx}話")
            chapter = data.get("chapter", "")

            # テキスト変換
            body = converter.convert(element.get("body", ""), "body")

            intro = ""
            if element.get("introduction"):
                intro = converter.convert(element["introduction"], "introduction")

            postscript = ""
            if element.get("postscript"):
                postscript = converter.convert(element["postscript"], "postscript")

            full_text = ""
            if intro:
                full_text += intro + "\n"
            full_text += body
            if postscript:
                full_text += "\n" + postscript

            parsed = parse_text(full_text, section_id=f"s{idx}")
            sections.append(EpubSection(
                index=idx,
                title=subtitle,
                parsed=parsed,
                chapter=chapter,
            ))

        # EPUB出力
        safe_title = safe_filename(novel.title)
        epub_path = Path(self.output_dir) / f"{safe_title}.epub"
        write_epub(
            title=novel.title,
            author=novel.author or "",
            sections=sections,
            output_path=epub_path,
            sitename=novel.sitename or "",
            toc_url=novel.toc_url,
        )
        return epub_path


class AddNovelWorker(QThread):
    """URLから小説情報を取得してDBに追加するワーカー。"""

    finished = Signal(bool, str)  # (success, message)

    def __init__(self, url: str, db_path: Path, parent=None):
        super().__init__(parent)
        self.url = url
        self.db_path = db_path

    def run(self):
        # ワーカースレッド内で新しいDB接続を作成（SQLiteスレッド安全性）
        db = Database(self.db_path)
        downloader: NovelDownloader | None = None
        try:
            # NovelDownloader.__init__() は webnovel/ が無いと FileNotFoundError を投げる。
            # その場合でも下の finally で必ず db.close() できるよう、構築は try 内で行う。
            downloader = NovelDownloader(db, Path(".narou"))
            metadata = downloader.fetch_novel_metadata(self.url)
            if metadata is None:
                self.finished.emit(False, "対応していないURLか、小説情報の取得に失敗しました")
                return

            # 既存チェック
            existing = db.get_novel_by_url(metadata["toc_url"])
            if existing:
                self.finished.emit(False, f"既に登録済みです: {existing.title}")
                return

            novel = Novel(
                title=metadata["title"],
                author=metadata["author"],
                toc_url=metadata["toc_url"],
                sitename=metadata["sitename"],
                novel_type=metadata["novel_type"],
                general_all_no=metadata["general_all_no"],
            )
            novel_id = db.add_novel(novel)
            self.finished.emit(True, f"追加しました: {novel.title} (ID: {novel_id})")

        except Exception as e:
            logger.exception("小説追加処理で予期せぬ例外: %s", self.url)
            self.finished.emit(False, f"エラー: {e}")
        finally:
            try:
                if downloader is not None:
                    downloader.close()
            finally:
                db.close()
