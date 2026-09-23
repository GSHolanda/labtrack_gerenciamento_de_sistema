"""Acesso a dados (padrão Repository).

Encapsula consultas SQLAlchemy (filtros, paginação, joins) atrás de métodos com
nomes do domínio, como ``find_by_code`` ou ``search``. Não decide regra de
negócio e não controla transação: quem faz ``commit`` é o serviço.

Pode importar: ``models``, ``database``, ``domain``, ``schemas``, ``core``.
"""
