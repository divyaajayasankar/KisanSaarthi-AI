from app.db import SessionLocal

from app.services.treatment_history_service import (
    evaluate_treatment_history,
)


# ============================================================
# RICE â€” BELOW MAXIMUM
# ============================================================

def test_rice_two_previous_applications_pass():

    db = SessionLocal()

    try:

        result = evaluate_treatment_history(
            db=db,
            crop="Rice",
            pest="Blast; Sheath blight",
            active_ingredient="Kresoxim-methyl",
            previous_application_count=2,
            days_since_last_application=None,
        )

        assert result["status"] == "pass"

        assert (
            "treatment_history_passed"
            in result["fired_rules"]
        )

        assert result["max_applications"] == 3

    finally:

        db.close()


# ============================================================
# RICE â€” MAXIMUM REACHED
# ============================================================

def test_rice_three_previous_applications_abstain():

    db = SessionLocal()

    try:

        result = evaluate_treatment_history(
            db=db,
            crop="Rice",
            pest="Blast; Sheath blight",
            active_ingredient="Kresoxim-methyl",
            previous_application_count=3,
            days_since_last_application=None,
        )

        assert result["status"] == "abstain"

        assert (
            "maximum_application_frequency_reached"
            in result["fired_rules"]
        )

        assert result["max_applications"] == 3

    finally:

        db.close()


# ============================================================
# GROUNDNUT â€” NO PREVIOUS APPLICATION
# ============================================================

def test_groundnut_zero_previous_applications_pass():

    db = SessionLocal()

    try:

        result = evaluate_treatment_history(
            db=db,
            crop="Groundnut",
            pest="White grub; Termite",
            active_ingredient="Thiamethoxam + Fipronil",
            previous_application_count=0,
            days_since_last_application=None,
        )

        assert result["status"] == "pass"

        assert (
            "treatment_history_passed"
            in result["fired_rules"]
        )

        assert result["max_applications"] == 1

    finally:

        db.close()


# ============================================================
# GROUNDNUT â€” FREQUENCY LIMIT REACHED
# ============================================================

def test_groundnut_one_previous_application_abstain():

    db = SessionLocal()

    try:

        result = evaluate_treatment_history(
            db=db,
            crop="Groundnut",
            pest="White grub; Termite",
            active_ingredient="Thiamethoxam + Fipronil",
            previous_application_count=1,
            days_since_last_application=None,
        )

        assert result["status"] == "abstain"

        assert (
            "maximum_application_frequency_reached"
            in result["fired_rules"]
        )

        assert result["max_applications"] == 1

    finally:

        db.close()


# ============================================================
# HISTORY NOT PROVIDED
# ============================================================

def test_treatment_history_not_provided():

    db = SessionLocal()

    try:

        result = evaluate_treatment_history(
            db=db,
            crop="Rice",
            pest="Blast; Sheath blight",
            active_ingredient="Kresoxim-methyl",
            previous_application_count=None,
            days_since_last_application=None,
        )

        assert result["status"] == "not_evaluated"

        assert (
            "treatment_history_not_provided"
            in result["fired_rules"]
        )

    finally:

        db.close()


# ============================================================
# NO VERIFIED RULE
# ============================================================

def test_unknown_treatment_history_rule_not_invented():

    db = SessionLocal()

    try:

        result = evaluate_treatment_history(
            db=db,
            crop="Unknown Crop",
            pest="Unknown Pest",
            active_ingredient="Unknown Ingredient",
            previous_application_count=1,
            days_since_last_application=None,
        )

        assert result["status"] == "not_evaluated"

        assert (
            "treatment_history_rule_not_found"
            in result["fired_rules"]
        )

        assert result["max_applications"] is None

    finally:

        db.close()
