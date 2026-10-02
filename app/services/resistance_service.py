from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_resistance import ResistanceRule


def _split_active_ingredients(
    active_ingredient: str,
) -> list[str]:
    """
    Split combination products such as:

        Thiamethoxam + Fipronil

    into:

        ["Thiamethoxam", "Fipronil"]
    """

    if not active_ingredient:
        return []

    return [
        ingredient.strip()
        for ingredient
        in active_ingredient.split("+")
        if ingredient.strip()
    ]


def evaluate_resistance_management(
    db: Session,
    crop: str,
    pest: str,
    active_ingredient: str,
    previous_application_count: int | None,
) -> dict:
    """
    Evaluate resistance-management information
    using verified IRAC / FRAC mode-of-action rules.

    Important:
    This service does NOT automatically ABSTAIN
    simply because the same active ingredient was
    previously used.

    Without a verified product-specific numeric
    prohibition, repeated use produces an
    evidence-grounded rotation recommendation.
    """

    # ---------------------------------------------------------
    # 1. Validate active ingredient
    # ---------------------------------------------------------

    ingredients = _split_active_ingredients(
        active_ingredient
    )

    if not ingredients:

        return {
            "status": "not_evaluated",
            "fired_rules": [
                "resistance_active_ingredient_missing",
            ],
            "explanation": (
                "Resistance management was not evaluated "
                "because no active ingredient was available."
            ),
            "mode_of_action_groups": [],
        }


    # ---------------------------------------------------------
    # 2. Find verified resistance rules
    # ---------------------------------------------------------

    matched_rules = []

    for ingredient in ingredients:

        rules = (
            db.execute(
                select(
                    ResistanceRule
                ).where(
                    ResistanceRule.crop
                    == crop,

                    ResistanceRule.pest
                    == pest,

                    ResistanceRule.active_ingredient
                    == ingredient,

                    ResistanceRule.verified
                    .is_(True),
                )
            )
            .scalars()
            .all()
        )

        matched_rules.extend(
            rules
        )


    # ---------------------------------------------------------
    # 3. No verified MoA information
    # ---------------------------------------------------------

    if not matched_rules:

        return {
            "status": "not_evaluated",
            "fired_rules": [
                "resistance_rule_not_found",
            ],
            "explanation": (
                "No verified IRAC or FRAC "
                "mode-of-action rule was found for "
                "the matched treatment."
            ),
            "mode_of_action_groups": [],
        }


    # ---------------------------------------------------------
    # 4. Prepare MoA information
    # ---------------------------------------------------------

    moa_groups = []

    for rule in matched_rules:

        moa_groups.append(
            {
                "active_ingredient":
                    rule.active_ingredient,

                "framework":
                    rule.framework,

                "moa_group":
                    rule.moa_group,

                "moa_name":
                    rule.moa_name,

                "resistance_risk":
                    rule.resistance_risk,

                "rotation_recommended":
                    rule.rotation_recommended,
            }
        )


    group_descriptions = [
        (
            f"{rule.active_ingredient}: "
            f"{rule.framework} Group "
            f"{rule.moa_group} "
            f"({rule.moa_name})"
        )
        for rule in matched_rules
    ]


    group_text = "; ".join(
        group_descriptions
    )


    # ---------------------------------------------------------
    # 5. Treatment history not supplied
    # ---------------------------------------------------------

    if previous_application_count is None:

        return {
            "status": "not_evaluated",
            "fired_rules": [
                "resistance_history_not_provided",
            ],
            "explanation": (
                "Verified resistance-management "
                f"information was found: {group_text}. "
                "Previous application count was not "
                "provided, so repeat-use rotation could "
                "not be evaluated."
            ),
            "mode_of_action_groups":
                moa_groups,
        }


    # ---------------------------------------------------------
    # 6. Invalid application count
    # ---------------------------------------------------------

    if previous_application_count < 0:

        return {
            "status": "not_evaluated",
            "fired_rules": [
                "resistance_history_invalid",
            ],
            "explanation": (
                "Resistance management could not be "
                "evaluated because the previous "
                "application count is invalid."
            ),
            "mode_of_action_groups":
                moa_groups,
        }


    # ---------------------------------------------------------
    # 7. No previous use
    # ---------------------------------------------------------

    if previous_application_count == 0:

        return {
            "status": "pass",
            "fired_rules": [
                "resistance_check_passed",
            ],
            "explanation": (
                "Verified mode-of-action information "
                f"was found: {group_text}. "
                "The farmer reported no previous "
                "applications of this matched treatment "
                "in the current crop cycle, so no "
                "repeat-use rotation warning is triggered."
            ),
            "mode_of_action_groups":
                moa_groups,
        }


    # ---------------------------------------------------------
    # 8. Previous use exists
    # ---------------------------------------------------------

    rotation_rules = [
        rule
        for rule in matched_rules
        if rule.rotation_recommended
    ]


    if rotation_rules:

        return {
            "status": "warning",
            "fired_rules": [
                "resistance_rotation_recommended",
            ],
            "explanation": (
                "Verified mode-of-action information "
                f"was found: {group_text}. "
                f"The farmer reported "
                f"{previous_application_count} previous "
                "application(s) of the matched treatment. "
                "To support resistance management, avoid "
                "unnecessary repeated use of the same "
                "mode-of-action group and consider rotation "
                "with an appropriate verified alternative "
                "when permitted by the product label and "
                "crop-pest recommendation."
            ),
            "mode_of_action_groups":
                moa_groups,
        }


    # ---------------------------------------------------------
    # 9. Rule exists but rotation is not marked
    # ---------------------------------------------------------

    return {
        "status": "pass",
        "fired_rules": [
            "resistance_check_passed",
        ],
        "explanation": (
            "Verified mode-of-action information "
            f"was found: {group_text}. "
            "No additional resistance-rotation warning "
            "is triggered by the available rule."
        ),
        "mode_of_action_groups":
            moa_groups,
    }