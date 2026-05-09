"""EPUB 3.0ファイルを生成するモジュール。

複数話構成のWeb小説をEPUBに変換する。
AosoraDownloaderのepub_writer.pyをnarou用に適応。
"""

import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .parser import ImageRef, ParsedSection

MIMETYPE = "application/epub+zip"

CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

STYLE_CSS = """\
@charset "UTF-8";
html {
  writing-mode: vertical-rl;
  -webkit-writing-mode: vertical-rl;
  -epub-writing-mode: vertical-rl;
}
body {
  font-family: serif;
  line-height: 1.8;
  margin: 1em;
}
h1 { font-size: 1.5em; margin: 2em 0.5em; }
h2 { font-size: 1.3em; margin: 1.5em 0.5em; }
h3 { font-size: 1.1em; margin: 1em 0.5em; }
p { text-indent: 1em; margin: 0; }
ruby rt { font-size: 0.5em; }
em.sesame {
  text-emphasis-style: sesame;
  -webkit-text-emphasis-style: sesame;
  font-style: normal;
}
span.tcy {
  text-combine-upright: all;
  -webkit-text-combine: horizontal;
  -epub-text-combine: horizontal;
}
span.dakuten {
  text-combine-upright: all;
  -webkit-text-combine: horizontal;
}
hr.pagebreak {
  page-break-after: always;
  border: none;
  margin: 0;
}
hr.separator {
  border: none;
  border-top: 1px solid #999;
  margin: 2em auto;
  width: 30%;
}
div.illustration {
  text-align: center;
  margin: 1em 0;
}
div.illustration img {
  max-width: 100%;
  max-height: 100%;
}
p.hang-indent {
  text-indent: 0.5em;
  margin: 0;
}
div.preface {
  margin-bottom: 2em;
  border-bottom: 1px dashed #ccc;
  padding-bottom: 1em;
}
div.postscript {
  margin-top: 2em;
  border-top: 1px dashed #ccc;
  padding-top: 1em;
}
/* タイトルページ */
body.titlepage {
  writing-mode: vertical-rl;
  -webkit-writing-mode: vertical-rl;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  text-align: center;
}
body.titlepage h1 {
  font-size: 2em;
  margin: 1em 0.5em;
  border-right: 3px solid #333;
  padding-right: 0.5em;
}
body.titlepage .author {
  font-size: 1.2em;
  margin: 0.5em;
}
body.titlepage .source {
  font-size: 0.8em;
  color: #888;
  margin-top: 2em;
}
/* カバーページ */
body.coverpage {
  writing-mode: horizontal-tb;
  margin: 0;
  padding: 0;
  text-align: center;
}
body.coverpage svg {
  width: 100%;
  height: 100%;
}
"""


class EpubSection:
    """EPUB内の1話分のデータ"""

    def __init__(self, index: int, title: str, parsed: ParsedSection,
                 chapter: str = ""):
        self.index = index
        self.title = title
        self.parsed = parsed
        self.chapter = chapter  # 章タイトル（あれば）
        self.filename = f"section_{index:04d}.xhtml"


def write_epub(
    title: str,
    author: str,
    sections: list[EpubSection],
    output_path: str | Path,
    sitename: str = "",
    toc_url: str = "",
    image_data: dict[str, bytes] | None = None,
) -> Path:
    """複数話構成のWeb小説をEPUBファイルに変換する。

    Args:
        title: 小説タイトル
        author: 著者名
        sections: 各話のデータリスト
        output_path: 出力ファイルパス
        sitename: サイト名（ソース表記用）
        toc_url: 目次ページURL
        image_data: {ファイル名: バイトデータ} の辞書
    """
    output_path = Path(output_path)
    book_id = str(uuid.uuid4())
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 全セクションの画像を収集
    all_images: list[ImageRef] = []
    actual_image_data: dict[str, bytes] = {}
    if image_data:
        for sec in sections:
            for img in sec.parsed.images:
                if img.filename in image_data and img.filename not in actual_image_data:
                    all_images.append(img)
                    actual_image_data[img.filename] = image_data[img.filename]

    content_opf = _build_content_opf(
        book_id, title, author, modified,
        sections=sections,
        images=all_images,
    )
    toc_xhtml = _build_toc_xhtml(title, sections)
    toc_ncx = _build_toc_ncx(book_id, title, sections)
    titlepage_xhtml = _build_titlepage_xhtml(title, author, sitename)
    cover_xhtml = _build_cover_xhtml(title, author)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetypeは無圧縮で最初に格納
        zf.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/toc.xhtml", toc_xhtml)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/Styles/style.css", STYLE_CSS)
        zf.writestr("OEBPS/Text/cover.xhtml", cover_xhtml)
        zf.writestr("OEBPS/Text/titlepage.xhtml", titlepage_xhtml)

        # 各話のXHTMLを格納
        for sec in sections:
            section_xhtml = _build_section_xhtml(sec)
            zf.writestr(f"OEBPS/Text/{sec.filename}", section_xhtml)

        # 画像ファイルを格納
        for filename, data in actual_image_data.items():
            zf.writestr(f"OEBPS/Images/{filename}", data)

    return output_path


