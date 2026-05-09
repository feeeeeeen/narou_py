import gzip
import http.client
import logging
import re
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests
import yaml

# yaml.CSafeDumper が利用可能なら使う（17倍高速）
_yaml_dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)

logger = logging.getLogger(__name__)

from narou.database import Database
from narou.helpers import pretreatment_source, safe_filename
from narou.html_to_aozora import html_to_aozora
from narou.http_utils import USER_AGENT
from narou.models import Chapter, Novel, Section
from narou.novel_info import NovelInfo
from narou.site_setting import SiteSetting, _ruby_regex_to_python

SECTION_SAVE_DIR = "本文"
RAW_DATA_DIR = "raw"
TOC_FILE_NAME = "toc.yaml"
WAITING_TIME_FOR_503 = 20
RETRY_MAX_FOR_503 = 5
# ウェイト管理（narou_rb準拠）
STEPS_WAIT_TIME = 5       # N話ごとのウェイト秒数
DEFAULT_INTERVAL = 0      # 各話間の基本間隔（秒）。0=ウェイトなし
DEFAULT_WAIT_STEPS = 0    # N話ごとにウェイトを入れる（0=サイト依存）
NAROU_WAIT_STEPS = 10     # なろう系サイトのデフォルト（10話ごと）
NOVEL_TYPE_SERIES = 1
NOVEL_TYPE_SS = 2


class DownloadResult:
    """ダウンロード結果"""
    def __init__(self, novel_id: int = 0, new_arrivals: bool = False,
                 status: str = "none", novel: Novel | None = None):
        self.novel_id = novel_id
        self.new_arrivals = new_arrivals
        self.status = status  # "ok", "none", "failed", "canceled"
        self.novel = novel


