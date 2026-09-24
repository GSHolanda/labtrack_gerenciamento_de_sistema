"""Rastreabilidade: regras de negócio (RN-xx) → testes que as verificam.

As regras são lidas de ``docs/sample-lifecycle.md`` e os testes declaram o que
cobrem com ``@pytest.mark.rules("RN-12", ...)``. A matriz resultante fica em
``docs/testing.md`` e é conferida por ``tests/unit/test_traceability.py``.

Para atualizar o documento depois de marcar novos testes::

    python -m tests.traceability --write
"""

import ast
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
TESTS_DIR = BACKEND / "tests"
RULES_DOC = ROOT / "docs" / "sample-lifecycle.md"
MATRIX_DOC = ROOT / "docs" / "testing.md"
START = "<!-- rule-matrix:start -->"
END = "<!-- rule-matrix:end -->"

_RULE_ROW = re.compile(r"^\| (RN-\d{2}) \| (.+?) \|\s*$")


@dataclass(frozen=True)
class Rule:
    id: str
    text: str


@dataclass(frozen=True)
class RuleTest:
    path: str  # relativo a backend/tests
    name: str
    rules: tuple[str, ...]


def documented_rules() -> list[Rule]:
    rules = []
    for line in RULES_DOC.read_text(encoding="utf-8").splitlines():
        match = _RULE_ROW.match(line)
        if match:
            rules.append(Rule(match.group(1), match.group(2).strip()))
    return rules


def _marked_rules(decorator: ast.expr) -> tuple[str, ...]:
    """IDs de ``@pytest.mark.rules("RN-01", ...)``; vazio para outros decoradores."""
    if not isinstance(decorator, ast.Call):
        return ()
    func = decorator.func
    if not (
        isinstance(func, ast.Attribute)
        and func.attr == "rules"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "mark"
    ):
        return ()
    return tuple(
        arg.value
        for arg in decorator.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    )


def marked_tests() -> list[RuleTest]:
    found = []
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                ids = tuple(rule for d in node.decorator_list for rule in _marked_rules(d))
                if ids:
                    relative = path.relative_to(TESTS_DIR).as_posix()
                    found.append(RuleTest(relative, node.name, ids))
    return found


def coverage() -> dict[str, list[RuleTest]]:
    by_rule: dict[str, list[RuleTest]] = defaultdict(list)
    for test in marked_tests():
        for rule in test.rules:
            by_rule[rule].append(test)
    return by_rule


def render_matrix() -> str:
    """Tabela Markdown: regra, resumo e testes (agrupados por arquivo)."""
    by_rule = coverage()
    lines = [
        "| Regra | Testes |",
        "| ----- | ------ |",
    ]
    for rule in documented_rules():
        files: dict[str, list[str]] = defaultdict(list)
        for test in by_rule.get(rule.id, []):
            files[test.path].append(test.name)
        cells = [
            f"`{path}`: " + ", ".join(f"`{name}`" for name in names)
            for path, names in files.items()
        ]
        lines.append(f"| {rule.id} | {'<br>'.join(cells) or '**sem teste**'} |")
    return "\n".join(lines)


def documented_matrix() -> str:
    text = MATRIX_DOC.read_text(encoding="utf-8")
    return text.split(START, 1)[1].split(END, 1)[0].strip()


def write_matrix() -> None:
    text = MATRIX_DOC.read_text(encoding="utf-8")
    before, rest = text.split(START, 1)
    after = rest.split(END, 1)[1]
    MATRIX_DOC.write_text(f"{before}{START}\n{render_matrix()}\n{END}{after}", encoding="utf-8")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write_matrix()
        print(f"Matriz atualizada em {MATRIX_DOC.relative_to(ROOT)}")
    else:
        print(render_matrix())
