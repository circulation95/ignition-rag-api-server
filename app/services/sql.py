from langchain_community.utilities import SQLDatabase

from app.core.config import settings


_sql_db: SQLDatabase | None = None


def build_db_uri() -> str:
    return (
        f"postgresql+psycopg2://{settings.sql_user}:{settings.sql_password}"
        f"@{settings.sql_host}:{settings.sql_port}/{settings.sql_db}"
    )


def get_sql_db() -> SQLDatabase:
    global _sql_db
    if _sql_db is None:
        _sql_db = SQLDatabase.from_uri(build_db_uri(), sample_rows_in_table_info=0)
    return _sql_db
