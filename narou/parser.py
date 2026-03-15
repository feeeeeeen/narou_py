"""青空文庫注記付きテキストをXHTMLに変換するパーサー。

converter.pyが出力する青空文庫注記形式のテキストを
EPUB用のXHTMLに変換する。AosoraDownloaderのparser.pyを
narou_rb用の注記セットに適応。
"""

import re
from dataclasses import dataclass, field
from html import escape


@dataclass
class ImageRef:
    filename: str       # 元のファイル名
    alt: str            # 説明文 / alt テキスト
    width: int = 0
    height: int = 0


@dataclass
class ParsedSection:
    """変換済みの1話分のデータ"""
    title: str = ""
    body_xhtml: str = ""
    headings: list[tuple[int, str, str]] = field(default_factory=list)  # (level, id, text)
    images: list[ImageRef] = field(default_factory=list)


# 漢字判定用パターン（仝々〆〇ヶ含む）
_KANJI_CHARS = r"\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u4EDD\u3005\u3006\u3007\u30F6"


def parse_text(text: str, section_id: str = "s1") -> ParsedSection:
    """converter.pyの出力テキストを解析してParsedSectionを返す。

    Args:
        text: 青空文庫注記付きテキスト（converter.pyの出力）
        section_id: 見出しIDのプレフィックス
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    section = ParsedSection()
    xhtml_lines: list[str] = []
    heading_counter = 0

    in_preface = False
    in_postscript = False

    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1

        # 前書き・後書きブロック
        if line.strip() == "［＃ここから前書き］":
            in_preface = True
            xhtml_lines.append('<div class="preface">')
            continue
        if line.strip() == "［＃ここで前書き終わり］":
            in_preface = False
            xhtml_lines.append("</div>")
            continue
        if line.strip() == "［＃ここから後書き］":
            in_postscript = True
            xhtml_lines.append('<div class="postscript">')
            continue
        if line.strip() == "［＃ここで後書き終わり］":
            in_postscript = False
            xhtml_lines.append("</div>")
            continue

        # 挿絵注記: ［＃挿絵（filename）入る］
        m_img = re.match(
            r"[\s　]*［＃挿絵（(.+?)）入る］\s*$", line
        )
        if m_img:
            filename = m_img.group(1)
            # URLの場合はそのまま、ファイル名の場合はImages/配下
            if filename.startswith("http"):
                src = escape(filename)
            else:
                src = f"../Images/{escape(filename)}"
                img_ref = ImageRef(filename=filename, alt="挿絵")
                section.images.append(img_ref)
            xhtml_lines.append(
                f'<div class="illustration">'
                f'<img src="{src}" alt="挿絵"/>'
                f'</div>'
            )
            continue

        # 改ページ
        if "［＃改ページ］" in line:
            line = line.replace("［＃改ページ］", "")
            if line.strip():
                xhtml_lines.append(f"<p>{_convert_inline(line)}</p>")
            xhtml_lines.append('<hr class="pagebreak"/>')
            continue

        # 区切り線
        if line.strip() == "［＃区切り線］":
            xhtml_lines.append('<hr class="separator"/>')
            continue

        # 空行
        if not line.strip():
            xhtml_lines.append("<p><br/></p>")
            continue

        # 二分アキ（行頭括弧の字下げ）
        m_half = re.match(r"［＃二分アキ］(.+)", line)
        if m_half:
            content = m_half.group(1)
            xhtml_lines.append(f'<p class="hang-indent">{_convert_inline(content)}</p>')
            continue

        # 通常行
        xhtml_lines.append(f"<p>{_convert_inline(line)}</p>")

    section.body_xhtml = "\n".join(xhtml_lines)
    return section


def _convert_inline(text: str) -> str:
    """インライン注記をXHTMLに変換する。"""

    # --- エスケープ前に処理（注記内のテキストを正しく扱うため） ---

    # ゴシック体: ［＃ゴシック体］...［＃ゴシック体終わり］
    text = re.sub(
        r"［＃ゴシック体］(.+?)［＃ゴシック体終わり］",
        lambda m: f'\x00B_START\x00{m.group(1)}\x00B_END\x00',
        text,
    )

    # 縦中横: ［＃縦中横］...［＃縦中横終わり］
    text = re.sub(
        r"［＃縦中横］(.+?)［＃縦中横終わり］",
        lambda m: f'\x00TCY_START\x00{m.group(1)}\x00TCY_END\x00',
        text,
    )

    # 濁点: ［＃濁点］...［＃濁点終わり］
    text = re.sub(
        r"［＃濁点］(.+?)［＃濁点終わり］",
        lambda m: f'\x00DAKUTEN_START\x00{m.group(1)}\x00DAKUTEN_END\x00',
        text,
    )

    # 傍点: ［＃傍点］...（単独行でない場合のインライン版）
    text = re.sub(
        r"(.+?)［＃「\1」に傍点］",
        lambda m: f'\x00SESAME_START\x00{m.group(1)}\x00SESAME_END\x00',
        text,
    )
    text = re.sub(
        r"［＃「(.+?)」に傍点］",
        lambda m: f'\x00SESAME_START\x00{m.group(1)}\x00SESAME_END\x00',
        text,
    )

    # 縦線の復元: ※［＃縦線］ → ｜
    text = text.replace("※［＃縦線］", "\x00TATESEN\x00")

    # --- HTMLエスケープ ---
    text = escape(text)

    # --- プレースホルダをHTMLタグに復元 ---
    text = text.replace("\x00B_START\x00", '<b>')
    text = text.replace("\x00B_END\x00", "</b>")
    text = text.replace("\x00TCY_START\x00", '<span class="tcy">')
    text = text.replace("\x00TCY_END\x00", "</span>")
    text = text.replace("\x00DAKUTEN_START\x00", '<span class="dakuten">')
    text = text.replace("\x00DAKUTEN_END\x00", "</span>")
    text = text.replace("\x00SESAME_START\x00", '<em class="sesame">')
    text = text.replace("\x00SESAME_END\x00", "</em>")
    text = text.replace("\x00TATESEN\x00", "｜")

    # ルビ: ｜base《ruby》
    text = re.sub(
        r"｜(.+?)《(.+?)》",
        r"<ruby>\1<rt>\2</rt></ruby>",
        text,
    )

    # ルビ: 漢字連続《ruby》（｜なし）
    text = re.sub(
        f"([{_KANJI_CHARS}]+)《(.+?)》",
        r"<ruby>\1<rt>\2</rt></ruby>",
        text,
    )

    # 残った注記で未処理のもの → hidden span
    text = re.sub(
        r"［＃(.+?)］",
        lambda m: f'<span class="note" hidden="">[{m.group(1)}]</span>',
        text,
    )

    return text
