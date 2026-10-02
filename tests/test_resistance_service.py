import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models_resistance import ResistanceRule
from app.services.resistance_service import (
    evaluate_resistance_management,
)


# ============================================================
# TEST DATABASE
# ============================================================

TEST_ENGINE = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=TEST_ENGINE,
)


@pytest.fixture()
def db():

    Base.metadata.drop_all(
        bind=TEST_ENGINE
    )

    Base.metadata.create_all(
        bind=TEST_ENGINE
    )


    session = TestingSessionLocal()


    # --------------------------------------------------------
    # Rice resistance rule
    # --------------------------------------------------------

    session.add(
        ResistanceRule(
            crop="Rice",
            pest="Blast; Sheath blight",
            active_ingredient="Kresoxim-methyl",
            framework="FRAC",
            moa_group="11",
            moa_name="QoI fungicides",
            resistance_risk="high",
            rotation_recommended=True,
            verified=True,
            source_name="FRAC",
            source_url="https://www.frac.info/",
            notes="Test resistance rule.",
        )
    )


    # --------------------------------------------------------
    # Groundnut - Thiamethoxam
    # --------------------------------------------------------

    session.add(
        ResistanceRule(
            crop="Groundnut",
            pest="White grub; Termite",
            active_ingredient="Thiamethoxam",
            framework="IRAC",
            moa_group="4A",
            moa_name="Neonicotinoids",
            resistance_risk="managed",
            rotation_recommended=True,
            verified=True,
            source_name="IRAC",
            source_url="https://irac-online.org/",
            notes="Test resistance rule.",
        )
    )


    # --------------------------------------------------------
    # Groundnut - Fipronil
    # --------------------------------------------------------

    session.add(
        ResistanceRule(
            crop="Groundnut",
            pest="White grub; Termite",
            active_ingredient="Fipronil",
            framework="IRAC",
            moa_group="2B",
            moa_name="Phenylpyrazoles (Fiproles)",
            resistance_risk="managed",
            rotation_recommended=True,
            verified=True,
            source_name="IRAC",
            source_url="https://irac-online.org/",
            notes="Test resistance rule.",
        )
    )


    session.commit()


    try:

        yield session

    finally:

        session.close()


# ============================================================
# TEST 1
# Rice with no previous application
# ============================================================

def test_rice_no_previous_application_passes(
    db,
):

    result = evaluate_resistance_management(
        db=db,
        crop="Rice",
        pest="Blast; Sheath blight",
        active_ingredient="Kresoxim-methyl",
        previous_application_count=0,
    )


    assert result["status"] == "pass"

    assert (
        "resistance_check_passed"
        in result["fired_rules"]
    )

    assert (
        len(
            result["mode_of_action_groups"]
        )
        == 1
    )

    assert (
        result[
            "mode_of_action_groups"
        ][0]["framework"]
        == "FRAC"
    )

    assert (
        result[
            "mode_of_action_groups"
        ][0]["moa_group"]
        == "11"
    )


# ============================================================
# TEST 2
# Rice repeated application -> rotation warning
# ============================================================

def test_rice_previous_application_warns(
    db,
):

    result = evaluate_resistance_management(
        db=db,
        crop="Rice",
        pest="Blast; Sheath blight",
        active_ingredient="Kresoxim-methyl",
        previous_application_count=1,
    )


    assert result["status"] == "warning"

    assert (
        "resistance_rotation_recommended"
        in result["fired_rules"]
    )

    assert (
        "FRAC Group 11"
        in result["explanation"]
    )


# ============================================================
# TEST 3
# Missing history -> not evaluated
# ============================================================

def test_missing_previous_application_count(
    db,
):

    result = evaluate_resistance_management(
        db=db,
        crop="Rice",
        pest="Blast; Sheath blight",
        active_ingredient="Kresoxim-methyl",
        previous_application_count=None,
    )


    assert (
        result["status"]
        == "not_evaluated"
    )

    assert (
        "resistance_history_not_provided"
        in result["fired_rules"]
    )


# ============================================================
# TEST 4
# Unknown resistance rule
# ============================================================

def test_unknown_resistance_rule(
    db,
):

    result = evaluate_resistance_management(
        db=db,
        crop="Unknown Crop",
        pest="Unknown Pest",
        active_ingredient="Unknown Ingredient",
        previous_application_count=1,
    )


    assert (
        result["status"]
        == "not_evaluated"
    )

    assert (
        "resistance_rule_not_found"
        in result["fired_rules"]
    )


# ============================================================
# TEST 5
# Combination treatment splits correctly
# ============================================================

def test_groundnut_combination_detects_two_groups(
    db,
):

    result = evaluate_resistance_management(
        db=db,
        crop="Groundnut",
        pest="White grub; Termite",
        active_ingredient=(
            "Thiamethoxam + Fipronil"
        ),
        previous_application_count=1,
    )


    assert (
        result["status"]
        == "warning"
    )

    assert (
        "resistance_rotation_recommended"
        in result["fired_rules"]
    )


    groups = (
        result[
            "mode_of_action_groups"
        ]
    )


    assert len(groups) == 2


    moa_groups = {
        group["moa_group"]
        for group in groups
    }


    assert moa_groups == {
        "4A",
        "2B",
    }


# ============================================================
# TEST 6
# Combination with no previous use
# ============================================================

def test_groundnut_combination_no_previous_use_passes(
    db,
):

    result = evaluate_resistance_management(
        db=db,
        crop="Groundnut",
        pest="White grub; Termite",
        active_ingredient=(
            "Thiamethoxam + Fipronil"
        ),
        previous_application_count=0,
    )


    assert (
        result["status"]
        == "pass"
    )

    assert (
        "resistance_check_passed"
        in result["fired_rules"]
    )

    assert (
        len(
            result[
                "mode_of_action_groups"
            ]
        )
        == 2
    )