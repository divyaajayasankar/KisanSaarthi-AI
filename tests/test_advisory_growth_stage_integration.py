from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============================================================
# SAFE MOCK WEATHER
# ============================================================

def safe_weather(*args, **kwargs):

    return {
        "weather": {
            "max_wind_speed_m_s": 2.0,
            "rain_total_mm": 0.0,
            "max_precipitation_probability": 10.0,
        },
        "source": "test-weather",
    }


# ============================================================
# COMMON RICE REQUEST
# ============================================================

def rice_payload(
    growth_stage=None,
):

    return {
        "farmer_id": None,

        "crop": "Rice",

        "pest": "Blast; Sheath blight",

        "field_area": 0.5,

        "area_unit": "hectare",

        "expected_harvest_days": 40,

        "growth_stage": growth_stage,

        "state": "Tamil Nadu",

        "district": "Coimbatore",

        # No coordinates:
        # avoids external SoilGrids calls during these tests.
        "latitude": None,

        "longitude": None,
    }


# ============================================================
# TEST 1
# VEGETATIVE STAGE SHOULD PASS
# ============================================================

def test_rice_vegetative_growth_stage_passes(
    monkeypatch,
):

    monkeypatch.setattr(
        "app.routers.advisory.get_location_weather",
        safe_weather,
    )

    response = client.post(
        "/api/advisory",
        json=rice_payload(
            growth_stage="vegetative",
        ),
    )

    assert response.status_code == 200

    data = response.json()

    # Growth stage itself must pass.
    assert (
        "growth_stage_passed"
        in data["fired_rules"]
    )

    # It must NOT stop because of growth stage.
    assert (
        "growth_stage_outside_application_window"
        not in data["fired_rules"]
    )

    # With mocked safe weather the advisory should continue.
    assert data["status"] == "recommend"

    assert data["weather_status"] == "proceed"


# ============================================================
# TEST 2
# REPRODUCTIVE STAGE SHOULD PASS
# ============================================================

def test_rice_reproductive_growth_stage_passes(
    monkeypatch,
):

    monkeypatch.setattr(
        "app.routers.advisory.get_location_weather",
        safe_weather,
    )

    response = client.post(
        "/api/advisory",
        json=rice_payload(
            growth_stage="reproductive",
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "growth_stage_passed"
        in data["fired_rules"]
    )

    assert (
        "growth_stage_outside_application_window"
        not in data["fired_rules"]
    )

    assert data["status"] == "recommend"

    assert data["weather_status"] == "proceed"


# ============================================================
# TEST 3
# PRE-HARVEST STAGE MUST ABSTAIN
# ============================================================

def test_rice_pre_harvest_growth_stage_abstains(
    monkeypatch,
):

    # --------------------------------------------------------
    # If weather gets called here, the test should fail.
    #
    # Growth-stage failure must stop BEFORE weather.
    # --------------------------------------------------------

    def weather_must_not_run(
        *args,
        **kwargs,
    ):

        raise AssertionError(
            "Weather must not run after "
            "growth-stage abstention."
        )

    monkeypatch.setattr(
        "app.routers.advisory.get_location_weather",
        weather_must_not_run,
    )

    response = client.post(
        "/api/advisory",
        json=rice_payload(
            growth_stage="pre_harvest",
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "abstain"

    assert (
        "growth_stage_outside_application_window"
        in data["fired_rules"]
    )

    # Safety requirement:
    # do not expose actionable pesticide information.
    assert data["active_ingredient"] is None

    assert data["scaled_dose_min"] is None

    assert data["scaled_dose_max"] is None

    assert data["dose_unit"] is None

    # Growth-stage failure must happen before weather/soil.
    assert data["weather_status"] is None

    assert data["soil_status"] == "not_evaluated"

    assert (
        data["soil_suitability_status"]
        == "not_evaluated"
    )


# ============================================================
# TEST 4
# MISSING GROWTH STAGE PRESERVES OLD BEHAVIOUR
# ============================================================

def test_missing_growth_stage_keeps_backward_compatibility(
    monkeypatch,
):

    monkeypatch.setattr(
        "app.routers.advisory.get_location_weather",
        safe_weather,
    )

    response = client.post(
        "/api/advisory",
        json=rice_payload(
            growth_stage=None,
        ),
    )

    assert response.status_code == 200

    data = response.json()

    # --------------------------------------------------------
    # Missing stage must NOT invent a stage restriction.
    # --------------------------------------------------------

    assert (
        "growth_stage_outside_application_window"
        not in data["fired_rules"]
    )

    # --------------------------------------------------------
    # We intentionally preserve previous behaviour when
    # growth_stage is absent.
    # --------------------------------------------------------

    assert data["status"] == "recommend"

    assert data["weather_status"] == "proceed"


# ============================================================
# TEST 5
# FLOWERING ALIAS SHOULD NORMALIZE TO REPRODUCTIVE
# ============================================================

def test_rice_flowering_alias_passes(
    monkeypatch,
):

    monkeypatch.setattr(
        "app.routers.advisory.get_location_weather",
        safe_weather,
    )

    response = client.post(
        "/api/advisory",
        json=rice_payload(
            growth_stage="flowering",
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "growth_stage_passed"
        in data["fired_rules"]
    )

    assert data["status"] == "recommend"
