import tempfile
import zipfile
from pathlib import Path

from narou.parser import ParsedSection, parse_text
from narou.epub_writer import EpubSection, write_epub


def _make_sections() -> list[EpubSection]:
    """テスト用の3話構成を作成"""
    sections = []
    for i in range(1, 4):
        parsed = parse_text(f"　第{i}話の本文です。\n　テスト。")
        sections.append(EpubSection(
            index=i,
            title=f"第{i}話 テスト",
            parsed=parsed,
        ))
    return sections


def test_write_epub_creates_file():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        result = write_epub(
            title="テスト小説",
            author="テスト著者",
            sections=sections,
            output_path=out,
        )
        assert result.exists()
        assert result.stat().st_size > 0


def test_epub_is_valid_zip():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)
        assert zipfile.is_zipfile(out)


def test_epub_contains_required_files():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)

        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "META-INF/container.xml" in names
            assert "OEBPS/content.opf" in names
            assert "OEBPS/toc.xhtml" in names
            assert "OEBPS/Styles/style.css" in names
            assert "OEBPS/Text/cover.xhtml" in names
            assert "OEBPS/Text/titlepage.xhtml" in names


def test_epub_contains_sections():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)

        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            assert "OEBPS/Text/section_0001.xhtml" in names
            assert "OEBPS/Text/section_0002.xhtml" in names
            assert "OEBPS/Text/section_0003.xhtml" in names


def test_epub_mimetype_is_first():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)

        with zipfile.ZipFile(out) as zf:
            assert zf.namelist()[0] == "mimetype"
            # mimetypeは無圧縮
            info = zf.getinfo("mimetype")
            assert info.compress_type == zipfile.ZIP_STORED


def test_epub_content_opf_has_metadata():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト小説タイトル", "著者名", sections, out)

        with zipfile.ZipFile(out) as zf:
            opf = zf.read("OEBPS/content.opf").decode("utf-8")
            assert "テスト小説タイトル" in opf
            assert "著者名" in opf
            assert "ja" in opf
            assert 'page-progression-direction="rtl"' in opf


def test_epub_toc_has_sections():
    sections = _make_sections()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)

        with zipfile.ZipFile(out) as zf:
            toc = zf.read("OEBPS/toc.xhtml").decode("utf-8")
            assert "第1話 テスト" in toc
            assert "第2話 テスト" in toc
            assert "第3話 テスト" in toc


def test_epub_toc_with_chapters():
    """章グルーピングのテスト"""
    sections = [
        EpubSection(1, "第1話", parse_text("テスト"), chapter="第一章"),
        EpubSection(2, "第2話", parse_text("テスト"), chapter="第一章"),
        EpubSection(3, "第3話", parse_text("テスト"), chapter="第二章"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)

        with zipfile.ZipFile(out) as zf:
            toc = zf.read("OEBPS/toc.xhtml").decode("utf-8")
            assert "第一章" in toc
            assert "第二章" in toc


def test_epub_section_content():
    sections = [
        EpubSection(1, "テスト話", parse_text("　本文テスト。")),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out)

        with zipfile.ZipFile(out) as zf:
            content = zf.read("OEBPS/Text/section_0001.xhtml").decode("utf-8")
            assert "本文テスト" in content
            assert "テスト話" in content
            assert "vertical-rl" in zf.read("OEBPS/Styles/style.css").decode("utf-8")


def test_epub_with_sitename():
    sections = [EpubSection(1, "話", parse_text("テスト"))]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out, sitename="小説家になろう")

        with zipfile.ZipFile(out) as zf:
            titlepage = zf.read("OEBPS/Text/titlepage.xhtml").decode("utf-8")
            assert "小説家になろう" in titlepage


def test_epub_with_images():
    parsed = parse_text("　テスト")
    parsed.images.append(ParsedSection().images.__class__())  # 不要
    # 直接ImageRefを使う
    from narou.parser import ImageRef
    parsed_with_img = parse_text("［＃挿絵（test.png）入る］")
    sections = [EpubSection(1, "話", parsed_with_img)]
    image_data = {"test.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 100}

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        write_epub("テスト", "著者", sections, out, image_data=image_data)

        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            assert "OEBPS/Images/test.png" in names
