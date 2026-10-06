from pathlib import Path
import csv
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from sqlalchemy import select

from app.db import Base, engine, SessionLocal
from app.models_resistance import ResistanceRule


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "resistance"
    / "resistance_rules.csv"
)


def parse_bool(value: str | None) -> bool:

    if value is None:
        return False

    return (
        value.strip()
        .lower()
        in {
            "true",
            "1",
            "yes",
            "y",
        }
    )


def main():

    if not CSV_PATH.exists():

        raise FileNotFoundError(
            f"Resistance CSV not found: {CSV_PATH}"
        )


    # Create resistance_rules table if needed
    Base.metadata.create_all(
        bind=engine
    )


    inserted = 0
    updated = 0


    with SessionLocal() as db:

        with CSV_PATH.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)


            for row in reader:

                crop = row["crop"].strip()

                pest = row["pest"].strip()

                active_ingredient = (
                    row["active_ingredient"]
                    .strip()
                )

                framework = (
                    row["framework"]
                    .strip()
                )

                moa_group = (
                    row["moa_group"]
                    .strip()
                )


                # ---------------------------------------------
                # Check whether this rule already exists
                # ---------------------------------------------

                existing = (
                    db.execute(
                        select(
                            ResistanceRule
                        ).where(
                            ResistanceRule.crop
                            == crop,

                            ResistanceRule.pest
                            == pest,

                            ResistanceRule.active_ingredient
                            == active_ingredient,

                            ResistanceRule.framework
                            == framework,

                            ResistanceRule.moa_group
                            == moa_group,
                        )
                    )
                    .scalars()
                    .first()
                )


                values = {

                    "moa_name":
                        row["moa_name"].strip(),

                    "resistance_risk":
                        (
                            row.get(
                                "resistance_risk",
                                ""
                            ).strip()
                            or None
                        ),

                    "rotation_recommended":
                        parse_bool(
                            row.get(
                                "rotation_recommended"
                            )
                        ),

                    "verified":
                        parse_bool(
                            row.get(
                                "verified"
                            )
                        ),

                    "source_name":
                        (
                            row.get(
                                "source_name",
                                ""
                            ).strip()
                            or None
                        ),

                    "source_url":
                        (
                            row.get(
                                "source_url",
                                ""
                            ).strip()
                            or None
                        ),

                    "notes":
                        (
                            row.get(
                                "notes",
                                ""
                            ).strip()
                            or None
                        ),
                }


                if existing:

                    for key, value in values.items():

                        setattr(
                            existing,
                            key,
                            value,
                        )

                    updated += 1


                else:

                    rule = ResistanceRule(

                        crop=crop,

                        pest=pest,

                        active_ingredient=
                            active_ingredient,

                        framework=framework,

                        moa_group=moa_group,

                        **values,
                    )

                    db.add(rule)

                    inserted += 1


        db.commit()


        all_rules = (
            db.execute(
                select(
                    ResistanceRule
                ).order_by(
                    ResistanceRule.id
                )
            )
            .scalars()
            .all()
        )


        print()
        print("Resistance rule ingestion complete.")
        print("-----------------------------------")

        print(
            f"Inserted: {inserted}"
        )

        print(
            f"Updated: {updated}"
        )

        print(
            f"Total resistance rules: "
            f"{len(all_rules)}"
        )

        print()


        for rule in all_rules:

            print(
                f"ID={rule.id} | "
                f"{rule.crop} | "
                f"{rule.pest} | "
                f"{rule.active_ingredient} | "
                f"{rule.framework} "
                f"{rule.moa_group} | "
                f"{rule.moa_name} | "
                f"rotation={rule.rotation_recommended} | "
                f"verified={rule.verified}"
            )


if __name__ == "__main__":

    main()
