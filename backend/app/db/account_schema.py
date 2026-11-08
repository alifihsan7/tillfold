from sqlalchemy import inspect, text


def ensure_account_archive_schema(engine):
    inspector = inspect(engine)
    if "accounts" not in inspector.get_table_names():
        return
    if "is_archived" not in {column["name"] for column in inspector.get_columns("accounts")}:
        with engine.begin() as connection:
            optional = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
            connection.execute(text(f"ALTER TABLE accounts ADD COLUMN {optional}is_archived BOOLEAN NOT NULL DEFAULT FALSE"))


def ensure_user_spreadsheet_schema(engine):
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    if "google_spreadsheet_id" not in {column["name"] for column in inspector.get_columns("users")}:
        with engine.begin() as connection:
            optional = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {optional}google_spreadsheet_id VARCHAR(255)"))

