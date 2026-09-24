"""Comandos de administração.

``python -m app.cli create-admin --username admin --email admin@labtrack.dev``
    Cria o primeiro administrador. A senha vem de ``LABTRACK_ADMIN_PASSWORD`` ou
    é solicitada no terminal.

``python -m app.cli seed-demo [--simulator-config ../instrument-simulator/config.json]``
    Gera os dados de demonstração num banco vazio, pelos próprios serviços. A senha
    dos usuários vem de ``LABTRACK_DEMO_PASSWORD`` (padrão: ``Demo@2026``).
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from app.cli.admin import ensure_admin
from app.cli.demo import DemoDataError, DemoSummary, seed_demo
from app.core.config import get_settings
from app.database.session import build_engine, build_session_factory

DEFAULT_DEMO_PASSWORD = "Demo@2026"


def create_admin(username: str, email: str, full_name: str, password: str) -> str:
    settings = get_settings()
    session = build_session_factory(build_engine(settings.database_url))()
    with session:
        _, created = ensure_admin(session, username, email, full_name, password)
    if not created:
        return f"Usuário '{username}' já existe; nada foi alterado."
    return f"Administrador '{username}' criado."


def run_seed_demo(simulator_config: Path | None, api_url: str) -> None:
    settings = get_settings()
    if settings.environment == "production":
        sys.exit("Dados de demonstração não podem ser gerados em produção.")
    password = os.getenv("LABTRACK_DEMO_PASSWORD") or DEFAULT_DEMO_PASSWORD
    if len(password) < 8:
        sys.exit("A senha de demonstração precisa ter pelo menos 8 caracteres.")

    session = build_session_factory(build_engine(settings.database_url))()
    with session:
        try:
            summary = seed_demo(session, password)
        except DemoDataError as error:
            sys.exit(str(error))
    _print_summary(summary)
    if simulator_config:
        _write_simulator_config(simulator_config, api_url, summary.instrument_keys)
        print(f"\nChaves gravadas em {simulator_config} (não versione este arquivo).")


def _print_summary(summary: DemoSummary) -> None:
    print("Dados de demonstração gerados.\n")
    print("Usuários:")
    for username, role in summary.users:
        print(f"  {username:<15} {role}")
    if summary.admin_created:
        print(f"  Senha de todos: {summary.password}")
    else:
        print(f"  Senha dos novos usuários: {summary.password} (admin já existia; senha mantida)")
    print("\nAmostras por status:")
    for status, total in summary.samples_by_status.items():
        print(f"  {status:<16} {total}")
    print("\nMensagens de instrumento recusadas (demonstração de RN-19 a RN-24):")
    for code, total in summary.rejected_messages.items():
        print(f"  {code:<25} {total}")
    print("\nChaves de integração (exibidas só agora):")
    for code, key in summary.instrument_keys.items():
        print(f"  {code:<12} {key}")


def _write_simulator_config(path: Path, api_url: str, keys: dict[str, str]) -> None:
    config = {
        "api_url": api_url,
        "oos_rate": 0.1,
        "interval_seconds": 10,
        "instruments": [{"code": code, "key": key} for code, key in keys.items()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Cria o usuário administrador")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--email", default="admin@labtrack.dev")
    admin.add_argument("--full-name", default="Administrador do Sistema")
    demo = commands.add_parser("seed-demo", help="Gera dados de demonstração (banco vazio)")
    demo.add_argument(
        "--simulator-config",
        type=Path,
        help="Arquivo JSON onde gravar as chaves dos equipamentos para o simulador",
    )
    demo.add_argument(
        "--api-url",
        default="http://localhost:8000/api/v1",
        help="URL da API gravada na configuração do simulador",
    )
    args = parser.parse_args(argv)

    if args.command == "seed-demo":
        run_seed_demo(args.simulator_config, args.api_url)
        return

    password = os.getenv("LABTRACK_ADMIN_PASSWORD") or getpass.getpass("Senha do administrador: ")
    if len(password) < 8:
        sys.exit("A senha precisa ter pelo menos 8 caracteres.")
    print(create_admin(args.username, args.email.lower(), args.full_name, password))


if __name__ == "__main__":
    main()
