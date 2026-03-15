import re
from pathlib import Path

import yaml


_GROUP_REF_RE = re.compile(r"\\\\k<(.+?)>")
# Ruby (?<name>...) → Python (?P<name>...)  ※先読み/後読みの (?<= (?<! は除外
_RUBY_NAMED_GROUP_RE = re.compile(r"\(\?<([^!=])")


def _ruby_regex_to_python(pattern: str) -> str:
    """Ruby正規表現の名前付きグループをPython構文に変換する"""
    return _RUBY_NAMED_GROUP_RE.sub(r"(?P<\1", pattern)


class SiteSetting:
    """サイト定義YAMLの読み込みと正規表現マッチング管理

    narou_rbのSiteSettingクラスをPythonに移植。
    YAML内の \\k<name> グループ参照を再帰的に展開する。
    YAMLの plain scalar では \\ がそのまま2文字として読み込まれるため、
    \\\\k<name> パターンにマッチさせる。
    """

    def __init__(self, yaml_path: Path):
        self._yaml: dict = {}
        self._match_values: dict[str, str] = {}
        with open(yaml_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                self._yaml = loaded

    @classmethod
    def load_file(cls, path: Path) -> "SiteSetting":
        return cls(path)

    def __getitem__(self, key: str):
        return self.replace_group_values(key)

    def __setitem__(self, key: str, value: str) -> None:
        self._match_values[key] = value

    def clear(self) -> None:
        self._match_values.clear()

    def matched(self, key: str) -> str | None:
        return self._match_values.get(key)

    def get_raw(self, key: str, default=None):
        """YAML定義から直接値を取得（グループ展開なし）"""
        return self._yaml.get(key, default)

    def multi_match(self, source: str, *keys: str) -> re.Match | None:
        """ソース文字列に対して複数キーの正規表現でマッチングする

        マッチした名前付きグループは _match_values に蓄積される。
        各キーについてマッチを試み、マッチしたグループを蓄積していく
        （Ruby版と同じく、外側のkeysループは全て回す）。
        """
        match_data = None
        for key in keys:
            setting_value = self[key]
            if setting_value is None:
                continue
            patterns = setting_value if isinstance(setting_value, list) else [setting_value]
            for pattern in patterns:
                if not isinstance(pattern, str):
                    continue
                try:
                    py_pattern = _ruby_regex_to_python(pattern)
                    m = re.search(py_pattern, source, re.DOTALL)
                except re.error:
                    continue
                if m:
                    match_data = m
                    self._match_values[key] = pattern
                    self._update_match_values(m)
                    break  # 内側のパターンループだけ抜ける
            # 外側のkeysループは継続（Ruby版と同じ挙動）
        return match_data

    def _update_match_values(self, match_data: re.Match) -> None:
        """マッチデータから名前付きグループを抽出してmatch_valuesに格納"""
        for name, value in match_data.groupdict().items():
            self._match_values[name] = value if value is not None else ""

    def replace_group_values(self, key: str, option_values: dict | None = None) -> str | dict | list | None:
        """\\k<name> 形式のグループ参照を再帰的に展開して値を返す"""
        if option_values is None:
            option_values = {}

        dest = option_values.get(key) or self._match_values.get(key) or self._yaml.get(key)
        if dest is None:
            return None
        if isinstance(dest, (dict, list)):
            return dest
        if not isinstance(dest, str):
            return dest

        values = {**self._yaml, **self._match_values, **option_values}

        def _replace_ref(m: re.Match) -> str:
            ref_key = m.group(1)
            ref_value = values.get(ref_key)
            if ref_value is None:
                return m.group(0)
            if not isinstance(ref_value, str):
                return str(ref_value)
            return _GROUP_REF_RE.sub(
                lambda inner: self.replace_group_values(inner.group(1), option_values) or inner.group(0),
                ref_value,
            )

        return _GROUP_REF_RE.sub(_replace_ref, dest)
