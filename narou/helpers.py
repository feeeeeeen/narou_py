import html
import os
import platform
import re
import subprocess
import sys
from pathlib import Path


# ファイル名に使えない文字の全角変換テーブル
_FILENAME_TRANS = str.maketrans(
    '/:*?"<>|.\t\n\\',
    "／：＊？\u201d〈〉｜．\x00\x00￥",
)


def safe_filename(name: str) -> str:
    """ファイル名に使えない文字を全角文字に置換する"""
    result = name.translate(_FILENAME_TRANS).replace("\x00", "")
    # パストラバーサル防止: .. を含むファイル名を拒否
    if ".." in result:
        result = result.replace("..", "．．")
    return result


# HTMLエンティティ復号テーブル（標準html.unescapeで対応しないもの含む）
_ENTITIES = {
    "&quot;": '"',
    "&amp;": "&",
    "&nbsp;": " ",
    "&lt;": "<",
    "&gt;": ">",
    "&copy;": "(c)",
    "&#39;": "'",
}


def restore_entity(text: str) -> str:
    """HTMLエンティティを復号する"""
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    return text


def pretreatment_source(src: str) -> str:
    """ダウンロードしたHTMLソースの前処理（エンティティ復号、\\r除去）"""
    return restore_entity(src).replace("\r", "")


def ampersand_to_entity(text: str) -> str:
    """アンパサンドをHTMLエンティティに変換"""
    return re.sub(r"&(?!amp;)", "&amp;", text, flags=re.IGNORECASE)


def extract_illust_chuki(text: str) -> tuple[str, list[str]]:
    """文章の中から挿絵注記を分離する"""
    illust_list: list[str] = []

    def _replace(m: re.Match) -> str:
        illust_list.append(m.group(1))
        return ""

    extracted = re.sub(r"[ 　\t]*?(［＃挿絵（.+?）入る］)\n?", _replace, text)
    return extracted, illust_list


def open_directory(path: Path) -> None:
    """OSの既定ファイラーでフォルダを開く"""
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
