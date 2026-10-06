import pytest

from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.models import RegistryEntry

import app.routers.advisory as advisory_router

from app.services.soil_service import SoilServiceError


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
            "https://ppqs.gov.in/"
            "test_registry.pdf"
        ),

        source_date=None,

        verified=True,

        is_test_data=False,
    )


    db.add(
        rice_entry
    )

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
        },

        "weather": {

            "forecast_window_hours": 24,

            "rain_total_mm": 0.0,

            "max_rain_probability": 0.10,

            "max_wind_speed_m_s": 1.5,

            "min_temperature_c": 25.0,

            "max_temperature_c": 31.0,

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
        },

        "weather": {

            "forecast_window_hours": 24,

            "rain_total_mm": 0.0,

            "max_rain_probability": 0.10,

            "max_wind_speed_m_s": 5.0,

            "min_temperature_c": 25.0,

            "max_temperature_c": 31.0,

            "conditions": [
                "clear sky"
            ],
        },

        "source": "TEST_WEATHER",
    }


# ============================================================
# MOCK VALID ROOT-ZONE SOIL
# ============================================================

def valid_soil(
    latitude: float,
    longitude: float,
):

    return {

        "coordinates": {

            "latitude": latitude,

            "longitude": longitude,
        },


        "root_zone": {

            "depth_top_cm": 0,

            "depth_bottom_cm": 30,

            "soil_ph": 6.53,

            "sand_percent": 44.92,

            "silt_percent": 19.25,

            "clay_percent": 35.78,

            "dominant_texture_component": "sand",

            "source": (
                "SoilGrids root-zone aggregation"
            ),
        },


        "aggregation": (
            "depth-weighted mean"
        ),


        "root_zone_depth": (
            "0-30cm"
        ),


        "source": (
            "TEST_SOILGRIDS"
        ),
    }


# ============================================================
# TEST 1
#
# SAFE WEATHER + VALID SOIL
#           â†“
#      RECOMMEND
# ============================================================

def test_safe_weather_and_valid_soil_recommends(
    monkeypatch,
):

    monkeypatch.setattr(
        advisory_router,
        "get_location_weather",
        safe_weather,
    )


    monkeypatch.setattr(
        advisory_router,
        "get_root_zone_soil_context",
        valid_soil,
    )


    response = client.post(

        "/api/advisory",

        json={

            "farmer_id": None,

            "crop": "Rice",

            "pest":
                "Blast; Sheath blight",

            "field_area": 0.5,

            "area_unit": "hectare",

            "expected_harvest_days": 40,

            "state": "Tamil Nadu",

            "district": "Chennai",

            "latitude": 11.0,

            "longitude": 77.0,
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert (
        data["status"]
        == "recommend"
    )


    assert (
        data["weather_status"]
        == "proceed"
    )


    assert (
        data["soil_status"]
        == "available"
    )


    assert (
        data["soil_source"]
        == "TEST_SOILGRIDS"
    )


    assert (
        data["soil_summary"][
            "root_zone"
        ][
            "soil_ph"
        ]
        == 6.53
    )


    assert (
        data["soil_summary"][
            "root_zone_depth"
        ]
        == "0-30cm"
    )


    assert (
        "soil_context_available"
        in data["fired_rules"]
    )


    assert (
        "weather_conditions_passed"
        in data["fired_rules"]
    )


    assert (
        data["scaled_dose_min"]
        == 250.0
    )


# ============================================================
# TEST 2
#
# SOIL FAILURE
#       â†“
# RECOMMEND WITHOUT INVENTING SOIL
# ============================================================

def test_soil_unavailable_does_not_invent_values(
    monkeypatch,
):

    monkeypatch.setattr(
        advisory_router,
        "get_location_weather",
        safe_weather,
    )


    def unavailable_soil(
        latitude: float,
        longitude: float,
    ):

        raise SoilServiceError(
            "Test soil service unavailable."
        )


    monkeypatch.setattr(
        advisory_router,
        "get_root_zone_soil_context",
        unavailable_soil,
    )


    response = client.post(

        "/api/advisory",

        json={

            "farmer_id": None,

            "crop": "Rice",

            "pest":
                "Blast; Sheath blight",

            "field_area": 0.5,

            "area_unit": "hectare",

            "expected_harvest_days": 40,

            "state": "Tamil Nadu",

            "district": "Chennai",

            "latitude": 11.0,

            "longitude": 77.0,
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert (
        data["status"]
        == "recommend"
    )


    assert (
        data["soil_status"]
        == "unavailable"
    )


    assert (
        data["soil_summary"]
        is None
    )


    assert (
        data["soil_source"]
        is None
    )


    assert (
        "soil_context_unavailable"
        in data["fired_rules"]
    )


# ============================================================
# TEST 3
#
# WEATHER FAILS
#       â†“
# SOIL MUST NOT RUN
# ============================================================

def test_weather_delay_stops_before_soil(
    monkeypatch,
):

    monkeypatch.setattr(
        advisory_router,
        "get_location_weather",
        unsafe_weather,
    )


    def soil_should_not_run(
        latitude: float,
        longitude: float,
    ):

        raise AssertionError(
            "Soil service must not run "
            "when weather already blocks spraying."
        )


    monkeypatch.setattr(
        advisory_router,
        "get_root_zone_soil_context",
        soil_should_not_run,
    )


    response = client.post(

        "/api/advisory",

        json={

            "farmer_id": None,

            "crop": "Rice",

            "pest":
                "Blast; Sheath blight",

            "field_area": 0.5,

            "area_unit": "hectare",

            "expected_harvest_days": 40,

            "state": "Tamil Nadu",

            "district": "Chennai",

            "latitude": 11.0,

            "longitude": 77.0,
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert (
        data["status"]
        == "delay"
    )


    assert (
        data["weather_status"]
        == "delay"
    )


    assert (
        data["soil_status"]
        == "not_evaluated"
    )


    assert (
        data["soil_summary"]
        is None
    )


# ============================================================
# TEST 4
#
# ONLY ONE COORDINATE
#       â†“
# SOIL INCOMPLETE
# ============================================================

def test_incomplete_soil_coordinates(
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

            "pest":
                "Blast; Sheath blight",

            "field_area": 0.5,

            "area_unit": "hectare",

            "expected_harvest_days": 40,

            "state": "Tamil Nadu",

            "district": "Chennai",

            "latitude": 11.0
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert (
        data["status"]
        == "recommend"
    )


    assert (
        data["soil_status"]
        == "incomplete"
    )


    assert (
        "soil_coordinates_incomplete"
        in data["fired_rules"]
    )


# ============================================================
# TEST 5
#
# NO FIELD COORDINATES
#       â†“
# SOIL NOT PROVIDED
# ============================================================

def test_no_soil_coordinates(
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

            "pest":
                "Blast; Sheath blight",

            "field_area": 0.5,

            "area_unit": "hectare",

            "expected_harvest_days": 40,

            "state": "Tamil Nadu",

            "district": "Chennai"
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert (
        data["status"]
        == "recommend"
    )


    assert (
        data["soil_status"]
        == "not_provided"
    )


    assert (
        "soil_context_not_provided"
        in data["fired_rules"]
    )
