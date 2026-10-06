from dataclasses import dataclass


# ============================================================
# RESULT
# ============================================================

@dataclass
class CropSoilRuleResult:
    status: str

    explanation: str

    fired_rules: list[str]

    crop: str

    observed_ph: float

    verified_min_ph: float | None

    verified_max_ph: float | None


# ============================================================
# EVALUATE VERIFIED CROP-SOIL RULE
# ============================================================

def evaluate_crop_soil_rule(
    crop: str,
    observed_ph: float,
    min_ph: float,
    max_ph: float,
    verified: bool,
) -> CropSoilRuleResult:
    """
    Evaluate measured/root-zone soil pH against a supplied,
    verified crop suitability range.

    Important:
    This function does NOT invent crop pH ranges.
    The range must come from verified external evidence.
    """

    # ========================================================
    # VERIFY RULE SOURCE
    # ========================================================

    if not verified:

        return CropSoilRuleResult(
            status="abstain",

            explanation=(
                f"A crop-soil rule exists for {crop}, "
                "but it has not been verified. "
                "No soil suitability decision was made."
            ),

            fired_rules=[
                "soil_rule_unverified"
            ],

            crop=crop,

            observed_ph=observed_ph,

            verified_min_ph=None,

            verified_max_ph=None,
        )


    # ========================================================
    # VALIDATE OBSERVED PH
    # ========================================================

    if observed_ph <= 0 or observed_ph > 14:

        return CropSoilRuleResult(
            status="abstain",

            explanation=(
                "The supplied soil pH value is invalid, "
                "so soil suitability cannot be evaluated."
            ),

            fired_rules=[
                "soil_ph_invalid"
            ],

            crop=crop,

            observed_ph=observed_ph,

            verified_min_ph=min_ph,

            verified_max_ph=max_ph,
        )


    # ========================================================
    # VALIDATE VERIFIED RANGE
    # ========================================================

    if (
        min_ph <= 0
        or max_ph > 14
        or max_ph < min_ph
    ):

        return CropSoilRuleResult(
            status="abstain",

            explanation=(
                f"The verified crop-soil rule for {crop} "
                "contains an invalid pH range."
            ),

            fired_rules=[
                "soil_rule_invalid"
            ],

            crop=crop,

            observed_ph=observed_ph,

            verified_min_ph=min_ph,

            verified_max_ph=max_ph,
        )


    # ========================================================
    # BELOW VERIFIED RANGE
    # ========================================================

    if observed_ph < min_ph:

        return CropSoilRuleResult(
            status="warning",

            explanation=(
                f"Root-zone soil pH {observed_ph:.2f} is below "
                f"the verified suitability range of "
                f"{min_ph:.2f}-{max_ph:.2f} for {crop}."
            ),

            fired_rules=[
                "soil_ph_below_verified_range"
            ],

            crop=crop,

            observed_ph=observed_ph,

            verified_min_ph=min_ph,

            verified_max_ph=max_ph,
        )


    # ========================================================
    # ABOVE VERIFIED RANGE
    # ========================================================

    if observed_ph > max_ph:

        return CropSoilRuleResult(
            status="warning",

            explanation=(
                f"Root-zone soil pH {observed_ph:.2f} is above "
                f"the verified suitability range of "
                f"{min_ph:.2f}-{max_ph:.2f} for {crop}."
            ),

            fired_rules=[
                "soil_ph_above_verified_range"
            ],

            crop=crop,

            observed_ph=observed_ph,

            verified_min_ph=min_ph,

            verified_max_ph=max_ph,
        )


    # ========================================================
    # WITHIN VERIFIED RANGE
    # ========================================================

    return CropSoilRuleResult(
        status="suitable",

        explanation=(
            f"Root-zone soil pH {observed_ph:.2f} falls within "
            f"the verified suitability range of "
            f"{min_ph:.2f}-{max_ph:.2f} for {crop}."
        ),

        fired_rules=[
            "soil_suitability_passed"
        ],

        crop=crop,

        observed_ph=observed_ph,

        verified_min_ph=min_ph,

        verified_max_ph=max_ph,
    )
