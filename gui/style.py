"""narou.rb Web UI 風のQSSスタイル定義。"""


def build_stylesheet() -> str:
    """アプリ全体のQSSスタイルシートを返す。"""
    return """
/* === 全体 === */
QMainWindow {
    background-color: #fafaf8;
    font-size: 13px;
    color: #333;
}

QDialog {
    background-color: #f5f5f5;
    font-size: 13px;
    color: #333;
}

QLabel {
    color: #333;
}

QCheckBox {
    color: #333;
}

QTabWidget::pane {
    border: 1px solid #ccc;
    background-color: #fff;
}

QTabBar::tab {
    background-color: #e0e0e0;
    color: #333;
    padding: 6px 16px;
    border: 1px solid #ccc;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #fff;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #eee;
}

QScrollArea {
    background-color: #fff;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #fff;
}

QSpinBox {
    padding: 2px 4px;
    border: 1px solid #ccc;
    border-radius: 3px;
    color: #333;
    background-color: #fff;
}

/* === テーブル === */
QTableView {
    gridline-color: #ddd0cc;
    alternate-background-color: #fffcef;
    background-color: #f8f3e5;
    color: #333;
    selection-background-color: #f5e67c;
    selection-color: #333;
    border: 1px solid #ccc;
}

QTableView::item {
    color: #333;
}

QTableView::item:hover {
    background-color: #ddeedd;
}

QHeaderView::section {
    background-color: #605555;
    color: #ddd0cc;
    padding: 5px 8px;
    border: none;
    font-weight: bold;
}

/* === ボタン共通 === */
QPushButton {
    padding: 5px 14px;
    border-radius: 4px;
    border: 1px solid #ccc;
    background-color: #f0f0f0;
    color: #333;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #e0e0e0;
}

/* === 個別ボタン === */
QPushButton#addBtn {
    background-color: #5cb85c;
    color: white;
    border-color: #4cae4c;
}
QPushButton#addBtn:hover {
    background-color: #449d44;
}

QPushButton#downloadBtn {
    background-color: #4a90d9;
    color: white;
    border-color: #357abd;
}
QPushButton#downloadBtn:hover {
    background-color: #357abd;
}

QPushButton#deleteBtn {
    background-color: #d9534f;
    color: white;
    border-color: #d43f3a;
}
QPushButton#deleteBtn:hover {
    background-color: #c9302c;
}

QPushButton#dirBtn {
    background-color: #f0ad4e;
    color: white;
    border-color: #eea236;
}
QPushButton#dirBtn:hover {
    background-color: #ec971f;
}

/* === テーブル内設定ボタン === */
QPushButton#settingBtn {
    background-color: #888;
    color: white;
    border: none;
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 11px;
}
QPushButton#settingBtn:hover {
    background-color: #666;
}

/* === ログ表示 === */
QPlainTextEdit#logView {
    background-color: #333;
    color: #fff;
    border: 1px solid #555;
    font-family: "Consolas", "MS Gothic", monospace;
    font-size: 12px;
}

/* === 入力欄 === */
QLineEdit {
    padding: 4px 8px;
    border: 1px solid #ccc;
    border-radius: 3px;
    color: #333;
    background-color: #fff;
}

/* === プログレスバー（ダイアログ用） === */
QProgressBar {
    border: 1px solid #ccc;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #4a90d9;
}
"""
