"""Regression tests for the Step 1 baseline fixes."""

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, engine
from app.models import RegistryEntry
from app.models_resistance import ResistanceRule
from app.services.constraint_engine import evaluate_advisory
from app.services.resistance_service import evaluate_resistance_management


def _entry(**overrides):
    values = dict(
        crop="Rice",
        pest="Blast",
        active_ingredient="TestAI",
        dose_min_per_hectare=500.0,
        dose_max_per_hectare=500.0,
        dose_unit="ml",
        phi_days=14,
        phi_not_applicable=False,
        verified=True,
        is_test_data=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_tests_never_use_live_database():
    assert not str(engine.url).endswith("/kisansaarthi.db")
    assert "kisansaarthi_test_" in str(engine.url)


def test_registry_entry_has_no_duplicate_columns():
    names = [column.name for column in RegistryEntry.__table__.columns]
    assert len(names) == len(set(names))


def test_phi_passed_fires_exactly_once():
    result = evaluate_advisory(
        registry_entry=_entry(),
        field_area=1,
        area_unit="hectare",
        expected_harvest_days=30,
    )
    assert result.status == "recommend"
    assert result.fired_rules.count("phi_passed") == 1


def test_phi_not_applicable_does_not_also_fire_phi_passed():
    result = evaluate_advisory(
        registry_entry=_entry(phi_days=0, phi_not_applicable=True),
        field_area=1,
        area_unit="hectare",
        expected_harvest_days=5,
    )
    assert result.status == "recommend"
    assert "phi_not_applicable" in result.fired_rules
    assert "phi_passed" not in result.fired_rules


def test_phi_rejection_unchanged():
    result = evaluate_advisory(
        registry_entry=_entry(phi_days=14),
        field_area=1,
        area_unit="hectare",
        expected_harvest_days=7,
    )
    assert result.status == "abstain"
    assert result.fired_rules.count("phi_rejected") == 1


def test_resistance_lookup_is_case_insensitive():
    memory_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=memory_engine)
    session = sessionmaker(bind=memory_engine)()
    try:
        session.add(
            ResistanceRule(
                crop="Rice",
                pest="Blast; Sheath blight",
                active_ingredient="Kresoxim-methyl",
                framework="FRAC",
                moa_group="11",
                moa_name="QoI fungicides",
                resistance_risk="high",
                rotation_recommended=True,
                verified=True,
                source_name="FRAC",
                source_url="https://www.frac.info/",
                notes="Test resistance rule.",
            )
        )
        session.commit()

        exact = evaluate_resistance_management(
            db=session,
            crop="Rice",
            pest="Blast; Sheath blight",
            active_ingredient="Kresoxim-methyl",
            previous_application_count=1,
        )
        lowered = evaluate_resistance_management(
            db=session,
            crop="rice",
            pest=" blast; sheath blight ",
            active_ingredient="KRESOXIM-METHYL",
            previous_application_count=1,
        )
        assert exact["mode_of_action_groups"]
        assert exact["fired_rules"] == lowered["fired_rules"]
        assert exact["mode_of_action_groups"] == lowered["mode_of_action_groups"]
    finally:
        session.close()
