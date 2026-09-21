from functools import lru_cache
from sqlalchemy import create_engine, text
from app.config import DATABASE_URL, STATEMENT_TIMEOUT_MS


@lru_cache(maxsize=1)
def get_engine():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada no .env")
    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        connect_args={
            "options": (
                f"-c statement_timeout={STATEMENT_TIMEOUT_MS} "
                f"-c default_transaction_read_only=on"
            )
        },
    )


def run_select(sql: str, max_rows: int):
    with get_engine().connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, r)) for r in result.fetchmany(max_rows)]
    return columns, rows