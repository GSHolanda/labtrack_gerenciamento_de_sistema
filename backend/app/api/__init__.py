"""Camada HTTP (entrada da aplicação).

Responsável apenas por: rotas REST, validação de entrada/saída (via ``schemas``),
autenticação/autorização (dependências do FastAPI) e tradução de erros para
códigos HTTP. Não contém regra de negócio: delega tudo para ``services``.

Nunca acessa ``repositories`` diretamente. Usa ``database`` e ``models`` apenas
para injetar a sessão e tipar o usuário autenticado.
"""
