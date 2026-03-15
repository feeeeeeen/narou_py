from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Novel:
    """小説メタデータ"""
    id: int = 0
    title: str = ""
    author: str = ""
    toc_url: str = ""
    sitename: str = ""
    novel_type: int = 1          # 1=連載, 2=短編
    is_end: bool = False
    last_update: datetime | None = None
    new_arrivals_date: datetime | None = None
    general_all_no: int = 0      # 全話数
    use_subdirectory: bool = False
    tags: list[str] = field(default_factory=list)
    file_title: str = ""
    story: str = ""
    archive_path: str = ""       # 小説データディレクトリ


@dataclass
class Chapter:
    """目次の1エピソード"""
    index: int = 0
    subtitle: str = ""
    href: str = ""
    chapter: str = ""            # 章タイトル
    subdate: str = ""            # 初回掲載日
    subupdate: str = ""          # 更新日


@dataclass
class Section:
    """1話分の本文データ"""
    subtitle: str = ""
    chapter: str = ""
    element: dict[str, str] = field(default_factory=dict)
    # element keys: introduction, body, postscript
