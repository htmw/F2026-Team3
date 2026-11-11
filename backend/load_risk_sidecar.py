from datetime import datetime

from sqlalchemy import insert, select, func

from database import engine
from risk_mvp.generate import generate
from risk_mvp.models import RISK_TABLES


EXPECTED_DB = "acadmate_risk_integration"


def parse_datetime(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def main():
    # Safety check
    if engine.url.database != EXPECTED_DB:
        raise RuntimeError(
            f"Refusing to load risk data into database: {engine.url.database}"
        )

    bundle = generate()

    print("Target database:", engine.url.database)
    print("Risk data to load:")

    for name, count in bundle["manifest"]["counts"].items():
        print(f"  {name}: {count}")

    with engine.begin() as connection:

        # Refuse to overwrite existing risk data
        for table in RISK_TABLES:
            existing = connection.execute(
                select(func.count()).select_from(table)
            ).scalar_one()

            if existing != 0:
                raise RuntimeError(
                    f"{table.name} already contains {existing} rows. "
                    "Refusing automatic overwrite."
                )

        # Insert in dependency-safe order
        for table in RISK_TABLES:
            rows = bundle["tables"][table.name]

            converted_rows = []

            for row in rows:
                converted = {}

                for column in table.columns:
                    value = row.get(column.name)

                    if value is not None and column.type.__class__.__name__.lower() == "datetime":
                        value = parse_datetime(value)

                    converted[column.name] = value

                converted_rows.append(converted)

            if converted_rows:
                connection.execute(insert(table), converted_rows)

            print(f"Inserted {len(converted_rows)} rows into {table.name}")

    print("\nRisk sidecar data imported successfully.")


if __name__ == "__main__":
    main()