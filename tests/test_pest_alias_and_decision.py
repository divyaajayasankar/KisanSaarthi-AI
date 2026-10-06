import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import RegistryEntry
from app.services import decision_controller as dc
from app.services.pest_alias_service import (
    find_alias_in_text,
    match_registry,
    resolve_pest,
    split_registry_pest,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    def add(crop, pest, verified=True, test=False):
        session.add(
            RegistryEntry(
                crop=crop, pest=pest, active_ingredient="TEST_AI", formulation="TEST",
                dose_min_per_hectare=100, dose_max_per_hectare=200, dose_unit="ml",
                phi_days=10, phi_not_applicable=False, source_document="TEST",
                source_page=0, source_url="TEST", verified=verified, is_test_data=test,
            )
        )

    add("Rice", "Blast; Sheath blight")
    add("Wheat", "Yellow rust")
    add("Okra", "Shoot and fruit borer", verified=False)
    session.commit()
    yield session
    session.close()


def test_split_compound_registry_string():
    assert split_registry_pest("Blast; Sheath blight") == ["blast", "sheath blight"]
    assert split_registry_pest("White grub, Termite") == ["white grub", "termite"]


def test_alias_found_in_english_free_text():
    alias = find_alias_in_text("Rice", "my paddy shows neck blast since 3 days")
    assert alias.canonical == "Blast"


def test_alias_found_in_tamil_text_with_suffix():
    alias = find_alias_in_text("rice", "நெல்லில் குலை நோய் வந்துள்ளது")
    assert alias.canonical == "Blast"


def test_longest_alias_wins():
    assert find_alias_in_text("tomato", "tomato late blight").canonical == "Late blight"


def test_resolve_to_full_compound_registry_pest(db):
    result = resolve_pest(db, "Rice", "rice blast")
    assert result.resolved
    assert result.registry_pest == "Blast; Sheath blight"
    assert result.method == "alias+registry"


def test_resolve_second_token(db):
    assert resolve_pest(db, "rice", "sheath blight").registry_pest == "Blast; Sheath blight"


def test_model_label_resolves(db):
    assert resolve_pest(db, "Rice", "brown_spot").method == "alias_unregistered"


def test_unique_word_subset_match(db):
    pest, token = match_registry(db, "Wheat", "rust")
    assert pest == "Yellow rust" and token == "yellow rust"


def test_unverified_registry_row_not_used(db):
    assert not resolve_pest(db, "Okra", "fruit borer").resolved


def test_unknown_phrase_not_found(db):
    assert resolve_pest(db, "Rice", "purple elephants").method == "not_found"


@pytest.mark.parametrize(
    "status,rules,expected,field",
    [
        ("recommend", ["phi_passed"], dc.ANSWER, None),
        ("delay", ["weather_rain_delay"], dc.ANSWER, None),
        ("abstain", ["phi_passed", "weather_context_missing"], dc.ASK_FOLLOW_UP, "location"),
        ("abstain", ["treatment_interval_context_missing"], dc.ASK_FOLLOW_UP, "days_since_last_application"),
        ("abstain", ["registration_missing"], dc.ABSTAIN, None),
        ("abstain", ["phi_rejected"], dc.ABSTAIN, None),
        (None, [], dc.ABSTAIN, None),
    ],
)
def test_engine_mapping(status, rules, expected, field):
    decision = dc.decide_engine(status=status, fired_rules=rules)
    assert decision.decision == expected
    assert decision.follow_up_field == field


def test_vision_thresholds(monkeypatch):
    monkeypatch.setattr(dc.settings, "vision_answer_threshold", 0.8)
    monkeypatch.setattr(dc.settings, "vision_ask_threshold", 0.55)
    assert dc.decide_vision(model_supported=True, confidence=0.91).decision == dc.ANSWER
    assert dc.decide_vision(model_supported=True, confidence=0.62).decision == dc.ASK_FOLLOW_UP
    assert dc.decide_vision(model_supported=True, confidence=0.30).decision == dc.ABSTAIN
    assert dc.decide_vision(model_supported=False, confidence=None).reason == "image_model_not_validated_for_crop"


def test_thresholds_configurable(monkeypatch):
    monkeypatch.setattr(dc.settings, "vision_answer_threshold", 0.95)
    assert dc.decide_vision(model_supported=True, confidence=0.91).decision == dc.ASK_FOLLOW_UP
