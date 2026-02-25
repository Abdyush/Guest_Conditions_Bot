from __future__ import annotations

import argparse

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ensure_project_on_sys_path()

from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unlink external user identity from guest_id")
    parser.add_argument("--provider", required=True, help="Identity provider, e.g. telegram")
    parser.add_argument("--external-user-id", required=True, help="External user identifier from provider")
    return parser


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()
    repo = PostgresUserIdentitiesRepository()
    repo.delete_identity(
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    print(
        "Identity unlinked: "
        f"provider={args.provider.strip().lower()}, external_user_id={args.external_user_id.strip()}"
    )


if __name__ == "__main__":
    main()

