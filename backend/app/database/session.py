"""Engine e fábrica de sessões do SQLAlchemy."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def build_engine(url: str, echo: bool = False) -> Engine:
    engine = create_engine(url, echo=echo, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        # O SQLite só valida chaves estrangeiras com este PRAGMA ligado.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objetos continuam legíveis após o commit do serviço.
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
