"""Engine e fábrica de sessões do SQLAlchemy."""

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(url: str, echo: bool = False) -> Engine:
    options: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
    if url.startswith("sqlite") and ":memory:" in url:
        # Banco em memória (testes): uma única conexão compartilhada entre threads.
        options.update(poolclass=StaticPool, connect_args={"check_same_thread": False})

    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        # O SQLite só valida chaves estrangeiras com este PRAGMA ligado.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objetos continuam legíveis após o commit do serviço.
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
