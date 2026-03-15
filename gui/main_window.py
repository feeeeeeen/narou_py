"""メインウィンドウ。"""

import os
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
)
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from narou.database import Database
from narou.models import Novel
from narou.settings import Settings
from gui.novel_setting_dialog import NovelSettingDialog
from gui.style import build_stylesheet
from gui.workers import AddNovelWorker, DownloadWorker


COLUMNS = ["ID", "タイトル", "著者", "サイト", "話数", "状態", "個別"]
COL_SETTING = 6  # 個別列のインデックス


class NovelTableModel(QAbstractTableModel):
    """小説一覧のテーブルモデル。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._novels: list[Novel] = []

    def set_novels(self, novels: list[Novel]):
        self.beginResetModel()
        self._novels = novels
        self.endResetModel()

    def get_novel(self, row: int) -> Novel | None:
        if 0 <= row < len(self._novels):
            return self._novels[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._novels)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        novel = self._novels[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return novel.id
            elif col == 1:
                return novel.title
            elif col == 2:
                return novel.author
            elif col == 3:
                return novel.sitename or ""
            elif col == 4:
                return novel.general_all_no or 0
            elif col == 5:
                if novel.is_end:
                    return "完結"
                return "連載中"
            elif col == COL_SETTING:
                return ""  # ボタン列はデリゲートで描画
            return None

        if role == Qt.ItemDataRole.ForegroundRole and col == 5:
            if novel.is_end:
                return QColor("#428bca")  # 完結: 青
            return QColor("#5cb85c")  # 連載中: 緑

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None


class SettingButtonDelegate(QStyledItemDelegate):
    """テーブルの「個別」列に設定ボタンを描画するデリゲート。"""

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        rect = option.rect.adjusted(4, 3, -4, -3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#888"))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QColor("#fff"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "設定")
        painter.restore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Narou - Web小説ダウンローダー")
        self.resize(900, 650)
        self.setStyleSheet(build_stylesheet())

        self._db_path = Path(".narou") / "database.db"
        self._db = Database(self._db_path)
        self._settings = Settings(Path("."), "gui_settings")
        self._worker: DownloadWorker | None = None
        self._add_worker: AddNovelWorker | None = None
        self._output_dir = self._settings.get(
            "output_dir", str(Path.home() / "Downloads")
        )

        self._setup_ui()
        self._reload_novels()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # === URL入力行 ===
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(
            "小説のURLを入力して追加 (例: https://ncode.syosetu.com/n1234ab/)"
        )
        self._url_input.setClearButtonEnabled(True)
        url_layout.addWidget(self._url_input)

        self._add_btn = QPushButton("追加")
        self._add_btn.setObjectName("addBtn")
        url_layout.addWidget(self._add_btn)
        layout.addLayout(url_layout)

        # === コントロール行 ===
        ctrl_layout = QHBoxLayout()

        self._download_btn = QPushButton("ダウンロード && EPUB変換")
        self._download_btn.setObjectName("downloadBtn")
        self._download_btn.setEnabled(False)
        ctrl_layout.addWidget(self._download_btn)

        self._delete_btn = QPushButton("削除")
        self._delete_btn.setObjectName("deleteBtn")
        self._delete_btn.setEnabled(False)
        ctrl_layout.addWidget(self._delete_btn)

        ctrl_layout.addStretch()

        self._count_label = QLabel("0 作品")
        ctrl_layout.addWidget(self._count_label)

        ctrl_layout.addStretch()

        self._dir_btn = QPushButton(f"保存先: {self._output_dir}")
        self._dir_btn.setObjectName("dirBtn")
        self._dir_btn.setToolTip(self._output_dir)
        ctrl_layout.addWidget(self._dir_btn)

        layout.addLayout(ctrl_layout)

        # === テーブルとログをQSplitterで分割 ===
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # テーブル
        self._model = NovelTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        # 列幅設定: タイトル列をStretchにして余白をなくす
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # タイトル列
        header.setStretchLastSection(False)

        # 「個別」列にボタンデリゲートを設定
        self._setting_delegate = SettingButtonDelegate(self._table)
        self._table.setItemDelegateForColumn(COL_SETTING, self._setting_delegate)

        # 個別列クリックで設定ダイアログを開く
        self._table.clicked.connect(self._on_table_clicked)

        self._splitter.addWidget(self._table)

        # ログ表示欄
        self._log_view = QPlainTextEdit()
        self._log_view.setObjectName("logView")
        self._log_view.setReadOnly(True)
        self._splitter.addWidget(self._log_view)

        # 初期サイズ比率: テーブル大きめ、ログ10行分
        fm = QFontMetrics(self._log_view.font())
        log_height = fm.lineSpacing() * 10 + 20
        self._splitter.setSizes([500, log_height])

        layout.addWidget(self._splitter)

        # === シグナル接続 ===
        self._add_btn.clicked.connect(self._on_add)
        self._url_input.returnPressed.connect(self._on_add)
        self._dir_btn.clicked.connect(self._on_select_dir)
        self._download_btn.clicked.connect(self._on_download)
        self._delete_btn.clicked.connect(self._on_delete)
        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

    def _log(self, message: str):
        """ログ表示欄にメッセージを追記する。"""
        self._log_view.appendPlainText(message)
        self._log_view.verticalScrollBar().setValue(
            self._log_view.verticalScrollBar().maximum()
        )

    def _reload_novels(self):
        """DBから小説一覧を再読み込み"""
        novels = self._db.list_novels()
        self._model.set_novels(novels)
        self._update_count()
        # 列幅の初期調整（タイトル列はStretchなので設定不要）
        self._table.setColumnWidth(0, 40)   # ID
        self._table.setColumnWidth(2, 150)  # 著者
        self._table.setColumnWidth(3, 100)  # サイト
        self._table.setColumnWidth(4, 50)   # 話数
        self._table.setColumnWidth(5, 60)   # 状態
        self._table.setColumnWidth(6, 50)   # 個別

    def _update_count(self):
        count = self._proxy.rowCount()
        self._count_label.setText(f"{count} 作品")

    def _on_table_clicked(self, index: QModelIndex):
        """テーブルセルクリック。個別列なら設定ダイアログを開く。"""
        # proxy経由なのでcolumnはそのまま使える
        if index.column() != COL_SETTING:
            return
        source_index = self._proxy.mapToSource(index)
        novel = self._model.get_novel(source_index.row())
        if not novel:
            return
        if not novel.archive_path:
            QMessageBox.warning(
                self, "警告", "まずダウンロードしてください。"
            )
            return
        dialog = NovelSettingDialog(novel.title, novel.archive_path, self)
        dialog.exec()

    def _on_selection_changed(self):
        selected = self._table.selectionModel().selectedRows()
        has_selection = len(selected) > 0
        self._download_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        if has_selection:
            self._download_btn.setText(
                f"ダウンロード && EPUB変換 ({len(selected)}件)"
            )
        else:
            self._download_btn.setText("ダウンロード && EPUB変換")

    def _on_add(self):
        url = self._url_input.text().strip()
        if not url:
            return

        self._add_btn.setEnabled(False)
        self._log(f"小説情報を取得中: {url}")

        self._add_worker = AddNovelWorker(url, self._db_path)
        self._add_worker.finished.connect(self._on_add_finished)
        self._add_worker.start()

    def _on_add_finished(self, success: bool, message: str):
        self._add_btn.setEnabled(True)
        self._log(message)
        if self._add_worker is not None:
            self._add_worker.deleteLater()
            self._add_worker = None

        if success:
            self._url_input.clear()
            self._reload_novels()

    def _on_select_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "保存先フォルダ", self._output_dir
        )
        if dir_path:
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                QMessageBox.warning(
                    self, "警告", f"保存先フォルダにアクセスできません:\n{e}"
                )
                return
            self._output_dir = dir_path
            self._dir_btn.setText(f"保存先: {dir_path}")
            self._dir_btn.setToolTip(dir_path)
            self._settings.set("output_dir", dir_path)
            self._settings.save()

    def _on_download(self):
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return

        novels: list[Novel] = []
        for idx in selected_rows:
            source_idx = self._proxy.mapToSource(idx)
            novel = self._model.get_novel(source_idx.row())
            if novel:
                novels.append(novel)

        if not novels:
            return

        try:
            os.makedirs(self._output_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(
                self, "エラー", f"保存先フォルダを作成できません:\n{e}"
            )
            return

        self._download_btn.setEnabled(False)
        self._add_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._log(f"ダウンロード開始: {len(novels)}件")

        self._worker = DownloadWorker(
            novels, self._db_path, self._output_dir,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_one.connect(self._on_finished_one)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, percent: int, message: str):
        self._log(message)

    def _on_finished_one(self, novel_id: int, success: bool, message: str):
        prefix = "OK" if success else "ERROR"
        self._log(f"[{prefix}] ID:{novel_id} - {message}")

    def _on_finished(self, success: int, errors: int):
        self._download_btn.setEnabled(True)
        self._add_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        msg = f"完了: {success}件成功"
        if errors:
            msg += f"、{errors}件エラー"
        self._log(msg)
        self._reload_novels()

    def _on_delete(self):
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return

        novels: list[Novel] = []
        for idx in selected_rows:
            source_idx = self._proxy.mapToSource(idx)
            novel = self._model.get_novel(source_idx.row())
            if novel:
                novels.append(novel)

        if not novels:
            return

        titles = "\n".join(f"  - {n.title}" for n in novels[:5])
        if len(novels) > 5:
            titles += f"\n  ... 他{len(novels) - 5}件"

        reply = QMessageBox.question(
            self, "確認",
            f"以下の{len(novels)}件を削除しますか？\n{titles}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for novel in novels:
            self._db.delete_novel(novel.id)
        self._reload_novels()
        self._log(f"{len(novels)}件を削除しました")

    def closeEvent(self, event):
        self._db.close()
        super().closeEvent(event)
