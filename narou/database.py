import sqlite3
from datetime import datetime
from pathlib import Path

from narou.models import Novel


class Database:
    """小説メタデータを管理するSQLiteデータベース"""

    ARCHIVE_ROOT = "小説データ"

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS novels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                toc_url TEXT NOT NULL UNIQUE,
                sitename TEXT NOT NULL DEFAULT '',
                novel_type INTEGER NOT NULL DEFAULT 1,
                is_end INTEGER NOT NULL DEFAULT 0,
                last_update TEXT,
                new_arrivals_date TEXT,
                general_all_no INTEGER NOT NULL DEFAULT 0,
                use_subdirectory INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '',
                file_title TEXT NOT NULL DEFAULT '',
                story TEXT NOT NULL DEFAULT '',
                archive_path TEXT NOT NULL DEFAULT ''
            )
        """)
        self.conn.commit()

    def _row_to_novel(self, row: sqlite3.Row) -> Novel:
        return Novel(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            toc_url=row["toc_url"],
            sitename=row["sitename"],
            novel_type=row["novel_type"],
            is_end=bool(row["is_end"]),
            last_update=datetime.fromisoformat(row["last_update"]) if row["last_update"] else None,
            new_arrivals_date=datetime.fromisoformat(row["new_arrivals_date"]) if row["new_arrivals_date"] else None,
            general_all_no=row["general_all_no"],
            use_subdirectory=bool(row["use_subdirectory"]),
            tags=row["tags"].split(",") if row["tags"] else [],
            file_title=row["file_title"],
            story=row["story"],
            archive_path=row["archive_path"],
        )

    def add_novel(self, novel: Novel) -> int:
        cur = self.conn.execute(
            """INSERT INTO novels
               (title, author, toc_url, sitename, novel_type, is_end,
                last_update, new_arrivals_date, general_all_no,
                use_subdirectory, tags, file_title, story, archive_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                novel.title, novel.author, novel.toc_url, novel.sitename,
                novel.novel_type, int(novel.is_end),
                novel.last_update.isoformat() if novel.last_update else None,
                novel.new_arrivals_date.isoformat() if novel.new_arrivals_date else None,
                novel.general_all_no, int(novel.use_subdirectory),
                ",".join(novel.tags), novel.file_title, novel.story, novel.archive_path,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_novel(self, novel_id: int) -> Novel | None:
        row = self.conn.execute("SELECT * FROM novels WHERE id = ?", (novel_id,)).fetchone()
        return self._row_to_novel(row) if row else None

    def get_novel_by_url(self, toc_url: str) -> Novel | None:
        row = self.conn.execute("SELECT * FROM novels WHERE toc_url = ?", (toc_url,)).fetchone()
        return self._row_to_novel(row) if row else None

    def update_novel(self, novel: Novel) -> None:
        self.conn.execute(
            """UPDATE novels SET
               title=?, author=?, toc_url=?, sitename=?, novel_type=?, is_end=?,
               last_update=?, new_arrivals_date=?, general_all_no=?,
               use_subdirectory=?, tags=?, file_title=?, story=?, archive_path=?
               WHERE id=?""",
            (
                novel.title, novel.author, novel.toc_url, novel.sitename,
                novel.novel_type, int(novel.is_end),
                novel.last_update.isoformat() if novel.last_update else None,
                novel.new_arrivals_date.isoformat() if novel.new_arrivals_date else None,
                novel.general_all_no, int(novel.use_subdirectory),
                ",".join(novel.tags), novel.file_title, novel.story, novel.archive_path,
                novel.id,
            ),
        )
        self.conn.commit()

    def delete_novel(self, novel_id: int) -> None:
        self.conn.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
        self.conn.commit()

    # ORDER BY にはパラメータバインディングが使えないためホワイトリストで検証
    _ALLOWED_SORT_COLUMNS = frozenset({"last_update", "title", "author", "id", "new_arrivals_date"})

    def list_novels(self, sort_by: str = "last_update") -> list[Novel]:
        if sort_by not in self._ALLOWED_SORT_COLUMNS:
            sort_by = "last_update"
        rows = self.conn.execute(f"SELECT * FROM novels ORDER BY {sort_by} DESC").fetchall()
        return [self._row_to_novel(row) for row in rows]

    def search_novels(self, query: str) -> list[Novel]:
        pattern = f"%{query}%"
        rows = self.conn.execute(
            "SELECT * FROM novels WHERE title LIKE ? OR author LIKE ? ORDER BY last_update DESC",
            (pattern, pattern),
        ).fetchall()
        return [self._row_to_novel(row) for row in rows]

    def close(self) -> None:
        self.conn.close()
