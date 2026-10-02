from sqlalchemy import inspect, text

from app.db import engine


TABLE_NAME = "registry_entries"
COLUMN_NAME = "phi_not_applicable"


inspector = inspect(engine)

existing_columns = {
    column["name"]
    for column in inspector.get_columns(
        TABLE_NAME
    )
}


if COLUMN_NAME in existing_columns:

    print(
        "phi_not_applicable already exists. "
        "No migration required."
    )

else:

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                ALTER TABLE registry_entries
                ADD COLUMN phi_not_applicable
                BOOLEAN NOT NULL DEFAULT 0
                """
            )
        )

    print(
        "Added phi_not_applicable column successfully."
    )