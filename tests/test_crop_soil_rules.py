from app.services.crop_soil_rules import (
    evaluate_crop_soil_rule,
)


# ============================================================
# 1. PH INSIDE VERIFIED RANGE
# ============================================================

def test_soil_ph_inside_range():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=6.5,
        min_ph=5.5,
        max_ph=7.0,
        verified=True,
    )

    assert result.status == "suitable"

    assert (
        "soil_suitability_passed"
        in result.fired_rules
    )


# ============================================================
# 2. PH BELOW VERIFIED RANGE
# ============================================================

def test_soil_ph_below_range():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=4.5,
        min_ph=5.5,
        max_ph=7.0,
        verified=True,
    )

    assert result.status == "warning"

    assert (
        "soil_ph_below_verified_range"
        in result.fired_rules
    )


# ============================================================
# 3. PH ABOVE VERIFIED RANGE
# ============================================================

def test_soil_ph_above_range():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=8.0,
        min_ph=5.5,
        max_ph=7.0,
        verified=True,
    )

    assert result.status == "warning"

    assert (
        "soil_ph_above_verified_range"
        in result.fired_rules
    )


# ============================================================
# 4. UNVERIFIED RULE
# ============================================================

def test_unverified_rule_abstains():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=6.5,
        min_ph=5.5,
        max_ph=7.0,
        verified=False,
    )

    assert result.status == "abstain"

    assert (
        "soil_rule_unverified"
        in result.fired_rules
    )


# ============================================================
# 5. INVALID OBSERVED PH
# ============================================================

def test_invalid_observed_ph_abstains():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=0,
        min_ph=5.5,
        max_ph=7.0,
        verified=True,
    )

    assert result.status == "abstain"

    assert (
        "soil_ph_invalid"
        in result.fired_rules
    )


# ============================================================
# 6. INVALID VERIFIED RANGE
# ============================================================

def test_invalid_verified_range_abstains():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=6.5,
        min_ph=8.0,
        max_ph=6.0,
        verified=True,
    )

    assert result.status == "abstain"

    assert (
        "soil_rule_invalid"
        in result.fired_rules
    )


# ============================================================
# 7. LOWER BOUNDARY IS ACCEPTED
# ============================================================

def test_exact_minimum_ph_passes():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=5.5,
        min_ph=5.5,
        max_ph=7.0,
        verified=True,
    )

    assert result.status == "suitable"


# ============================================================
# 8. UPPER BOUNDARY IS ACCEPTED
# ============================================================

def test_exact_maximum_ph_passes():

    result = evaluate_crop_soil_rule(
        crop="TestCrop",
        observed_ph=7.0,
        min_ph=5.5,
        max_ph=7.0,
        verified=True,
    )

    assert result.status == "suitable"
