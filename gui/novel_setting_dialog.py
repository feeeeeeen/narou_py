"""小説ごとの変換設定ダイアログ。"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from narou.novel_setting import DEFAULT_SETTINGS, REPLACE_NAME, NovelSetting


class NovelSettingDialog(QDialog):
    """小説の変換設定を編集するダイアログ。"""

    def __init__(self, title: str, archive_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"変換設定 - {title}")
        self.resize(600, 500)
        self._archive_path = Path(archive_path)

        # 設定読み込み
        self._setting = (
            NovelSetting.load(self._archive_path)
            if self._archive_path.exists()
            else NovelSetting()
        )
        self._widgets: dict[str, QWidget] = {}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # タブ
        tabs = QTabWidget()
        tabs.addTab(self._create_settings_tab(), "変換設定")
        tabs.addTab(self._create_replace_tab(), "置換設定")
        layout.addWidget(tabs)

        # ボタン
        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("デフォルトに戻す")
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        btn_layout.addWidget(btn_box)
        layout.addLayout(btn_layout)

    def _create_settings_tab(self) -> QWidget:
        """変換設定タブ: DEFAULT_SETTINGSから動的にウィジェットを生成する。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        form = QFormLayout(container)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        for s in DEFAULT_SETTINGS:
            name = s["name"]
            stype = s["type"]
            help_text = s["help"]
            current = getattr(self._setting, name, s["value"])

            if stype == "boolean":
                widget = QCheckBox()
                widget.setChecked(bool(current))
            elif stype == "integer":
                widget = QSpinBox()
                widget.setRange(0, 9999)
                widget.setValue(int(current))
            else:  # string
                widget = QLineEdit(str(current))

            self._widgets[name] = widget
            form.addRow(help_text, widget)

        scroll.setWidget(container)
        return scroll

    def _create_replace_tab(self) -> QWidget:
        """置換設定タブ: replace.txtの検索/置換ペアをテーブルで編集する。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 説明ラベル
        desc = QLabel("検索パターンと置換文字列のペアを設定します。（正規表現使用可）")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # テーブル
        self._replace_table = QTableWidget()
        self._replace_table.setColumnCount(2)
        self._replace_table.setHorizontalHeaderLabels(["検索", "置換"])
        self._replace_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._replace_table)

        # 既存パターンを読み込み
        for src, dst in self._setting.replace_pattern:
            self._add_replace_row(src, dst)

        # ボタン行
        btn_row = QHBoxLayout()
        add_btn = QPushButton("行を追加")
        add_btn.clicked.connect(lambda: self._add_replace_row("", ""))
        remove_btn = QPushButton("選択行を削除")
        remove_btn.clicked.connect(self._remove_replace_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    def _add_replace_row(self, src: str, dst: str):
        row = self._replace_table.rowCount()
        self._replace_table.insertRow(row)
        self._replace_table.setItem(row, 0, QTableWidgetItem(src))
        self._replace_table.setItem(row, 1, QTableWidgetItem(dst))

    def _remove_replace_row(self):
        rows = set()
        for item in self._replace_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._replace_table.removeRow(row)

    def _on_save(self):
        """設定をsetting.iniとreplace.txtに保存する。"""
        # 設定値をNovelSettingに反映
        for s in DEFAULT_SETTINGS:
            name = s["name"]
            widget = self._widgets[name]
            if isinstance(widget, QCheckBox):
                setattr(self._setting, name, widget.isChecked())
            elif isinstance(widget, QSpinBox):
                setattr(self._setting, name, widget.value())
            elif isinstance(widget, QLineEdit):
                setattr(self._setting, name, widget.text())

        # setting.ini 保存
        self._archive_path.mkdir(parents=True, exist_ok=True)
        self._setting.save(self._archive_path)

        # replace.txt 保存
        lines = []
        for row in range(self._replace_table.rowCount()):
            src_item = self._replace_table.item(row, 0)
            dst_item = self._replace_table.item(row, 1)
            src = src_item.text() if src_item else ""
            dst = dst_item.text() if dst_item else ""
            if src:
                lines.append(f"{src}\t{dst}")
        replace_path = self._archive_path / REPLACE_NAME
        if lines:
            replace_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
        elif replace_path.exists():
            replace_path.unlink()

        self.accept()

    def _on_reset(self):
        """全設定をデフォルト値に戻す。"""
        reply = QMessageBox.question(
            self,
            "確認",
            "すべての設定をデフォルトに戻しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for s in DEFAULT_SETTINGS:
            name = s["name"]
            default = s["value"]
            widget = self._widgets[name]
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(default))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(default))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(default))
