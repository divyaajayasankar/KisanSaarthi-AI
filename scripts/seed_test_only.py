"""Insert one TEST-ONLY registry row for UI pipeline checks.

The row is flagged is_test_data=True and uses a fake crop/pest so it can
never be confused with a verified CIB&RC record.
"""

from app.db import Base, SessionLocal, engine
from app.models import RegistryEntry


def main() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        existing = (
            db.query(RegistryEntry)
            .filter_by(
                crop="demo_crop",
                pest="demo_pest",
                is_test_data=True,
            )
            .first()
        )

        if existing:
            print("TEST-ONLY registry row already present.")
            return

        db.add(
            RegistryEntry(
                crop="demo_crop",
                pest="demo_pest",
                active_ingredient="TEST_ACTIVE_INGREDIENT",
                formulation="TEST",
                dose_min_per_hectare=100.0,
                dose_max_per_hectare=100.0,
                dose_unit="ml",
                water_volume_l_per_ha=None,
                phi_days=10,
                phi_not_applicable=False,
                source_document="TEST_ONLY_DO_NOT_CITE",
                source_page=0,
                source_url="TEST_ONLY_DO_NOT_CITE",
                source_date=None,
                verified=True,
                is_test_data=True,
            )
        )
        db.commit()

    print("Inserted TEST-ONLY registry row.")
    print("Use crop=demo_crop and pest=demo_pest only to verify the UI pipeline.")


if __name__ == "__main__":
    main()
