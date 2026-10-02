from sqlalchemy.orm import Session

from app.models_growth_stage import GrowthStageRule
from app.services.growth_stage_rules import (
    evaluate_growth_stage_rule,
)


def find_growth_stage_rule(
    db: Session,
    crop: str,
    pest: str,
    active_ingredient: str,
) -> GrowthStageRule | None:
    """
    Find one verified growth-stage rule matching the
    crop + pest + active ingredient already selected
    from the verified pesticide registry.
    """

    if not crop or not pest or not active_ingredient:
        return None

    return (
        db.query(GrowthStageRule)
        .filter(
            GrowthStageRule.crop.ilike(crop.strip()),
            GrowthStageRule.pest.ilike(pest.strip()),
            GrowthStageRule.active_ingredient.ilike(
                active_ingredient.strip()
            ),
            GrowthStageRule.verified.is_(True),
        )
        .first()
    )


def evaluate_farmer_growth_stage(
    db: Session,
    crop: str,
    pest: str,
    active_ingredient: str,
    growth_stage: str | None,
) -> dict:
    """
    Retrieve the verified DB rule and evaluate the
    farmer's current crop growth stage.
    """

    if growth_stage is None:

        return {
            "status": "not_evaluated",
            "growth_stage": None,
            "application_timing": None,
            "source_document": None,
            "source_page": None,
            "source_url": None,
            "fired_rules": [
                "growth_stage_not_provided"
            ],
            "explanation": (
                "Growth stage was not provided."
            ),
        }

    rule = find_growth_stage_rule(
        db=db,
        crop=crop,
        pest=pest,
        active_ingredient=active_ingredient,
    )

    if rule is None:

        return {
            "status": "not_evaluated",
            "growth_stage": growth_stage,
            "application_timing": None,
            "source_document": None,
            "source_page": None,
            "source_url": None,
            "fired_rules": [
                "growth_stage_rule_not_found"
            ],
            "explanation": (
                "No verified growth-stage rule is "
                "available for this crop, pest and "
                "active-ingredient combination."
            ),
        }

    allowed_stages = [
        stage.strip()
        for stage in rule.allowed_stages.split(";")
        if stage.strip()
    ]

    result = evaluate_growth_stage_rule(
        growth_stage=growth_stage,
        allowed_stages=allowed_stages,
        verified=rule.verified,
        application_timing=rule.application_timing,
    )

    return {
        "status": result.status,
        "growth_stage": result.growth_stage,
        "allowed_stages": allowed_stages,
        "application_timing": rule.application_timing,
        "source_document": rule.source_document,
        "source_page": rule.source_page,
        "source_url": rule.source_url,
        "fired_rules": result.fired_rules,
        "explanation": result.explanation,
    }