class NovelDownloader:
    """小説ダウンロードエンジン

    narou_rb の Downloader クラスをPythonに移植。
    """

    def __init__(self, db: Database, base_dir: Path,
                 session: requests.Session | None = None):
        self.db = db
        self.base_dir = base_dir
        self.archive_root = base_dir / Database.ARCHIVE_ROOT
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.site_settings = self._load_site_settings()
        self._novel_info_client = NovelInfo(self.session)
        # ウェイト管理（narou_rb準拠: N話ごとにバッチウェイト）
        self._interval_sleep_time = DEFAULT_INTERVAL
        self._max_steps_wait_time = max(STEPS_WAIT_TIME, self._interval_sleep_time)
        self._wait_counter = 0
        self._last_download_time = time.time() - 20  # 初回はカウンタリセット
        # http.client 持続接続キャッシュ（ホスト→接続）
        self._ssl_ctx = ssl.create_default_context()
        self._connections: dict[str, http.client.HTTPSConnection | http.client.HTTPConnection] = {}

    def _load_site_settings(self) -> list[SiteSetting]:
        """webnovel/*.yaml からサイト定義をすべて読み込む"""
        webnovel_dir = self._find_webnovel_dir()
        settings = []
        for yaml_path in sorted(webnovel_dir.glob("*.yaml")):
            settings.append(SiteSetting.load_file(yaml_path))
        return settings

    def _find_webnovel_dir(self) -> Path:
        """webnovel/ ディレクトリを探す"""
        # 実行ファイルと同じディレクトリ or base_dir
        candidates = [
            self.base_dir / "webnovel",
            Path(__file__).parent.parent / "webnovel",
        ]
        for d in candidates:
            if d.exists():
                return d
        raise FileNotFoundError("webnovel/ ディレクトリが見つかりません")

    # ========== メインAPI ==========

    def download(self, target: str, force: bool = False,
                 progress_callback: Callable[[int, int, str], None] | None = None) -> DownloadResult:
        """小説をダウンロードする

        Args:
            target: URL, Nコード, または小説ID
            force: 全話強制ダウンロード
            progress_callback: (current, total, message) の進捗コールバック
        """
        setting = self._resolve_target(target)
        if not setting:
            return DownloadResult(status="failed")

        return self._run_download(setting, force, progress_callback)

    def fetch_novel_metadata(self, url: str) -> dict | None:
        """URL からサイト判定・目次取得を行いメタデータ辞書を返す（GUI 追加用）。

        Returns:
            {"toc_url", "title", "author", "sitename", "novel_type", "general_all_no"}
            の辞書。サイト未対応または取得失敗時は None。
        """
        setting = self._resolve_target(url)
        if setting is None:
            return None

        toc = self._get_table_of_contents(setting)
        if toc is None:
            return None

        return {
            "toc_url": setting["toc_url"],
            "title": toc.get("title", "不明"),
            "author": toc.get("author", "不明"),
            "sitename": setting.get_raw("name") or "",
            "novel_type": toc.get("novel_type", 0),
            "general_all_no": len(toc.get("subtitles", [])),
        }

    def close(self) -> None:
        """持続接続キャッシュを閉じる。

        DownloadWorker などの呼び出し元は処理終了後にこのメソッドを呼ぶことで、
        TIME_WAIT に残る HTTP/HTTPS 接続を明示的に解放できる。
        """
        for conn in self._connections.values():
            try:
                conn.close()
            except OSError:
                pass
        self._connections.clear()

    def _resolve_target(self, target: str) -> SiteSetting | None:
        """入力をサイト設定に解決する。

        SiteSetting は self.site_settings として共有されるため、複数回 resolve すると
        前回の `_match_values` が残留して別小説の値を引き継ぐ恐れがある。冒頭で全設定の
        `clear()` を呼び、毎回まっさらな状態から照合する。
        """
        # 残留マッチ値のクリア（複数 URL を順次解決する場合の値混入防止）
        for setting in self.site_settings:
            setting.clear()

        target_lower = target.strip().lower()

        # URL の場合
        if target_lower.startswith("http"):
            for setting in self.site_settings:
                if setting.multi_match(target_lower, "url"):
                    ncode = setting.matched("ncode")
                    if ncode:
                        setting["ncode"] = ncode.lower()
                    return setting
            return None

        # Nコード の場合
        if re.match(r"^n\d+[a-z]+$", target_lower):
            # なろうのサイト設定を使用
            for setting in self.site_settings:
                if setting.get_raw("name") == "小説家になろう":
                    setting["ncode"] = target_lower
                    return setting
            return None

        # 数値ID の場合
        try:
            novel_id = int(target)
            novel = self.db.get_novel(novel_id)
            if novel:
                for setting in self.site_settings:
                    if setting.multi_match(novel.toc_url.lower(), "url"):
                        ncode = setting.matched("ncode")
                        if ncode:
                            setting["ncode"] = ncode.lower()
                        return setting
        except ValueError:
            pass

        return None

    def _run_download(self, setting: SiteSetting, force: bool,
                      progress_callback: Callable | None) -> DownloadResult:
        """ダウンロード処理本体"""
        # 目次取得
        toc = self._get_table_of_contents(setting)
        if not toc:
            return DownloadResult(status="failed")

        title = toc["title"]
        author = toc.get("author", "")
        toc_url = setting["toc_url"]

        # DB検索・新規/既存判定
        existing = self.db.get_novel_by_url(toc_url)
        is_new = existing is None

        # 小説データディレクトリ
        sitename = setting.get_raw("name") or ""
        ncode = setting.matched("ncode") or ""
        file_title = ncode
        if setting.get_raw("append_title_to_folder_name"):
            file_title += " " + safe_filename(title).strip()

        archive_path = self.archive_root / sitename / file_title
        archive_path.mkdir(parents=True, exist_ok=True)
        (archive_path / SECTION_SAVE_DIR).mkdir(exist_ok=True)
        (archive_path / RAW_DATA_DIR).mkdir(exist_ok=True)

        # 既存目次との差分チェック
        old_toc = self._load_toc(archive_path)
        subtitles = toc["subtitles"]

        if old_toc and not force:
            update_subtitles = self._update_body_check(
                old_toc.get("subtitles", []), subtitles
            )
        else:
            update_subtitles = subtitles

        new_arrivals = is_new or len(update_subtitles) > 0

        # 各話ダウンロード
        novel_type = self._detect_novel_type(setting, toc)
        downloaded_count = 0
        total = len(update_subtitles)

        # ウェイトステップ数を決定（narou_rb準拠）
        download_wait_steps = DEFAULT_WAIT_STEPS
        if setting.get_raw("is_narou"):
            if download_wait_steps > NAROU_WAIT_STEPS or download_wait_steps == 0:
                download_wait_steps = NAROU_WAIT_STEPS

        if total > 0:
            for i, sub_info in enumerate(update_subtitles):
                if progress_callback:
                    progress_callback(i + 1, total, sub_info.get("subtitle", ""))

                element = self._download_section(sub_info, setting, archive_path,
                                                 download_wait_steps)
                self._save_section(archive_path, sub_info, element)
                downloaded_count += 1

        # 目次保存
        self._save_toc(archive_path, toc)

        # DB更新
        novel = existing or Novel()
        novel.title = title
        novel.author = author
        novel.toc_url = toc_url
        novel.sitename = sitename
        novel.novel_type = novel_type
        novel.is_end = toc.get("end", False)
        novel.last_update = datetime.now()
        novel.general_all_no = len(subtitles)
        novel.file_title = file_title
        novel.story = toc.get("story", "")
        novel.archive_path = str(archive_path)

        if is_new:
            novel.new_arrivals_date = datetime.now()
            novel.id = self.db.add_novel(novel)
        else:
            if new_arrivals:
                novel.new_arrivals_date = datetime.now()
            self.db.update_novel(novel)

        status = "ok" if downloaded_count > 0 or is_new else "none"
        return DownloadResult(
            novel_id=novel.id,
            new_arrivals=new_arrivals,
            status=status,
            novel=novel,
        )

    # ========== 目次取得 ==========

    def _get_table_of_contents(self, setting: SiteSetting) -> dict | None:
        """目次ページを取得してパースする"""
        toc_url = setting["toc_url"]
        if not toc_url:
            return None

        cookie = setting.get_raw("cookie") or ""
        headers = {}
        if cookie:
            headers["Cookie"] = cookie

        try:
            toc_source = self._http_get(toc_url, headers=headers)
        except requests.RequestException as e:
            logger.warning("目次ページの取得に失敗: %s - %s", toc_url, e)
            return None

        # メタデータ取得（NovelInfo経由）
        info = self._novel_info_client.load(setting)
        if not info or not info.get("title"):
            # 小説情報が取れなければ目次ページから直接パース
            setting.multi_match(toc_source, "title", "author", "story")
            if not setting.matched("title"):
                return None
            info = {
                "title": setting.matched("title"),
                "writer": setting.matched("author") or "",
                "story": html_to_aozora(setting.matched("story") or ""),
                "end": False,
                "novel_type": 1,
            }

        title = info["title"]

        # 連載/短編判定
        novel_type = info.get("novel_type", 1)
        if novel_type == NOVEL_TYPE_SERIES:
            subtitles = self._parse_subtitles(toc_source, setting)
            # ページネーション対応
            subtitles = self._fetch_all_toc_pages(subtitles, toc_source, setting, headers)
        else:
            subtitles = self._create_short_story_subtitles(setting, info)

        return {
            "title": title,
            "author": info.get("writer", ""),
            "toc_url": toc_url,
            "story": info.get("story", ""),
            "end": info.get("end", False),
            "novel_type": novel_type,
            "subtitles": subtitles,
        }

    def _parse_subtitles(self, toc_source: str, setting: SiteSetting) -> list[dict]:
        """目次HTMLからエピソード一覧を抽出する"""
        subtitles = []
        remaining = toc_source
        pattern_str = setting["subtitles"]
        if not pattern_str:
            return subtitles

        py_pattern = _ruby_regex_to_python(pattern_str)
        while remaining:
            m = re.search(py_pattern, remaining, re.DOTALL)
            if not m:
                break
            remaining = remaining[m.end():]
            groups = m.groupdict()
            subtitle_text = (groups.get("subtitle") or "").replace("\t", "").replace("\n", "").strip()
            subtitles.append({
                "index": groups.get("index", ""),
                "href": groups.get("href", ""),
                "chapter": groups.get("chapter") or "",
                "subtitle": subtitle_text,
                "file_subtitle": safe_filename(subtitle_text),
                "subdate": (groups.get("subdate") or "").strip(),
                "subupdate": (groups.get("subupdate") or "").strip(),
            })
        return subtitles

    def _fetch_all_toc_pages(self, subtitles: list[dict], toc_source: str,
                             setting: SiteSetting, headers: dict) -> list[dict]:
        """目次のページネーションを処理する"""
        toc_next_pattern = setting["toc_next_url"]
        if not toc_next_pattern:
            return subtitles

        current_source = toc_source
        py_pattern = _ruby_regex_to_python(toc_next_pattern)
        while True:
            m = re.search(py_pattern, current_source, re.DOTALL)
            if not m:
                break
            next_path = m.groupdict().get("toc_next_url", "")
            if not next_path:
                break
            next_url = setting["top_url"] + next_path
            try:
                current_source = self._http_get(next_url, headers=headers)
            except requests.RequestException as e:
                logger.warning("目次ページネーション取得失敗: %s - %s", next_url, e)
                break
            page_subtitles = self._parse_subtitles(current_source, setting)
            if not page_subtitles:
                break
            subtitles.extend(page_subtitles)
        return subtitles

    def _create_short_story_subtitles(self, setting: SiteSetting, info: dict) -> list[dict]:
        """短編用の目次情報を生成"""
        title = setting["title"] or info.get("title", "")
        return [{
            "index": "1",
            "href": setting.replace_group_values("href", {"index": "1"}) or "/1/",
            "chapter": "",
            "subtitle": title,
            "file_subtitle": safe_filename(title),
            "subdate": str(info.get("general_firstup", "")),
            "subupdate": str(info.get("novelupdated_at", "")),
        }]

    # ========== 各話ダウンロード ==========

    def _download_section(self, subtitle_info: dict, setting: SiteSetting,
                          archive_path: Path,
                          download_wait_steps: int = 0) -> dict:
        """1話分のHTMLを取得し、本文・前書き・後書きに分割する"""
        self._sleep_for_download(download_wait_steps)

        href = subtitle_info["href"]
        if href.startswith("/"):
            url = setting["top_url"] + href
        else:
            url = setting["toc_url"] + href

        cookie = setting.get_raw("cookie") or ""
        headers = {"Cookie": cookie} if cookie else {}
        raw = self._http_get(url, headers=headers)

        # 生データ保存
        self._save_raw_data(archive_path, subtitle_info, raw)

        if setting.get_raw("is_narou"):
            element = self._extract_elements_from_narou_html(raw)
            element["data_type"] = "text"
        else:
            setting.multi_match(raw, "body_pattern", "introduction_pattern", "postscript_pattern")
            element = {"data_type": "html"}
            for part in ("introduction", "body", "postscript"):
                element[part] = setting.matched(part) or ""

        return element

    def _extract_elements_from_narou_html(self, html: str) -> dict:
        """なろうHTML本文ページからテキストを抽出する"""
        element = {"introduction": "", "body": "", "postscript": ""}

        # 前書き
        m = re.search(
            r'<div class="js-novel-text p-novel__text p-novel__text--preface">(.*?)</div>',
            html, re.DOTALL,
        )
        if m:
            element["introduction"] = self._html_to_text(m.group(1))

        # 本文（preface でも afterword でもないもの）
        m = re.search(
            r'<div class="js-novel-text p-novel__text">\s*(.*?)\s*</div>',
            html, re.DOTALL,
        )
        if m:
            element["body"] = self._html_to_text(m.group(1))

        # 後書き
        m = re.search(
            r'<div class="js-novel-text p-novel__text p-novel__text--afterword">(.*?)</div>',
            html, re.DOTALL,
        )
        if m:
            element["postscript"] = self._html_to_text(m.group(1))

        return element

    @staticmethod
    def _html_to_text(html: str) -> str:
        """HTML断片をプレーンテキストに変換する（なろう本文用）"""
        text = html
        # <br> → 改行
        text = re.sub(r"<br\s*/?>", "\n", text)
        # <p>...</p> → 中身 + 改行
        text = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: m.group(1) + "\n", text, flags=re.DOTALL)
        # ルビ（フル形式）
        text = re.sub(
            r"<ruby>([^<]*)<rb>([^<]*)</rb><rp>[^<]*</rp><rt>([^<]*)</rt><rp>[^<]*</rp></ruby>",
            lambda m: f"｜{m.group(2)}《{m.group(3)}》",
            text,
        )
        # ルビ（シンプル形式）
        text = re.sub(
            r"<ruby>([^<]*)<rt>([^<]*)</rt></ruby>",
            lambda m: f"｜{m.group(1)}《{m.group(2)}》",
            text,
        )
        # 残りのHTMLタグを除去
        text = re.sub(r"<[^>]+>", "", text)
        # HTMLエンティティ
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&nbsp;", " ")
        # 連続空行を整理
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ========== 差分チェック ==========

    def _update_body_check(self, old_subtitles: list[dict],
                           latest_subtitles: list[dict]) -> list[dict]:
        """更新された話のみを返す"""
        old_by_index = {s["index"]: s for s in old_subtitles}
        update_list = []
        for latest in latest_subtitles:
            idx = latest["index"]
            old = old_by_index.get(idx)
            if not old:
                update_list.append(latest)
                continue
            # タイトル変更
            if old.get("subtitle") != latest.get("subtitle"):
                update_list.append(latest)
                continue
            # 章変更
            if old.get("chapter") != latest.get("chapter"):
                update_list.append(latest)
                continue
            # 更新日チェック
            old_update = old.get("subupdate") or old.get("subdate", "")
            latest_update = latest.get("subupdate") or latest.get("subdate", "")
            if latest_update > old_update:
                update_list.append(latest)
                continue
            # download_time を引き継ぐ
            latest["download_time"] = old.get("download_time")
        return update_list

    # ========== HTTP ==========

    def _get_connection(self, parsed) -> http.client.HTTPSConnection | http.client.HTTPConnection:
        """ホストごとの持続接続を取得（なければ作成）"""
        host = parsed.hostname
        port = parsed.port
        key = f"{parsed.scheme}://{host}:{port or ''}"

        conn = self._connections.get(key)
        if conn is not None:
            return conn

        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(
                host, port=port or 443, context=self._ssl_ctx, timeout=30
            )
        else:
            conn = http.client.HTTPConnection(host, port=port or 80, timeout=30)
        self._connections[key] = conn
        return conn

    def _http_get(self, url: str, headers: dict | None = None) -> str:
        """http.client 持続接続による高速HTTP GET（503リトライ・適応型バックオフ連携）"""
        retry_count = RETRY_MAX_FOR_503
        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        req_headers = {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if headers:
            req_headers.update(headers)

        while True:
            conn = self._get_connection(parsed)
            try:
                conn.request("GET", path, headers=req_headers)
                resp = conn.getresponse()

                if resp.status == 503 and retry_count > 0:
                    resp.read()  # レスポンスボディを消費して接続を再利用可能にする
                    retry_count -= 1
                    time.sleep(WAITING_TIME_FOR_503)
                    continue

                if resp.status >= 400:
                    resp.read()
                    raise requests.exceptions.HTTPError(
                        f"{resp.status} {resp.reason}: {url}", response=None
                    )

                raw_data = resp.read()

                # gzip展開
                encoding = resp.getheader("Content-Encoding", "")
                if "gzip" in encoding:
                    raw_data = gzip.decompress(raw_data)

                charset = resp.headers.get_content_charset() or "utf-8"
                body = raw_data.decode(charset)
                return pretreatment_source(body)

            except (http.client.RemoteDisconnected, ConnectionResetError, OSError):
                # 接続が切れた場合はキャッシュを破棄してリトライ
                key = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}"
                self._connections.pop(key, None)
                if retry_count > 0:
                    retry_count -= 1
                    continue
                raise requests.exceptions.ConnectionError(
                    f"接続エラー: {url}"
                )

    def _sleep_for_download(self, download_wait_steps: int) -> None:
        """narou_rb準拠のダウンロードウェイト

        - 前回DLから max_steps_wait_time 以上経過していればカウンタリセット
        - N話ごとに長めのウェイト（max_steps_wait_time）
        - それ以外は interval_sleep_time（デフォルト0=ウェイトなし）
        """
        if time.time() - self._last_download_time > self._max_steps_wait_time:
            self._wait_counter = 0

        if (download_wait_steps > 0
                and self._wait_counter % download_wait_steps == 0
                and self._wait_counter >= download_wait_steps):
            time.sleep(self._max_steps_wait_time)
        elif self._wait_counter > 0 and self._interval_sleep_time > 0:
            time.sleep(self._interval_sleep_time)

        self._wait_counter += 1
        self._last_download_time = time.time()

    # ========== ファイルI/O ==========

    @staticmethod
    def _validate_path(path: Path, expected_base: Path) -> None:
        """パスが期待するベースディレクトリ内に収まることを検証する"""
        resolved = path.resolve()
        base_resolved = expected_base.resolve()
        if not resolved.is_relative_to(base_resolved):
            raise ValueError(f"不正な保存パス: {path}")

    def _save_raw_data(self, archive_path: Path, subtitle_info: dict, raw: str) -> None:
        """生データを保存"""
        index = subtitle_info["index"]
        file_subtitle = subtitle_info.get("file_subtitle", "")
        raw_dir = archive_path / RAW_DATA_DIR
        raw_dir.mkdir(exist_ok=True)
        path = raw_dir / f"{index} {file_subtitle}.html"
        self._validate_path(path, raw_dir)
        path.write_text(raw, encoding="utf-8")

    def _save_section(self, archive_path: Path, subtitle_info: dict, element: dict) -> None:
        """本文データを保存"""
        index = subtitle_info["index"]
        file_subtitle = subtitle_info.get("file_subtitle", "")
        section_dir = archive_path / SECTION_SAVE_DIR
        section_dir.mkdir(exist_ok=True)
        info = {**subtitle_info, "element": element, "download_time": datetime.now().isoformat()}
        path = section_dir / f"{index} {file_subtitle}.yaml"
        self._validate_path(path, section_dir)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(info, f, allow_unicode=True, default_flow_style=False, Dumper=_yaml_dumper)

    def _save_toc(self, archive_path: Path, toc: dict) -> None:
        """目次データを保存"""
        path = archive_path / TOC_FILE_NAME
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(toc, f, allow_unicode=True, default_flow_style=False, Dumper=_yaml_dumper)

    def _load_toc(self, archive_path: Path) -> dict | None:
        """保存済み目次データを読み込む"""
        path = archive_path / TOC_FILE_NAME
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            logger.warning("目次ファイルの読み込み失敗: %s - %s", path, e)
            return None

    def _detect_novel_type(self, setting: SiteSetting, toc: dict) -> int:
        """連載/短編を判定"""
        return toc.get("novel_type", NOVEL_TYPE_SERIES)
