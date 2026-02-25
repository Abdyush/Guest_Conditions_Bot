from __future__ import annotations

import argparse

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ensure_project_on_sys_path()

from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Link external user identity to guest_id")
    parser.add_argument("--provider", required=True, help="Identity provider, e.g. telegram")
    parser.add_argument("--external-user-id", required=True, help="External user identifier from provider")
    parser.add_argument("--guest-id", required=True, help="Internal guest_id, e.g. G1")
    return parser


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()
    repo = PostgresUserIdentitiesRepository()
    repo.upsert_identity(
        provider=args.provider,
        external_user_id=args.external_user_id,
        guest_id=args.guest_id,
    )
    resolved_guest_id = repo.resolve_guest_id(
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    print(
        "Identity linked: "
        f"provider={args.provider.strip().lower()}, external_user_id={args.external_user_id.strip()}, guest_id={resolved_guest_id}"
    )


if __name__ == "__main__":
    main()

