from pathlib import Path

import yaml


class Settings:
    """YAMLベースの設定ストレージ（Inventory相当）

    スコープ:
      - local: .narou/ ディレクトリ
      - global: ~/.narousetting/ ディレクトリ
    """

    LOCAL_DIR = ".narou"
    GLOBAL_DIR_NAME = ".narousetting"

    def __init__(self, base_dir: Path, name: str, scope: str = "local"):
        if scope == "local":
            self._dir = base_dir / self.LOCAL_DIR
        else:
            self._dir = Path.home() / self.GLOBAL_DIR_NAME
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{name}.yaml"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    self._data = loaded

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)

    @property
    def data(self) -> dict:
        return self._data

    @property
    def path(self) -> Path:
        return self._path
