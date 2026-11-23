from sqlalchemy import inspect, text


def legacy_allocation(slug, target):
    return None if slug.startswith("utama") and target == 0 else target


LEGACY_ALLOCATION_SQL = "CASE WHEN slug LIKE 'utama%' AND target_amount = 0 THEN NULL ELSE target_amount END"


def ensure_pocket_schema(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        # 1. Seamless migration: Rename legacy jago_pockets to universal pockets
        if "jago_pockets" in tables and "pockets" not in tables:
            connection.execute(text("ALTER TABLE jago_pockets RENAME TO pockets"))
        elif "jago_pockets" in tables and "pockets" in tables:
            # If pockets table was created empty by create_all while jago_pockets had data
            p_count = connection.execute(text("SELECT COUNT(*) FROM pockets")).scalar()
            j_count = connection.execute(text("SELECT COUNT(*) FROM jago_pockets")).scalar()
            if p_count == 0 and j_count > 0:
                # Copy existing data from jago_pockets to pockets
                j_cols = [c["name"] for c in inspector.get_columns("jago_pockets")]
                p_cols = [c["name"] for c in inspector.get_columns("pockets")]
                common_cols = [c for c in j_cols if c in p_cols]
                cols_str = ", ".join(common_cols)
                select_cols = cols_str
                if "allocation_amount" in p_cols and "allocation_amount" not in j_cols and {"slug", "target_amount"} <= set(j_cols):
                    cols_str += ", allocation_amount"
                    select_cols += f", {LEGACY_ALLOCATION_SQL}"
                connection.execute(text(f"INSERT INTO pockets ({cols_str}) SELECT {select_cols} FROM jago_pockets"))
                connection.execute(text("DROP TABLE jago_pockets"))

    # Re-inspect tables after migration
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    target_table = "pockets" if "pockets" in tables else ("jago_pockets" if "jago_pockets" in tables else None)

    if target_table:
        columns = {column["name"] for column in inspector.get_columns(target_table)}
        if "allocation_amount" not in columns:
            with engine.begin() as connection:
                if engine.dialect.name == "postgresql":
                    connection.execute(text(f"LOCK TABLE {target_table} IN ACCESS EXCLUSIVE MODE"))
                elif engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                current_columns = {column["name"] for column in inspect(connection).get_columns(target_table)}
                if "allocation_amount" not in current_columns:
                    connection.execute(text(f"ALTER TABLE {target_table} ADD COLUMN allocation_amount BIGINT"))
                    if {"slug", "target_amount"} <= current_columns:
                        connection.execute(text(f"UPDATE {target_table} SET allocation_amount = {LEGACY_ALLOCATION_SQL}"))
        with engine.begin() as connection:
            if "subscription_id" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {target_table} ADD COLUMN subscription_id INTEGER "
                    "REFERENCES subscriptions(id) ON DELETE RESTRICT"
                ))
            if "balance" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {target_table} ADD COLUMN balance BIGINT DEFAULT 0 NOT NULL"
                ))
            if "account_id" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {target_table} ADD COLUMN account_id INTEGER "
                    "REFERENCES accounts(id) ON DELETE CASCADE"
                ))
            if "role" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {target_table} ADD COLUMN role VARCHAR(30) DEFAULT 'operasional' NOT NULL"
                ))
            indexes = {idx["name"] for idx in inspector.get_indexes(target_table)}
            if "uq_pocket_subscription" not in indexes:
                connection.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS uq_pocket_subscription "
                    f"ON {target_table} (user_id, subscription_id)"
                ))

    if "transactions" in tables:
        tx_columns = {column["name"] for column in inspector.get_columns("transactions")}
        if "pocket_id" not in tx_columns:
            ref_table = target_table or "pockets"
            with engine.begin() as connection:
                connection.execute(text(
                    f"ALTER TABLE transactions ADD COLUMN pocket_id INTEGER "
                    f"REFERENCES {ref_table}(id) ON DELETE SET NULL"
                ))

    if target_table:
        # Add and initialize the anchor atomically once. Existing allocations were
        # interpreted against the current cycle; preserve that starting balance.
        with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text(f"LOCK TABLE {target_table} IN ACCESS EXCLUSIVE MODE"))
            elif engine.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            current_columns = {column["name"] for column in inspect(connection).get_columns(target_table)}
            if "allocation_start_date" not in current_columns:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                from app.core.config import settings
                from sqlalchemy.orm import Session

                connection.execute(text(f"ALTER TABLE {target_table} ADD COLUMN allocation_start_date DATE"))
                today = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
                required = {"paycheck_configs", "paycheck_sessions", "paycheck_cycles",
                            "paycheck_receipts", "legacy_paycheck_cycles", "transactions"}
                user_ids = list(connection.execute(text(f"SELECT DISTINCT user_id FROM {target_table}" )).scalars())
                with Session(bind=connection) as db:
                    for user_id in user_ids:
                        start = today
                        if required <= tables:
                            from app.api.v1.endpoints.pockets import get_current_cycle_bounds
                            start, _ = get_current_cycle_bounds(db, user_id, today)
                        connection.execute(text(f"UPDATE {target_table} SET allocation_start_date=:start WHERE user_id=:user_id"),
                                           {"start": start, "user_id": user_id})


# Backward compatibility alias
ensure_pocket_subscription_schema = ensure_pocket_schema
