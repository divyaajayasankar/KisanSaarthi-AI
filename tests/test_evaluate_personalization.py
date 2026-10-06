"""The personalization evaluator must pass against the real engine on a
known fixture, and must FAIL when the engine is wrong (so it can actually
detect regressions)."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models_crop_soil  # noqa: F401
import app.models_resistance  # noqa: F401
from app.db import Base
from app.models import RegistryEntry
from app.models_growth_stage import GrowthStageRule
from app.models_treatment_history import TreatmentHistoryRule
from scripts import evaluate_personalization as ep


def _registry(crop, pest, ai, dose, unit, phi, na=False):
    return RegistryEntry(
        crop=crop, pest=pest, active_ingredient=ai, formulation="FIXTURE",
        dose_min_per_hectare=dose, dose_max_per_hectare=dose, dose_unit=unit, phi_days=phi,
        phi_not_applicable=na, source_document="FIXTURE", source_page=1,
        source_url="https://example.org/fixture", verified=True, is_test_data=False,
    )


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        _registry("Rice", "Blast; Sheath blight", "Tricyclazole", 300, "g", 14),
        _registry("Banana", "Sigatoka", "Propiconazole", 500, "ml", 0, na=True),
        GrowthStageRule(
            crop="Rice", pest="Blast; Sheath blight", active_ingredient="Tricyclazole",
            allowed_stages="vegetative;reproductive", application_timing="fixture",
            source_document="FIXTURE", source_page=1, source_url="x", source_date="2020-01-01", verified=True,
        ),
        TreatmentHistoryRule(
            crop="Rice", pest="Blast; Sheath blight", active_ingredient="Tricyclazole",
            max_applications=3, min_interval_days=None, history_scope="season", application_stage=None,
            verified=True, source_document="FIXTURE", source_page=1, source_url="x", notes="fixture",
        ),
    ])
    session.commit()
    yield session
    session.close()


def test_all_dimensions_pass_on_the_real_engine(db):
    rice = db.query(RegistryEntry).filter_by(crop="Rice").one()
    banana = db.query(RegistryEntry).filter_by(crop="Banana").one()
    results = (
        ep.dose_cases(rice) + ep.phi_cases(rice) + ep.phi_cases(banana)
        + ep.growth_cases(db, rice) + ep.history_cases(db, rice) + ep.weather_cases()
    )
    failed = [r for r in results if not r["pass"]]
    assert not failed, failed
    dimensions = {r["dimension"] for r in results}
    assert dimensions == {"dose", "phi", "growth_stage", "history", "weather"}
    assert len([r for r in results if r["dimension"] == "history"]) == 2


def test_phi_cases_cover_both_sides_of_the_boundary(db):
    rice = db.query(RegistryEntry).filter_by(crop="Rice").one()
    scenarios = {r["scenario"]: (r["expected"], r["actual"]) for r in ep.phi_cases(rice)}
    assert scenarios["harvest in 13 d, PHI 14 d"] == ("abstain", "abstain")
    assert scenarios["harvest in 14 d, PHI 14 d"] == ("recommend", "recommend")


def test_evaluator_detects_a_broken_dose_scaling(db, monkeypatch):
    """Same acre factor 5% too high -> dose cases must fail."""
    real = ep.evaluate_advisory

    def wrong(**kwargs):
        result = real(**kwargs)
        if result.scaled_dose_min is not None:
            result.scaled_dose_min = round(result.scaled_dose_min * 1.05, 2)
        return result

    monkeypatch.setattr(ep, "evaluate_advisory", wrong)
    rice = db.query(RegistryEntry).filter_by(crop="Rice").one()
    assert any(not r["pass"] for r in ep.dose_cases(rice))


def test_evaluator_detects_a_phi_regression(db, monkeypatch):
    def always_recommend(**kwargs):
        return SimpleNamespace(status="recommend", scaled_dose_min=1.0)

    monkeypatch.setattr(ep, "evaluate_advisory", always_recommend)
    rice = db.query(RegistryEntry).filter_by(crop="Rice").one()
    assert any(not r["pass"] for r in ep.phi_cases(rice))
