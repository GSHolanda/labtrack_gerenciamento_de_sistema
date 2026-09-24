"""Controle de acesso baseado em perfis (RBAC).

As rotas exigem **permissões**, nunca perfis. A matriz abaixo é a única fonte
da verdade sobre o que cada perfil pode fazer; mudar uma regra de acesso é
alterar uma linha aqui (e o teste correspondente).
"""

from enum import StrEnum

from app.domain.enums import RoleCode


class Permission(StrEnum):
    USER_MANAGE = "USER_MANAGE"
    MASTER_DATA_MANAGE = "MASTER_DATA_MANAGE"
    TEST_DEFINITION_MANAGE = "TEST_DEFINITION_MANAGE"
    INSTRUMENT_MANAGE = "INSTRUMENT_MANAGE"
    SAMPLE_READ = "SAMPLE_READ"
    SAMPLE_CREATE = "SAMPLE_CREATE"
    SAMPLE_ASSIGN_TESTS = "SAMPLE_ASSIGN_TESTS"
    SAMPLE_ANALYZE = "SAMPLE_ANALYZE"
    RESULT_ENTER = "RESULT_ENTER"
    SAMPLE_REVIEW = "SAMPLE_REVIEW"
    SAMPLE_CANCEL = "SAMPLE_CANCEL"
    AUDIT_READ = "AUDIT_READ"
    REPORT_EXPORT = "REPORT_EXPORT"
    DASHBOARD_VIEW = "DASHBOARD_VIEW"


P = Permission

# Nome e descrição de cada perfil (espelhados na migração 0002).
ROLE_DEFINITIONS: dict[RoleCode, tuple[str, str]] = {
    RoleCode.ADMIN: ("Administrador", "Gerencia usuários, cadastros, testes e instrumentos."),
    RoleCode.ANALYST: (
        "Analista de Laboratório",
        "Registra amostras, executa análises e insere resultados.",
    ),
    RoleCode.REVIEWER: ("Revisor", "Revisa resultados e aprova ou reprova amostras."),
    RoleCode.MANAGER: (
        "Gestor",
        "Acompanha indicadores, audit trail e pode cancelar amostras.",
    ),
}

ROLE_PERMISSIONS: dict[RoleCode, frozenset[Permission]] = {
    # Configura o sistema, mas não manipula dados analíticos (segregação de funções).
    RoleCode.ADMIN: frozenset(
        {
            P.USER_MANAGE,
            P.MASTER_DATA_MANAGE,
            P.TEST_DEFINITION_MANAGE,
            P.INSTRUMENT_MANAGE,
            P.SAMPLE_READ,
            P.AUDIT_READ,
            P.DASHBOARD_VIEW,
        }
    ),
    # Produz resultados, mas não os aprova.
    RoleCode.ANALYST: frozenset(
        {
            P.SAMPLE_READ,
            P.SAMPLE_CREATE,
            P.SAMPLE_ASSIGN_TESTS,
            P.SAMPLE_ANALYZE,
            P.RESULT_ENTER,
            P.REPORT_EXPORT,
            P.DASHBOARD_VIEW,
        }
    ),
    RoleCode.REVIEWER: frozenset(
        {P.SAMPLE_READ, P.SAMPLE_REVIEW, P.AUDIT_READ, P.REPORT_EXPORT, P.DASHBOARD_VIEW}
    ),
    RoleCode.MANAGER: frozenset(
        {P.SAMPLE_READ, P.SAMPLE_CANCEL, P.AUDIT_READ, P.REPORT_EXPORT, P.DASHBOARD_VIEW}
    ),
}


def permissions_for(role: str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[RoleCode(role)]
    except ValueError:
        return frozenset()


def has_permission(role: str, permission: Permission) -> bool:
    return permission in permissions_for(role)
