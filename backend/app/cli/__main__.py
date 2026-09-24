"""Uso: ``python -m app.cli create-admin --username admin --email admin@labtrack.dev``.

A senha é lida de ``LABTRACK_ADMIN_PASSWORD`` ou solicitada no terminal.
"""

import argparse
import getpass
import os
import sys

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.session import build_engine, build_session_factory
from app.domain.audit import Actor, AuditAction
from app.domain.enums import RoleCode
from app.models import User
from app.repositories.user_repository import RoleRepository, UserRepository
from app.services.audit_service import AuditService


def create_admin(username: str, email: str, full_name: str, password: str) -> str:
    settings = get_settings()
    session = build_session_factory(build_engine(settings.database_url))()
    with session:
        users = UserRepository(session)
        if users.find_by_username(username):
            return f"Usuário '{username}' já existe; nada foi alterado."
        role = RoleRepository(session).find_by_code(RoleCode.ADMIN)
        if role is None:
            raise SystemExit("Perfis não encontrados. Execute 'alembic upgrade head' antes.")

        user = users.add(
            User(
                username=username,
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                role=role,
            )
        )
        AuditService(session).record(
            Actor.system("LabTrack CLI"),
            AuditAction.USER_CREATED,
            entity_type="user",
            entity_id=user.id,
            entity_label=user.username,
            new_value={"username": username, "email": email, "role": RoleCode.ADMIN},
        )
        session.commit()
    return f"Administrador '{username}' criado."


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Cria o usuário administrador")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--email", default="admin@labtrack.dev")
    admin.add_argument("--full-name", default="Administrador do Sistema")
    args = parser.parse_args(argv)

    password = os.getenv("LABTRACK_ADMIN_PASSWORD") or getpass.getpass("Senha do administrador: ")
    if len(password) < 8:
        sys.exit("A senha precisa ter pelo menos 8 caracteres.")
    print(create_admin(args.username, args.email.lower(), args.full_name, password))


if __name__ == "__main__":
    main()
