from langchain_core.tools import tool

from app.services.sql import get_sql_db


@tool
def db_list_tables():
    """List all tables."""
    try:
        return get_sql_db().get_table_names()
    except Exception as exc:
        return f"Error: {exc}"


@tool
def db_get_schema(table_names: str):
    """Get schema info for table names (comma separated)."""
    try:
        if isinstance(table_names, list):
            table_names = ", ".join(table_names)
        return get_sql_db().get_table_info(table_names.split(","))
    except Exception as exc:
        return f"Error: {exc}"


@tool
def db_query(query: str):
    """Run a read-only SELECT query. Always include LIMIT."""
    try:
        if any(x in query.lower() for x in ["update", "delete", "drop", "insert"]):
            return "Error: Read-only allowed."
        return get_sql_db().run(query)
    except Exception as exc:
        return f"SQL Error: {exc}"


sql_tools_list = [db_list_tables, db_get_schema, db_query]
