"""Casos de uso e regras de negócio da aplicação.

Orquestra repositórios e regras do domínio dentro de uma transação: cadastro de
amostras, workflow de status, registro de resultados com avaliação OOS,
integração com instrumentos e gravação do audit trail. Não conhece HTTP; sinaliza
falhas com exceções da aplicação, que a camada ``api`` converte em respostas.

Pode importar: ``repositories``, ``models``, ``domain``, ``schemas``, ``core``,
``database``.
"""
