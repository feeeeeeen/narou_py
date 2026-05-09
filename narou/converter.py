"""テキスト変換エンジン

narou_rb の converterbase.rb（1229行）をPythonに移植。
縦書き用の日本語テキスト整形を行う24段階の変換パイプライン。
"""
import re
import unicodedata

from narou.novel_setting import NovelSetting

# ========== 定数 ==========

KANJI_NUM = "〇一二三四五六七八九"
KANJI_NUM_TR_FROM = "0123456789"
KANJI_NUM_TR_TO = KANJI_NUM
ZENKAKU_NUM = "０１２３４５６７８９"
KANJI_NUM_UNITS = ["", "万", "億", "兆", "京"]
KANJI_KURAI = ["", "十", "百", "千"]
KANJI_NUM_UNITS_DIGIT = {
    "十": 1, "百": 2, "千": 3, "万": 4, "億": 8, "兆": 12, "京": 16
}

RECONVERT_UNIT = "％㎜㎝㎞㎎㎏㏄㎡㎥"

# 括弧
BRACKETS = [("「", "」"), ("『", "』")]

# 記号変換テーブル（str.maketrans用dict）
SYMBOLS_TR = {
    "-": "\uFF0D", "=": "\uFF1D", "+": "\uFF0B", "/": "\uFF0F", "*": "\uFF0A",
    "'": "\u2018", '"': "\u201D", "\\": "\uFFE5",
    "%": "\uFF05", "$": "\uFF04", "#": "\uFF03", "&": "\uFF06",
    "!": "\uFF01", "?": "\uFF1F", "<": "\u3008", ">": "\u3009",
    "\uFF1C": "\u3008", "\uFF1E": "\u3009",  # ＜＞ → 〈〉
    "(": "\uFF08", ")": "\uFF09", "|": "\uFF5C",
    "\u2010": "\uFF0D",  # ‐ → －
    ",": "\uFF0C", ".": "\uFF0E", "_": "\uFF3F",
    ";": "\uFF1B", ":": "\uFF1A", "[": "\uFF3B", "]": "\uFF3D",
}

# ローマ数字変換
ROME_NUM_ALPHA = ["II", "III", "IV", "VI", "VII", "VIII", "IX",
                  "ii", "iii", "iv", "vi", "vii", "viii", "ix"]
ROME_NUM_CHAR = ["Ⅱ", "Ⅲ", "Ⅳ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ",
                 "ⅱ", "ⅲ", "ⅳ", "ⅵ", "ⅶ", "ⅷ", "ⅸ"]

# ルビ対象文字
CHARACTER_OF_RUBY = r"一-龠Ａ-Ｚａ-ｚA-Za-z"

# 前書き・後書きのセパレータ
AUTHOR_INTRODUCTION_SPLITTER = re.compile(r"^　*[*＊]{44}$")
AUTHOR_POSTSCRIPT_SPLITTER = re.compile(r"^　*[*＊]{48}$")

# 半角→全角カナ変換テーブル（NKF互換）
_HANKAKU_KANA = "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ"
_ZENKAKU_KANA = "ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜"

# 英文判定
ENGLISH_MIN_LEN = 8

# Stashキー用: 16進数字(0-9,a-f)をUnicode私用領域にマッピングし、
# 数字変換・アルファベット変換パイプラインの影響を完全に回避する
_PUA_STASH_BASE = 0xE010  # U+E010〜U+E01F (16文字分)
_PUA_STASH_RANGE = "".join(chr(_PUA_STASH_BASE + i) for i in range(16))
_PUA_STASH_RE = f"[{_PUA_STASH_RANGE}]+"


def _encode_stash_key(n: int) -> str:
    """整数をPUA文字列にエンコード"""
    return "".join(chr(_PUA_STASH_BASE + int(c, 16)) for c in hex(n)[2:])


def _decode_stash_key(pua: str) -> int:
    """PUA文字列を整数にデコード"""
    return int("".join(hex(ord(c) - _PUA_STASH_BASE)[2:] for c in pua), 16)


