"""Testes de arquitetura: garantem a regra de dependência entre as camadas.

Funciona como um "ArchUnit" simplificado: analisa os imports de cada arquivo
com ``ast`` e falha se uma camada importar algo que não deveria (por exemplo,
FastAPI dentro de ``services`` ou SQLAlchemy dentro de ``domain``).
"""

import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
    "core": (
        "app.api",
        "app.services",
        "app.repositories",
        "app.models",
        "app.database",
        "app.schemas",
        "app.domain",
    ),
    "domain": (
        "fastapi",
        "starlette",
        "sqlalchemy",
        "app.api",
        "app.services",
        "app.repositories",
        "app.models",
        "app.database",
        "app.schemas",
    ),
    "models": (
        "fastapi",
        "starlette",
        "app.api",
        "app.services",
        "app.repositories",
        "app.schemas",
    ),
    "database": ("fastapi", "starlette", "app.api", "app.services", "app.repositories"),
    "schemas": (
        "sqlalchemy",
        "app.api",
        "app.services",
        "app.repositories",
        "app.database",
        "app.models",
    ),
    "repositories": ("fastapi", "starlette", "app.api", "app.services"),
    "services": ("fastapi", "starlette", "app.api"),
    "api": ("app.repositories",),
}


def _imported_modules(path: Path) -> set[str]:
    """Retorna os módulos importados por um arquivo, com imports relativos resolvidos."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = list(path.relative_to(APP_DIR.parent).with_suffix("").parts[:-1])
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                parent = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join(parent + ([node.module] if node.module else []))
            modules.add(base)
            modules.update(f"{base}.{alias.name}" for alias in node.names)

    return modules


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_layer_respects_dependency_rule(layer: str) -> None:
    layer_dir = APP_DIR / layer
    assert layer_dir.is_dir(), f"Camada '{layer}' não encontrada em {APP_DIR}"

    violations = [
        f"{file.relative_to(APP_DIR.parent)} importa '{module}'"
        for file in sorted(layer_dir.rglob("*.py"))
        for module in sorted(_imported_modules(file))
        if any(_matches(module, forbidden) for forbidden in FORBIDDEN_IMPORTS[layer])
    ]

    assert not violations, "Violação da regra de dependência:\n" + "\n".join(violations)
