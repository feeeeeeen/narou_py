from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


# デフォルト設定の定義
DEFAULT_SETTINGS: list[dict[str, Any]] = [
    {"name": "enable_convert_num_to_kanji", "type": "boolean", "value": True,
     "help": "数字の漢数字変換を有効に"},
    {"name": "enable_kanji_num_with_units", "type": "boolean", "value": True,
     "help": "漢数字変換した場合、千・万などに変換するか"},
    {"name": "kanji_num_with_units_lower_digit_zero", "type": "integer", "value": 3,
     "help": "〇(ゼロ)が最低この数字以上付いてないと千・万などをつける対象にしない"},
    {"name": "enable_alphabet_force_zenkaku", "type": "boolean", "value": False,
     "help": "アルファベットを強制的に全角にする"},
    {"name": "enable_half_indent_bracket", "type": "boolean", "value": True,
     "help": "行頭かぎ括弧に二分アキを挿入する"},
    {"name": "enable_auto_indent", "type": "boolean", "value": True,
     "help": "自動行頭字下げ機能"},
    {"name": "enable_auto_join_in_brackets", "type": "boolean", "value": True,
     "help": "かぎ括弧内自動連結を有効に"},
    {"name": "enable_inspect_invalid_openclose_brackets", "type": "boolean", "value": False,
     "help": "かぎ括弧内のとじ開きが正しくされているかどうか調査する"},
    {"name": "enable_auto_join_line", "type": "boolean", "value": True,
     "help": "行末が読点で終わっている部分を出来るだけ連結する"},
    {"name": "enable_enchant_midashi", "type": "boolean", "value": True,
     "help": "改ページ直後の行に中見出しを付与する"},
    {"name": "enable_author_comments", "type": "boolean", "value": True,
     "help": "作者コメントを検出するか"},
    {"name": "enable_erase_introduction", "type": "boolean", "value": False,
     "help": "前書きを削除するか"},
    {"name": "enable_erase_postscript", "type": "boolean", "value": False,
     "help": "後書きを削除するか"},
    {"name": "enable_ruby", "type": "boolean", "value": True,
     "help": "ルビ処理を有効に"},
    {"name": "enable_illust", "type": "boolean", "value": True,
     "help": "挿絵タグを有効にする"},
    {"name": "enable_transform_fraction", "type": "boolean", "value": False,
     "help": "分数表記変換"},
    {"name": "enable_transform_date", "type": "boolean", "value": False,
     "help": "日付表記変換"},
    {"name": "date_format", "type": "string", "value": "%Y年%m月%d日",
     "help": "日付フォーマット"},
    {"name": "enable_convert_horizontal_ellipsis", "type": "boolean", "value": True,
     "help": "中黒の三点リーダー変換"},
    {"name": "enable_convert_page_break", "type": "boolean", "value": False,
     "help": "連続空行を改ページに変換"},
    {"name": "to_page_break_threshold", "type": "integer", "value": 10,
     "help": "改ページ変換の空行数閾値"},
    {"name": "enable_dakuten_font", "type": "boolean", "value": True,
     "help": "濁点フォントを使用するか"},
    {"name": "enable_display_end_of_book", "type": "boolean", "value": True,
     "help": "本読了表示"},
    {"name": "enable_add_date_to_title", "type": "boolean", "value": False,
     "help": "タイトルに日付付加"},
    {"name": "title_date_format", "type": "string", "value": "(%-m/%-d)",
     "help": "タイトル日付フォーマット"},
    {"name": "title_date_align", "type": "string", "value": "right",
     "help": "タイトル日付位置"},
    {"name": "enable_ruby_youon_to_big", "type": "boolean", "value": False,
     "help": "ルビの拗音を大きくする"},
    {"name": "enable_pack_blank_line", "type": "boolean", "value": True,
     "help": "空行を減らす"},
]

INI_NAME = "setting.ini"
REPLACE_NAME = "replace.txt"


@dataclass
class NovelSetting:
    """小説別の変換設定（29項目）"""

    enable_convert_num_to_kanji: bool = True
    enable_kanji_num_with_units: bool = True
    kanji_num_with_units_lower_digit_zero: int = 3
    enable_alphabet_force_zenkaku: bool = False
    enable_half_indent_bracket: bool = True
    enable_auto_indent: bool = True
    enable_auto_join_in_brackets: bool = True
    enable_inspect_invalid_openclose_brackets: bool = False
    enable_auto_join_line: bool = True
    enable_enchant_midashi: bool = True
    enable_author_comments: bool = True
    enable_erase_introduction: bool = False
    enable_erase_postscript: bool = False
    enable_ruby: bool = True
    enable_illust: bool = True
    enable_transform_fraction: bool = False
    enable_transform_date: bool = False
    date_format: str = "%Y年%m月%d日"
    enable_convert_horizontal_ellipsis: bool = True
    enable_convert_page_break: bool = False
    to_page_break_threshold: int = 10
    enable_dakuten_font: bool = True
    enable_display_end_of_book: bool = True
    enable_add_date_to_title: bool = False
    title_date_format: str = "(%-m/%-d)"
    title_date_align: str = "right"
    enable_ruby_youon_to_big: bool = False
    enable_pack_blank_line: bool = True

    # 追加属性（dataclassフィールド外）
    archive_path: str = ""
    title: str = ""
    author: str = ""
    replace_pattern: list = field(default_factory=list)

    @classmethod
    def load(cls, archive_path: Path) -> "NovelSetting":
        """setting.ini から設定を読み込む"""
        setting = cls()
        setting.archive_path = str(archive_path)

        ini_path = archive_path / INI_NAME
        if ini_path.exists():
            ini_data = _parse_ini(ini_path)
            for f in fields(cls):
                if f.name in ("archive_path", "title", "author", "replace_pattern"):
                    continue
                if f.name in ini_data:
                    setattr(setting, f.name, ini_data[f.name])

        setting._load_replace_pattern()
        return setting

    def save(self, archive_path: Path | None = None) -> None:
        """setting.ini に設定を保存する"""
        path = Path(archive_path or self.archive_path)
        ini_path = path / INI_NAME
        lines = ["; 小説変換設定\n"]
        for s in DEFAULT_SETTINGS:
            name = s["name"]
            val = getattr(self, name, s["value"])
            lines.append(f"; {s['help']}\n")
            lines.append(f"{name}={val}\n\n")
        ini_path.write_text("".join(lines), encoding="utf-8-sig")

    def _load_replace_pattern(self) -> None:
        """replace.txt からカスタム置換パターンを読み込む"""
        self.replace_pattern = []
        path = Path(self.archive_path) / REPLACE_NAME
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.rstrip()
            if not line or line.startswith(";"):
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[0]:
                self.replace_pattern.append((parts[0], parts[1]))


def _parse_ini(path: Path) -> dict:
    """簡易INIパーサー（[global]セクション対応）"""
    data: dict = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("["):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # 型推定
            if val.lower() == "true":
                data[key] = True
            elif val.lower() == "false":
                data[key] = False
            else:
                try:
                    data[key] = int(val)
                except ValueError:
                    data[key] = val
    return data
