from __future__ import annotations

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ensure_project_on_sys_path()

from src.presentation.telegram.bot import run_polling


def main() -> None:
    load_env_if_available()
    run_polling()


if __name__ == "__main__":
    main()