class TextConverter:
    """テキスト変換エンジン"""

    def __init__(self, setting: NovelSetting):
        self.setting = setting
        # Stash用リスト
        self._kanji_num_list: dict[int, str] = {}
        self._num_comma_list: dict[int, str] = {}
        self._num_comma_counter = 0
        self._english_sentences: list[str] = []
        self._url_list: list[str] = []
        self._illust_list: list[str] = []
        self._force_indent_list: list[str] = []
        self._text_type = ""

    def convert(self, text: str, text_type: str = "body") -> str:
        """メイン変換エントリーポイント

        text_type: "subtitle", "body", "introduction", "postscript",
                   "chapter", "story", "textfile"
        """
        self._text_type = text_type

        # 前処理
        text = self._before_convert(text, text_type)
        # メイン変換
        text = self._convert_main(text, text_type)
        # 後処理
        text = self._after_convert(text, text_type)
        return text

    def _before_convert(self, text: str, text_type: str) -> str:
        """前処理"""
        # replace.txt による置換
        for pattern, replacement in self.setting.replace_pattern:
            try:
                text = re.sub(pattern, replacement, text)
            except re.error:
                text = text.replace(pattern, replacement)
        return text

    def _convert_main(self, text: str, text_type: str) -> str:
        """text_type に応じた変換処理"""
        if text_type == "introduction":
            if self.setting.enable_erase_introduction:
                return ""
            text = "［＃ここから前書き］\n" + self._convert_for_all_data(text) + "\n［＃ここで前書き終わり］"
        elif text_type == "postscript":
            if self.setting.enable_erase_postscript:
                return ""
            text = "［＃ここから後書き］\n" + self._convert_for_all_data(text) + "\n［＃ここで後書き終わり］"
        elif text_type in ("subtitle", "chapter"):
            text = self._hankaku_kana_to_zenkaku(text)
            text = self._convert_numbers(text)
            text = self._symbols_to_zenkaku(text)
        elif text_type == "story":
            text = self._hankaku_kana_to_zenkaku(text)
            text = self._convert_numbers(text)
        else:
            text = self._convert_for_all_data(text)
        return text

    def _after_convert(self, text: str, text_type: str) -> str:
        """後処理: stash済みデータの復元"""
        text = self._rebuild_url(text)
        text = self._rebuild_illust(text)
        text = self._rebuild_english_sentences(text)
        text = self._rebuild_hankaku_num_and_comma(text)
        text = self._rebuild_force_indent(text)
        return text

    # ========== 24段階変換パイプライン ==========

    def _convert_for_all_data(self, data: str) -> str:
        """24段階の変換チェーン"""
        data = self._hankaku_kana_to_zenkaku(data)           # 1
        data = self._auto_join_in_brackets(data)             # 2
        if self.setting.enable_auto_join_line:
            data = self._auto_join_line(data)                # 3
        data = self._erase_comments_block(data)              # 4
        data = self._replace_illust_tag(data)                # 5
        data = self._replace_url(data)                       # 6
        data = self._replace_narou_tag(data)                 # 7
        data = self._convert_rome_numeric(data)              # 8
        data = self._alphabet_to_zenkaku(data)               # 9
        data = self._force_indent_special_chapter(data)      # 10
        data = self._convert_numbers(data)                   # 11
        data = self._exception_reconvert_kanji_to_num(data)  # 12
        if self.setting.enable_kanji_num_with_units:
            data = self._convert_kanji_num_with_unit(data)   # 13
        data = self._rebuild_kanji_num(data)                 # 14
        data = self._insert_separate_space(data)             # 15
        data = self._convert_special_characters(data)        # 16
        data = self._convert_fraction_and_date(data)         # 17
        data = self._modify_kana_ni_to_kanji_ni(data)        # 18
        data = self._convert_dakuten_char_to_font(data)      # 19
        # ルビ処理
        if self.setting.enable_ruby:
            data = self._narou_ruby(data)                    # 20
        # 行頭字下げ
        if self.setting.enable_auto_indent:
            data = self._auto_indent(data)                   # 21
        # 行頭括弧
        if self.setting.enable_half_indent_bracket:
            data = self._half_indent_bracket(data)           # 22
        # 空行整理
        if self.setting.enable_pack_blank_line:
            data = self._pack_blank_line(data)               # 23
        # 改ページ変換
        if self.setting.enable_convert_page_break:
            data = self._convert_page_break(data)            # 24
        return data

    # ========== 1. 半角カナ→全角 ==========

    def _hankaku_kana_to_zenkaku(self, data: str) -> str:
        """半角カナを全角カナに変換"""
        # NFKC正規化で半角カナ→全角カナ（副作用あるため個別変換）
        result = []
        for ch in data:
            if ch in _HANKAKU_KANA:
                idx = _HANKAKU_KANA.index(ch)
                result.append(_ZENKAKU_KANA[idx])
            else:
                result.append(ch)
        text = "".join(result)
        # 濁点・半濁点の結合
        text = text.replace("カ゛", "ガ").replace("キ゛", "ギ").replace("ク゛", "グ")
        text = text.replace("ケ゛", "ゲ").replace("コ゛", "ゴ")
        text = text.replace("サ゛", "ザ").replace("シ゛", "ジ").replace("ス゛", "ズ")
        text = text.replace("セ゛", "ゼ").replace("ソ゛", "ゾ")
        text = text.replace("タ゛", "ダ").replace("チ゛", "ヂ").replace("ツ゛", "ヅ")
        text = text.replace("テ゛", "デ").replace("ト゛", "ド")
        text = text.replace("ハ゛", "バ").replace("ヒ゛", "ビ").replace("フ゛", "ブ")
        text = text.replace("ヘ゛", "ベ").replace("ホ゛", "ボ")
        text = text.replace("ハ゜", "パ").replace("ヒ゜", "ピ").replace("フ゜", "プ")
        text = text.replace("ヘ゜", "ペ").replace("ホ゜", "ポ")
        text = text.replace("ウ゛", "ヴ")
        # em-dash → 全角ダッシュ
        text = text.replace("\u2014", "―")
        return text

    # ========== 2. かぎ括弧内連結 ==========

    def _auto_join_in_brackets(self, data: str) -> str:
        """かぎ括弧内の改行を自動連結"""
        if not self.setting.enable_auto_join_in_brackets:
            return data
        for open_b, close_b in BRACKETS:
            # ネスト対応の括弧マッチ
            pattern = re.compile(
                rf"({re.escape(open_b)}[^{re.escape(open_b)}{re.escape(close_b)}]*"
                rf"(?:(?:{re.escape(open_b)}[^{re.escape(open_b)}{re.escape(close_b)}]*"
                rf"{re.escape(close_b)}[^{re.escape(open_b)}{re.escape(close_b)}]*)*)"
                rf"{re.escape(close_b)})",
                re.DOTALL,
            )
            data = pattern.sub(lambda m: self._join_inner_bracket(m.group(0)), data)
        return data

    def _join_inner_bracket(self, text: str) -> str:
        """括弧内部の改行を連結"""
        if "\n" not in text:
            return text
        lines = text.split("\n")
        joined = "".join(line.lstrip("　 \t") for line in lines)
        return joined

    # ========== 3. 自動行連結 ==========

    def _auto_join_line(self, data: str) -> str:
        """行末読点での自動連結"""
        return re.sub(
            r"([^、])、\n　([^「『(（【<＜〈《≪…‥―])",
            r"\1、\2",
            data,
        )

    # ========== 4. コメントブロック削除 ==========

    def _erase_comments_block(self, data: str) -> str:
        """コメントブロック（===で囲まれた部分等）を削除"""
        data = re.sub(r"^={10,}\n.*?\n={10,}$", "", data, flags=re.MULTILINE | re.DOTALL)
        return data

    # ========== 5. 挿絵タグ ==========

    def _replace_illust_tag(self, data: str) -> str:
        """挿絵注記を退避"""
        if not self.setting.enable_illust:
            data = re.sub(r"［＃挿絵（.+?）入る］", "", data)
            return data

        def _stash(m: re.Match) -> str:
            self._illust_list.append(m.group(0))
            idx = len(self._illust_list) - 1
            return f"［＃挿絵＝{_encode_stash_key(idx)}］"

        return re.sub(r"［＃挿絵（.+?）入る］", _stash, data)

    def _rebuild_illust(self, data: str) -> str:
        def _rebuild(m: re.Match) -> str:
            key = _decode_stash_key(m.group(1))
            if 0 <= key < len(self._illust_list):
                return self._illust_list[key]
            return m.group(0)
        data = re.sub(rf"［＃挿絵＝({_PUA_STASH_RE})］", _rebuild, data)
        self._illust_list.clear()
        return data

    # ========== 6. URL保護 ==========

    def _replace_url(self, data: str) -> str:
        """URLを退避"""
        def _stash(m: re.Match) -> str:
            self._url_list.append(m.group(0))
            idx = len(self._url_list) - 1
            return f"［＃ＵＲＬ＝{_encode_stash_key(idx)}］"

        return re.sub(r"https?://[\w/:%#$&?()~.=+\-]+", _stash, data)

    def _rebuild_url(self, data: str) -> str:
        def _rebuild(m: re.Match) -> str:
            key = _decode_stash_key(m.group(1))
            if 0 <= key < len(self._url_list):
                return self._url_list[key]
            return m.group(0)
        data = re.sub(rf"［＃ＵＲＬ＝({_PUA_STASH_RE})］", _rebuild, data)
        self._url_list.clear()
        return data

    # ========== 7. なろうタグ置換 ==========

    def _replace_narou_tag(self, data: str) -> str:
        """なろう独自タグを青空文庫注記に変換"""
        # <b>太字</b> → ゴシック体
        data = re.sub(r"<b>(.+?)</b>", r"［＃ゴシック体］\1［＃ゴシック体終わり］", data, flags=re.IGNORECASE)
        # 区切り線
        data = re.sub(r"^-{5,}$", "［＃区切り線］", data, flags=re.MULTILINE)
        return data

    # ========== 8. ローマ数字変換 ==========

    def _convert_rome_numeric(self, data: str) -> str:
        """英字のローマ数字表記を記号に変換"""
        for alpha, char in zip(ROME_NUM_ALPHA, ROME_NUM_CHAR):
            data = re.sub(rf"\b{alpha}\b", char, data)
        return data

    # ========== 9. アルファベット全角化 ==========

    def _alphabet_to_zenkaku(self, data: str) -> str:
        """アルファベットを全角に変換（英文は保護）"""
        force = self.setting.enable_alphabet_force_zenkaku

        if not force:
            # 英文（スペース区切り2語以上 or 8字以上の小文字含む）を保護
            def _stash_english(m: re.Match) -> str:
                text = m.group(0)
                if " " in text or (len(text) >= ENGLISH_MIN_LEN and any(c.islower() for c in text)):
                    self._english_sentences.append(text)
                    idx = len(self._english_sentences) - 1
                    return f"［＃英文＝{_encode_stash_key(idx)}］"
                return text

            data = re.sub(r"[\w.,!?'\" &:;_-]+", _stash_english, data)

        # 半角英字→全角
        result = []
        for ch in data:
            if "A" <= ch <= "Z":
                result.append(chr(ord(ch) - ord("A") + ord("Ａ")))
            elif "a" <= ch <= "z":
                result.append(chr(ord(ch) - ord("a") + ord("ａ")))
            else:
                result.append(ch)
        data = "".join(result)
        data = self._symbols_to_zenkaku(data)
        return data

    def _rebuild_english_sentences(self, data: str) -> str:
        def _rebuild(m: re.Match) -> str:
            key = _decode_stash_key(m.group(1))
            if 0 <= key < len(self._english_sentences):
                return self._english_sentences[key]
            return m.group(0)
        data = re.sub(rf"［＃英文＝({_PUA_STASH_RE})］", _rebuild, data)
        self._english_sentences.clear()
        return data

    # ========== 記号全角化 ==========

    def _symbols_to_zenkaku(self, data: str) -> str:
        """記号を全角に変換"""
        # 引用符 → 〝〟
        data = re.sub(r"[''']([^'\"\n]+)[''']", r"〝\1〟", data)
        data = re.sub(r'[""〝〟"]([^"\n]+)[""〝〟"]', r"〝\1〟", data)
        # tr変換
        data = data.translate(str.maketrans(SYMBOLS_TR))
        data = data.replace("\\", "\uFFE5")
        # 《》は≪≫に（ルビ記法とぶつかるため）
        data = data.replace("《", "≪").replace("》", "≫")
        return data

    # ========== 10. 章見出し字下げ ==========

    def _force_indent_special_chapter(self, data: str) -> str:
        """章見出しっぽい文字列を字下げ・ゴシック化"""
        pattern = re.compile(
            rf"^[ 　\t]*([－―<＜〈\-]*)([0-9０-９{KANJI_NUM}]{{1,3}})([－―>＞〉\-]*)$",
            re.MULTILINE,
        )

        def _replace(m: re.Match) -> str:
            top, num, bottom = m.group(1), m.group(2), m.group(3)
            if not top and not bottom:
                return m.group(0)
            text = f"　　　［＃ゴシック体］{top}{num}{bottom}［＃ゴシック体終わり］"
            self._force_indent_list.append(text)
            idx = len(self._force_indent_list) - 1
            return f"［＃章見出し＝{_encode_stash_key(idx)}］"

        return pattern.sub(_replace, data)

    def _rebuild_force_indent(self, data: str) -> str:
        def _rebuild(m: re.Match) -> str:
            key = _decode_stash_key(m.group(1))
            if 0 <= key < len(self._force_indent_list):
                return self._force_indent_list[key]
            return m.group(0)
        data = re.sub(rf"［＃章見出し＝({_PUA_STASH_RE})］", _rebuild, data)
        self._force_indent_list.clear()
        return data

    # ========== 11. 数字変換 ==========

    def _convert_numbers(self, data: str) -> str:
        """数字変換メインルーチン"""
        # 小数点を中黒に
        data = re.sub(
            rf"([\d０-９{KANJI_NUM}]+?)[.．]([\d０-９{KANJI_NUM}]+?)",
            r"\1・\2",
            data,
        )
        if (self.setting.enable_convert_num_to_kanji
                and self._text_type not in ("subtitle", "chapter", "story")):
            data = self._num_to_kanji(data)
        else:
            data = self._hankaku_num_to_zenkaku_num(data)
        return data

    def _num_to_kanji(self, data: str) -> str:
        """半角/全角数字を漢数字に変換"""
        # 既存の漢数字を退避
        data = self._stash_kanji_num(data)
        # カンマ付き数字を退避
        def _stash_comma(m: re.Match) -> str:
            self._num_comma_counter += 1
            self._num_comma_list[self._num_comma_counter] = m.group(0)
            return f"［＃半角数字＝{_encode_stash_key(self._num_comma_counter)}］"
        data = re.sub(r"\d[\d,]+\d", _stash_comma, data)
        # 半角→全角→漢数字
        data = self._hankaku_to_zenkaku_num(data)
        data = self._zenkaku_num_to_kanji(data)
        return data

    def _stash_kanji_num(self, data: str) -> str:
        """既存の漢数字を退避"""
        counter = [0]
        def _stash(m: re.Match) -> str:
            key = counter[0]
            self._kanji_num_list[key] = m.group(0)
            counter[0] += 1
            return f"［＃漢数字＝{_encode_stash_key(key)}］"
        return re.sub(rf"[{KANJI_NUM}十百千万億兆京]+", _stash, data)

    def _rebuild_kanji_num(self, data: str) -> str:
        """退避した漢数字を復元"""
        def _rebuild(m: re.Match) -> str:
            key = _decode_stash_key(m.group(1))
            return self._kanji_num_list.get(key, m.group(0))
        data = re.sub(rf"［＃漢数字＝({_PUA_STASH_RE})］", _rebuild, data)
        self._kanji_num_list.clear()
        return data

    def _rebuild_hankaku_num_and_comma(self, data: str) -> str:
        def _rebuild(m: re.Match) -> str:
            key = _decode_stash_key(m.group(1))
            return self._num_comma_list.get(key, m.group(0))
        data = re.sub(rf"［＃半角数字＝({_PUA_STASH_RE})］", _rebuild, data)
        self._num_comma_list.clear()
        return data

    def _hankaku_to_zenkaku_num(self, data: str) -> str:
        """半角数字→全角数字"""
        return data.translate(str.maketrans("0123456789", ZENKAKU_NUM))

    def _zenkaku_num_to_kanji(self, data: str) -> str:
        """全角数字→漢数字"""
        return data.translate(str.maketrans(ZENKAKU_NUM, KANJI_NUM))

    def _hankaku_num_to_zenkaku_num(self, data: str) -> str:
        """半角数字→全角数字（漢数字変換なし時）

        1桁・3桁以上: 全角化
        2桁: 縦中横
        """
        def _replace(m: re.Match) -> str:
            num = m.group(0)
            if len(num) == 2:
                return self._tcy(num)
            return num.translate(str.maketrans("0123456789", ZENKAKU_NUM))

        return re.sub(r"\d+", _replace, data)

    @staticmethod
    def _tcy(text: str) -> str:
        """縦中横注記"""
        return f"［＃縦中横］{text}［＃縦中横終わり］"

    # ========== 12. 漢数字→アラビア数字（例外復帰） ==========

    def _exception_reconvert_kanji_to_num(self, data: str) -> str:
        """アルファベットや単位記号に隣接する漢数字をアラビア数字に戻す"""
        kanji_to_zen = str.maketrans(KANJI_NUM, ZENKAKU_NUM)
        # パターン1: アルファベット+漢数字
        data = re.sub(
            rf"([Ａ-Ｚａ-ｚ])([{KANJI_NUM}・～]+)",
            lambda m: m.group(1) + m.group(2).translate(kanji_to_zen),
            data,
        )
        # パターン2: 漢数字+単位記号
        data = re.sub(
            rf"([{KANJI_NUM}・～]+)([Ａ-Ｚａ-ｚ{RECONVERT_UNIT}])",
            lambda m: m.group(1).translate(kanji_to_zen) + m.group(2),
            data,
        )
        return data

    # ========== 13. 漢数字単位変換 ==========

    def _convert_kanji_num_with_unit(self, data: str) -> str:
        """漢数字に千・万等の単位を付与する"""
        threshold = self.setting.kanji_num_with_units_lower_digit_zero

        def _replace(m: re.Match) -> str:
            kanji = m.group(0)
            # 〇が threshold 個未満なら変換しない
            zero_count = kanji.count("〇")
            if zero_count < threshold:
                return kanji
            num = self._kanji_to_integer(kanji)
            if num is None or num == 0:
                return kanji
            return self._integer_to_kanji_with_unit(num)

        return re.sub(rf"[{KANJI_NUM}]+", _replace, data)

    @staticmethod
    def _kanji_to_integer(kanji: str) -> int | None:
        """漢数字文字列を整数に変換"""
        try:
            digits = "".join(str(KANJI_NUM.index(ch)) for ch in kanji if ch in KANJI_NUM)
            return int(digits) if digits else None
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _integer_to_kanji_with_unit(num: int) -> str:
        """整数を単位付き漢数字に変換（例: 10000 → 一万）"""
        if num == 0:
            return "〇"
        result = ""
        for unit_idx in range(len(KANJI_NUM_UNITS) - 1, -1, -1):
            unit_value = 10 ** (unit_idx * 4) if unit_idx > 0 else 1
            if unit_idx == 0:
                # 残り
                if num > 0:
                    for ch in str(num):
                        result += KANJI_NUM[int(ch)]
                break
            part = num // unit_value
            if part > 0:
                # 千・百・十の位を処理
                part_str = ""
                for kurai_idx in range(3, -1, -1):
                    kurai_value = 10 ** kurai_idx if kurai_idx > 0 else 1
                    digit = part // kurai_value
                    if digit > 0:
                        if digit > 1 or kurai_idx == 0:
                            part_str += KANJI_NUM[digit]
                        if kurai_idx > 0:
                            part_str += KANJI_KURAI[kurai_idx]
                    part %= kurai_value
                result += part_str + KANJI_NUM_UNITS[unit_idx]
                num %= unit_value
        return result

    # ========== 15. 感嘆符後の全角アキ ==========

    def _insert_separate_space(self, data: str) -> str:
        """感嘆符・疑問符の直後に全角アキを挿入"""
        no_space_after = r'[」］\]』】〉》〕＞>≫)）"' + "'" + r'〟　☆★♪［―]'

        def _replace(m: re.Match) -> str:
            marks, next_ch = m.group(1), m.group(2)
            if next_ch == " ":
                next_ch = "　"
            if re.match(no_space_after, next_ch):
                return marks + next_ch
            return marks + "　" + next_ch

        return re.sub(r"([!?！？]+)([^!?！？])", _replace, data)

    # ========== 16. 特殊文字変換 ==========

    def _convert_special_characters(self, data: str) -> str:
        """特殊文字変換"""
        # 中黒の三点リーダー変換
        if self.setting.enable_convert_horizontal_ellipsis:
            data = re.sub(r"・{3,}", lambda m: "…" * (len(m.group(0)) // 3 + (1 if len(m.group(0)) % 3 else 0)), data)
        # 三点リーダー正規化
        data = data.replace("。。。", "…")
        data = data.replace("．．．", "…")
        # ダッシュ正規化
        data = data.replace("──", "――")
        return data

    # ========== 17. 分数・日付変換 ==========

    def _convert_fraction_and_date(self, data: str) -> str:
        """分数・日付表記の変換"""
        if self.setting.enable_transform_fraction:
            data = re.sub(
                rf"([{KANJI_NUM}０-９]+)／([{KANJI_NUM}０-９]+)",
                r"\2分の\1",
                data,
            )
        # 日付変換は設定有効時のみ
        if self.setting.enable_transform_date:
            def _date_replace(m: re.Match) -> str:
                from datetime import datetime
                try:
                    dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    return dt.strftime(self.setting.date_format)
                except (ValueError, TypeError):
                    return m.group(0)
            data = re.sub(r"(20\d{2})／(\d{1,2})／(\d{1,2})", _date_replace, data)
        return data

    # ========== 18. カタカナニ→漢字二 ==========

    def _modify_kana_ni_to_kanji_ni(self, data: str) -> str:
        """カタカナ「ニ」を漢数字「二」と区別しにくいので変換しない
        （実際にはRuby版でも条件限定的なので最小限の実装）"""
        return data

    # ========== 19. 濁点フォント変換 ==========

    def _convert_dakuten_char_to_font(self, data: str) -> str:
        """濁点付き特殊文字をフォント指定に変換"""
        if not self.setting.enable_dakuten_font:
            return data
        # か゛→ ［＃濁点］か［＃濁点終わり］ のようなパターン
        def _replace(m: re.Match) -> str:
            return f"［＃濁点］{m.group(1)}［＃濁点終わり］"
        data = re.sub(r"([\u3041-\u3093])゛", _replace, data)
        data = re.sub(r"([\u30A1-\u30F3])゛", _replace, data)
        return data

    # ========== 20. ルビ処理 ==========

    def _narou_ruby(self, data: str) -> str:
        """ルビ記法の処理"""
        # ≪≫ルビ
        data = re.sub(
            r"(.+?)≪([^≪]+?)≫",
            lambda m: self._to_ruby(m.group(0), m.group(1), m.group(2)),
            data,
        )
        # （）ルビ（20字以下のひらがな・カタカナ）
        data = re.sub(
            r"(.+?)（([ぁ-んァ-ヶーゝゞ・Ａ-Ｚａ-ｚA-Za-z 　]{1,20})）",
            lambda m: self._to_ruby(m.group(0), m.group(1), m.group(2)),
            data,
        )
        # 縦線処理
        data = data.replace("［＃ルビ用縦線］", "｜")
        data = data.replace("｜", "※［＃縦線］")
        return data

    def _to_ruby(self, original: str, base: str, ruby: str) -> str:
        """ルビ変換判定"""
        if not base:
            return original
        # 直前に｜がある場合はルビ化抑制
        if base.endswith("｜"):
            return base[:-1] + f"（{ruby}）" if "（" in original else base[:-1] + f"≪{ruby}≫"

        # ルビ対象文字の判定
        m = re.search(rf"([{CHARACTER_OF_RUBY}]+)$", base)
        if m:
            ruby_base = m.group(1)
            prefix = base[:m.start()]
            return f"{prefix}［＃ルビ用縦線］{ruby_base}《{ruby}》"
        return original

    # ========== 21. 自動行頭字下げ ==========

    def _auto_indent(self, data: str) -> str:
        """自動行頭字下げ"""
        # ダッシュで始まる行はフルインデント
        data = re.sub(r"^[ 　\t]*(――)", r"　\1", data, flags=re.MULTILINE)
        # 字下げされていない行に字下げ追加
        ignore_chars = r"[　 \t「『（(【〈《≪〝―…‥※［＃]"

        def _indent(m: re.Match) -> str:
            ch = m.group(1)
            if ch in (" ", "　"):
                return "　"
            return f"　{ch}"

        data = re.sub(rf"^([^{ignore_chars[1:-1]}])", _indent, data, flags=re.MULTILINE)
        return data

    # ========== 22. 行頭括弧二分アキ ==========

    def _half_indent_bracket(self, data: str) -> str:
        """行頭括弧に二分アキを挿入"""
        target = r"^[ 　\t]*((?:[〔「『(（【〈《≪〝]))"
        data = re.sub(target, r"［＃二分アキ］\1", data, flags=re.MULTILINE)
        return data

    # ========== 23. 空行整理 ==========

    def _pack_blank_line(self, data: str) -> str:
        """連続空行を減らす"""
        data = re.sub(r"\n{4,}", "\n\n\n", data)
        return data

    # ========== 24. 改ページ変換 ==========

    def _convert_page_break(self, data: str) -> str:
        """連続空行を改ページに変換"""
        threshold = self.setting.to_page_break_threshold
        pattern = r"\n{" + str(threshold) + r",}"
        data = re.sub(pattern, "\n［＃改ページ］\n", data)
        return data
