from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
)

from app.db import Base


# ============================================================
# TREATMENT HISTORY RULE
# ============================================================

class TreatmentHistoryRule(Base):

    __tablename__ = "treatment_history_rules"

    # --------------------------------------------------------
    # PRIMARY KEY
    # --------------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # --------------------------------------------------------
    # CROP / PEST / ACTIVE INGREDIENT
    # --------------------------------------------------------

    crop = Column(
        String,
        nullable=False,
        index=True,
    )

    pest = Column(
        String,
        nullable=False,
        index=True,
    )

    active_ingredient = Column(
        String,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # VERIFIED APPLICATION-FREQUENCY RULE
    # --------------------------------------------------------

    max_applications = Column(
        Integer,
        nullable=True,
    )

    # --------------------------------------------------------
    # OPTIONAL REPEAT INTERVAL
    #
    # NULL is valid when the authoritative source does not
    # explicitly provide a minimum repeat interval.
    # --------------------------------------------------------

    min_interval_days = Column(
        Float,
        nullable=True,
    )

    # --------------------------------------------------------
    # RULE SCOPE
    # --------------------------------------------------------

    history_scope = Column(
        String,
        nullable=False,
        default="crop_cycle",
    )

    application_stage = Column(
        String,
        nullable=True,
    )

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    verified = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    # --------------------------------------------------------
    # SOURCE PROVENANCE
    # --------------------------------------------------------

    source_document = Column(
        String,
        nullable=False,
    )

    source_page = Column(
        Integer,
        nullable=True,
    )

    source_url = Column(
        Text,
        nullable=False,
    )

    notes = Column(
        Text,
        nullable=True,
    )
