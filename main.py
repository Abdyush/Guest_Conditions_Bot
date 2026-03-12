from __future__ import annotations

from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _bootstrap() -> None:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if load_dotenv is not None:
        load_dotenv()


def main() -> None:
    _bootstrap()
    from src.presentation.telegram.bot import run_polling

    run_polling()


if __name__ == "__main__":
    main()
