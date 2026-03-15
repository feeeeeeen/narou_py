# Narou Downloader (Python版)

「小説家になろう」等のWeb小説をダウンロードし、縦書きEPUBに変換するGUIアプリケーション。
[Narou.rb](https://github.com/whiteleaf7/narou) をベースにPython + PySide6で再実装したもの。

> **原作**: このソフトウェアは [whiteleaf](https://github.com/whiteleaf7) 氏による [Narou.rb](https://github.com/whiteleaf7/narou) (MIT License) を元に、Pythonで再実装したものです。テキスト変換パイプラインやサイト定義YAMLの設計は Narou.rb に基づいています。

## 機能

- Web小説の自動ダウンロード（なろう・ノクターン等に対応）
- 24段階のテキスト変換パイプラインによる縦書き整形
- EPUB 3.0形式での出力（縦書き・目次・カバー自動生成）
- PySide6によるGUIインターフェース
- PyInstallerによる単一exe配布

## 必要環境

- Python 3.14+
- 依存パッケージ: `requirements.txt` 参照

```bash
pip install -r requirements.txt
```

## 使い方

### 開発環境での実行

```bash
py -3.14 main.py
```

### exeビルド

```bash
# テスト実行 → PyInstallerビルド
build.bat

# または手動で
py -3.14 -m pytest tests/ -v
py -3.14 -m PyInstaller narou_py.spec --noconfirm
```

ビルド成果物は `dist/NarouDownloader.exe` に出力される。

### GUI操作

1. URL入力欄にWeb小説のURLまたはNコード（例: `n9636x`）を入力して「追加」
2. 一覧から小説を選択して「ダウンロード」
3. ダウンロード完了後、出力先フォルダにEPUBが生成される

## プロジェクト構成

```
narou_py/
├── main.py              # エントリーポイント
├── requirements.txt     # 依存パッケージ
├── narou_py.spec        # PyInstallerビルド設定
├── build.bat            # ビルドスクリプト
├── narou/               # コアライブラリ
│   ├── converter.py     #   テキスト変換エンジン（24段階パイプライン）
│   ├── database.py      #   SQLiteデータベース層
│   ├── downloader.py    #   ダウンロードエンジン
│   ├── epub_writer.py   #   EPUB 3.0ファイル生成
│   ├── helpers.py       #   ユーティリティ関数
│   ├── html_to_aozora.py#   HTML→青空文庫形式変換
│   ├── illustration.py  #   挿絵ダウンロード
│   ├── models.py        #   データモデル（Novel, Chapter, Section）
│   ├── narou_api.py     #   なろうAPI・定数
│   ├── novel_info.py    #   小説情報ページパーサ
│   ├── novel_setting.py #   小説個別設定
│   ├── parser.py        #   青空文庫注記→XHTML変換
│   ├── settings.py      #   アプリ設定
│   └── site_setting.py  #   サイト定義YAML管理
├── gui/                 # GUIモジュール
│   ├── main_window.py   #   メインウィンドウ（PySide6）
│   └── workers.py       #   QThreadバックグラウンドワーカー
├── webnovel/            # サイト定義YAML（*.yaml）
├── preset/              # 小説個別プリセット
└── tests/               # テストスイート（113テスト）
```

## アーキテクチャ

### データフロー

```
URL / Nコード
    │
    ▼
NovelDownloader.download()
    ├─ SiteSetting（webnovel/*.yaml）でURL解析・サイト判定
    ├─ NovelInfo.load() で小説メタデータ取得（HTMLパース）
    ├─ 目次HTMLパース → エピソード一覧（Chapter）
    ├─ 各話HTMLダウンロード → 本文抽出（introduction/body/postscript）
    ├─ YAMLファイルとして保存（本文/<index>.yaml）
    └─ SQLiteデータベースに小説情報を登録・更新
    │
    ▼
DownloadWorker._convert_to_epub()
    ├─ 保存済みYAMLを番号順に読み込み
    ├─ TextConverter.convert() で24段階テキスト変換
    ├─ parse_text() で青空文庫注記→XHTML変換
    └─ write_epub() でEPUB 3.0ファイルを生成
```

### 主要コンポーネント

#### NovelDownloader (`narou/downloader.py`)

Web小説のダウンロードを担当。`webnovel/`のYAML定義に基づき、サイトごとのHTML構造に対応する。
なろう系サイトでは専用の`_extract_elements_from_narou_html()`でCSSクラスベースの本文抽出を行う。
503エラーは最大5回リトライ（20秒待機）。なろうでは10話ごとにウェイトを入れる。

#### TextConverter (`narou/converter.py`)

テキストを縦書き日本語向けに整形する24段階の変換パイプライン:

| # | 処理 |
|---|------|
| 1 | 半角カナ→全角（濁点結合含む） |
| 2 | かぎ括弧内改行の自動連結 |
| 3 | 行末読点での自動行連結 |
| 4 | コメントブロック削除 |
| 5-6 | 挿絵・URL退避（stash） |
| 7 | なろうタグ→青空文庫注記 |
| 8 | ローマ数字変換 |
| 9 | アルファベット全角化（英文保護） |
| 10 | 章見出し字下げ・ゴシック化 |
| 11-14 | 数字変換（漢数字化/縦中横） |
| 15 | 感嘆符・疑問符後の全角アキ |
| 16 | 特殊文字正規化（三点リーダー等） |
| 17 | 分数・日付変換 |
| 18 | カタカナ「ニ」→漢字「二」 |
| 19 | 濁点フォント変換 |
| 20 | ルビ処理 |
| 21-22 | 字下げ・二分アキ |
| 23-24 | 空行整理・改ページ変換 |

変換中にURLや挿絵、英文、数字等を一時退避（stash）し、パイプライン通過後に復元するパターンを使用。
stashキーには全角マーカー付き16進数（`ｘ{hex}ｘ`）を使い、数字変換パイプラインとの干渉を防ぐ。

#### Database (`narou/database.py`)

SQLiteベースの小説メタデータ管理。QThreadワーカーからはスレッドごとに新しい接続を作成する（SQLiteスレッド安全性）。

#### EPUB生成 (`narou/parser.py` + `narou/epub_writer.py`)

- `parser.py`: 青空文庫注記付きテキストを行単位で処理し、XHTML断片に変換
- `epub_writer.py`: EPUB 3.0準拠のZIPを生成。縦書きCSS（`writing-mode: vertical-rl`）、SVGカバー、章別目次を含む

#### SiteSetting (`narou/site_setting.py`)

`webnovel/`ディレクトリのYAMLファイルでサイトごとのURL規則・HTML構造を定義。
Rubyの正規表現（`(?<name>...)`、`\k<name>`）をPython形式に自動変換する機能を持つ。

### GUI (`gui/`)

- `MainWindow`: URL追加、小説一覧表示（ソート・検索・複数選択）、ダウンロード、削除
- `DownloadWorker`: ダウンロード→変換→EPUB生成をQThreadで実行
- `AddNovelWorker`: URL解析→メタデータ取得→DB追加をQThreadで実行

## narou.rb からの移行における技術的な差異

### Ruby → Python で対応が必要だった点

| 項目 | Ruby (narou.rb) | Python (narou_py) |
|------|----------------|-------------------|
| 正規表現名前付きグループ | `(?<name>...)` | `(?P<name>...)` に自動変換 |
| 正規表現逆参照 | `\k<name>` | `(?P=name)` に自動変換 |
| データベース | YAML (`database.yaml`) | SQLite |
| GUI | Sinatra + WebSocket | PySide6 |
| 配布形式 | gem | PyInstaller単一exe |
| User-Agent | 明示指定 | `session.headers["User-Agent"]`で直接設定（`setdefault`不可） |
| `multi_match`のbreak | `break`は内側ループのみ | 外側ループに`break`を置かないよう注意 |
| txtdownload API | 廃止済み | HTML本文ページから直接パース |

### サイトHTML構造への対応

syosetu.comのHTML構造は刷新済み。新しいCSSクラス体系に対応:
- 目次: `p-eplist__sublist`, `p-eplist__chapter-title`
- 本文: `p-novel__text--preface`, `p-novel__text--body`, `p-novel__text--afterword`
- 小説情報: `p-infotop-data__title`, `p-infotop-data__value`
- HTTPS必須、User-Agent必須（なしだと403）
- R18サイトはCookie (`over18=yes`) が必要

## テスト

```bash
# 全テスト実行
py -3.14 -m pytest tests/ -v

# 特定テストファイル
py -3.14 -m pytest tests/test_converter.py -v
```

テスト構成（121テスト）:

| テストファイル | テスト数 | 対象 |
|-------------|---------|------|
| test_converter.py | 31 | テキスト変換パイプライン |
| test_parser.py | 17 | 青空文庫注記→XHTMLパーサ |
| test_epub_writer.py | 11 | EPUB生成 |
| test_html_to_aozora.py | 11 | HTML→青空文庫変換 |
| test_helpers.py | 10 | ユーティリティ関数 |
| test_downloader.py | 9 | ダウンロードエンジン |
| test_site_setting.py | 8 | サイト定義YAML |
| test_security.py | 8 | セキュリティ回帰テスト |
| test_database.py | 7 | データベース操作 |
| test_models.py | 5 | データモデル |
| test_gui_model.py | 3 | GUIテーブルモデル |

## データ保存構造

```
.narou/
├── database.db              # SQLiteデータベース
└── 小説データ/
    └── <safe_title>/        # 小説ごとのディレクトリ
        ├── raw/             # ダウンロードした生HTML
        │   └── <index> <subtitle>.html
        └── 本文/            # パース済みセクションデータ
            └── <index> <subtitle>.yaml
```

各セクションのYAML構造:
```yaml
index: 1
subtitle: "第1話 タイトル"
chapter: "第一章"
element:
  body: "本文テキスト..."
  introduction: "前書きテキスト..."
  postscript: "後書きテキスト..."
download_time: "2024-01-01T00:00:00"
```

## 謝辞

このソフトウェアは以下のプロジェクトを元に作成されました:

- **[Narou.rb](https://github.com/whiteleaf7/narou)** by [whiteleaf](https://github.com/whiteleaf7) — Web小説ダウンローダー・変換ツール（Ruby）。テキスト変換パイプライン、サイト定義YAML、青空文庫注記体系の設計はNarou.rbに基づいています。

### narou.rb からの主な変更点

- **言語**: Ruby → Python 3.14
- **GUI**: Sinatra + WebSocket Web UI → PySide6 デスクトップアプリ
- **データベース**: YAML (`database.yaml`) → SQLite
- **配布形式**: gem → PyInstaller 単一exe
- **サイト対応**: syosetu.com の新HTML構造（2025年〜）に対応
- **API変更対応**: txtdownload API廃止に伴い、HTML本文ページからの直接パースに変更

## ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照してください。

本ソフトウェアは [Narou.rb](https://github.com/whiteleaf7/narou) (Copyright (c) 2013 whiteleaf, MIT License) を元にしています。
