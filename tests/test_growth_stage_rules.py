from app.services.growth_stage_rules import (
    evaluate_growth_stage_rule,
    normalize_growth_stage,
)


def test_normalize_flowering():

    assert (
        normalize_growth_stage(
            "Flowering Stage"
        )
        == "reproductive"
    )


def test_missing_growth_stage():

    result = evaluate_growth_stage_rule(
        growth_stage=None,
        allowed_stages=["vegetative"],
        verified=True,
    )

    assert result.status == "not_evaluated"

    assert (
        "growth_stage_not_provided"
        in result.fired_rules
    )


def test_invalid_growth_stage():

    result = evaluate_growth_stage_rule(
        growth_stage="unknown_stage",
        allowed_stages=["vegetative"],
        verified=True,
    )

    assert result.status == "abstain"

    assert (
        "growth_stage_invalid"
        in result.fired_rules
    )


def test_unverified_rule_not_used():

    result = evaluate_growth_stage_rule(
        growth_stage="flowering",
        allowed_stages=["reproductive"],
        verified=False,
    )

    assert result.status == "not_evaluated"

    assert (
        "growth_stage_rule_unverified"
        in result.fired_rules
    )


def test_allowed_growth_stage():

    result = evaluate_growth_stage_rule(
        growth_stage="vegetative",
        allowed_stages=[
            "vegetative",
            "reproductive",
        ],
        verified=True,
    )

    assert result.status == "pass"

    assert (
        "growth_stage_passed"
        in result.fired_rules
    )


def test_outside_application_window():

    result = evaluate_growth_stage_rule(
        growth_stage="preharvest",
        allowed_stages=[
            "vegetative",
            "reproductive",
        ],
        verified=True,
        application_timing=(
            "early vegetative to reproductive stage"
        ),
    )

    assert result.status == "abstain"

    assert (
        "growth_stage_outside_application_window"
        in result.fired_rules
    )


def test_flowering_maps_to_reproductive():

    result = evaluate_growth_stage_rule(
        growth_stage="flowering",
        allowed_stages=[
            "reproductive"
        ],
        verified=True,
    )

    assert result.status == "pass"

    assert result.growth_stage == "reproductive"