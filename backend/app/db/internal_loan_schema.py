from sqlalchemy import inspect, text
from app.db.session import Base
import app.models.internal_loan


def ensure_internal_loan_schema(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "internal_loans" not in tables:
        app.models.internal_loan.InternalLoan.__table__.create(bind=engine, checkfirst=True)
    else:
        columns = {column["name"] for column in inspector.get_columns("internal_loans")}
        with engine.begin() as connection:
            optional = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
            if "status" not in columns:
                connection.execute(text(f"ALTER TABLE internal_loans ADD COLUMN {optional}status VARCHAR(30) NOT NULL DEFAULT 'active'"))
            if "remaining_amount" not in columns:
                connection.execute(text(f"ALTER TABLE internal_loans ADD COLUMN {optional}remaining_amount BIGINT NOT NULL DEFAULT 0"))
            if "settled_at" not in columns:
                connection.execute(text(f"ALTER TABLE internal_loans ADD COLUMN {optional}settled_at TIMESTAMP WITH TIME ZONE"))
            if "note" not in columns:
                connection.execute(text(f"ALTER TABLE internal_loans ADD COLUMN {optional}note VARCHAR(255)"))