def _build_content_opf(
    book_id: str,
    title: str,
    author: str,
    modified: str,
    sections: list[EpubSection] | None = None,
    images: list[ImageRef] | None = None,
) -> str:
    sections = sections or []
    images = images or []

    # manifest items
    manifest_items = [
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '    <item id="nav" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="css" href="Styles/style.css" media-type="text/css"/>',
        '    <item id="cover" href="Text/cover.xhtml" media-type="application/xhtml+xml" properties="svg"/>',
        '    <item id="titlepage" href="Text/titlepage.xhtml" media-type="application/xhtml+xml"/>',
    ]

    for sec in sections:
        item_id = f"section_{sec.index:04d}"
        manifest_items.append(
            f'    <item id="{item_id}" href="Text/{sec.filename}" media-type="application/xhtml+xml"/>'
        )

    for i, img in enumerate(images):
        ext = img.filename.rsplit(".", 1)[-1].lower()
        media_type = {
            "png": "image/png", "jpg": "image/jpeg",
            "jpeg": "image/jpeg", "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "image/png")
        manifest_items.append(
            f'    <item id="img{i}" href="Images/{_xml_escape(img.filename)}" media-type="{media_type}"/>'
        )

    manifest_str = "\n".join(manifest_items)

    # spine items
    spine_items = [
        '    <itemref idref="cover"/>',
        '    <itemref idref="titlepage"/>',
    ]
    for sec in sections:
        item_id = f"section_{sec.index:04d}"
        spine_items.append(f'    <itemref idref="{item_id}"/>')
    spine_str = "\n".join(spine_items)

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         unique-identifier="BookId" xml:lang="ja">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">urn:uuid:{book_id}</dc:identifier>
    <dc:title>{_xml_escape(title)}</dc:title>
    <dc:language>ja</dc:language>
    <dc:creator>{_xml_escape(author)}</dc:creator>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
{manifest_str}
  </manifest>
  <spine toc="ncx" page-progression-direction="rtl">
{spine_str}
  </spine>
</package>"""


def _build_cover_xhtml(title: str, author: str) -> str:
    """SVGベースのカバーページを生成する。"""
    esc_title = _xml_escape(title)
    esc_author = _xml_escape(author)

    title_lines = _wrap_text(title, 10)
    title_tspans = ""
    start_y = max(200, 400 - len(title_lines) * 50)
    for i, tl in enumerate(title_lines):
        title_tspans += f'      <tspan x="300" dy="{0 if i == 0 else 60}">{_xml_escape(tl)}</tspan>\n'

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja">
<head>
  <title>{esc_title}</title>
  <link rel="stylesheet" type="text/css" href="../Styles/style.css"/>
</head>
<body class="coverpage">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" preserveAspectRatio="xMidYMid meet">
    <rect width="600" height="800" fill="#f5f0e8"/>
    <rect x="30" y="30" width="540" height="740" fill="none" stroke="#8b7355" stroke-width="2"/>
    <rect x="35" y="35" width="530" height="730" fill="none" stroke="#8b7355" stroke-width="0.5"/>
    <text text-anchor="middle" font-family="serif" font-size="42" fill="#333" y="{start_y}">
{title_tspans}    </text>
    <line x1="200" y1="550" x2="400" y2="550" stroke="#8b7355" stroke-width="1"/>
    <text text-anchor="middle" font-family="serif" font-size="24" fill="#555" x="300" y="600">
      {esc_author}
    </text>
  </svg>
</body>
</html>"""


def _build_titlepage_xhtml(title: str, author: str, sitename: str) -> str:
    """タイトルページXHTMLを生成する。"""
    esc_title = _xml_escape(title)
    esc_author = _xml_escape(author)

    source_html = ""
    if sitename:
        source_html = f'\n  <p class="source">{_xml_escape(sitename)}</p>'

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja">
<head>
  <title>{esc_title}</title>
  <link rel="stylesheet" type="text/css" href="../Styles/style.css"/>
</head>
<body class="titlepage">
  <h1>{esc_title}</h1>
  <p class="author">{esc_author}</p>{source_html}
</body>
</html>"""


def _build_toc_xhtml(title: str, sections: list[EpubSection]) -> str:
    """目次XHTMLを生成する。章でグルーピングする。"""
    toc_items = ""
    current_chapter = None

    for sec in sections:
        if sec.chapter and sec.chapter != current_chapter:
            if current_chapter is not None:
                toc_items += "      </ol>\n      </li>\n"
            current_chapter = sec.chapter
            toc_items += f'      <li><span>{_xml_escape(current_chapter)}</span>\n      <ol>\n'

        indent = "        " if current_chapter else "      "
        toc_items += f'{indent}<li><a href="Text/{sec.filename}">{_xml_escape(sec.title)}</a></li>\n'

    if current_chapter is not None:
        toc_items += "      </ol>\n      </li>\n"

    if not toc_items:
        toc_items = f'      <li><a href="Text/titlepage.xhtml">{_xml_escape(title)}</a></li>\n'

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ja">
<head>
  <title>目次</title>
</head>
<body>
  <nav epub:type="toc">
    <h1>目次</h1>
    <ol>
{toc_items}    </ol>
  </nav>
</body>
</html>"""


def _build_toc_ncx(book_id: str, title: str, sections: list[EpubSection]) -> str:
    """EPUB2互換のNCX目次を生成する。"""
    nav_points = ""
    play_order = 1

    for sec in sections:
        nav_points += f"""\
    <navPoint id="navPoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>{_xml_escape(sec.title)}</text></navLabel>
      <content src="Text/{sec.filename}"/>
    </navPoint>
"""
        play_order += 1

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{_xml_escape(title)}</text></docTitle>
  <navMap>
{nav_points}  </navMap>
</ncx>"""


def _build_section_xhtml(sec: EpubSection) -> str:
    """各話のXHTMLを生成する。"""
    esc_title = _xml_escape(sec.title)
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja">
<head>
  <title>{esc_title}</title>
  <link rel="stylesheet" type="text/css" href="../Styles/style.css"/>
</head>
<body>
<h2>{esc_title}</h2>
{sec.parsed.body_xhtml}
</body>
</html>"""


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """テキストを指定文字数で折り返す。"""
    lines = []
    while text:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    return lines
