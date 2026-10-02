from types import SimpleNamespace

from app.services.constraint_engine import evaluate_advisory


def make_entry(
    phi=10,
    verified=True,
    dose_min=100.0,
    dose_max=100.0,
):
    return SimpleNamespace(
        verified=verified,
        dose_min_per_hectare=dose_min,
        dose_max_per_hectare=dose_max,
        dose_unit="ml",
        phi_days=phi,
        active_ingredient="TEST_AI",
    )


def test_exact_dose_scaling():
    result = evaluate_advisory(
        registry_entry=make_entry(),
        field_area=0.5,
        area_unit="hectare",
        expected_harvest_days=20,
    )

    assert result.status == "recommend"
    assert result.scaled_dose_min == 50.0
    assert result.scaled_dose_max == 50.0
    assert "area_dose_scaling" in result.fired_rules


def test_dose_range_scaling():
    result = evaluate_advisory(
        registry_entry=make_entry(
            dose_min=500,
            dose_max=750,
        ),
        field_area=0.5,
        area_unit="hectare",
        expected_harvest_days=20,
    )

    assert result.status == "recommend"
    assert result.scaled_dose_min == 250.0
    assert result.scaled_dose_max == 375.0


def test_phi_rejects_when_harvest_too_close():
    result = evaluate_advisory(
        registry_entry=make_entry(phi=10),
        field_area=1,
        area_unit="hectare",
        expected_harvest_days=6,
    )

    assert result.status == "abstain"
    assert "phi_rejected" in result.fired_rules


def test_unverified_registry_abstains():
    result = evaluate_advisory(
        registry_entry=make_entry(
            verified=False
        ),
        field_area=1,
        area_unit="hectare",
        expected_harvest_days=20,
    )

    assert result.status == "abstain"
    assert "registry_unverified" in result.fired_rules


def test_invalid_dose_range_abstains():
    result = evaluate_advisory(
        registry_entry=make_entry(
            dose_min=750,
            dose_max=500,
        ),
        field_area=1,
        area_unit="hectare",
        expected_harvest_days=20,
    )

    assert result.status == "abstain"
    assert "invalid_registered_dose" in result.fired_rules