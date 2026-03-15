import re
from urllib.parse import urljoin


def html_to_aozora(html_str: str, current_url: str | None = None) -> str:
    """HTMLタグを青空文庫形式に変換する

    narou_rb の html.rb#to_aozora 相当。
    """
    text = html_str
    text = _br_to_aozora(text)
    text = _ruby_to_aozora(text)
    text = _b_to_aozora(text)
    text = _i_to_aozora(text)
    text = _s_to_aozora(text)
    text = _img_to_aozora(text, current_url)
    text = _delete_tags(text)
    return text


def _br_to_aozora(text: str) -> str:
    """<br> を改行に変換、既存の改行は除去"""
    text = re.sub(r"[\r\n]+", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    return text


def _ruby_to_aozora(text: str) -> str:
    """<ruby><rt> をルビ記法に変換"""
    # 元テキスト中の《》をエスケープ
    text = text.replace("《", "≪").replace("》", "≫")

    def _replace_ruby(m: re.Match) -> str:
        inner = m.group(1)
        parts = re.split(r"<rt>", inner, flags=re.IGNORECASE)
        if len(parts) < 2:
            return _delete_tags(parts[0])
        ruby_base = _delete_tags(re.split(r"<rp>", parts[0], flags=re.IGNORECASE)[0])
        ruby_text = _delete_tags(re.split(r"<rp>", parts[1], flags=re.IGNORECASE)[0])
        return f"｜{ruby_base}《{ruby_text}》"

    return re.sub(r"<ruby>(.+?)</ruby>", _replace_ruby, text, flags=re.IGNORECASE)


def _b_to_aozora(text: str) -> str:
    text = re.sub(r"<b>", "［＃太字］", text, flags=re.IGNORECASE)
    text = re.sub(r"</b>", "［＃太字終わり］", text, flags=re.IGNORECASE)
    return text


def _i_to_aozora(text: str) -> str:
    text = re.sub(r"<i>", "［＃斜体］", text, flags=re.IGNORECASE)
    text = re.sub(r"</i>", "［＃斜体終わり］", text, flags=re.IGNORECASE)
    return text


def _s_to_aozora(text: str) -> str:
    text = re.sub(r"<s>", "［＃取消線］", text, flags=re.IGNORECASE)
    text = re.sub(r"</s>", "［＃取消線終わり］", text, flags=re.IGNORECASE)
    return text


def _img_to_aozora(text: str, current_url: str | None = None) -> str:
    """<img> を挿絵注記に変換"""
    def _replace_img(m: re.Match) -> str:
        src = m.group("src")
        if current_url:
            src = urljoin(current_url, src)
        return f"［＃挿絵（{src}）入る］"

    return re.sub(r'<img.+?src="(?P<src>.+?)".*?>', _replace_img, text, flags=re.IGNORECASE)


def _delete_tags(text: str) -> str:
    """HTMLタグを除去"""
    return re.sub(r"<.+?>", "", text)
