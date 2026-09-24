"""Dependências compartilhadas pelas rotas."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    """Uma sessão por requisição.

    O commit é responsabilidade do serviço (fim do caso de uso). Aqui garantimos
    apenas que nada fique pendente: em caso de erro, desfaz; no fim, fecha.
    """
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]
