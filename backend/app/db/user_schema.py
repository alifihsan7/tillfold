from sqlalchemy import inspect, text
from app.db.account_schema import ensure_user_spreadsheet_schema


def ensure_user_session_schema(engine):
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    if "session_version" not in {column["name"] for column in inspector.get_columns("users")}:
        with engine.begin() as connection:
            optional = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {optional}session_version INTEGER NOT NULL DEFAULT 0"))


__all__ = ["ensure_user_spreadsheet_schema", "ensure_user_session_schema"]
