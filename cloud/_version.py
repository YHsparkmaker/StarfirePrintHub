"""
版本号读取 — 单一事实源
读取项目根目录的 VERSION 文件。
"""
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"

try:
    __version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
except Exception:
    __version__ = "0.0.0-unknown"
