from sqlalchemy.orm import Session

from app.models_treatment_history import (
    TreatmentHistoryRule,
)


# ============================================================
# TREATMENT-HISTORY EVALUATION
# ============================================================

def evaluate_treatment_history(
    db: Session,
    crop: str,
    pest: str,
    active_ingredient: str,
    previous_application_count: int | None,
    days_since_last_application: int | None = None,
) -> dict:
    """
    Evaluate whether another application is allowed based on
    verified treatment-history rules.

    Returns one of:

        pass
        abstain
        not_evaluated
    """

    # ========================================================
    # STEP 1 â€” HISTORY NOT PROVIDED
    # ========================================================

    if previous_application_count is None:

        return {
            "status": "not_evaluated",

            "fired_rules": [
                "treatment_history_not_provided"
            ],

            "explanation": (
                "Previous treatment history was not provided, "
                "so no treatment-frequency rule was applied."
            ),

            "previous_application_count": None,

            "max_applications": None,

            "min_interval_days": None,

            "days_since_last_application": (
                days_since_last_application
            ),

            "source_document": None,

            "source_page": None,

            "source_url": None,
        }


    # ========================================================
    # STEP 2 â€” INVALID HISTORY VALUE
    # ========================================================

    if previous_application_count < 0:

        return {
            "status": "abstain",

            "fired_rules": [
                "treatment_history_invalid_count"
            ],

            "explanation": (
                "Previous application count cannot be negative. "
                "The system will not issue an advisory using "
                "invalid treatment-history information."
            ),

            "previous_application_count": (
                previous_application_count
            ),

            "max_applications": None,

            "min_interval_days": None,

            "days_since_last_application": (
                days_since_last_application
            ),

            "source_document": None,

            "source_page": None,

            "source_url": None,
        }


    # ========================================================
    # STEP 3 â€” FIND VERIFIED RULE
    # ========================================================

    rules = (
        db.query(
            TreatmentHistoryRule
        )
        .filter(
            TreatmentHistoryRule.crop.ilike(
                crop
            ),

            TreatmentHistoryRule.pest.ilike(
                pest
            ),

            TreatmentHistoryRule.active_ingredient.ilike(
                active_ingredient
            ),

            TreatmentHistoryRule.verified.is_(
                True
            ),
        )
        .all()
    )


    # ========================================================
    # STEP 4 â€” NO VERIFIED RULE
    # ========================================================

    if len(rules) == 0:

        return {
            "status": "not_evaluated",

            "fired_rules": [
                "treatment_history_rule_not_found"
            ],

            "explanation": (
                "No verified treatment-history rule was found "
                "for this crop, pest and active ingredient. "
                "The system did not invent a frequency limit."
            ),

            "previous_application_count": (
                previous_application_count
            ),

            "max_applications": None,

            "min_interval_days": None,

            "days_since_last_application": (
                days_since_last_application
            ),

            "source_document": None,

            "source_page": None,

            "source_url": None,
        }


    # ========================================================
    # STEP 5 â€” MULTIPLE VERIFIED RULES
    # ========================================================

    if len(rules) > 1:

        return {
            "status": "not_evaluated",

            "fired_rules": [
                "multiple_treatment_history_rules"
            ],

            "explanation": (
                "Multiple verified treatment-history rules were "
                "found. The system did not automatically select "
                "one."
            ),

            "previous_application_count": (
                previous_application_count
            ),

            "max_applications": None,

            "min_interval_days": None,

            "days_since_last_application": (
                days_since_last_application
            ),

            "source_document": None,

            "source_page": None,

            "source_url": None,
        }


    # ========================================================
    # EXACTLY ONE VERIFIED RULE
    # ========================================================

    rule = rules[0]

    max_applications = (
        rule.max_applications
    )

    min_interval_days = (
        rule.min_interval_days
    )


    # ========================================================
    # STEP 6 â€” MAXIMUM APPLICATION COUNT
    # ========================================================

    if max_applications is not None:

        if (
            previous_application_count
            >= max_applications
        ):

            return {
                "status": "abstain",

                "fired_rules": [
                    "maximum_application_frequency_reached"
                ],

                "explanation": (
                    f"The verified treatment-history rule allows "
                    f"a maximum of {max_applications} application(s) "
                    f"within the defined {rule.history_scope}. "
                    f"The farmer reported "
                    f"{previous_application_count} previous "
                    f"application(s), so another application is "
                    f"not issued."
                ),

                "previous_application_count": (
                    previous_application_count
                ),

                "max_applications": (
                    max_applications
                ),

                "min_interval_days": (
                    min_interval_days
                ),

                "days_since_last_application": (
                    days_since_last_application
                ),

                "source_document": (
                    rule.source_document
                ),

                "source_page": (
                    rule.source_page
                ),

                "source_url": (
                    rule.source_url
                ),
            }


    # ========================================================
    # STEP 7 â€” MINIMUM REPEAT INTERVAL
    # ========================================================
    #
    # IMPORTANT:
    #
    # A repeat interval applies only when there has already
    # been at least one previous application.
    #
    # Example:
    #
    # previous_application_count = 0
    #
    # There is no previous treatment date, therefore
    # days_since_last_application is NOT required.
    #
    # ========================================================

    if (
        min_interval_days is not None
        and
        previous_application_count > 0
    ):

        # ----------------------------------------------------
        # INTERVAL REQUIRED BUT HISTORY DATE NOT PROVIDED
        # ----------------------------------------------------

        if days_since_last_application is None:

            return {
                "status": "abstain",

                "fired_rules": [
                    "treatment_interval_context_missing"
                ],

                "explanation": (
                    "The verified treatment-history rule contains "
                    "a minimum repeat interval, but the number of "
                    "days since the previous application was not "
                    "provided."
                ),

                "previous_application_count": (
                    previous_application_count
                ),

                "max_applications": (
                    max_applications
                ),

                "min_interval_days": (
                    min_interval_days
                ),

                "days_since_last_application": None,

                "source_document": (
                    rule.source_document
                ),

                "source_page": (
                    rule.source_page
                ),

                "source_url": (
                    rule.source_url
                ),
            }


        # ----------------------------------------------------
        # INVALID INTERVAL VALUE
        # ----------------------------------------------------

        if days_since_last_application < 0:

            return {
                "status": "abstain",

                "fired_rules": [
                    "treatment_interval_invalid"
                ],

                "explanation": (
                    "Days since the previous application cannot "
                    "be negative."
                ),

                "previous_application_count": (
                    previous_application_count
                ),

                "max_applications": (
                    max_applications
                ),

                "min_interval_days": (
                    min_interval_days
                ),

                "days_since_last_application": (
                    days_since_last_application
                ),

                "source_document": (
                    rule.source_document
                ),

                "source_page": (
                    rule.source_page
                ),

                "source_url": (
                    rule.source_url
                ),
            }


        # ----------------------------------------------------
        # INTERVAL TOO SHORT
        # ----------------------------------------------------

        if (
            days_since_last_application
            < min_interval_days
        ):

            return {
                "status": "abstain",

                "fired_rules": [
                    "minimum_treatment_interval_not_met"
                ],

                "explanation": (
                    f"The verified minimum repeat interval is "
                    f"{min_interval_days} day(s), but only "
                    f"{days_since_last_application} day(s) have "
                    f"passed since the previous application."
                ),

                "previous_application_count": (
                    previous_application_count
                ),

                "max_applications": (
                    max_applications
                ),

                "min_interval_days": (
                    min_interval_days
                ),

                "days_since_last_application": (
                    days_since_last_application
                ),

                "source_document": (
                    rule.source_document
                ),

                "source_page": (
                    rule.source_page
                ),

                "source_url": (
                    rule.source_url
                ),
            }


    # ========================================================
    # STEP 8 â€” HISTORY CHECK PASSED
    # ========================================================

    fired_rules = [
        "treatment_history_passed"
    ]

    explanation_parts = []


    # --------------------------------------------------------
    # APPLICATION COUNT EXPLANATION
    # --------------------------------------------------------

    if max_applications is not None:

        remaining = (
            max_applications
            - previous_application_count
        )

        explanation_parts.append(
            f"The farmer reported "
            f"{previous_application_count} previous "
            f"application(s). The verified maximum is "
            f"{max_applications}, so the treatment-history "
            f"frequency check passed."
        )

        explanation_parts.append(
            f"{remaining} application slot(s) remain under "
            f"this verified maximum."
        )


    # --------------------------------------------------------
    # FIRST APPLICATION
    # --------------------------------------------------------

    if previous_application_count == 0:

        fired_rules.append(
            "no_previous_application"
        )

        explanation_parts.append(
            "The farmer reported no previous application "
            "of this treatment."
        )


        if min_interval_days is not None:

            explanation_parts.append(
                "Because this is the first application, "
                "the verified minimum repeat interval does "
                "not need to be evaluated."
            )


    # --------------------------------------------------------
    # NO VERIFIED REPEAT INTERVAL
    # --------------------------------------------------------

    if min_interval_days is None:

        fired_rules.append(
            "repeat_interval_not_specified"
        )

        explanation_parts.append(
            "No fixed repeat interval in days is present in "
            "the verified rule, so the system did not invent "
            "one."
        )


    # --------------------------------------------------------
    # VERIFIED INTERVAL SATISFIED
    # --------------------------------------------------------

    elif previous_application_count > 0:

        fired_rules.append(
            "minimum_treatment_interval_met"
        )

        explanation_parts.append(
            f"The verified minimum repeat interval of "
            f"{min_interval_days} day(s) was satisfied."
        )


    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {
        "status": "pass",

        "fired_rules": (
            fired_rules
        ),

        "explanation": (
            " ".join(
                explanation_parts
            )
        ),

        "previous_application_count": (
            previous_application_count
        ),

        "max_applications": (
            max_applications
        ),

        "min_interval_days": (
            min_interval_days
        ),

        "days_since_last_application": (
            days_since_last_application
        ),

        "source_document": (
            rule.source_document
        ),

        "source_page": (
            rule.source_page
        ),

        "source_url": (
            rule.source_url
        ),
    }
