from app.db import SessionLocal
from app.models import RegistryEntry

with SessionLocal() as db:
    existing = db.query(RegistryEntry).filter_by(crop="demo_crop", pest="demo_pest", is_test_data=True).first()
    if not existing:
        db.add(
            RegistryEntry(
                crop="demo_crop",
                pest="demo_pest",
                active_ingredient="TEST_ACTIVE_INGREDIENT",
                dose_per_hectare=100.0,
                dose_unit="ml",
                phi_days=10,
                source_artifact="TEST_ONLY_DO_NOT_CITE",
                verified=True,
                is_test_data=True,
            )
        )
        db.commit()

print("Inserted TEST-ONLY registry row.")
print("Use crop=demo_crop and pest=demo_pest only to verify the UI pipeline.")
