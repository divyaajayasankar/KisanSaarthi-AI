from app.db import SessionLocal

from app.models_growth_stage import (
    GrowthStageRule,
)

from app.models_resistance import (
    ResistanceRule,
)


CROP = "Banana"
PEST = "Sigatoka"
ACTIVE = "Bacillus subtilis"


PPQS_URL = (
    "https://ppqs.gov.in/sites/default/files/"
    "bacillus_subtilis_1.50_liquid_formulation_"
    "t_stanes_bs-1_strain_accession_no._"
    "mtcc_25072_1.pdf"
)

FRAC_URL = (
    "https://www.frac.info/"
    "media/a5vnynr3/frac-moa-poster-2025.pdf"
)


with SessionLocal() as db:

    # ========================================================
    # 1. BANANA GROWTH-STAGE RULE
    # ========================================================

    growth = (
        db.query(GrowthStageRule)
        .filter(
            GrowthStageRule.crop.ilike(CROP),
            GrowthStageRule.pest.ilike(PEST),
            GrowthStageRule.active_ingredient.ilike(
                ACTIVE
            ),
            GrowthStageRule.verified.is_(True),
        )
        .first()
    )


    if growth is None:

        growth = GrowthStageRule(
            crop=CROP,

            pest=PEST,

            active_ingredient=ACTIVE,

            allowed_stages=(
                "vegetative;reproductive"
            ),

            application_timing=(
                "Foliar spray on disease incidence "
                "during vegetative/reproductive phase "
                "of the crop."
            ),

            source_document=(
                "PPQS Bacillus subtilis 1.50% "
                "Liquid Formulation Primary "
                "Package Label"
            ),

            # Technical sentinel only.
            source_page=0,

            source_url=PPQS_URL,

            source_date="2026-09-20",

            verified=True,
        )

        db.add(growth)

        print(
            "Added Banana growth-stage rule."
        )

    else:

        print(
            "Banana growth-stage rule already exists."
        )


    # ========================================================
    # 2. BANANA RESISTANCE / MOA RULE
    # ========================================================

    resistance = (
        db.query(ResistanceRule)
        .filter(
            ResistanceRule.crop.ilike(CROP),
            ResistanceRule.pest.ilike(PEST),
            ResistanceRule.active_ingredient.ilike(
                ACTIVE
            ),
            ResistanceRule.verified.is_(True),
        )
        .first()
    )


    if resistance is None:

        resistance = ResistanceRule(
            crop=CROP,

            pest=PEST,

            active_ingredient=ACTIVE,

            framework="FRAC",

            moa_group="BM02",

            moa_name=(
                "Microbial biologicals with "
                "multiple modes of action"
            ),

            resistance_risk=(
                "resistance not known"
            ),

            rotation_recommended=True,

            verified=True,

            source_name=(
                "FRAC Mode of Action Classification"
            ),

            source_url=FRAC_URL,

            notes=(
                "FRAC BM02 includes bacterial "
                "Bacillus spp., including "
                "Bacillus subtilis. Used by "
                "KisanSaarthi for mode-of-action "
                "context."
            ),
        )

        db.add(resistance)

        print(
            "Added Banana FRAC BM02 rule."
        )

    else:

        print(
            "Banana resistance rule already exists."
        )


    db.commit()


print()
print("Banana verified support update complete.")