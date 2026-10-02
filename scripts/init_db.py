from app.db import Base, engine, SessionLocal
from app.models import DataProvenance

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    if not db.query(DataProvenance).filter_by(artifact_name="CIBRC Major Uses").first():
        db.add(
            DataProvenance(
                artifact_name="CIBRC Major Uses",
                source_url="https://ppqs.gov.in/",
                verified=False,
                notes="Manual download and verification required before real advisory use.",
            )
        )
    db.commit()

print("Database tables created.")
print("CIBRC provenance row added as UNVERIFIED.")
