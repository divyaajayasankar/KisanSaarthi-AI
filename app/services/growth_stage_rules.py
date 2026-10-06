from dataclasses import dataclass


VALID_GROWTH_STAGES = {
    "sowing",
    "seedling",
    "vegetative",
    "reproductive",
    "pre_harvest",
}


@dataclass
class GrowthStageRuleResult:
    status: str
    explanation: str
    fired_rules: list[str]
    growth_stage: str | None


def normalize_growth_stage(
    growth_stage: str | None,
) -> str | None:

    if growth_stage is None:
        return None

    cleaned = (
        growth_stage
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "sowing_stage": "sowing",
        "seedling_stage": "seedling",
        "vegetative_stage": "vegetative",

        # Flowering and fruiting are reproductive stages
        "flowering": "reproductive",
        "flowering_stage": "reproductive",
        "fruiting": "reproductive",
        "fruiting_stage": "reproductive",
        "reproductive_stage": "reproductive",

        "preharvest": "pre_harvest",
        "pre_harvest_stage": "pre_harvest",
    }

    return aliases.get(
        cleaned,
        cleaned,
    )


def evaluate_growth_stage_rule(
    growth_stage: str | None,
    allowed_stages: list[str] | None,
    verified: bool,
    application_timing: str | None = None,
) -> GrowthStageRuleResult:

    stage = normalize_growth_stage(
        growth_stage
    )

    # No farmer growth stage
    if stage is None:

        return GrowthStageRuleResult(
            status="not_evaluated",
            explanation=(
                "Growth stage was not provided, so the "
                "application-stage rule was not evaluated."
            ),
            fired_rules=[
                "growth_stage_not_provided"
            ],
            growth_stage=None,
        )

    # Invalid stage
    if stage not in VALID_GROWTH_STAGES:

        return GrowthStageRuleResult(
            status="abstain",
            explanation=(
                f"'{growth_stage}' is not a supported "
                "growth-stage value."
            ),
            fired_rules=[
                "growth_stage_invalid"
            ],
            growth_stage=stage,
        )

    # Never use unverified rules
    if not verified:

        return GrowthStageRuleResult(
            status="not_evaluated",
            explanation=(
                "The application-stage rule is not verified "
                "and was therefore not used."
            ),
            fired_rules=[
                "growth_stage_rule_unverified"
            ],
            growth_stage=stage,
        )

    normalized_allowed = {
        normalize_growth_stage(item)
        for item in (
            allowed_stages or []
        )
    }

    normalized_allowed.discard(
        None
    )

    # No usable stage evidence
    if not normalized_allowed:

        return GrowthStageRuleResult(
            status="not_evaluated",
            explanation=(
                "No verified normalized application stage "
                "is available for this treatment."
            ),
            fired_rules=[
                "growth_stage_rule_missing"
            ],
            growth_stage=stage,
        )

    # Farmer stage is not within verified application stages
    if stage not in normalized_allowed:

        timing = (
            application_timing
            or "the verified application stage"
        )

        return GrowthStageRuleResult(
            status="abstain",
            explanation=(
                f"The current crop stage '{stage}' is outside "
                f"{timing}."
            ),
            fired_rules=[
                "growth_stage_outside_application_window"
            ],
            growth_stage=stage,
        )

    # Stage passes
    return GrowthStageRuleResult(
        status="pass",
        explanation=(
            "The current crop stage is within the verified "
            "application-stage window."
        ),
        fired_rules=[
            "growth_stage_passed"
        ],
        growth_stage=stage,
    )
