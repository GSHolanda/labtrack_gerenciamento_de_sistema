"""Toda regra de negócio documentada tem teste, e a matriz publicada está em dia."""

from tests.traceability import (
    MATRIX_DOC,
    coverage,
    documented_matrix,
    documented_rules,
    marked_tests,
    render_matrix,
)


def test_rules_are_documented_in_sequence() -> None:
    ids = [rule.id for rule in documented_rules()]
    assert ids == [f"RN-{number:02d}" for number in range(1, len(ids) + 1)]
    assert len(ids) >= 28


def test_every_business_rule_has_at_least_one_test() -> None:
    covered = coverage()
    missing = [rule.id for rule in documented_rules() if not covered.get(rule.id)]
    assert missing == [], f"Regras sem teste marcado com @pytest.mark.rules: {missing}"


def test_markers_only_reference_documented_rules() -> None:
    known = {rule.id for rule in documented_rules()}
    unknown = [
        f"{test.path}::{test.name} -> {rule}"
        for test in marked_tests()
        for rule in test.rules
        if rule not in known
    ]
    assert unknown == []


def test_published_matrix_is_up_to_date() -> None:
    assert documented_matrix() == render_matrix(), (
        f"{MATRIX_DOC.name} desatualizado: rode `python -m tests.traceability --write` em backend/"
    )
