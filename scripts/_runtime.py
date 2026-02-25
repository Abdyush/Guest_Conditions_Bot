from __future__ import annotations

from pathlib import Path
import sys

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover
    _load_dotenv = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_project_on_sys_path() -> Path:
    root = project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def load_env_if_available() -> None:
    if _load_dotenv is not None:
        _load_dotenv()
