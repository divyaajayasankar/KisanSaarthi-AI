import pytest

from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.models import RegistryEntry

import app.routers.advisory as advisory_router


# ============================================================
# TEST DATABASE
# ============================================================

TEST_DATABASE_URL = "sqlite://"


engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db

    finally:
        db.close()


# ============================================================
# TEST SETUP
# ============================================================

@pytest.fixture(autouse=True)
def prepare_test_environment():

    app.dependency_overrides[
        get_db
    ] = override_get_db

    Base.metadata.drop_all(
        bind=engine
    )

    Base.metadata.create_all(
        bind=engine
    )

    db = TestingSessionLocal()

    rice_entry = RegistryEntry(
        crop="Rice",

        pest="Blast; Sheath blight",

        active_ingredient=(
            "TEST_ACTIVE_INGREDIENT"
        ),

        formulation=(
            "TEST_FORMULATION"
        ),

        dose_min_per_hectare=500.0,

        dose_max_per_hectare=500.0,

        dose_unit="ml",

        water_volume_l_per_ha=500.0,

        phi_days=30,

        source_document=(
            "test_registry.pdf"
        ),

        source_page=1,

        source_url=(
            "https://ppqs.gov.in/test_registry.pdf"
        ),

        source_date=None,

        verified=True,

        is_test_data=False,
    )

    db.add(rice_entry)
    db.commit()
    db.close()

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


# ============================================================
# MOCK SAFE WEATHER
# ============================================================

def safe_weather(
    district: str,
    state: str,
):
    return {
        "location": {
            "name": district,
            "state": state,
            "country": "IN",
            "latitude": 13.0,
            "longitude": 80.0,
        },

        "weather": {
            "forecast_window_hours": 24,
            "rain_total_mm": 0.0,
            "max_rain_probability": 0.10,
            "max_wind_speed_m_s": 1.5,
            "min_temperature_c": 25.0,
            "max_temperature_c": 30.0,
            "conditions": [
                "clear sky"
            ],
        },

        "source": "TEST_WEATHER",
    }


# ============================================================
# MOCK UNSAFE WEATHER
# ============================================================

def unsafe_weather(
    district: str,
    state: str,
):
    return {
        "location": {
            "name": district,
            "state": state,
            "country": "IN",
            "latitude": 13.0,
            "longitude": 80.0,
        },

        "weather": {
            "forecast_window_hours": 24,
            "rain_total_mm": 5.0,
            "max_rain_probability": 0.90,
            "max_wind_speed_m_s": 5.0,
            "min_temperature_c": 25.0,
            "max_temperature_c": 30.0,
            "conditions": [
                "rain"
            ],
        },

        "source": "TEST_WEATHER",
    }


# ============================================================
# TEST 1 â€” SAFE WEATHER â†’ RECOMMEND
# ============================================================

def test_safe_weather_recommends(
    monkeypatch,
):

    monkeypatch.setattr(
        advisory_router,
        "get_location_weather",
        safe_weather,
    )

    response = client.post(
        "/api/advisory",
        json={
            "farmer_id": None,
            "crop": "Rice",
            "pest": "Blast; Sheath blight",
            "field_area": 0.5,
            "area_unit": "hectare",
            "expected_harvest_days": 40,
            "state": "Tamil Nadu",
            "district": "Chennai",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "recommend"

    assert (
        data["scaled_dose_min"]
        == 250.0
    )

    assert (
        data["scaled_dose_max"]
        == 250.0
    )

    assert (
        data["weather_status"]
        == "proceed"
    )

    assert (
        "phi_passed"
        in data["fired_rules"]
    )

    assert (
        "weather_conditions_passed"
        in data["fired_rules"]
    )

    assert (
        data["weather_source"]
        == "TEST_WEATHER"
    )


# ============================================================
# TEST 2 â€” UNSAFE WEATHER â†’ DELAY
# ============================================================

def test_unsafe_weather_delays(
    monkeypatch,
):

    monkeypatch.setattr(
        advisory_router,
        "get_location_weather",
        unsafe_weather,
    )

    response = client.post(
        "/api/advisory",
        json={
            "farmer_id": None,
            "crop": "Rice",
            "pest": "Blast; Sheath blight",
            "field_area": 0.5,
            "area_unit": "hectare",
            "expected_harvest_days": 40,
            "state": "Tamil Nadu",
            "district": "Chennai",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "delay"

    assert (
        data["weather_status"]
        == "delay"
    )

    assert (
        "weather_rain_delay"
        in data["fired_rules"]
    )

    assert (
        "weather_high_wind_delay"
        in data["fired_rules"]
    )

    assert (
        data["active_ingredient"]
        is None
    )

    assert (
        data["scaled_dose_min"]
        is None
    )

    assert (
        data["scaled_dose_max"]
        is None
    )


# ============================================================
# TEST 3 â€” LOCATION MISSING â†’ ABSTAIN
# ============================================================

def test_missing_weather_context_abstains():

    response = client.post(
        "/api/advisory",
        json={
            "farmer_id": None,
            "crop": "Rice",
            "pest": "Blast; Sheath blight",
            "field_area": 0.5,
            "area_unit": "hectare",
            "expected_harvest_days": 40,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "abstain"

    assert (
        "weather_context_missing"
        in data["fired_rules"]
    )

    assert (
        data["weather_status"]
        == "unavailable"
    )


# ============================================================
# TEST 4 â€” PHI FAILS BEFORE WEATHER
# ============================================================

def test_phi_failure_stops_before_weather(
    monkeypatch,
):

    def weather_should_not_run(
        district: str,
        state: str,
    ):
        raise AssertionError(
            "Weather API must not run after PHI rejection."
        )

    monkeypatch.setattr(
        advisory_router,
        "get_location_weather",
        weather_should_not_run,
    )

    response = client.post(
        "/api/advisory",
        json={
            "farmer_id": None,
            "crop": "Rice",
            "pest": "Blast; Sheath blight",
            "field_area": 0.5,
            "area_unit": "hectare",
            "expected_harvest_days": 20,
            "state": "Tamil Nadu",
            "district": "Chennai",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "abstain"

    assert (
        "phi_rejected"
        in data["fired_rules"]
    )

    assert (
        "weather_rain_delay"
        not in data["fired_rules"]
    )

    assert (
        "weather_high_wind_delay"
        not in data["fired_rules"]
    )


# ============================================================
# TEST 5 â€” REGISTRATION MISSING â†’ ABSTAIN
# ============================================================

def test_missing_registration_abstains():

    response = client.post(
        "/api/advisory",
        json={
            "farmer_id": None,
            "crop": "UnsupportedCrop",
            "pest": "UnsupportedPest",
            "field_area": 1.0,
            "area_unit": "hectare",
            "expected_harvest_days": 50,
            "state": "Tamil Nadu",
            "district": "Chennai",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "abstain"

    assert (
        "registration_missing"
        in data["fired_rules"]
    )
