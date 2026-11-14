from sqlalchemy import inspect, text


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
                connection.execute(text(f"INSERT INTO pockets ({cols_str}) SELECT {cols_str} FROM jago_pockets"))
                connection.execute(text("DROP TABLE jago_pockets"))

    # Re-inspect tables after migration
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    target_table = "pockets" if "pockets" in tables else ("jago_pockets" if "jago_pockets" in tables else None)

    if target_table:
        columns = {column["name"] for column in inspector.get_columns(target_table)}
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


# Backward compatibility alias
ensure_pocket_subscription_schema = ensure_pocket_schema
