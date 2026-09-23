"""Camada de domínio: regras de negócio puras do LIMS.

Enums, máquina de estados da amostra, avaliação de especificação (OOS) e matriz
de permissões por perfil. Não depende de FastAPI, SQLAlchemy nem de nenhum
detalhe de infraestrutura, por isso é trivial de testar e sobrevive a uma
troca de tecnologia.

Pode importar: ``core`` (apenas exceções/utilitários sem dependência externa).
"""
