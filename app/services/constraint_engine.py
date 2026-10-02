from dataclasses import dataclass


# ============================================================
# AREA CONVERSION
# ============================================================

AREA_TO_HECTARE = {
    "hectare": 1.0,
    "ha": 1.0,

    "acre": 0.40468564224,

    "cent": 0.0040468564224,

    "guntha": 0.010117141056,

    "sqm": 0.0001,
    "square_metre": 0.0001,
    "square metre": 0.0001,
}


# ============================================================
# CONSTRAINT RESULT
# ============================================================

@dataclass
class ConstraintResult:

    status: str

    active_ingredient: str | None

    scaled_dose_min: float | None

    scaled_dose_max: float | None

    dose_unit: str | None

    explanation: str

    fired_rules: list[str]


# ============================================================
# ADVISORY CONSTRAINT ENGINE
# ============================================================

def evaluate_advisory(
    *,
    registry_entry,
    field_area: float,
    area_unit: str,
    expected_harvest_days: int,
) -> ConstraintResult:

    fired_rules = [
        "registration_exists"
    ]

    # --------------------------------------------------------
    # 1. AREA UNIT VALIDATION
    # --------------------------------------------------------

    unit = area_unit.strip().lower()

    if unit not in AREA_TO_HECTARE:

        return ConstraintResult(
            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                f"Unsupported area unit '{area_unit}'. "
                "Please provide hectare, acre, cent, "
                "guntha, or square metre."
            ),

            fired_rules=(
                fired_rules
                + ["area_unit_unsupported"]
            ),
        )

    # --------------------------------------------------------
    # 2. REGISTRY VERIFICATION
    # --------------------------------------------------------

    if not registry_entry.verified:

        return ConstraintResult(
            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "The matching pesticide registry evidence "
                "has not been verified. "
                "KisanSaarthi will not issue a recommendation."
            ),

            fired_rules=(
                fired_rules
                + ["registry_unverified"]
            ),
        )

    # --------------------------------------------------------
    # 3. VALIDATE REGISTERED DOSE RANGE
    # --------------------------------------------------------

    dose_min = (
        registry_entry.dose_min_per_hectare
    )

    dose_max = (
        registry_entry.dose_max_per_hectare
    )

    if (
        dose_min is None
        or dose_max is None
        or dose_min <= 0
        or dose_max <= 0
        or dose_max < dose_min
    ):

        return ConstraintResult(
            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "The registered dose range is missing "
                "or invalid, so the system will not guess."
            ),

            fired_rules=(
                fired_rules
                + ["invalid_registered_dose"]
            ),
        )

    fired_rules.append(
        "registered_dose_valid"
    )

    # --------------------------------------------------------
    # 4. CONVERT FARMER AREA TO HECTARES
    # --------------------------------------------------------

    hectares = (
        field_area
        * AREA_TO_HECTARE[unit]
    )

    fired_rules.append(
        "area_converted_to_hectare"
    )

    # --------------------------------------------------------
    # 5. SCALE MINIMUM AND MAXIMUM DOSE
    # --------------------------------------------------------

    scaled_min = (
        dose_min
        * hectares
    )

    scaled_max = (
        dose_max
        * hectares
    )

    scaled_min = round(
        scaled_min,
        2,
    )

    scaled_max = round(
        scaled_max,
        2,
    )

    fired_rules.append(
        "area_dose_scaling"
    )

        # --------------------------------------------------------
    # 6. PHI VALIDATION
    # --------------------------------------------------------

    phi_days = (
        registry_entry.phi_days
    )

    phi_not_applicable = bool(
        getattr(
            registry_entry,
            "phi_not_applicable",
            False,
        )
    )


    # --------------------------------------------------------
    # 6A. EXPLICIT PHI NOT APPLICABLE
    # --------------------------------------------------------

    if phi_not_applicable:

        fired_rules.append(
            "phi_not_applicable"
        )

        phi_explanation = (
            "The verified source marks the "
            "pre-harvest interval as not applicable "
            "for this registered use. "
            "No numerical PHI was inferred."
        )


    else:

        # ----------------------------------------------------
        # 6B. PHI MUST EXIST WHEN APPLICABLE
        # ----------------------------------------------------

        if phi_days is None:

            return ConstraintResult(
                status="abstain",

                active_ingredient=None,

                scaled_dose_min=None,

                scaled_dose_max=None,

                dose_unit=None,

                explanation=(
                    "The pre-harvest interval could not "
                    "be verified from the registry."
                ),

                fired_rules=(
                    fired_rules
                    + ["phi_missing"]
                ),
            )


        # ----------------------------------------------------
        # 7. PHI SAFETY CHECK
        # ----------------------------------------------------

        if (
            phi_days
            >
            expected_harvest_days
        ):

            fired_rules.append(
                "phi_rejected"
            )

            return ConstraintResult(
                status="abstain",

                active_ingredient=None,

                scaled_dose_min=None,

                scaled_dose_max=None,

                dose_unit=None,

                explanation=(
                    f"This option requires a "
                    f"{phi_days}-day pre-harvest interval, "
                    f"but harvest is expected in "
                    f"{expected_harvest_days} days."
                ),

                fired_rules=(
                    fired_rules
                ),
            )


        fired_rules.append(
            "phi_passed"
        )


        phi_explanation = (
            f"The {phi_days}-day PHI fits the "
            f"{expected_harvest_days}-day "
            f"harvest horizon."
        )
    # --------------------------------------------------------
    # 7. PHI SAFETY CHECK
    # --------------------------------------------------------

    if phi_days > expected_harvest_days:

        fired_rules.append(
            "phi_rejected"
        )

        return ConstraintResult(
            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                f"This option requires a "
                f"{phi_days}-day pre-harvest interval, "
                f"but harvest is expected in "
                f"{expected_harvest_days} days."
            ),

            fired_rules=fired_rules,
        )

    fired_rules.append(
        "phi_passed"
    )

    # --------------------------------------------------------
    # 8. CREATE DOSE EXPLANATION
    # --------------------------------------------------------

    if scaled_min == scaled_max:

        dose_text = (
            f"{scaled_min} "
            f"{registry_entry.dose_unit}"
        )

    else:

        dose_text = (
            f"{scaled_min}–{scaled_max} "
            f"{registry_entry.dose_unit}"
        )

    # --------------------------------------------------------
    # 9. SUCCESS
    # --------------------------------------------------------

    return ConstraintResult(
        status="recommend",

        active_ingredient=(
            registry_entry.active_ingredient
        ),

        scaled_dose_min=scaled_min,

        scaled_dose_max=scaled_max,

        dose_unit=(
            registry_entry.dose_unit
        ),

                explanation=(
            f"Verified registry match. "
            f"For {field_area} {area_unit}, "
            f"the registered scaled dose is "
            f"{dose_text}. "
            f"{phi_explanation}"
        ),
        

        fired_rules=fired_rules,
    )